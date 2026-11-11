#!/usr/bin/env python3
"""
schedule_phase1.py
Background daemon that waits until the Phase 1 deadline (Nov 12, 2026 at 08:00:00 EST),
then automatically executes finalize_phase1.py.
"""

import time
import sys
import os
from datetime import datetime

# Phase 1 Target: November 12, 2026 at 08:00:00 AM EST
DEFAULT_TARGET = datetime(2026, 11, 12, 8, 0, 0)

def wait_and_finalize(target_dt=DEFAULT_TARGET):
    now = datetime.now()
    diff = (target_dt - now).total_seconds()

    print(f"==================================================")
    print(f" ⏳ PHASE 1 AUTOMATED SCHEDULER ACTIVE")
    print(f" Current Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Target Time:  {target_dt.strftime('%Y-%m-%d %H:%M:%S')} (EST)")
    print(f" Time to Wait: {int(diff)} seconds ({diff/3600:.2f} hours)")
    print(f"==================================================")

    if diff > 0:
        # Check every 60 seconds until deadline
        while True:
            now = datetime.now()
            remaining = (target_dt - now).total_seconds()
            if remaining <= 0:
                break
            
            # Print heartbeat every hour or when under 5 minutes
            if int(remaining) % 3600 < 60 or remaining < 300:
                print(f"[{now.strftime('%H:%M:%S')}] Waiting for Phase 1 deadline... {int(remaining/60)} minutes remaining.")

            sleep_chunk = min(60, max(1, remaining))
            time.sleep(sleep_chunk)

    print(f"\n⏰ Deadline reached at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}! Executing Phase 1 finalization...")
    import finalize_phase1
    finalize_phase1.run_finalize(push_to_git=True)

if __name__ == "__main__":
    wait_and_finalize()
