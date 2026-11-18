#!/usr/bin/env python3
"""
finalize_phases.py
Finalizes any competition phase (1-4) whose deadline has been reached:
1. Fetches latest leaderboard & merged team submissions from Kaggle API (with exclusions).
2. Identifies and locks in the Phase Winning Team (name, best score, submissions, rank).
3. Updates settings and exports data/leaderboard.json.
4. Commits and pushes official results to GitHub Pages.
"""

import os
import sys
import subprocess
import threading
from datetime import datetime, timezone
import kaggle_service
import db
import export_data

_finalize_lock = threading.Lock()


def run_finalize(phase_num, push_to_git=True, force=False):
    with _finalize_lock:
        info = db.get_phase_info(phase_num)
        if not info:
            raise ValueError(f"Unknown phase number: {phase_num}")
        if info.get("is_completed") and not force:
            return info

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("=" * 50)
        print(f" 🏆 FINALIZING PHASE {phase_num} - {now_str}")
        print("=" * 50)

        # 1. Fetch latest scores from Kaggle (uses merged team exclusions for BAIM Group)
        print(f"\n[Step 1/4] Fetching Phase {phase_num} submissions from Kaggle API...")
        sync_res = kaggle_service.sync_scores()
        print("Sync status:", sync_res.get("message", sync_res.get("error", "Complete")))

        # 2. Lock in winner in Database
        print(f"\n[Step 2/4] Locking in Phase {phase_num} Winner in Database...")
        phase_info = db.finalize_phase_in_db(phase_num)
        winner_name = phase_info.get("winner_name")
        winner_score = phase_info.get("winner_score")
        winner_rank = phase_info.get("winner_rank")
        winner_subs = phase_info.get("winner_submissions")
        winner_members = phase_info.get("winner_members")

        print(f"\n🎉 PHASE {phase_num} WINNER ANNOUNCEMENT:")
        print(f"   Team:        {winner_name}")
        print(f"   Members:     {winner_members}")
        print(f"   Best Score:  {winner_score} RMSE")
        print(f"   Submissions: {winner_subs}")
        print(f"   Kaggle Rank: #{winner_rank}")

        # 3. Export to JSON for GitHub Pages
        print("\n[Step 3/4] Exporting to data/leaderboard.json...")
        export_data.export_to_json()

        # 4. Git commit and push if enabled
        if push_to_git:
            print("\n[Step 4/4] Pushing official results to GitHub Pages...")
            repo_dir = os.path.dirname(os.path.abspath(__file__))
            try:
                subprocess.run(["git", "add", "data/leaderboard.json"], check=True, cwd=repo_dir)
                commit_msg = f"Official Phase {phase_num} Winner: {winner_name} (Score: {winner_score} RMSE, {winner_subs} subs) [{now_str}]"
                subprocess.run(["git", "commit", "-m", commit_msg], check=False, cwd=repo_dir)
                subprocess.run(["git", "push", "origin", "main"], check=True, cwd=repo_dir)
                print(f"✅ Successfully pushed Phase {phase_num} winner announcement to GitHub!")
            except Exception as e:
                print(f"⚠️ Git push notice: {e}")

        print("=" * 50)
        print(f" 🏁 PHASE {phase_num} SUCCESSFULLY CONCLUDED!")
        print("=" * 50)
        return phase_info


def check_and_finalize_due_phases(push_to_git=True):
    now_utc = datetime.now(timezone.utc)
    finalized = []
    for cfg in db.PHASES_CONFIG:
        pnum = cfg["phase_number"]
        info = db.get_phase_info(pnum)
        if info and not info.get("is_completed"):
            deadline_dt = datetime.fromisoformat(cfg["deadline"]).astimezone(timezone.utc)
            if now_utc >= deadline_dt:
                res = run_finalize(pnum, push_to_git=push_to_git)
                finalized.append(res)
    return finalized


if __name__ == "__main__":
    push = "--no-push" not in sys.argv
    phase_arg = None
    for arg in sys.argv[1:]:
        if arg.isdigit():
            phase_arg = int(arg)
    if phase_arg:
        run_finalize(phase_arg, push_to_git=push, force="--force" in sys.argv)
    else:
        check_and_finalize_due_phases(push_to_git=push)
