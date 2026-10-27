#!/usr/bin/env python3
"""
House Prices Regression Modeling & Submission Script
Author: Murat Aydogdu (murt001)
Competition: House Prices - Advanced Regression Techniques

Pipeline:
1. Load train.csv and test.csv
2. Log-transform target variable SalePrice: log1p(SalePrice)
3. Domain-specific Feature Engineering (TotalSF, Age, Bathrooms, Quality combinations)
4. Missing value imputation & categorical encoding
5. 5-Fold Cross-Validation on:
   - RidgeCV (L2 Regularized Linear)
   - LassoCV (L1 Regularized Sparse)
   - ElasticNetCV
   - HistGradientBoostingRegressor
   - GradientBoostingRegressor
   - RandomForestRegressor
6. Weighted ensemble blending
7. Predict on test.csv, invert log transform: expm1(predictions)
8. Export to murt001.csv
9. Submit to Kaggle via Kaggle CLI / API
"""

import os
import sys
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold, cross_val_score
from sklearn.linear_model import RidgeCV, LassoCV, ElasticNetCV
from sklearn.ensemble import (
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor
)
from sklearn.preprocessing import RobustScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.metrics import root_mean_squared_error

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "house-prices-advanced-regression-techniques")
TRAIN_PATH = os.path.join(DATA_DIR, "train.csv")
TEST_PATH = os.path.join(DATA_DIR, "test.csv")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "murt001.csv")

def load_data():
    print(f"Loading data from {DATA_DIR}...")
    train = pd.read_csv(TRAIN_PATH)
    test = pd.read_csv(TEST_PATH)
    print(f"Train shape: {train.shape}, Test shape: {test.shape}")
    return train, test

def engineer_features(train, test):
    print("Engineering features...")
    # Remove extreme outliers in train (GrLivArea > 4000 with SalePrice < 300000, per documentation)
    train = train[~((train["GrLivArea"] > 4000) & (train["SalePrice"] < 300000))].copy()
    
    y = np.log1p(train["SalePrice"].values)
    train_ids = train["Id"].values
    test_ids = test["Id"].values

    df = pd.concat([train.drop(columns=["Id", "SalePrice"]), test.drop(columns=["Id"])], axis=0).reset_index(drop=True)

    # Impute LotFrontage based on Neighborhood median
    df["LotFrontage"] = df.groupby("Neighborhood")["LotFrontage"].transform(lambda x: x.fillna(x.median()))

    # Categorical features where NA means 'None' / missing feature
    none_cols = [
        "Alley", "BsmtQual", "BsmtCond", "BsmtExposure", "BsmtFinType1", "BsmtFinType2",
        "FireplaceQu", "GarageType", "GarageFinish", "GarageQual", "GarageCond",
        "PoolQC", "Fence", "MiscFeature", "MasVnrType"
    ]
    for c in none_cols:
        if c in df.columns:
            df[c] = df[c].fillna("None")

    # Numeric features where NA means 0
    zero_cols = [
        "GarageYrBlt", "GarageArea", "GarageCars", "BsmtFinSF1", "BsmtFinSF2",
        "BsmtUnfSF", "TotalBsmtSF", "BsmtFullBath", "BsmtHalfBath", "MasVnrArea"
    ]
    for c in zero_cols:
        if c in df.columns:
            df[c] = df[c].fillna(0)

    # Impute remaining categorical features with mode
    mode_cols = ["MSZoning", "Electrical", "KitchenQual", "Exterior1st", "Exterior2nd", "SaleType", "Utilities", "Functional"]
    for c in mode_cols:
        if c in df.columns:
            df[c] = df[c].fillna(df[c].mode()[0])

    # Convert numeric variables that are actually categorical
    df["MSSubClass"] = df["MSSubClass"].astype(str)
    df["YrSold"] = df["YrSold"].astype(str)
    df["MoSold"] = df["MoSold"].astype(str)

    # Domain specific feature engineering
    # 1. Total Square Footage
    df["TotalSF"] = df["TotalBsmtSF"] + df["1stFlrSF"] + df["2ndFlrSF"]
    df["TotalPorchSF"] = df["OpenPorchSF"] + df["EnclosedPorch"] + df["3SsnPorch"] + df["ScreenPorch"]
    
    # 2. Total Bathrooms
    df["TotalBath"] = df["FullBath"] + (0.5 * df["HalfBath"]) + df["BsmtFullBath"] + (0.5 * df["BsmtHalfBath"])

    # 3. Age & Remodel
    yr_sold_numeric = pd.to_numeric(df["YrSold"], errors="coerce").fillna(2010)
    df["Age"] = yr_sold_numeric - df["YearBuilt"]
    df["RemodelAge"] = yr_sold_numeric - df["YearRemodAdd"]
    df["IsNew"] = (df["YearBuilt"] == yr_sold_numeric).astype(int)
    df["HasRemodel"] = (df["YearRemodAdd"] != df["YearBuilt"]).astype(int)

    # 4. Binary amenity flags
    df["HasPool"] = (df["PoolArea"] > 0).astype(int)
    df["HasGarage"] = (df["GarageArea"] > 0).astype(int)
    df["HasBsmt"] = (df["TotalBsmtSF"] > 0).astype(int)
    df["HasFireplace"] = (df["Fireplaces"] > 0).astype(int)
    df["Has2ndFlr"] = (df["2ndFlrSF"] > 0).astype(int)

    # 5. Quality interactions
    qual_map = {"Ex": 5, "Gd": 4, "TA": 3, "Fa": 2, "Po": 1, "None": 0}
    for qc in ["ExterQual", "ExterCond", "BsmtQual", "BsmtCond", "HeatingQC", "KitchenQual", "FireplaceQu", "GarageQual", "GarageCond"]:
        if qc in df.columns:
            df[qc + "_Score"] = df[qc].map(qual_map).fillna(0)

    df["OverallGrade"] = df["OverallQual"] * df["OverallCond"]

    # One-hot encode all categorical columns
    categorical_cols = df.select_dtypes(include=["object"]).columns.tolist()
    df = pd.get_dummies(df, columns=categorical_cols, drop_first=True)

    # Fill any remaining NaNs
    df = df.fillna(df.median(numeric_only=True))

    n_train = len(train)
    X_train = df.iloc[:n_train].copy()
    X_test = df.iloc[n_train:].copy()

    # Scale numeric features with RobustScaler
    scaler = RobustScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    print(f"Processed feature matrix: {X_train.shape[1]} features.")
    return X_train_scaled, y, X_test_scaled, test_ids

def train_and_evaluate(X, y, X_test):
    kf = KFold(n_splits=5, shuffle=True, random_state=42)

    print("\n--- Training Models with 5-Fold Cross Validation ---")
    
    # 1. RidgeCV
    alphas_ridge = [0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 20.0, 50.0]
    ridge = RidgeCV(alphas=alphas_ridge, cv=5)
    ridge_scores = np.sqrt(-cross_val_score(ridge, X, y, scoring="neg_mean_squared_error", cv=kf))
    print(f"RidgeCV RMSE:           {ridge_scores.mean():.5f} (std: {ridge_scores.std():.5f})")
    ridge.fit(X, y)
    ridge_preds = ridge.predict(X_test)

    # 2. LassoCV
    lasso = LassoCV(alphas=np.logspace(-4, -1, 30), max_iter=10000, cv=5, random_state=42)
    lasso_scores = np.sqrt(-cross_val_score(lasso, X, y, scoring="neg_mean_squared_error", cv=kf))
    print(f"LassoCV RMSE:           {lasso_scores.mean():.5f} (std: {lasso_scores.std():.5f})")
    lasso.fit(X, y)
    lasso_preds = lasso.predict(X_test)

    # 3. ElasticNetCV
    enet = ElasticNetCV(l1_ratio=[0.1, 0.5, 0.7, 0.9], cv=5, max_iter=10000, random_state=42)
    enet_scores = np.sqrt(-cross_val_score(enet, X, y, scoring="neg_mean_squared_error", cv=kf))
    print(f"ElasticNetCV RMSE:      {enet_scores.mean():.5f} (std: {enet_scores.std():.5f})")
    enet.fit(X, y)
    enet_preds = enet.predict(X_test)

    # 4. HistGradientBoostingRegressor (Modern LightGBM-style GBDT)
    hgbt = HistGradientBoostingRegressor(
        max_iter=600,
        learning_rate=0.03,
        max_depth=5,
        min_samples_leaf=15,
        l2_regularization=1.5,
        random_state=42
    )
    hgbt_scores = np.sqrt(-cross_val_score(hgbt, X, y, scoring="neg_mean_squared_error", cv=kf))
    print(f"HistGradientBoost RMSE: {hgbt_scores.mean():.5f} (std: {hgbt_scores.std():.5f})")
    hgbt.fit(X, y)
    hgbt_preds = hgbt.predict(X_test)

    # 5. GradientBoostingRegressor (Huber loss for outlier resistance)
    gbr = GradientBoostingRegressor(
        n_estimators=700,
        learning_rate=0.03,
        max_depth=4,
        max_features="sqrt",
        min_samples_leaf=12,
        loss="huber",
        random_state=42
    )
    gbr_scores = np.sqrt(-cross_val_score(gbr, X, y, scoring="neg_mean_squared_error", cv=kf))
    print(f"GradientBoosting RMSE:  {gbr_scores.mean():.5f} (std: {gbr_scores.std():.5f})")
    gbr.fit(X, y)
    gbr_preds = gbr.predict(X_test)

    # 6. Ensemble Blend
    print("\n--- Blending Ensemble Predictions ---")
    # Weights optimized to balance regularized linear models + gradient boosting
    # Ridge: 0.25, Lasso: 0.20, ENet: 0.15, HistGB: 0.20, GBR: 0.20
    final_log_preds = (
        0.25 * ridge_preds +
        0.20 * lasso_preds +
        0.15 * enet_preds +
        0.20 * hgbt_preds +
        0.20 * gbr_preds
    )

    final_sale_price = np.expm1(final_log_preds)
    return final_sale_price

def create_submission(test_ids, predictions):
    print(f"\nWriting predictions to {OUTPUT_PATH}...")
    sub = pd.DataFrame({
        "Id": test_ids,
        "SalePrice": predictions
    })
    sub.to_csv(OUTPUT_PATH, index=False)
    print(f"Done! Preview of predictions:")
    print(sub.head(10))
    print(f"Total rows: {len(sub)}")
    assert len(sub) == 1459, f"Expected 1459 predictions, got {len(sub)}"
    assert not sub["SalePrice"].isnull().any(), "Found NaN values in predictions!"
    return OUTPUT_PATH

def submit_to_kaggle():
    print("\nSubmitting to Kaggle competition 'house-prices-advanced-regression-techniques'...")
    import subprocess
    cmd = [
        "/opt/homebrew/bin/python3.9",
        "/opt/homebrew/bin/kaggle",
        "competitions",
        "submit",
        "-c", "house-prices-advanced-regression-techniques",
        "-f", OUTPUT_PATH,
        "-m", "BAIM 330 Ensemble Regression (Ridge + Lasso + ENet + GBDT) by murt001"
    ]
    env = os.environ.copy()
    env["KAGGLE_CONFIG_DIR"] = os.path.dirname(os.path.abspath(__file__))
    
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    print("STDOUT:\n", result.stdout)
    if result.stderr:
        print("STDERR:\n", result.stderr)

    return result.returncode == 0

if __name__ == "__main__":
    train, test = load_data()
    X_train, y_train, X_test, test_ids = engineer_features(train, test)
    predictions = train_and_evaluate(X_train, y_train, X_test)
    create_submission(test_ids, predictions)
    submit_to_kaggle()
