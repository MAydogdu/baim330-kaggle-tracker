#!/bin/bash
# ===============================================================
# BAIM 330: Applied Data Mining - Kaggle Competition Website
# Western New England University
# ===============================================================

PORT=${1:-8000}

echo "=========================================================="
echo " Starting BAIM 330 Kaggle Tracker Website..."
echo " Competition: House Prices - Advanced Regression Techniques"
echo " Port: http://127.0.0.1:$PORT"
echo " Admin Default Password: baim330admin"
echo "=========================================================="

python3 server.py "$PORT"
