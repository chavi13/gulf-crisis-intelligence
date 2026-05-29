"""
05_training_testing.py
Trains XGBoost and Prophet models on price data from gulf_data.db.
Fixes applied vs original notebook:
  1. Reads from build_features.py (no CSV)
  2. Prophet growth='flat' for crack spreads (mean-reverting)
  3. Floor/cap added to Prophet (no negative forecasts)
  4. Test set extended to include 2025-2026 crisis period
  5. Model files saved to gulf project models/ folder
"""

import sys
import os
import pickle
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

from prophet import Prophet
from xgboost import XGBRegressor
from sklearn.metrics import (mean_absolute_percentage_error,
                             mean_squared_error, mean_absolute_error)

# ── Path setup ────────────────────────────────────────────────
PROJECT_ROOT = '/Users/chavimangla/Desktop/gulf-crisis-intelligence'
sys.path.insert(0, PROJECT_ROOT)
from models.build_features import build_features_df

MODELS_DIR = os.path.join(PROJECT_ROOT, 'models')

# ── Load features ─────────────────────────────────────────────
print("=" * 70)
print("NOTEBOOK 05: FORECASTING MODEL DEVELOPMENT")
print("=" * 70)

prices = build_features_df()
print(f"\nTotal data: {len(prices):,} rows "
      f"({prices['Date'].min().date()} → {prices['Date'].max().date()})")

# ── Training strategy ─────────────────────────────────────────
# Brent:         full history (no regime shift)
# Crack spreads: post-COVID only (+60-90% structural shift)
train_ranges = {
    'Brent_Price':    '2007-07-30',
    'Diesel_Crack':   '2020-01-01',
    'Gasoline_Crack': '2020-01-01',
    'Jet_Crack':      '2020-01-01',
}

# Test set includes 2025 + full Gulf crisis (2026)
test_start = '2025-01-01'
products   = ['Brent_Price', 'Diesel_Crack', 'Gasoline_Crack', 'Jet_Crack']

print("\n" + "=" * 70)
print("TRAIN/TEST SPLIT:")
print("=" * 70)
for product, start in train_ranges.items():
    train_days = len(prices[(prices['Date'] >= start) &
                            (prices['Date'] < test_start)])
    test_days  = len(prices[prices['Date'] >= test_start])
    print(f"  {product:20s}: train {start} → 2024-12-31 "
          f"({train_days:,} days) | test 2025+ ({test_days} days)")


# ── Helper functions ──────────────────────────────────────────
def evaluate_forecast(actual, predicted, product_name=""):
    mask = ~(np.isnan(actual) | np.isnan(predicted))
    a, p = actual[mask], predicted[mask]
    if len(a) == 0:
        return {'MAPE': np.nan, 'RMSE': np.nan,
                'MAE': np.nan, 'Direction_Acc': np.nan}
    mape = mean_absolute_percentage_error(a, p) * 100
    rmse = np.sqrt(mean_squared_error(a, p))
    mae  = mean_absolute_error(a, p)
    dir_acc = (np.diff(a) > 0) == (np.diff(p) > 0)
    return {'MAPE': mape, 'RMSE': rmse, 'MAE': mae,
            'Direction_Acc': dir_acc.mean() * 100}


def create_xgboost_features(df, target_col,
                            lags=[7, 14, 30],
                            rolling_windows=[60, 90]):
    feature_df = df.copy()

    for lag in lags:
        feature_df[f'{target_col}_lag_{lag}'] = \
            feature_df[target_col].shift(lag)

    for window in rolling_windows:
        feature_df[f'{target_col}_ma_{window}'] = \
            feature_df[target_col].rolling(window).mean()
        feature_df[f'{target_col}_std_{window}'] = \
            feature_df[target_col].rolling(window).std()

    for window in [30, 60]:
        feature_df[f'{target_col}_pct_change_{window}'] = \
            feature_df[target_col].pct_change(window) * 100

    feature_df['month']       = feature_df['Date'].dt.month
    feature_df['quarter']     = feature_df['Date'].dt.quarter
    feature_df['day_of_year'] = feature_df['Date'].dt.dayofyear

    # Rolling baseline — replaces Year
    # Captures current market regime without memorizing calendar
    # 252 trading days = 1 year rolling average of the target itself
    # Tells model: "what has this spread averaged over the last year?"
    # Automatically adjusts when regime changes — unlike Year which only goes up
    feature_df[f'{target_col}_baseline_252'] = (
        feature_df[target_col].rolling(252).mean()
    )

    # Vol regime one-hot — title case matches build_features.py
    feature_df['Vol_Regime_Low']    = \
        (feature_df['Vol_Regime'] == 'Low').astype(int)
    feature_df['Vol_Regime_Medium'] = \
        (feature_df['Vol_Regime'] == 'Medium').astype(int)
    feature_df['Vol_Regime_High']   = \
        (feature_df['Vol_Regime'] == 'High').astype(int)

    if 'Diesel_Crack' in df.columns and 'Gasoline_Crack' in df.columns:
        feature_df['Diesel_Gasoline_Spread'] = \
            (df['Diesel_Crack'] - df['Gasoline_Crack']).shift(7)
    if 'Diesel_Crack' in df.columns and 'Jet_Crack' in df.columns:
        feature_df['Diesel_Jet_Spread'] = \
            (df['Diesel_Crack'] - df['Jet_Crack']).shift(7)

    return feature_df.dropna()


# ── XGBoost training ──────────────────────────────────────────
print("\n" + "=" * 70)
print("TRAINING XGBOOST MODELS")
print("=" * 70)

xgb_models  = {}
xgb_results = {}

EXCLUDE_COLS = ['Date', 'Vol_Regime',
                'Brent_Price', 'Diesel_Price', 'Gasoline_Price',
                'Jet_Price', 'Diesel_Crack', 'Gasoline_Crack',
                'Jet_Crack', 'Brent_Return', 'Diesel_Return',
                'Gasoline_Return', 'Jet_Return',
                'Brent_Vol', 'Diesel_Vol', 'Gasoline_Vol', 'Jet_Vol',
                'Brent_Diesel_Corr', 'Brent_Gasoline_Corr',
                'Brent_Jet_Corr',
                'Year']   # excluded — replaced by rolling baseline

for product in products:
    print(f"\n  {product}")
    feature_df = create_xgboost_features(prices, product)

    train_mask = ((feature_df['Date'] >= train_ranges[product]) &
                  (feature_df['Date'] <  test_start))
    test_mask  =  (feature_df['Date'] >= test_start)

    train_data = feature_df[train_mask].copy()
    test_data  = feature_df[test_mask].copy()

    feature_cols = [c for c in feature_df.columns
                    if c not in EXCLUDE_COLS + [product]]

    X_train, y_train = train_data[feature_cols], train_data[product]
    X_test,  y_test  = test_data[feature_cols],  test_data[product]

    print(f"    Train: {len(X_train):,} | Test: {len(X_test):,} "
          f"| Features: {len(feature_cols)}")

    model = XGBRegressor(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        objective='reg:squarederror', early_stopping_rounds=20,
        random_state=42, n_jobs=-1
    )
    model.fit(X_train, y_train,
              eval_set=[(X_test, y_test)], verbose=False)

    y_pred   = model.predict(X_test)
    metrics  = evaluate_forecast(y_test.values, y_pred,
                                 product_name=product)
    xgb_models[product]  = model
    xgb_results[product] = {
        'predictions': y_pred, 'actual': y_test.values,
        'dates': test_data['Date'].values, 'metrics': metrics
    }

    top_feat = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False).iloc[0]

    print(f"    MAPE: {metrics['MAPE']:.2f}% | "
          f"Top feature: {top_feat['feature']} "
          f"({top_feat['importance']:.1%})")


# ── Prophet training ──────────────────────────────────────────
print("\n" + "=" * 70)
print("TRAINING PROPHET MODELS")
print("=" * 70)

prophet_models  = {}
prophet_results = {}

for product in products:
    print(f"\n  {product}")

    train_mask = ((prices['Date'] >= train_ranges[product]) &
                  (prices['Date'] <  test_start))
    test_mask  =  (prices['Date'] >= test_start)

    train_df = prices[train_mask].copy().reset_index(drop=True)
    test_df  = prices[test_mask].copy().reset_index(drop=True)

    # Prophet requires ds/y columns
    prophet_train = train_df[['Date', product]].copy()
    prophet_train.columns = ['ds', 'y']
    prophet_train = prophet_train.dropna().reset_index(drop=True)

    # Vol regime regressors — title case
    prophet_train['Vol_Regime_Low']  = \
        (train_df['Vol_Regime'] == 'Low').astype(int).values
    prophet_train['Vol_Regime_High'] = \
        (train_df['Vol_Regime'] == 'High').astype(int).values

    # ── FIX: floor/cap for crack spreads ─────────────────────
    is_crack = 'Crack' in product
    if is_crack:
        floor = 0.0
        cap   = float(train_df[product].quantile(0.99) * 1.5)
        prophet_train['floor'] = floor
        prophet_train['cap']   = cap
        print(f"    Floor: ${floor:.0f} | Cap: ${cap:.2f}")

    # ── FIX: growth parameter ─────────────────────────────────
    # Brent trends → linear
    # Crack spreads mean-revert → flat
    growth = 'flat' if is_crack else 'linear'

    model = Prophet(
        growth=growth,
        yearly_seasonality=True if product == 'Gasoline_Crack' else 'auto',
        weekly_seasonality=False,
        daily_seasonality=False,
        changepoint_prior_scale=0.01,
        seasonality_prior_scale=20,
        interval_width=0.80,
        seasonality_mode='multiplicative'
    )
    model.add_regressor('Vol_Regime_Low')
    model.add_regressor('Vol_Regime_High')

    model.fit(prophet_train)

    # Prepare test data
    prophet_test = test_df[['Date', product]].copy()
    prophet_test.columns = ['ds', 'y']
    prophet_test = prophet_test.dropna().reset_index(drop=True)
    prophet_test['Vol_Regime_Low']  = \
        (test_df['Vol_Regime'] == 'Low').astype(int).values
    prophet_test['Vol_Regime_High'] = \
        (test_df['Vol_Regime'] == 'High').astype(int).values

    if is_crack:
        prophet_test['floor'] = floor
        prophet_test['cap']   = cap

    forecast  = model.predict(prophet_test)
    predicted = forecast['yhat'].values

    # Clip negatives on crack spreads
    if is_crack and predicted.min() < 0:
        print(f"    ⚠ Clipping {(predicted < 0).sum()} negative forecasts")
        predicted = np.maximum(predicted, 0)

    actual  = test_df[product].values[:len(predicted)]
    metrics = evaluate_forecast(actual, predicted, product_name=product)

    prophet_models[product]  = model
    prophet_results[product] = {
        'forecast': forecast, 'actual': actual,
        'dates': test_df['Date'].values[:len(predicted)],
        'metrics': metrics
    }

    print(f"    MAPE: {metrics['MAPE']:.2f}% | "
          f"growth={growth}")


# ── Ensemble ──────────────────────────────────────────────────
print("\n" + "=" * 70)
print("ENSEMBLE RESULTS")
print("=" * 70)

ensemble_results = {}
for product in products:
    xgb_pred     = xgb_results[product]['predictions']
    prophet_pred = prophet_results[product]['forecast']['yhat'].values
    actual       = xgb_results[product]['actual']

    # Brent: 80/20 weighted ensemble
    # Crack spreads: XGBoost only (Prophet still noisy on spreads)
    if product == 'Brent_Price':
        ensemble_pred = 0.80 * xgb_pred + 0.20 * prophet_pred
    else:
        ensemble_pred = xgb_pred

    metrics = evaluate_forecast(actual, ensemble_pred,
                                product_name=product)
    ensemble_results[product] = {
        'predictions': ensemble_pred, 'actual': actual,
        'dates': xgb_results[product]['dates'], 'metrics': metrics
    }

print(f"\n  {'Product':20s} {'Prophet':>10} {'XGBoost':>10} "
      f"{'Ensemble':>10}")
print("  " + "-" * 54)
for product in products:
    pm = prophet_results[product]['metrics']['MAPE']
    xm = xgb_results[product]['metrics']['MAPE']
    em = ensemble_results[product]['metrics']['MAPE']
    print(f"  {product:20s} {pm:>9.2f}% {xm:>9.2f}% {em:>9.2f}%")

avg_ensemble = np.mean([ensemble_results[p]['metrics']['MAPE']
                        for p in products])
print(f"\n  Average ensemble MAPE: {avg_ensemble:.2f}%")
status = ("✅ TARGET HIT" if 11 <= avg_ensemble <= 15
          else "⚠ Review")
print(f"  Status: {status}")


# ── Save models ───────────────────────────────────────────────
print("\n" + "=" * 70)
print("SAVING MODELS")
print("=" * 70)

for product, model in prophet_models.items():
    path = os.path.join(MODELS_DIR, f'prophet_{product}.pkl')
    with open(path, 'wb') as f:
        pickle.dump(model, f)
    print(f"  ✅ Saved: models/prophet_{product}.pkl")

for product, model in xgb_models.items():
    path = os.path.join(MODELS_DIR, f'xgboost_{product}.json')
    model.save_model(path)
    print(f"  ✅ Saved: models/xgboost_{product}.json")

print("\n" + "=" * 70)
print("✅ TRAINING COMPLETE")
print("=" * 70)