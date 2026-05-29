"""
volatility_tracker.py
Computes Brent realized volatility and classifies daily vol regime.
Writes to volatility_log table in gulf_data.db.

Logic:
    1. Load all Brent daily prices from price_data
    2. Compute daily log returns: ln(Pt / Pt-1)
    3. 20-day rolling std of returns → annualise × √252 → expressed as %
    4. 90-day rolling average of annualised vol (baseline)
    5. vol_ratio = realized_vol_20d_annualized / vol_90d_avg
    6. Percentile-based regime over full history:
           LOW    → below 33rd percentile
           MEDIUM → 33rd–66th percentile
           HIGH   → above 66th percentile
    7. shock_flag = 1 when vol_ratio ≥ 2.0
    8. INSERT OR REPLACE all rows into volatility_log
    9. Print regime distribution + latest state on every run

Expected output:
    ~590 rows (2024-01-02 to today minus 20-day warmup)
    HIGH regime populated during Gulf crisis period (Feb–May 2026)
    Multiple shock days in crisis window

Run:
    python models/volatility_tracker.py
"""

import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime
import os

# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'processed', 'gulf_data.db'
)

VOL_WINDOW        = 20    # rolling window for realized vol (trading days)
BASELINE_WINDOW   = 90    # rolling window for baseline average (trading days)
ANNUALISE_FACTOR  = np.sqrt(252)
SHOCK_MULTIPLIER  = 2.0   # vol_ratio threshold to set shock_flag = 1

# Percentile thresholds for regime classification
# Computed fresh from full history on every run — adapts as data grows
LOW_PCT    = 33
HIGH_PCT   = 66


# ── Data loading ──────────────────────────────────────────────────────────────

def load_brent_prices(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Load all Brent daily closing prices from price_data.
    Returns DataFrame indexed by date, single column 'price'.
    Raises ValueError if no data found — prices_ingestor.py must run first.
    """
    df = pd.read_sql(
        """
        SELECT date, price
        FROM   price_data
        WHERE  ticker IN ('Brent', 'BRENT')
        ORDER  BY date ASC
        """,
        conn,
        parse_dates=['date'],
    )

    if df.empty:
        raise ValueError(
            "No Brent price data found in price_data (tried ticker IN ('Brent', 'BRENT')). "
            "Run ingestion/prices_ingestor.py first."
        )

    df = df.set_index('date').sort_index()
    df = df[~df.index.duplicated(keep='last')]   # remove any accidental duplicates

    print(
        f"  [OK] Loaded {len(df):,} Brent price rows "
        f"({df.index[0].date()} → {df.index[-1].date()})"
    )
    return df


# ── Volatility computation ────────────────────────────────────────────────────

def compute_volatility(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute rolling realized volatility metrics on a Brent price DataFrame.

    Adds columns:
        log_return                  — daily log return
        realized_vol_20d            — 20-day rolling std of log returns (raw)
        realized_vol_20d_annualized — annualised, expressed as percentage
        vol_90d_avg                 — 90-day rolling mean of annualised vol
        vol_ratio                   — realized_vol_20d_annualized / vol_90d_avg
        vol_regime                  — LOW / MEDIUM / HIGH (percentile-based)
        shock_flag                  — 1 if vol_ratio ≥ SHOCK_MULTIPLIER, else 0

    Drops rows where realized_vol_20d cannot be computed (first VOL_WINDOW days).
    """

    # Step 1 — Daily log returns
    df['log_return'] = np.log(df['price'] / df['price'].shift(1))

    # Step 2 — 20-day rolling std → annualise → express as %
    df['realized_vol_20d'] = df['log_return'].rolling(VOL_WINDOW).std()
    df['realized_vol_20d_annualized'] = df['realized_vol_20d'] * ANNUALISE_FACTOR * 100

    # Step 3 — 90-day rolling average of annualised vol (the baseline)
    df['vol_90d_avg'] = df['realized_vol_20d_annualized'].rolling(BASELINE_WINDOW).mean()

    # Step 4 — Vol ratio: current vol vs recent baseline
    # Avoid division by zero — if baseline is 0 (impossible in practice) set ratio to NaN
    df['vol_ratio'] = np.where(
        df['vol_90d_avg'] > 0,
        df['realized_vol_20d_annualized'] / df['vol_90d_avg'],
        np.nan
    )

    # Step 5 — Percentile-based regime thresholds over full computed history
    # Use only rows where vol is defined (after warmup period)
    valid_vol = df['realized_vol_20d_annualized'].dropna()

    if len(valid_vol) < VOL_WINDOW:
        raise ValueError(
            f"Not enough Brent data to compute volatility. "
            f"Need at least {VOL_WINDOW} rows, found {len(valid_vol)}."
        )

    low_threshold  = np.percentile(valid_vol, LOW_PCT)
    high_threshold = np.percentile(valid_vol, HIGH_PCT)

    print(f"  [OK] Vol thresholds (percentile-based, full history):")
    print(f"       LOW  < {low_threshold:.1f}%  (below {LOW_PCT}th pct)")
    print(f"       MEDIUM {low_threshold:.1f}% – {high_threshold:.1f}%")
    print(f"       HIGH > {high_threshold:.1f}%  (above {HIGH_PCT}th pct)")

    # Step 6 — Classify each row
    def classify(vol):
        if pd.isna(vol):
            return None
        if vol < low_threshold:
            return 'LOW'
        elif vol < high_threshold:
            return 'MEDIUM'
        else:
            return 'HIGH'

    df['vol_regime'] = df['realized_vol_20d_annualized'].apply(classify)

    # Step 7 — Shock flag
    df['shock_flag'] = (
        df['realized_vol_20d_annualized'].notna() &
        df['vol_90d_avg'].notna() &
        (df['vol_ratio'] >= SHOCK_MULTIPLIER)
    ).astype(int)

    # Drop rows where vol cannot be computed (first VOL_WINDOW trading days)
    df = df.dropna(subset=['realized_vol_20d_annualized'])

    # ── Summary stats ────────────────────────────────────────────────────────
    print(f"\n  [OK] Computed vol for {len(df):,} dates")
    print(f"\n  Regime distribution:")
    regime_counts = df['vol_regime'].value_counts()
    for regime in ['HIGH', 'MEDIUM', 'LOW']:
        count = regime_counts.get(regime, 0)
        pct   = 100 * count / len(df)
        print(f"       {regime:<8} {count:>4} days  ({pct:.1f}%)")

    shock_count = df['shock_flag'].sum()
    print(f"\n  Shock periods: {shock_count} days flagged (vol_ratio ≥ {SHOCK_MULTIPLIER}×)")

    if shock_count == 0:
        print("  [WARNING] No shock days found — verify Brent backfill covers crisis period")

    return df


# ── Database write ────────────────────────────────────────────────────────────

def write_volatility_log(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """
    Write computed volatility metrics to volatility_log.
    Uses INSERT OR REPLACE — idempotent, safe to re-run daily.
    Returns number of rows written.
    """
    rows = []
    for date, row in df.iterrows():

        # vol_90d_avg and vol_ratio are NaN for the first ~90 rows
        # Store as NULL — downstream queries must handle this
        vol_90d_avg = float(row['vol_90d_avg']) if not pd.isna(row['vol_90d_avg']) else None
        vol_ratio   = float(row['vol_ratio'])   if not pd.isna(row['vol_ratio'])   else None

        rows.append({
            'date':                        date.strftime('%Y-%m-%d'),
            'brent_price':                 round(float(row['price']), 4),
            'daily_return':                round(float(row['log_return']), 6) if not pd.isna(row['log_return']) else None,
            'realized_vol_20d':            round(float(row['realized_vol_20d_annualized']), 4),
            'realized_vol_20d_annualized': round(float(row['realized_vol_20d_annualized']), 4),
            'vol_90d_avg':                 round(vol_90d_avg, 4) if vol_90d_avg is not None else None,
            'vol_ratio':                   round(vol_ratio, 4)   if vol_ratio   is not None else None,
            'vol_regime':                  row['vol_regime'],
            'shock_flag':                  int(row['shock_flag']),
        })

    conn.executemany(
        """
        INSERT OR REPLACE INTO volatility_log
            (date, brent_price, daily_return,
             realized_vol_20d, realized_vol_20d_annualized,
             vol_90d_avg, vol_ratio, vol_regime, shock_flag)
        VALUES
            (:date, :brent_price, :daily_return,
             :realized_vol_20d, :realized_vol_20d_annualized,
             :vol_90d_avg, :vol_ratio, :vol_regime, :shock_flag)
        """,
        rows,
    )
    conn.commit()

    print(f"\n  [OK] {len(rows):,} rows written to volatility_log")
    return len(rows)


# ── Summary print ─────────────────────────────────────────────────────────────

def print_summary(conn: sqlite3.Connection) -> None:
    """Print the latest volatility state from the database after writing."""

    latest = conn.execute(
        """
        SELECT date, brent_price, realized_vol_20d_annualized,
               vol_90d_avg, vol_ratio, vol_regime, shock_flag
        FROM   volatility_log
        ORDER  BY date DESC
        LIMIT  1
        """
    ).fetchone()

    if not latest:
        print("  [WARNING] volatility_log is empty after write — investigate")
        return

    date, price, vol, avg, ratio, regime, shock = latest

    shock_label = "⚠️  SHOCK PERIOD" if shock else "Normal"
    ratio_str   = f"{ratio:.2f}×" if ratio is not None else "N/A"
    avg_str     = f"{avg:.1f}%" if avg is not None else "N/A"

    print(f"\n  Latest vol state ({date}):")
    print(f"    Brent price:            ${price:.2f}/bbl")
    print(f"    Realized vol (20d ann): {vol:.1f}%")
    print(f"    90-day vol baseline:    {avg_str}")
    print(f"    Vol ratio:              {ratio_str}")
    print(f"    Regime:                 {regime}")
    print(f"    Status:                 {shock_label}")

    # Also show the crisis window snapshot if data covers it
    crisis_rows = conn.execute(
        """
        SELECT COUNT(*) as n,
               SUM(shock_flag) as shocks,
               AVG(realized_vol_20d_annualized) as avg_vol
        FROM   volatility_log
        WHERE  date BETWEEN '2026-02-01' AND '2026-05-25'
        """
    ).fetchone()

    if crisis_rows and crisis_rows[0] > 0:
        n, shocks, avg_crisis_vol = crisis_rows
        print(f"\n  Gulf crisis window (Feb–May 2026):")
        print(f"    Trading days covered:   {n}")
        print(f"    Shock days:             {shocks}")
        print(f"    Avg annualised vol:     {avg_crisis_vol:.1f}%")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print(f"VOLATILITY TRACKER — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    print(f"\n[1/4] Connecting to database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. "
            "Check DB_PATH or run from project root."
        )

    conn = sqlite3.connect(DB_PATH)

    try:
        print("\n[2/4] Loading Brent prices...")
        brent_df = load_brent_prices(conn)

        print("\n[3/4] Computing volatility metrics...")
        vol_df = compute_volatility(brent_df)

        print("\n[4/4] Writing to volatility_log...")
        write_volatility_log(conn, vol_df)

        print_summary(conn)

    finally:
        conn.close()

    print(f"\n{'='*60}")
    print(f"[DONE] volatility_tracker.py complete")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()