"""
Data export module for GitHub Pages static deployment.
Exports current database state into data/leaderboard.json.
"""

import os
import json
from db import get_leaderboard_data, get_history_data, get_all_teams, get_setting

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUTPUT_PATH = os.path.join(DATA_DIR, "leaderboard.json")

def export_to_json():
    os.makedirs(DATA_DIR, exist_ok=True)
    leaderboard = get_leaderboard_data()
    history = get_history_data()
    teams = get_all_teams()

    data = {
        "competition_id": leaderboard.get("competition_id", "house-prices-advanced-regression-techniques"),
        "last_sync": leaderboard.get("last_sync"),
        "total_teams": leaderboard.get("total_teams"),
        "winner": leaderboard.get("winner"),
        "standings": leaderboard.get("standings", []),
        "history": history,
        "teams": teams
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Data exported successfully to: {OUTPUT_PATH}")
    return OUTPUT_PATH

if __name__ == "__main__":
    export_to_json()
