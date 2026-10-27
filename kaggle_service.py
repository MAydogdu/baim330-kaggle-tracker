"""
Kaggle Integration Service for BAIM 330
Supports:
1. Kaggle Official REST API (via urllib.request with Basic Auth)
2. Kaggle CLI fallback (if available)
3. Direct CSV Leaderboard parsing (for drag-and-drop or manual uploads)
"""

import os
import io
import csv
import json
import base64
import zipfile
import urllib.request
import urllib.error
import subprocess
from datetime import datetime
from db import get_setting, get_all_teams, record_snapshot, set_setting

DEFAULT_COMPETITION = "house-prices-advanced-regression-techniques"

def get_kaggle_credentials():
    """
    Retrieves Kaggle credentials in order of priority:
    1. Local project directory kaggle.json
    2. Database settings (configured via Admin Panel)
    3. Environment variables KAGGLE_USERNAME, KAGGLE_KEY
    4. ~/.kaggle/kaggle.json (if accessible)
    """
    # 1. Check local project directory for kaggle.json
    local_kaggle_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "kaggle.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Copy of kaggle.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kaggle.json"),
    ]
    for kpath in local_kaggle_paths:
        try:
            if os.path.exists(kpath):
                with open(kpath, "r") as f:
                    data = json.load(f)
                    u = data.get("username", "").strip()
                    k = data.get("key", "").strip()
                    if u and k:
                        return u, k, "project_kaggle_json"
        except Exception:
            pass

    # 2. Check Database settings
    username = get_setting("kaggle_username", "").strip()
    key = get_setting("kaggle_key", "").strip()

    if username and key:
        return username, key, "db_settings"

    # 3. Check Environment variables
    env_user = os.environ.get("KAGGLE_USERNAME", "").strip()
    env_key = os.environ.get("KAGGLE_KEY", "").strip()
    if env_user and env_key:
        return env_user, env_key, "env_vars"

    # 4. Try ~/.kaggle/kaggle.json
    try:
        kaggle_file = os.path.expanduser("~/.kaggle/kaggle.json")
        if os.path.exists(kaggle_file):
            with open(kaggle_file, "r") as f:
                data = json.load(f)
                u = data.get("username", "").strip()
                k = data.get("key", "").strip()
                if u and k:
                    return u, k, "home_kaggle_json"
    except Exception:
        pass

    return None, None, "missing"

def parse_csv_leaderboard_content(csv_text):
    """
    Parses Kaggle leaderboard CSV text into a structured list of entries.
    Common Kaggle leaderboard columns:
    - TeamId, TeamName, SubmissionDate, Score
    - or Rank, TeamName, Score, Entries, Last
    """
    entries = []
    reader = csv.DictReader(io.StringIO(csv_text))
    
    # Normalize field names to lowercase
    for raw_row in reader:
        row = {k.strip().lower(): v.strip() for k, v in raw_row.items() if k}
        
        # Determine team name
        team_name = row.get("teamname") or row.get("team name") or row.get("team") or ""
        
        # Determine score
        score_val = None
        for key in ["score", "publicscore", "public score", "value"]:
            if key in row and row[key] != "":
                try:
                    score_val = float(row[key])
                    break
                except ValueError:
                    continue

        # Determine rank
        rank_val = None
        for key in ["rank", "place"]:
            if key in row and row[key] != "":
                try:
                    rank_val = int(row[key])
                    break
                except ValueError:
                    continue

        if team_name and score_val is not None:
            entries.append({
                "team_name": team_name,
                "score": score_val,
                "rank": rank_val
            })
            
    return entries

def fetch_kaggle_leaderboard_api(username, key, competition_id):
    """
    Fetches the public leaderboard from Kaggle REST API:
    https://www.kaggle.com/api/v1/competitions/{competition_id}/leaderboard/download
    """
    url = f"https://www.kaggle.com/api/v1/competitions/{competition_id}/leaderboard/download"
    req = urllib.request.Request(url)
    
    # HTTP Basic Authentication
    auth_str = f"{username}:{key}"
    auth_bytes = auth_str.encode("utf-8")
    auth_b64 = base64.b64encode(auth_bytes).decode("ascii")
    req.add_header("Authorization", f"Basic {auth_b64}")
    req.add_header("User-Agent", "BAIM330-KaggleTracker/1.0")

    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            content = response.read()
            
            # Check if Kaggle returned a zip file
            if content.startswith(b"PK"):
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    # Find CSV inside ZIP
                    csv_filename = None
                    for name in z.namelist():
                        if name.endswith(".csv"):
                            csv_filename = name
                            break
                    if not csv_filename and len(z.namelist()) > 0:
                        csv_filename = z.namelist()[0]
                        
                    if csv_filename:
                        csv_text = z.read(csv_filename).decode("utf-8", errors="replace")
                        return parse_csv_leaderboard_content(csv_text), None
            else:
                # May be raw CSV or JSON
                try:
                    text = content.decode("utf-8", errors="replace")
                    if text.strip().startswith("{") or text.strip().startswith("["):
                        data = json.loads(text)
                        entries = []
                        items = data if isinstance(data, list) else data.get("teams", [])
                        for item in items:
                            tname = item.get("teamName") or item.get("name")
                            score = item.get("score")
                            rank = item.get("rank")
                            if tname and score is not None:
                                entries.append({
                                    "team_name": tname,
                                    "score": float(score),
                                    "rank": int(rank) if rank else None
                                })
                        return entries, None
                    else:
                        return parse_csv_leaderboard_content(text), None
                except Exception as e:
                    return None, f"Failed to parse Kaggle response: {str(e)}"
                    
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return None, "Kaggle Authentication Failed (401). Please check your Kaggle Username and API Key in Admin Settings."
        elif e.code == 404:
            return None, f"Competition '{competition_id}' not found on Kaggle (404)."
        else:
            return None, f"Kaggle API HTTP {e.code}: {e.reason}"
    except Exception as e:
        return None, f"Network or connection error fetching from Kaggle: {str(e)}"

    return None, "Unknown error fetching Kaggle leaderboard"

def sync_scores(competition_id=None):
    """
    Orchestrates updating the scores for all registered teams:
    1. Retrieves Kaggle credentials
    2. Downloads latest leaderboard
    3. Matches each tracked team
    4. Records new snapshots
    """
    if not competition_id:
        competition_id = get_setting("competition_id", DEFAULT_COMPETITION)

    username, key, source = get_kaggle_credentials()
    
    if not username or not key:
        return {
            "success": False,
            "error": "Kaggle credentials not configured. Please add your Kaggle Username and API Key in the Admin Panel settings, or upload the leaderboard CSV.",
            "source": source
        }

    leaderboard_entries, err = fetch_kaggle_leaderboard_api(username, key, competition_id)
    if err:
        return {
            "success": False,
            "error": err,
            "source": source
        }

    return process_leaderboard_entries(leaderboard_entries, source=f"kaggle_api ({username})")

def process_leaderboard_entries(entries, source="kaggle_api"):
    """
    Given a list of { team_name, score, rank }, matches registered teams
    and records snapshots.
    """
    teams = get_all_teams()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    updated_teams = []
    unmatched_teams = []

    # Map normalized Kaggle team names in leaderboard
    # Kaggle team names can have different capitalization
    for team in teams:
        target_name = team["kaggle_name"].strip().lower()
        matched_entry = None

        # Try exact match first
        for entry in entries:
            cand_name = entry["team_name"].strip().lower()
            if cand_name == target_name:
                matched_entry = entry
                break
                
        # Try substring match if exact not found
        if not matched_entry:
            for entry in entries:
                cand_name = entry["team_name"].strip().lower()
                if target_name in cand_name or cand_name in target_name:
                    matched_entry = entry
                    break

        if matched_entry:
            record_snapshot(
                team_id=team["id"],
                score=matched_entry["score"],
                kaggle_rank=matched_entry.get("rank"),
                recorded_at=now_str,
                notes=f"Synced from Kaggle Leaderboard (Team: {matched_entry['team_name']})",
                source=source
            )
            updated_teams.append({
                "team_id": team["id"],
                "name": team["name"],
                "kaggle_name": team["kaggle_name"],
                "matched_as": matched_entry["team_name"],
                "score": matched_entry["score"],
                "rank": matched_entry.get("rank")
            })
        else:
            unmatched_teams.append({
                "team_id": team["id"],
                "name": team["name"],
                "kaggle_name": team["kaggle_name"]
            })

    set_setting("last_sync_time", now_str)

    return {
        "success": True,
        "sync_time": now_str,
        "total_entries_in_leaderboard": len(entries),
        "updated_teams": updated_teams,
        "unmatched_teams": unmatched_teams,
        "message": f"Successfully updated {len(updated_teams)} out of {len(teams)} teams."
    }
