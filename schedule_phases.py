#!/usr/bin/env python3
"""
schedule_phases.py
Background scheduler that monitors all competition phase deadlines:
- Phase 1: Nov 12, 2026 at 08:00 AM EST
- Phase 2: Nov 19, 2026 at 08:00 AM EST
- Phase 3: Dec 03, 2026 at 08:00 AM EST
- Phase 4: Dec 10, 2026 at 10:00 AM EST
Automatically snapshots scores, locks in each phase winner, exports JSON, and pushes to GitHub.
"""

import time
from datetime import datetime, timezone
import db
import finalize_phases


def run_scheduler():
    print("=" * 50)
    print(" ⏳ MULTI-PHASE AUTOMATED SCHEDULER ACTIVE")
    print("=" * 50)
    for cfg in db.PHASES_CONFIG:
        info = db.get_phase_info(cfg["phase_number"])
        status = "✅ Completed" if info and info.get("is_completed") else "🕒 Pending"
        print(f"  Phase {cfg['phase_number']}: {cfg['deadline_text']} [{status}]")
    print("=" * 50)

    while True:
        try:
            finalize_phases.check_and_finalize_due_phases(push_to_git=True)
            # Check if all phases are completed
            all_done = all(
                (db.get_phase_info(cfg["phase_number"]) or {}).get("is_completed")
                for cfg in db.PHASES_CONFIG
            )
            if all_done:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] All 4 phases concluded. Scheduler exiting.")
                break
        except Exception as e:
            print(f"[Scheduler Error] {e}")

        time.sleep(30)


if __name__ == "__main__":
    run_scheduler()
