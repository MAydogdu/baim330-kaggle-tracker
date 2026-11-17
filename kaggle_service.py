"""
Kaggle Integration Service for BAIM 330
Supports:
1. Kaggle Official REST API (via urllib.request with Basic Auth)
2. Kaggle CLI fallback (if available)
3. Direct CSV Leaderboard parsing (for drag-and-drop or manual uploads)
"""

import os
import io
import re
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
    
    # Normalize field names to lowercase and strip UTF-8 BOM / whitespace
    for raw_row in reader:
        row = {k.lstrip('\ufeff').strip().lower(): v.strip() for k, v in raw_row.items() if k}
        
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
                    rank_val = int(float(row[key]))
                    break
                except ValueError:
                    continue

        # Determine submission count from Kaggle
        sub_count = None
        for key in ["submissioncount", "submission count", "entries", "submissions", "submission_count"]:
            if key in row and row[key] != "":
                try:
                    sub_count = int(float(row[key]))
                    break
                except ValueError:
                    continue

        # Determine team members if available
        team_members = row.get("teammemberusernames") or row.get("teammembers") or row.get("members") or ""

        if team_name and score_val is not None:
            entries.append({
                "team_name": team_name,
                "score": score_val,
                "rank": rank_val,
                "submission_count": sub_count,
                "team_members": team_members
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
                        csv_text = z.read(csv_filename).decode("utf-8-sig", errors="replace")
                        return parse_csv_leaderboard_content(csv_text), None
            else:
                # May be raw CSV or JSON
                try:
                    text = content.decode("utf-8-sig", errors="replace")
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

def fetch_kaggle_submissions_api(username, key, competition_id):
    """
    Fetches the authenticated team's submissions directly from Kaggle REST API:
    https://www.kaggle.com/api/v1/competitions/submissions/list/{competition_id}
    """
    url = f"https://www.kaggle.com/api/v1/competitions/submissions/list/{competition_id}"
    req = urllib.request.Request(url)
    auth_str = f"{username}:{key}"
    auth_bytes = auth_str.encode("utf-8")
    auth_b64 = base64.b64encode(auth_bytes).decode("ascii")
    req.add_header("Authorization", f"Basic {auth_b64}")
    req.add_header("User-Agent", "BAIM330-KaggleTracker/1.0")

    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            text = response.read().decode("utf-8-sig", errors="replace")
            data = json.loads(text)
            return data, None
    except Exception as e:
        return None, f"Error fetching team submissions from Kaggle: {str(e)}"

def filter_merged_team_submissions(submissions, exclude_files=None, min_date=None, exclude_users=None, exclude_user_before=None):
    """
    Filters team submissions according to competition and instructor rules:
    - Excludes specific submission files (e.g., 'HousePrices_GradientBoosting_Submission.csv')
    - Excludes submissions prior to min_date (default 2026-10-28 UTC, i.e., >=20 days old at merge)
    - Excludes instructor submissions (e.g., 'maydogdu')
    - Excludes submissions from specific users prior to a cutoff (e.g., Juliany prior to merge)
    - Excludes submissions with status error or missing scores
    """
    from datetime import timezone
    
    if not submissions:
        return []

    if exclude_files is None:
        exclude_files = ["HousePrices_GradientBoosting_Submission.csv"]
    if exclude_users is None:
        exclude_users = ["maydogdu"]
    if min_date is None:
        min_date = datetime(2026, 10, 28, 0, 0, 0, tzinfo=timezone.utc)
    if exclude_user_before is None:
        exclude_user_before = {
            "julianybournigal": datetime(2026, 11, 16, 23, 0, 0, tzinfo=timezone.utc)
        }

    eligible = []
    for s in submissions:
        # Check status and score
        score_val = s.get("publicScore") or s.get("publicScoreNullable")
        if not score_val or str(score_val).strip() == "":
            continue
        try:
            score = float(score_val)
        except (ValueError, TypeError):
            continue

        file_name = s.get("fileName") or s.get("fileNameNullable") or ""
        ref = str(s.get("ref", ""))
        
        # 1. Exclude specific files
        if any(excl.lower() in file_name.lower() for excl in exclude_files) or ref == "58186093":
            continue

        # 2. Exclude instructor submissions
        by_user = (s.get("submittedBy") or s.get("submittedByNullable") or "").strip().lower()
        if by_user in [u.lower() for u in exclude_users]:
            continue

        # 3. Parse date
        date_str = s.get("date") or ""
        dt = None
        for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"]:
            try:
                dt = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
                break
            except Exception:
                pass

        # Exclude submissions older than min_date (>= 20 days old at merge)
        if dt and dt < min_date:
            continue

        # Exclude pre-merge submissions for specified users (e.g. Juliany prior to merge)
        if by_user in exclude_user_before and dt and dt <= exclude_user_before[by_user]:
            continue

        eligible.append({
            "ref": ref,
            "fileName": file_name,
            "score": score,
            "submittedBy": by_user,
            "date": str(dt) if dt else date_str,
            "dt": dt
        })

    return eligible

def find_rank_in_leaderboard(score, entries):
    """
    Finds the Kaggle leaderboard rank corresponding to a given RMSE score.
    """
    if not entries or score is None:
        return None
    valid_entries = [e for e in entries if e.get("score") is not None and e.get("rank") is not None]
    if not valid_entries:
        return None
    
    # 1. Try exact match
    for e in valid_entries:
        if abs(e["score"] - score) < 0.00005:
            return e["rank"]

    # 2. Find closest rank
    closest = min(valid_entries, key=lambda e: abs(e["score"] - score))
    return closest.get("rank")

def sync_scores(competition_id=None):
    """
    Orchestrates updating the scores for all registered teams:
    1. Retrieves Kaggle credentials
    2. Downloads latest leaderboard
    3. Fetches authenticated team submissions (for merged student teams)
    4. Matches each tracked team and applies exclusion filters
    5. Records new snapshots
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

    # Fetch team submissions for merged/authenticated team to handle custom exclusion rules
    team_submissions, _ = fetch_kaggle_submissions_api(username, key, competition_id)

    return process_leaderboard_entries(leaderboard_entries, team_submissions=team_submissions, source=f"kaggle_api ({username})")

def process_leaderboard_entries(entries, team_submissions=None, source="kaggle_api"):
    """
    Given a list of { team_name, score, rank }, matches registered teams
    and records snapshots.
    """
    teams = get_all_teams()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    updated_teams = []
    unmatched_teams = []

    # Pre-calculate eligible submissions for BAIM Group / merged student teams
    merged_best_sub = None
    merged_eligible_subs = []
    if team_submissions:
        merged_eligible_subs = filter_merged_team_submissions(team_submissions)
        if merged_eligible_subs:
            merged_best_sub = min(merged_eligible_subs, key=lambda x: x["score"])

    # Map normalized Kaggle team names in leaderboard
    # Kaggle team names can have different capitalization
    for team in teams:
        target_name = team["kaggle_name"].strip().lower()
        matched_entry = None

        # Special handling for merged student team 'BAIM Group':
        # Derive score directly from eligible submissions of the merged Kaggle team
        if ("baim" in target_name and not team.get("is_instructor")) and merged_best_sub:
            rank = find_rank_in_leaderboard(merged_best_sub["score"], entries)
            matched_entry = {
                "team_name": "BAIM Group",
                "score": merged_best_sub["score"],
                "rank": rank,
                "submission_count": len(merged_eligible_subs),
                "notes": f"Best eligible submission: {merged_best_sub['fileName']} by {merged_best_sub['submittedBy']} ({merged_best_sub['score']} RMSE)"
            }

        # 1. Try exact match first
        if not matched_entry:
            for entry in entries:
                cand_name = entry["team_name"].strip().lower()
                if cand_name == target_name:
                    matched_entry = entry
                    break

        # 2. Try normalized alphanumeric match (e.g. spaces/punctuation differences)
        if not matched_entry:
            target_norm = re.sub(r'[^a-z0-9]', '', target_name)
            for entry in entries:
                cand_norm = re.sub(r'[^a-z0-9]', '', entry["team_name"].lower())
                if target_norm and cand_norm and cand_norm == target_norm:
                    matched_entry = entry
                    break

        # 3. Try flexible match removing '330' (e.g. 'BAIM330 Group' vs 'BAIM Group')
        if not matched_entry:
            target_no330 = target_name.replace("330", "").strip()
            for entry in entries:
                cand_name = entry["team_name"].strip().lower()
                cand_no330 = cand_name.replace("330", "").strip()
                if target_no330 and cand_no330 and (target_no330 == cand_no330 or target_no330 == cand_name or cand_name == target_no330):
                    matched_entry = entry
                    break

        # 4. Try substring match if exact not found
        if not matched_entry:
            for entry in entries:
                cand_name = entry["team_name"].strip().lower()
                if len(target_name) >= 4 and len(cand_name) >= 4:
                    if target_name in cand_name or cand_name in target_name:
                        matched_entry = entry
                        break

        # 5. Try team members username match fallback (for non-instructor teams)
        if not matched_entry and team.get("members") and not team.get("is_instructor"):
            member_tokens = [m.strip().lower() for m in re.split(r'[,;/ ]+', team["members"]) if len(m.strip()) >= 3]
            for entry in entries:
                entry_members = entry.get("team_members", "").lower()
                if entry_members and any(token in entry_members for token in member_tokens):
                    matched_entry = entry
                    break

        if matched_entry:
            notes_str = matched_entry.get("notes") or f"Synced from Kaggle Leaderboard (Team: {matched_entry['team_name']})"
            record_snapshot(
                team_id=team["id"],
                score=matched_entry["score"],
                kaggle_rank=matched_entry.get("rank"),
                recorded_at=now_str,
                notes=notes_str,
                source=source,
                submission_count=matched_entry.get("submission_count")
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
