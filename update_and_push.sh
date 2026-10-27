#!/bin/bash
# ===============================================================
# BAIM 330: Update Kaggle Scores & Push to Live Website (GitHub Pages)
# ===============================================================

set -e

echo "=========================================================="
echo " 1. Syncing latest scores from Kaggle..."
echo "=========================================================="
python3 sync_kaggle.py

echo "=========================================================="
echo " 2. Pushing latest standings to GitHub..."
echo "=========================================================="
git add data/leaderboard.json index.html app.js style.css
TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
git commit -m "Update competition scores [$TIMESTAMP]" || echo "No changes to commit."
git push origin main

echo "=========================================================="
echo " ✅ Done! Live website updated at:"
echo " https://maydogdu.github.io/baim330-kaggle-tracker/"
echo "=========================================================="
