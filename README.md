# BAIM 330: Applied Data Mining - Kaggle Competition Tracker

A tailored web platform for **BAIM 330: Applied Data Mining** at Western New England University (WNEU) to track student groups competing in Kaggle's **[House Prices - Advanced Regression Techniques](https://www.kaggle.com/competitions/house-prices-advanced-regression-techniques)** competition.

🌐 **Live Website URL (GitHub Pages):**  
👉 **[https://maydogdu.github.io/baim330-kaggle-tracker/](https://maydogdu.github.io/baim330-kaggle-tracker/)**

---

## 🌟 Key Features

1. **Main Screen & Class Leaderboard**
   - **Winner Spotlight**: Prominently highlights the #1 leading student group with a trophy badge, best RMSE score, Kaggle global rank, and submission counts.
   - **Instructor Benchmark Card**: Shows the instructor's submission benchmark (e.g., Prof. Aydogdu) and tracks whether any student team has beaten the benchmark score.
   - **Live Standings Table**: Gold, Silver, and Bronze podium ranks with trend indicators showing score changes (`↓` improvement vs `↑` regression) and direct links to Kaggle profiles.
   - **Evaluation Metric Awareness**: House Prices evaluates on Root-Mean-Squared-Error (RMSE) between the logarithm of predicted and observed sale prices; **lower score is better**.

2. **Time Series History & Progression Analysis**
   - **Interactive Chart.js Graph**: Visualizes each group's progression across the semester from day one.
   - **Milestone Tracking**: Hover tooltips show the submission date, score, global rank, and model notes (e.g. Ridge, Random Forest, XGBoost, Stacking).
   - **Toggle Controls**: Show/hide the instructor benchmark line or zoom into specific date ranges.
   - **Complete Submissions Log**: Chronological table of all recorded scores.

3. **Administrative Panel (Protected)**
   - **Secure Access**: Authenticated via administrative password (default: `baim330admin`, customizable in UI).
   - **"Update Current Scores Now" Button**: One-click action to fetch the latest Kaggle public leaderboard, match team handles, and automatically record new time-series snapshots.
   - **Group Management**: Add, edit, or delete student teams (Team Name, Kaggle Handle, Student Members, and Student vs. Instructor Benchmark designation).
   - **Manual Score Entry**: Manually record or backfill score snapshots for any team at any date/time.
   - **Flexible Kaggle Sync**:
     - Direct Kaggle REST API integration using Kaggle username & API key.
     - Direct Leaderboard CSV drag-and-drop uploader (downloadable with one click from Kaggle).
   - **Demo History Seeder**: Instantly generates realistic sample progression data across project milestones for testing.

---

## 🚀 Quick Start

The application is built using Python 3's built-in standard library (`http.server`, `sqlite3`, `json`, `urllib.request`). **No external packages, virtualenv, or `pip install` required!**

### 1. Launch the Server

Run either:
```bash
./start.sh
```
or
```bash
python3 server.py 8000
```

### 2. Open in Browser

Navigate to:
```
http://localhost:8000
```

---

## 🔑 Administrative Access

- Click **Admin Login** in the top navigation bar.
- Default Password:
  ```
  baim330admin
  ```
- You can change the admin password at any time from the Admin Panel.

---

## ⚙️ Connecting to Kaggle

To enable automatic 1-click score fetching:
1. Log into your Kaggle account and go to [kaggle.com/settings](https://www.kaggle.com/settings).
2. Under the **API** section, click **Create New Token**. This downloads a `kaggle.json` file.
3. Open the **Admin Panel** on the website:
   - Enter your **Kaggle Username** and **Kaggle API Key** under the Kaggle Configuration card.
   - Click **Save Kaggle Credentials**.
4. When you click **Update Current Scores Now**, the server will query Kaggle's API and update all teams in real time!

*Note: If you already have `~/.kaggle/kaggle.json` configured on your machine or environment variables `KAGGLE_USERNAME` and `KAGGLE_KEY`, the server automatically detects them.*

---

## 📁 File Structure

```
competition-website/
├── server.py              # Zero-dependency Python HTTP server & REST API
├── db.py                  # SQLite database management (teams, snapshots, settings)
├── kaggle_service.py      # Kaggle API fetcher and CSV parser
├── baim330_competition.db # SQLite database file (created automatically)
├── start.sh               # One-click launch script
├── static/
│   ├── index.html         # Responsive Single Page Application UI
│   ├── app.js             # Client-side routing, Chart.js graphs & API calls
│   └── style.css          # Styling & badge effects
└── README.md              # Project documentation
```
