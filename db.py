"""
Database module for BAIM 330 Kaggle Tracker
Uses SQLite (standard library, zero external dependencies).
"""

import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baim330_competition.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Teams table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            kaggle_name TEXT NOT NULL,
            members TEXT DEFAULT '',
            is_instructor INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    # Historical score snapshots
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            score REAL NOT NULL,
            kaggle_rank INTEGER,
            recorded_at TEXT NOT NULL,
            notes TEXT DEFAULT '',
            source TEXT DEFAULT 'kaggle_api',
            FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE
        )
    """)

    # App settings (Kaggle credentials, admin password hash, competition id)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    conn.commit()

    # Seed default settings if not exists
    cursor.execute("SELECT value FROM settings WHERE key = 'competition_id'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", 
                       ("competition_id", "house-prices-advanced-regression-techniques"))
    
    cursor.execute("SELECT value FROM settings WHERE key = 'admin_password'")
    if not cursor.fetchone():
        # Default admin password: baim330admin
        cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", 
                       ("admin_password", "baim330admin"))

    # Seed initial default 3 groups + instructor if no teams exist
    cursor.execute("SELECT COUNT(*) as count FROM teams")
    if cursor.fetchone()["count"] == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        teams_data = [
            ("Group 1", "baim330_team1", "Student Group 1", 0, now),
            ("Group 2", "baim330_team2", "Student Group 2", 0, now),
            ("Group 3", "baim330_team3", "Student Group 3", 0, now),
            ("Instructor (Benchmark)", "prof_aydogdu", "Prof. Murat Aydogdu", 1, now)
        ]
        cursor.executemany("""
            INSERT INTO teams (name, kaggle_name, members, is_instructor, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, teams_data)

        # Insert realistic starting baseline scores for today (2026-10-27)
        # In House Prices, RMSE typically ranges from 0.11 to 0.18
        today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        initial_snapshots = [
            (1, 0.14250, 1420, today_str, "Initial baseline submission", "manual"),
            (2, 0.13820, 1180, today_str, "Baseline model (Random Forest)", "manual"),
            (3, 0.15110, 1890, today_str, "Baseline model (Linear Regression)", "manual"),
            (4, 0.12940, 850, today_str, "Instructor benchmark (XGBoost)", "manual")
        ]
        cursor.executemany("""
            INSERT INTO snapshots (team_id, score, kaggle_rank, recorded_at, notes, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, initial_snapshots)

    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))
    conn.commit()
    conn.close()

def get_all_teams():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM teams ORDER BY is_instructor ASC, name ASC")
    teams = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return teams

def add_team(name, kaggle_name, members="", is_instructor=0):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO teams (name, kaggle_name, members, is_instructor, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (name.strip(), kaggle_name.strip(), members.strip(), 1 if is_instructor else 0, now))
    team_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return team_id

def update_team(team_id, name, kaggle_name, members, is_instructor):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE teams
        SET name = ?, kaggle_name = ?, members = ?, is_instructor = ?
        WHERE id = ?
    """, (name.strip(), kaggle_name.strip(), members.strip(), 1 if is_instructor else 0, team_id))
    conn.commit()
    conn.close()

def delete_team(team_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM snapshots WHERE team_id = ?", (team_id,))
    cursor.execute("DELETE FROM teams WHERE id = ?", (team_id,))
    conn.commit()
    conn.close()

def record_snapshot(team_id, score, kaggle_rank=None, recorded_at=None, notes="", source="kaggle_api"):
    if not recorded_at:
        recorded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO snapshots (team_id, score, kaggle_rank, recorded_at, notes, source)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (team_id, float(score), kaggle_rank, recorded_at, notes, source))
    snapshot_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return snapshot_id

def delete_snapshot(snapshot_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM snapshots WHERE id = ?", (snapshot_id,))
    conn.commit()
    conn.close()

def get_leaderboard_data():
    """
    Returns current standings for all teams.
    For Kaggle House Prices, evaluation is RMSE: LOWER SCORE IS BETTER!
    Winning group is the student team with the lowest score.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all teams
    cursor.execute("SELECT * FROM teams")
    teams = [dict(row) for row in cursor.fetchall()]

    standings = []
    for team in teams:
        # Get latest score snapshot
        cursor.execute("""
            SELECT score, kaggle_rank, recorded_at, notes, source
            FROM snapshots
            WHERE team_id = ?
            ORDER BY recorded_at DESC, id DESC
            LIMIT 1
        """, (team["id"],))
        latest = cursor.fetchone()

        # Get best (minimum) score for this team (since lower RMSE is better)
        cursor.execute("""
            SELECT MIN(score) as best_score, COUNT(*) as submission_count
            FROM snapshots
            WHERE team_id = ?
        """, (team["id"],))
        stats = cursor.fetchone()

        # Get previous score to show change/trend
        cursor.execute("""
            SELECT score, recorded_at
            FROM snapshots
            WHERE team_id = ?
            ORDER BY recorded_at DESC, id DESC
            LIMIT 1 OFFSET 1
        """, (team["id"],))
        previous = cursor.fetchone()

        delta = None
        trend = "unchanged"
        if latest and previous:
            diff = latest["score"] - previous["score"]
            delta = round(diff, 5)
            # In RMSE: negative diff means score improved!
            if diff < -0.00001:
                trend = "improved"
            elif diff > 0.00001:
                trend = "regressed"

        standings.append({
            "team_id": team["id"],
            "name": team["name"],
            "kaggle_name": team["kaggle_name"],
            "members": team["members"],
            "is_instructor": bool(team["is_instructor"]),
            "latest_score": latest["score"] if latest else None,
            "best_score": stats["best_score"] if stats and stats["best_score"] is not None else None,
            "kaggle_rank": latest["kaggle_rank"] if latest else None,
            "last_updated": latest["recorded_at"] if latest else None,
            "submission_count": stats["submission_count"] if stats else 0,
            "delta": delta,
            "trend": trend,
            "notes": latest["notes"] if latest else ""
        })

    # Sort standings:
    # Teams with valid scores first (sorted ascending by best_score because lower RMSE is better)
    with_score = [t for t in standings if t["best_score"] is not None]
    without_score = [t for t in standings if t["best_score"] is None]
    with_score.sort(key=lambda t: t["best_score"])

    # Assign class ranks:
    # Student teams get ranks 1, 2, 3...
    # Instructor is benchmark
    student_rank = 1
    winner = None
    for item in with_score:
        if not item["is_instructor"]:
            item["class_rank"] = student_rank
            if winner is None:
                winner = item
            student_rank += 1
        else:
            item["class_rank"] = None # Benchmark doesn't take student podium spot


    for item in without_score:
        item["class_rank"] = None

    all_ranked = with_score + without_score
    conn.close()

    return {
        "standings": all_ranked,
        "winner": winner,
        "competition_id": get_setting("competition_id", "house-prices-advanced-regression-techniques"),
        "total_teams": len(all_ranked),
        "last_sync": get_setting("last_sync_time", None)
    }

def get_history_data():
    """
    Returns time series data for all teams for Chart.js.
    Shows, for each day, the best score of each team.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # All raw snapshots for chronological table log
    cursor.execute("""
        SELECT s.id, s.team_id, t.name as team_name, t.is_instructor,
               s.score, s.kaggle_rank, s.recorded_at, s.notes, s.source
        FROM snapshots s
        JOIN teams t ON s.team_id = t.id
        ORDER BY s.recorded_at ASC, s.id ASC
    """)
    snapshots = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT id, name, is_instructor FROM teams ORDER BY name ASC")
    teams = [dict(row) for row in cursor.fetchall()]

    # Daily best score query: for each team and each day, take the MIN(score)
    cursor.execute("""
        SELECT s.team_id, t.name as team_name,
               DATE(s.recorded_at) as day,
               MIN(s.score) as best_daily_score,
               MIN(s.kaggle_rank) as best_rank,
               COUNT(*) as submissions_count
        FROM snapshots s
        JOIN teams t ON s.team_id = t.id
        GROUP BY s.team_id, DATE(s.recorded_at)
        ORDER BY day ASC
    """)
    daily_records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # Structure data by team: one point per day representing the best score that day
    team_series = {}
    for team in teams:
        team_series[team["id"]] = {
            "team_id": team["id"],
            "team_name": team["name"],
            "is_instructor": bool(team["is_instructor"]),
            "points": []
        }

    for r in daily_records:
        tid = r["team_id"]
        if tid in team_series:
            team_series[tid]["points"].append({
                "x": r["day"], # 'YYYY-MM-DD'
                "y": r["best_daily_score"], # Best RMSE achieved on that day
                "kaggle_rank": r["best_rank"],
                "submissions_count": r["submissions_count"],
                "notes": f"Best on {r['day']} ({r['submissions_count']} submissions)"
            })

    snapshots_desc = list(reversed(snapshots))

    return {
        "teams": teams,
        "series": list(team_series.values()),
        "snapshots": snapshots_desc
    }
