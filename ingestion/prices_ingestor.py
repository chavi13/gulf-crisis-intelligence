import argparse
import yfinance as yf
import sqlite3
from datetime import datetime
import pandas as pd

DB_PATH = "data/processed/gulf_data.db"

# ─────────────────────────────────────────────
# Tickers fetched from yfinance
#
# EXISTING:
# TTF   — Title Transfer Facility (European gas benchmark) $/MMBtu
# BRENT — Brent crude oil $/barrel
# HH    — Henry Hub (US natural gas benchmark) $/MMBtu
# JKM   — Japan Korea Marker (Asian LNG benchmark) $/MMBtu
#
# NEW (Sprint 1 — refined products for crack spread calculation):
# RBOB_Gasoline — US gasoline futures $/gallon
# HeatingOil    — Heating oil / diesel proxy $/gallon
# WTI           — West Texas Intermediate crude $/barrel
#
# ⚠️ UNIT WARNING:
# RBOB_Gasoline and HeatingOil are stored in $/gallon as returned
# by yfinance. To compute crack spreads in $/barrel, multiply by 42.
# This conversion is applied in the crack spread model (Sprint 2),
# not here. Raw prices are always stored as-is.
# ─────────────────────────────────────────────
TICKERS = {
    # Existing — do not modify
    "TTF":            "TTE=F",
    "BRENT":          "BZ=F",
    "HH":             "NG=F",
    "JKM":            "JKM=F",

    # New — refined products
    "RBOB_Gasoline":  "RB=F",
    "HeatingOil":     "HO=F",
    "WTI":            "CL=F",
}

# ─────────────────────────────────────────────
# FIX 3 — Stale data detection threshold
# If the same price repeats for this many consecutive
# trading days, it is flagged as potentially stale.
# yfinance occasionally returns cached/stale data
# for commodity futures, particularly TTF.
# ─────────────────────────────────────────────
STALE_REPEAT_THRESHOLD = 5


def fetch_prices(start="2025-01-01"):
    all_data = []

    for name, ticker in TICKERS.items():
        print(f"  Fetching {name} ({ticker})...")
        try:
            df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
            if df.empty:
                print(f"  WARNING: no data returned for {ticker}")
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            ticker_rows = []
            for date, row in df.iterrows():
                price = round(float(row["Close"]), 4)
                ticker_rows.append({
                    "date":   date.strftime("%Y-%m-%d"),
                    "ticker": name,
                    "price":  price
                })

            # FIX 3 — Stale data validation
            # Check if the same price repeats for STALE_REPEAT_THRESHOLD
            # or more consecutive trading days — signals yfinance
            # returning cached data rather than real market prices
            prices_only = [r["price"] for r in ticker_rows]
            max_streak = 1
            current_streak = 1
            for i in range(1, len(prices_only)):
                if prices_only[i] == prices_only[i - 1]:
                    current_streak += 1
                    max_streak = max(max_streak, current_streak)
                else:
                    current_streak = 1

            if max_streak >= STALE_REPEAT_THRESHOLD:
                print(f"  WARNING: {name} has {max_streak} consecutive identical prices — possible stale data from yfinance")
            else:
                print(f"  {name}: {len(ticker_rows)} trading days fetched, stale check OK (max streak: {max_streak})")

            all_data.extend(ticker_rows)

        except Exception as e:
            print(f"  ERROR fetching {name}: {e}")

    return all_data


def store_prices(rows):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    fetched_at = datetime.now().isoformat()

    # FIX 1 — Removed plain INSERT, replaced with INSERT OR REPLACE.
    # Previous code inserted every row blindly on every run,
    # causing exactly 5 duplicate rows per date per ticker
    # (the script was run 5 times during Phase 1 setup).
    # INSERT OR REPLACE checks the UNIQUE(date, ticker) constraint:
    # if a row for that date and ticker already exists, it updates it.
    # if it does not exist, it inserts it as a new row.
    # This means running the ingestor daily never creates duplicates.

    inserted = 0
    errors = 0

    for row in rows:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO price_data
                (date, ticker, price, fetched_at)
                VALUES (?, ?, ?, ?)
            """, (row["date"], row["ticker"], row["price"], fetched_at))
            inserted += 1
        except Exception as e:
            print(f"  Row error: {e} — row: {row}")
            errors += 1

    conn.commit()
    conn.close()

    print(f"\n  Inserted/updated: {inserted}")
    print(f"  Errors:           {errors}")

    return inserted


if __name__ == "__main__":

    # ─────────────────────────────────────────────
    # Two run modes:
    #   python prices_ingestor.py             → daily mode  (start = 2025-01-01)
    #   python prices_ingestor.py --backfill  → backfill mode (start = 2024-01-01)
    #
    # Daily mode: what run_all.py calls every day. Fetches recent data only.
    # Backfill mode: run ONCE manually to extend history back to 2024.
    #                Safe to re-run — INSERT OR REPLACE prevents duplicates.
    # ─────────────────────────────────────────────
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Fetch from 2024-01-01 instead of 2025-01-01"
    )
    args = parser.parse_args()

    if args.backfill:
        START_DATE = "2006-01-01"
        print(f"Mode: BACKFILL — fetching from {START_DATE}")
    else:
        START_DATE = "2025-01-01"
        print(f"Mode: DAILY — fetching from {START_DATE}")

    print("Fetching price data...")
    rows = fetch_prices(start=START_DATE)
    n = store_prices(rows)
    print(f"\nStored/updated {n} rows in price_data")

    conn = sqlite3.connect(DB_PATH)

    # Show most recent prices per ticker
    df = pd.read_sql("""
        SELECT date, ticker, price
        FROM price_data
        ORDER BY date DESC, ticker
        LIMIT 15
    """, conn)
    print("\nMost recent prices:")
    print(df.to_string(index=False))

    # Show date coverage per ticker
    coverage_df = pd.read_sql("""
        SELECT ticker,
               COUNT(DISTINCT date) as trading_days,
               MIN(date) as earliest,
               MAX(date) as latest
        FROM price_data
        GROUP BY ticker
        ORDER BY ticker
    """, conn)
    print("\nDate coverage by ticker:")
    print(coverage_df.to_string(index=False))

    # Duplicate check on every run
    dup_df = pd.read_sql("""
        SELECT date, ticker, COUNT(*) as count
        FROM price_data
        GROUP BY date, ticker
        HAVING COUNT(*) > 1
    """, conn)
    conn.close()

    if dup_df.empty:
        print("\nDuplicate check: PASSED — no duplicates found")
    else:
        print(f"\nDuplicate check: FAILED — {len(dup_df)} duplicate groups found")
        print(dup_df.to_string(index=False))