"""
build_features.py
Replaces notebooks 03 and 04.
Reads raw prices and physical market data from gulf_data.db,
engineers all features, adds Vol_Regime labels.
Returns a clean DataFrame ready for model training.

Usage:
  - Run standalone:  python models/build_features.py
  - Import in training: from models.build_features import build_features_df
"""

import sqlite3
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

DB_PATH = 'data/processed/gulf_data.db'


def build_features_df(db_path=DB_PATH):
    """
    Full feature engineering pipeline.
    Returns DataFrame with all features + Vol_Regime column.
    """

    print("=" * 60)
    print("BUILD FEATURES")
    print("=" * 60)

    # ── Step 1: Load prices from gulf_data.db ────────────────────
    print("\n[1/6] Loading prices from gulf_data.db...")

    conn = sqlite3.connect(db_path)
    raw = pd.read_sql("""
        SELECT date, ticker, price
        FROM price_data
        WHERE ticker IN ('BRENT', 'HeatingOil', 'RBOB_Gasoline')
        ORDER BY date ASC
    """, conn)
    conn.close()

    # Pivot long → wide
    prices = raw.pivot(
        index='date', columns='ticker', values='price'
    ).reset_index()
    prices.columns.name = None
    prices = prices.rename(columns={
        'date':          'Date',
        'BRENT':         'Brent_Price',
        'HeatingOil':    'Diesel_Price',
        'RBOB_Gasoline': 'Gasoline_Price',
    })
    prices['Date'] = pd.to_datetime(prices['Date'])

    # Convert $/gallon → $/barrel (× 42)
    # Brent already in $/barrel
    # HeatingOil and RBOB_Gasoline futures quoted in $/gallon
    prices['Diesel_Price']   = prices['Diesel_Price']   * 42
    prices['Gasoline_Price'] = prices['Gasoline_Price'] * 42

    # Jet fuel proxy: HeatingOil × 1.04
    # Jet-A trades OTC with no public futures — heating oil is the
    # closest liquid proxy (both are middle distillates)
    prices['Jet_Price'] = prices['Diesel_Price'] * 1.04

    prices = prices.sort_values('Date').reset_index(drop=True)
    prices = prices.dropna(
        subset=['Brent_Price', 'Diesel_Price', 'Gasoline_Price']
    )

    print(f"  Loaded {len(prices):,} rows | "
          f"{prices['Date'].min().date()} → {prices['Date'].max().date()}")

    # ── Step 2: Returns ───────────────────────────────────────────
    print("\n[2/6] Computing returns...")
    prices['Brent_Return']    = prices['Brent_Price'].pct_change()    * 100
    prices['Diesel_Return']   = prices['Diesel_Price'].pct_change()   * 100
    prices['Gasoline_Return'] = prices['Gasoline_Price'].pct_change() * 100
    prices['Jet_Return']      = prices['Jet_Price'].pct_change()      * 100

    # ── Step 3: Crack spreads and inter-product spreads ───────────
    print("[3/6] Computing crack spreads and inter-product spreads...")
    prices['Diesel_Crack']   = prices['Diesel_Price']   - prices['Brent_Price']
    prices['Gasoline_Crack'] = prices['Gasoline_Price'] - prices['Brent_Price']
    prices['Jet_Crack']      = prices['Jet_Price']      - prices['Brent_Price']

    prices['Diesel_Gasoline_Spread'] = (prices['Diesel_Price']
                                        - prices['Gasoline_Price'])
    prices['Diesel_Jet_Spread']      = (prices['Diesel_Price']
                                        - prices['Jet_Price'])
    prices['Gasoline_Jet_Spread']    = (prices['Gasoline_Price']
                                        - prices['Jet_Price'])

    # ── Step 4: Rolling volatility and correlations ───────────────
    print("[4/6] Computing rolling volatility and correlations...")

    prices['Brent_Vol']    = (prices['Brent_Return'].rolling(30).std()
                              * np.sqrt(252))
    prices['Diesel_Vol']   = (prices['Diesel_Return'].rolling(30).std()
                              * np.sqrt(252))
    prices['Gasoline_Vol'] = (prices['Gasoline_Return'].rolling(30).std()
                              * np.sqrt(252))
    prices['Jet_Vol']      = (prices['Jet_Return'].rolling(30).std()
                              * np.sqrt(252))

    prices['Brent_Diesel_Corr']   = (prices['Brent_Return']
                                     .rolling(90)
                                     .corr(prices['Diesel_Return']))
    prices['Brent_Gasoline_Corr'] = (prices['Brent_Return']
                                     .rolling(90)
                                     .corr(prices['Gasoline_Return']))
    prices['Brent_Jet_Corr']      = (prices['Brent_Return']
                                     .rolling(90)
                                     .corr(prices['Jet_Return']))

    # Calendar features
    prices['Month']   = prices['Date'].dt.month
    prices['Quarter'] = prices['Date'].dt.quarter
    prices['Year']    = prices['Date'].dt.year

    # ── Step 5: Physical market features ─────────────────────────
    print("[5/6] Loading physical market features from refinery_data...")

    conn = sqlite3.connect(db_path)
    refinery_raw = pd.read_sql("""
        SELECT date, series_id, value
        FROM refinery_data
        WHERE series_id IN ('WPULEUS3','WCESTUS1','WGTSTUS1','WDISTUS1')
        ORDER BY date ASC
    """, conn)
    conn.close()

    # Pivot long → wide
    refinery = refinery_raw.pivot(
        index='date', columns='series_id', values='value'
    ).reset_index()
    refinery.columns.name = None
    refinery = refinery.rename(columns={
        'date':     'Date',
        'WPULEUS3': 'refinery_utilization',
        'WCESTUS1': 'crude_stocks',
        'WGTSTUS1': 'gasoline_stocks',
        'WDISTUS1': 'distillate_stocks',
    })
    refinery['Date'] = pd.to_datetime(refinery['Date'])

    # Week-on-week changes
    # Negative = draw (bullish for spreads)
    # Positive = build (bearish for spreads)
    refinery['crude_stocks_change']      = refinery['crude_stocks'].diff()
    refinery['gasoline_stocks_change']   = refinery['gasoline_stocks'].diff()
    refinery['distillate_stocks_change'] = refinery['distillate_stocks'].diff()

    # Merge into daily price DataFrame on date
    # refinery_data is weekly — forward-fill carries each Wednesday
    # reading forward until the next Wednesday reading arrives
    prices = prices.merge(refinery, on='Date', how='left')

    physical_cols = [
        'refinery_utilization',
        'crude_stocks',       'crude_stocks_change',
        'gasoline_stocks',    'gasoline_stocks_change',
        'distillate_stocks',  'distillate_stocks_change',
    ]
    prices[physical_cols] = prices[physical_cols].ffill()

    covered = prices['refinery_utilization'].notna().sum()
    print(f"  Physical features: {covered} of {len(prices)} days covered")
    print(f"  First date with physical data: "
          f"{prices.loc[prices['refinery_utilization'].notna(), 'Date'].min().date()}")

    # ── Step 6: Vol_Regime classification ────────────────────────
    print("[6/6] Classifying volatility regimes...")

    valid_vol = prices['Brent_Vol'].dropna()
    low_threshold    = valid_vol.quantile(0.33)
    medium_threshold = valid_vol.quantile(0.66)

    def classify_regime(vol):
        if pd.isna(vol):
            return None
        if vol < low_threshold:
            return 'Low'
        elif vol < medium_threshold:
            return 'Medium'
        else:
            return 'High'

    prices['Vol_Regime'] = prices['Brent_Vol'].apply(classify_regime)

    # Drop rows where vol cannot be computed (first 30 days)
    prices = prices.dropna(subset=['Brent_Vol'])

    # ── Summary ───────────────────────────────────────────────────
    regime_counts = prices['Vol_Regime'].value_counts()
    print(f"\n  Vol thresholds (percentile-based):")
    print(f"    Low    < {low_threshold:.1f}%")
    print(f"    Medium   {low_threshold:.1f}% – {medium_threshold:.1f}%")
    print(f"    High   > {medium_threshold:.1f}%")
    print(f"\n  Regime distribution:")
    for regime in ['High', 'Medium', 'Low']:
        count = regime_counts.get(regime, 0)
        print(f"    {regime:8s}: {count} days ({count/len(prices)*100:.1f}%)")

    crisis = prices[prices['Date'] >= '2026-02-01']
    if len(crisis) > 0:
        high_in_crisis = (crisis['Vol_Regime'] == 'High').sum()
        print(f"\n  Gulf crisis window (Feb 2026+):")
        print(f"    {len(crisis)} trading days | {high_in_crisis} HIGH regime days")

    print(f"\n  Final dataset: {len(prices):,} rows | {len(prices.columns)} columns")
    print("\n✅ build_features_df() complete")

    return prices


if __name__ == '__main__':
    df = build_features_df()
    print(f"\nColumns: {list(df.columns)}")
    print(f"\nSample (last 5 rows):")
    print(df[['Date', 'Brent_Price', 'Diesel_Crack',
              'refinery_utilization', 'distillate_stocks_change',
              'Brent_Vol', 'Vol_Regime']].tail())