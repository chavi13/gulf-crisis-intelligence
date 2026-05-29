"""
shock_detector.py
Utility module — reads volatility_log and surfaces shock/regime signals.
All other modules import from here. Nothing here does new computation —
it only reads what volatility_tracker.py has already written.
"""

import sqlite3
import pandas as pd

DB_PATH = 'data/processed/gulf_data.db'


def get_current_vol_state():
    """
    Returns the most recent volatility reading as a clean dictionary.
    Call this anywhere you need to know what the market is doing right now.
    """
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("""
        SELECT date, realized_vol_20d, vol_90d_avg,
               vol_ratio, vol_regime, shock_flag
        FROM volatility_log
        ORDER BY date DESC
        LIMIT 1
    """).fetchone()
    conn.close()

    if not row:
        return None

    return {
        'date':        row[0],
        'vol_20d':     row[1],
        'vol_90d_avg': row[2],
        'vol_ratio':   row[3],
        'regime':      row[4],
        'shock_flag':  row[5],
        'in_shock':    row[5] == 1
    }


def get_shock_days(lookback_days=30):
    """
    Returns count of shock days in the last N calendar days.
    """
    conn = sqlite3.connect(DB_PATH)
    result = conn.execute("""
        SELECT COUNT(*)
        FROM volatility_log
        WHERE shock_flag = 1
          AND date >= date('now', ?)
    """, (f'-{lookback_days} days',)).fetchone()
    conn.close()
    return result[0] if result else 0


def get_vol_history(days=180):
    """
    Returns DataFrame of recent vol history for charting.
    """
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT date, realized_vol_20d, vol_90d_avg,
               vol_ratio, vol_regime, shock_flag
        FROM volatility_log
        ORDER BY date ASC
    """, conn, parse_dates=['date'])
    conn.close()
    return df.tail(days)


def classify_period(start_date, end_date):
    """
    Given a date range, returns shock activity summary.
    is_crisis = True when more than 20% of days were shock days.
    """
    conn = sqlite3.connect(DB_PATH)
    result = conn.execute("""
        SELECT
            COUNT(*)              as total_days,
            SUM(shock_flag)       as shock_days,
            AVG(realized_vol_20d) as avg_vol,
            MAX(realized_vol_20d) as peak_vol
        FROM volatility_log
        WHERE date BETWEEN ? AND ?
    """, (start_date, end_date)).fetchone()
    conn.close()

    total, shocks, avg_vol, peak_vol = result
    shock_pct = (shocks / total * 100) if total else 0

    return {
        'total_days': total,
        'shock_days': shocks,
        'shock_pct':  round(shock_pct, 1),
        'avg_vol':    round(avg_vol, 1) if avg_vol else None,
        'peak_vol':   round(peak_vol, 1) if peak_vol else None,
        'is_crisis':  shock_pct >= 20
    }


if __name__ == '__main__':
    print("\n=== Current vol state ===")
    state = get_current_vol_state()
    for k, v in state.items():
        print(f"  {k}: {v}")

    print(f"\n=== Shock days (last 30d) ===")
    print(f"  {get_shock_days(30)} shock days")

    print(f"\n=== Gulf crisis window ===")
    crisis = classify_period('2026-02-01', '2026-05-22')
    for k, v in crisis.items():
        print(f"  {k}: {v}")