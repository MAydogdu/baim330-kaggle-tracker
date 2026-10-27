#!/usr/bin/env python3
"""
BAIM 330 Kaggle Tracker - Web Server
Lightweight, robust HTTP server using Python 3 standard library.
No external dependencies required (no pip, no flask/express needed).
"""

import os
import sys
import json
import hashlib
import mimetypes
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from datetime import datetime

from db import (
    init_db, get_db_connection, get_leaderboard_data, get_history_data,
    get_all_teams, add_team, update_team, delete_team, record_snapshot,
    delete_snapshot, get_setting, set_setting
)
from kaggle_service import (
    sync_scores, process_leaderboard_entries, parse_csv_leaderboard_content,
    get_kaggle_credentials
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
SERVER_SECRET = "baim330_competition_secret_salt_2026"

def generate_admin_token(password):
    return hashlib.sha256(f"{password}_{SERVER_SECRET}".encode("utf-8")).hexdigest()

def is_authorized(headers):
    expected_pwd = get_setting("admin_password", "baim330admin")
    valid_token = generate_admin_token(expected_pwd)
    
    # Check X-Admin-Token header
    token = headers.get("X-Admin-Token")
    if token and token == valid_token:
        return True
        
    # Check Authorization: Bearer <token>
    auth = headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        if token == valid_token:
            return True

    return False

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class RequestHandler(BaseHTTPRequestHandler):

    def send_json(self, data, status_code=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message, status_code=400):
        self.send_json({"error": message, "success": False}, status_code=status_code)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()

    def read_json_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length).decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def read_raw_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(content_length)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # API Endpoints
        if path == "/api/leaderboard":
            data = get_leaderboard_data()
            return self.send_json(data)

        elif path == "/api/history":
            data = get_history_data()
            return self.send_json(data)

        elif path == "/api/teams":
            teams = get_all_teams()
            return self.send_json({"teams": teams})

        elif path == "/api/admin/settings":
            u, k, source = get_kaggle_credentials()
            settings = {
                "competition_id": get_setting("competition_id", "house-prices-advanced-regression-techniques"),
                "kaggle_configured": bool(u and k),
                "kaggle_username": u if u else "",
                "credentials_source": source,
                "has_custom_password": get_setting("admin_password", "baim330admin") != "baim330admin"
            }
            return self.send_json(settings)

        elif path == "/api/admin/check-auth":
            authed = is_authorized(self.headers)
            return self.send_json({"authenticated": authed})

        # Public Refresh Endpoint (GET or POST)
        elif path == "/api/refresh":
            comp_id = get_setting("competition_id", "house-prices-advanced-regression-techniques")
            result = sync_scores(comp_id)
            if result.get("success"):
                try:
                    import export_data
                    export_data.export_to_json()
                except Exception as e:
                    print("Export error:", e)
                return self.send_json(result)
            else:
                return self.send_error_json(result.get("error", "Failed to fetch from Kaggle"))

        # Static files
        self.serve_static_file(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Public Refresh Endpoint (Anyone can request a Kaggle fetch)
        if path == "/api/refresh":
            comp_id = get_setting("competition_id", "house-prices-advanced-regression-techniques")
            result = sync_scores(comp_id)
            if result.get("success"):
                try:
                    import export_data
                    export_data.export_to_json()
                except Exception as e:
                    print("Export error:", e)
                return self.send_json(result)
            else:
                return self.send_error_json(result.get("error", "Failed to fetch from Kaggle"))

        # Admin Login
        if path == "/api/admin/login":
            body = self.read_json_body()
            password = body.get("password", "").strip()
            stored_pwd = get_setting("admin_password", "baim330admin")
            if password == stored_pwd:
                token = generate_admin_token(stored_pwd)
                return self.send_json({
                    "success": True,
                    "token": token,
                    "message": "Authentication successful"
                })
            else:
                return self.send_error_json("Invalid admin password", status_code=401)

        # The following endpoints require admin authorization
        if path.startswith("/api/admin/"):
            if not is_authorized(self.headers):
                return self.send_error_json("Unauthorized. Admin access required.", status_code=401)

        # Trigger Kaggle Sync
        if path == "/api/admin/update":
            body = self.read_json_body()
            comp_id = body.get("competition_id")
            result = sync_scores(comp_id)
            if not result.get("success"):
                return self.send_json(result, status_code=400)
            
            # Export data for static GitHub Pages view
            try:
                import export_data
                export_data.export_to_json()
            except Exception as e:
                print("Export error:", e)

            return self.send_json(result)

        # Add Team
        elif path == "/api/admin/teams":
            body = self.read_json_body()
            name = body.get("name", "").strip()
            kaggle_name = body.get("kaggle_name", "").strip()
            members = body.get("members", "").strip()
            is_instructor = body.get("is_instructor", 0)

            if not name or not kaggle_name:
                return self.send_error_json("Group name and Kaggle name are required.")

            try:
                team_id = add_team(name, kaggle_name, members, is_instructor)
                return self.send_json({
                    "success": True,
                    "team_id": team_id,
                    "message": f"Team '{name}' added successfully."
                })
            except Exception as e:
                return self.send_error_json(f"Error adding team: {str(e)}")

        # Add Manual Score Snapshot
        elif path == "/api/admin/snapshot":
            body = self.read_json_body()
            team_id = body.get("team_id")
            score = body.get("score")
            kaggle_rank = body.get("kaggle_rank")
            recorded_at = body.get("recorded_at")
            notes = body.get("notes", "Manual entry")

            if team_id is None or score is None:
                return self.send_error_json("team_id and score are required.")

            try:
                score_flt = float(score)
            except ValueError:
                return self.send_error_json("Invalid score format. Must be a numeric float (e.g., 0.12345).")

            snap_id = record_snapshot(
                team_id=int(team_id),
                score=score_flt,
                kaggle_rank=int(kaggle_rank) if kaggle_rank else None,
                recorded_at=recorded_at if recorded_at else None,
                notes=notes,
                source="manual"
            )
            return self.send_json({
                "success": True,
                "snapshot_id": snap_id,
                "message": "Snapshot recorded successfully."
            })

        # Save Settings
        elif path == "/api/admin/settings":
            body = self.read_json_body()
            if "kaggle_username" in body:
                set_setting("kaggle_username", body["kaggle_username"].strip())
            if "kaggle_key" in body and body["kaggle_key"].strip():
                set_setting("kaggle_key", body["kaggle_key"].strip())
            if "competition_id" in body and body["competition_id"].strip():
                set_setting("competition_id", body["competition_id"].strip())
            if "new_admin_password" in body and body["new_admin_password"].strip():
                new_pwd = body["new_admin_password"].strip()
                set_setting("admin_password", new_pwd)
                # Return new token for the new password
                token = generate_admin_token(new_pwd)
                return self.send_json({"success": True, "token": token, "message": "Settings and password updated successfully."})

            return self.send_json({"success": True, "message": "Settings saved successfully."})

        # Upload Kaggle Leaderboard CSV
        elif path == "/api/admin/upload-csv":
            body = self.read_json_body()
            csv_content = body.get("csv_content", "")
            if not csv_content:
                return self.send_error_json("No CSV content received.")
            
            entries = parse_csv_leaderboard_content(csv_content)
            if not entries:
                return self.send_error_json("Could not parse any valid leaderboard entries from CSV.")

            result = process_leaderboard_entries(entries, source="csv_upload")
            return self.send_json(result)

        # Seed Demo Progression
        elif path == "/api/admin/seed-demo":
            self.seed_demo_progression()
            return self.send_json({"success": True, "message": "Demo progression history seeded successfully."})

        else:
            return self.send_error_json("Endpoint not found", status_code=404)

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if not is_authorized(self.headers):
            return self.send_error_json("Unauthorized", status_code=401)

        if path.startswith("/api/admin/teams/"):
            team_id = int(path.split("/")[-1])
            body = self.read_json_body()
            name = body.get("name", "").strip()
            kaggle_name = body.get("kaggle_name", "").strip()
            members = body.get("members", "").strip()
            is_instructor = body.get("is_instructor", 0)

            if not name or not kaggle_name:
                return self.send_error_json("Group name and Kaggle name are required.")

            update_team(team_id, name, kaggle_name, members, is_instructor)
            return self.send_json({"success": True, "message": "Team updated successfully."})
        else:
            return self.send_error_json("Endpoint not found", status_code=404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if not is_authorized(self.headers):
            return self.send_error_json("Unauthorized", status_code=401)

        if path.startswith("/api/admin/teams/"):
            team_id = int(path.split("/")[-1])
            delete_team(team_id)
            return self.send_json({"success": True, "message": "Team and associated history deleted."})

        elif path.startswith("/api/admin/snapshot/"):
            snapshot_id = int(path.split("/")[-1])
            delete_snapshot(snapshot_id)
            return self.send_json({"success": True, "message": "Snapshot deleted."})

        else:
            return self.send_error_json("Endpoint not found", status_code=404)

    def seed_demo_progression(self):
        """Seeds realistic historical progress snapshots for BAIM 330 teams"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, is_instructor FROM teams")
        teams = {row["name"]: row["id"] for row in cursor.fetchall()}
        conn.close()

        # Progression across past milestones leading up to today
        milestones = [
            # 2 weeks ago
            ("2026-10-13 14:00:00", [
                ("Group 1", 0.1650, 2400, "Initial Linear Regression"),
                ("Group 2", 0.1580, 2150, "Ridge + Lasso Baseline"),
                ("Group 3", 0.1720, 2800, "Simple Decision Tree"),
                ("Instructor (Benchmark)", 0.1380, 1180, "Initial Baseline Benchmark")
            ]),
            # 1 week ago
            ("2026-10-20 11:30:00", [
                ("Group 1", 0.1495, 1750, "Added Feature Engineering & Log Transform"),
                ("Group 2", 0.1440, 1490, "Random Forest + Imputation"),
                ("Group 3", 0.1610, 2300, "Handling Outliers"),
                ("Instructor (Benchmark)", 0.1320, 950, "LightGBM Model Benchmark")
            ]),
            # Today
            ("2026-10-27 12:00:00", [
                ("Group 1", 0.1378, 1150, "Ensemble XGBoost + Ridge"),
                ("Group 2", 0.1395, 1260, "Hyperparameter Tuned CatBoost"),
                ("Group 3", 0.1480, 1720, "Gradient Boosting with Target Encoding"),
                ("Instructor (Benchmark)", 0.1265, 780, "Stacked Ensemble Benchmark")
            ])
        ]

        for timestamp, team_entries in milestones:
            for t_name, score, rank, note in team_entries:
                tid = teams.get(t_name)
                if tid:
                    record_snapshot(
                        team_id=tid,
                        score=score,
                        kaggle_rank=rank,
                        recorded_at=timestamp,
                        notes=note,
                        source="demo_seed"
                    )

    def serve_static_file(self, req_path):
        # Security: Immediately reject sensitive file patterns
        lower_path = req_path.lower()
        if any(bad in lower_path for bad in ["kaggle", ".json", ".db", ".py", ".env", ".git", ".."]):
            if not lower_path.endswith((".css", ".js", ".html", ".png", ".jpg", ".svg", ".ico")):
                self.send_error(403, "Access Denied")
                return

        if req_path == "/" or req_path == "":
            req_path = "/index.html"

        file_path = os.path.join(STATIC_DIR, req_path.lstrip("/"))
        
        # Security: prevent directory traversal
        if not os.path.abspath(file_path).startswith(STATIC_DIR):
            self.send_error(403, "Access Denied")
            return

        if not os.path.exists(file_path) or os.path.isdir(file_path):
            # Fallback to index.html for SPA-style routing if needed
            file_path = os.path.join(STATIC_DIR, "index.html")

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {str(e)}")

def run_server(port=8000, host="0.0.0.0"):
    init_db()
    server_address = (host, port)
    httpd = ThreadedHTTPServer(server_address, RequestHandler)
    print("=" * 65)
    print(f"  🏆 BAIM 330: Applied Data Mining - Kaggle Tracker Server")
    print(f"  🌐 Running locally at: http://localhost:{port} (and http://127.0.0.1:{port})")
    print(f"  🔑 Default Admin Password: baim330admin")
    print(f"  📊 Competition: House Prices - Advanced Regression Techniques")
    print("=" * 65)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer shutting down gracefully.")
        httpd.server_close()

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port=port)
