#!/usr/bin/env python3
"""
finalize_phase1.py
Finalizes Phase 1 of the BAIM 330 Kaggle Competition:
1. Fetches final leaderboard scores from Kaggle API.
2. Identifies and locks in the Phase 1 Winning Team.
3. Updates settings and exports data/leaderboard.json.
4. Commits and pushes official results to GitHub Pages.
"""

import os
import sys
import subprocess
from datetime import datetime
import kaggle_service
import db
import export_data

def run_finalize(push_to_git=True):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"==================================================")
    print(f" 🏆 FINALIZING PHASE 1 - {now_str}")
    print(f"==================================================")

    # 1. Fetch latest scores from Kaggle
    print("\n[Step 1/4] Fetching final submissions from Kaggle API...")
    sync_res = kaggle_service.sync_scores()
    print("Sync status:", sync_res.get("message", sync_res.get("error", "Complete")))

    # 2. Lock in winner in Database
    print("\n[Step 2/4] Locking in Phase 1 Winner in Database...")
    phase1_info = db.finalize_phase1_in_db()
    winner_name = phase1_info.get("winner_name")
    winner_score = phase1_info.get("winner_score")
    winner_rank = phase1_info.get("winner_rank")
    winner_members = phase1_info.get("winner_members")

    print(f"\n🎉 PHASE 1 WINNER ANNOUNCEMENT:")
    print(f"   Team:        {winner_name}")
    print(f"   Members:     {winner_members}")
    print(f"   Final Score: {winner_score} RMSE")
    print(f"   Kaggle Rank: #{winner_rank}")

    # 3. Export to JSON for GitHub Pages
    print("\n[Step 3/4] Exporting to data/leaderboard.json...")
    json_path = export_data.export_to_json()

    # 4. Git commit and push if enabled
    if push_to_git:
        print("\n[Step 4/4] Pushing official results to GitHub Pages...")
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        try:
            subprocess.run(["git", "add", "data/leaderboard.json"], check=True, cwd=repo_dir)
            commit_msg = f"Official Phase 1 Winner: {winner_name} (Score: {winner_score} RMSE) [{now_str}]"
            subprocess.run(["git", "commit", "-m", commit_msg], check=False, cwd=repo_dir)
            subprocess.run(["git", "push", "origin", "main"], check=True, cwd=repo_dir)
            print("✅ Successfully pushed Phase 1 winner announcement to GitHub!")
        except Exception as e:
            print(f"⚠️ Git push notice: {e}")

    print(f"\n==================================================")
    print(f" 🏁 PHASE 1 SUCCESSFULLY CONCLUDED!")
    print(f"==================================================")
    return phase1_info

if __name__ == "__main__":
    push = "--no-push" not in sys.argv
    run_finalize(push_to_git=push)
