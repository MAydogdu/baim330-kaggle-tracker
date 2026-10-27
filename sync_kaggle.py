"""
Standalone Kaggle synchronization script.
Syncs latest scores from Kaggle and exports data/leaderboard.json.
"""

import sys
import kaggle_service
import export_data

def sync_and_export():
    print("Fetching latest leaderboard from Kaggle...")
    result = kaggle_service.sync_scores()
    
    if result.get("success"):
        print("Kaggle sync successful!")
        print(f"Updated {len(result.get('updated_teams', []))} teams:")
        for t in result.get("updated_teams", []):
            print(f"  - {t['name']}: {t['score']} RMSE")
            
        unmatched = result.get("unmatched_teams", [])
        if unmatched:
            print(f"Unmatched {len(unmatched)} teams (pending submissions):")
            for t in unmatched:
                print(f"  - {t['name']} ({t['kaggle_name']})")
                
        # Export data/leaderboard.json
        export_data.export_to_json()
        print("Ready for GitHub deployment.")
        return 0
    else:
        print("Sync failed:", result.get("error"))
        return 1

if __name__ == "__main__":
    sys.exit(sync_and_export())
