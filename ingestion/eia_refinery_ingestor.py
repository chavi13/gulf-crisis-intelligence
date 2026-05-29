"""
eia_refinery_ingestor.py
========================
Fetches 4 EIA weekly data series and writes them to the `refinery_data` table.

Series fetched:
    WPULEUS3  — US Refinery Utilization Rate (%)
    WCESTUS1  — US Crude Oil Stocks excl. SPR (thousand barrels)
    WGTSTUS1  — US Gasoline Stocks (thousand barrels)
    WDISTUS1  — US Distillate Stocks (thousand barrels)

Two API calls are required because EIA v2 splits these across different endpoints:
    Call 1 → petroleum/pnp/wiup/data/   → WPULEUS3
    Call 2 → petroleum/stoc/wstk/data/  → WCESTUS1, WGTSTUS1, WDISTUS1

This was confirmed during Task 4 Phase 1 validation. Using a single endpoint
for all 4 series returns no data for the inventory series — silently.

Usage:
    python ingestion/eia_refinery_ingestor.py

Safe to re-run — uses INSERT OR REPLACE. Will not create duplicates.
"""

import sqlite3
import requests
from datetime import datetime, date

# ── Config ────────────────────────────────────────────────────────────────────

EIA_API_KEY = "jHPRrb1SSrD0ZtoeKAXhePOWjyv0sedKz4XP0sIV"
BASE_URL     = "https://api.eia.gov/v2/"
DB_PATH      = "data/processed/gulf_data.db"
START_DATE   = "2006-01-01"   # 2.5 years of history — matches backfill from Task 3

# ── Series definition ─────────────────────────────────────────────────────────
#
# Structure:
#   series_id → (endpoint_path, series_name, unit)
#
# IMPORTANT: WPULEUS3 is on a DIFFERENT endpoint to the three stock series.
# Do not merge these into one call — the wiup endpoint will return nothing
# for WCESTUS1, WGTSTUS1, WDISTUS1, and vice versa.

SERIES = {
    # Utilization endpoint
    "WPULEUS3": (
        "petroleum/pnp/wiup/data/",
        "Refinery_Utilization_Rate",
        "%"
    ),
    # Stocks endpoint — all three live here
    "WCESTUS1": (
        "petroleum/stoc/wstk/data/",
        "US_Crude_Stocks_ExSPR",
        "MBBL"
    ),
    "WGTSTUS1": (
        "petroleum/stoc/wstk/data/",
        "US_Gasoline_Stocks",
        "MBBL"
    ),
    "WDISTUS1": (
        "petroleum/stoc/wstk/data/",
        "US_Distillate_Stocks",
        "MBBL"
    ),
}


# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_series(series_id: str, endpoint: str, series_name: str, unit: str) -> list[dict]:
    """
    Fetch one EIA weekly series from the given endpoint.

    Returns a list of dicts ready for INSERT into refinery_data:
        { date, series_id, series_name, value, unit }

    Skips rows where value is None or cannot be cast to float — EIA occasionally
    returns null for the most recent week if the data hasn't been published yet.
    """
    url = f"{BASE_URL}{endpoint}"

    params = {
        "api_key":   EIA_API_KEY,
        "frequency": "weekly",
        "data[]":    "value",
        "facets[series][]": series_id,
        "start":     START_DATE,
        "end":       date.today().isoformat(),
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length":    5000,    # EIA max per call; ~130 rows for 2.5 years weekly — well within limit
        "offset":    0,
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Network or HTTP error fetching {series_id}: {e}")
        return []

    payload = resp.json()

    # EIA v2 wraps data in response → data
    raw_rows = payload.get("response", {}).get("data", [])

    if not raw_rows:
        print(f"  [WARN]  {series_id}: API returned 0 rows — check endpoint or series ID")
        return []

    rows = []
    skipped = 0
    for row in raw_rows:
        raw_value = row.get("value")

        # Skip null values — EIA publishes nulls for unpublished periods
        if raw_value is None:
            skipped += 1
            continue

        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            skipped += 1
            continue

        rows.append({
            "date":        row["period"],    # e.g. "2026-05-16"
            "series_id":   series_id,
            "series_name": series_name,
            "value":       value,
            "unit":        unit,
        })

    print(f"  [FETCH] {series_name} ({series_id}): {len(rows)} rows fetched"
          + (f", {skipped} nulls skipped" if skipped else ""))
    return rows


# ── Write ─────────────────────────────────────────────────────────────────────

def write_to_db(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """
    Write rows to refinery_data using INSERT OR REPLACE.

    UNIQUE(date, series_id) is enforced at the table level (setupdb.py).
    INSERT OR REPLACE means this is safe to re-run — existing rows are
    overwritten with the same data, no duplicates accumulate.
    """
    if not rows:
        return 0

    conn.executemany("""
        INSERT OR REPLACE INTO refinery_data
            (date, series_id, series_name, value, unit)
        VALUES
            (:date, :series_id, :series_name, :value, :unit)
    """, rows)
    conn.commit()
    return len(rows)


# ── Validate ──────────────────────────────────────────────────────────────────

def validate(conn: sqlite3.Connection) -> None:
    """
    Print a sanity-check table after writing.

    For each series: row count, date range, average value, min, max.
    These numbers should be checked against known reasonable ranges:
        Refinery_Utilization_Rate : avg ~88–92%,  min ~65%,  max ~97%
        US_Crude_Stocks_ExSPR     : avg ~430,000– 460,000 MBBL
        US_Gasoline_Stocks        : avg ~220,000–250,000 MBBL
        US_Distillate_Stocks      : avg ~100,000–130,000 MBBL
    """
    print("\n  [VALIDATION] refinery_data — summary by series:")
    print(f"  {'Series':<35} {'Rows':>5}  {'From':<12} {'To':<12} {'Avg':>12} {'Min':>12} {'Max':>12}")
    print("  " + "-" * 105)

    summary = conn.execute("""
        SELECT
            series_name,
            COUNT(*)                AS n,
            MIN(date)               AS earliest,
            MAX(date)               AS latest,
            ROUND(AVG(value), 1)    AS avg_val,
            ROUND(MIN(value), 1)    AS min_val,
            ROUND(MAX(value), 1)    AS max_val
        FROM refinery_data
        GROUP BY series_name
        ORDER BY series_name
    """).fetchall()

    if not summary:
        print("  [WARN] No rows found in refinery_data — something went wrong above.")
        return

    for row in summary:
        name, n, earliest, latest, avg, lo, hi = row
        print(f"  {name:<35} {n:>5}  {earliest:<12} {latest:<12} {avg:>12} {lo:>12} {hi:>12}")

    # Duplicate check
    dupes = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT date, series_id, COUNT(*) as cnt
            FROM refinery_data
            GROUP BY date, series_id
            HAVING cnt > 1
        )
    """).fetchone()[0]

    if dupes == 0:
        print("\n  [OK] Duplicate check PASSED — no duplicate (date, series_id) pairs.")
    else:
        print(f"\n  [WARN] {dupes} duplicate (date, series_id) pairs found — investigate.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print(f"eia_refinery_ingestor.py — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    conn = sqlite3.connect(DB_PATH)

    total_written = 0

    for series_id, (endpoint, series_name, unit) in SERIES.items():
        rows = fetch_series(series_id, endpoint, series_name, unit)
        n = write_to_db(conn, rows)
        print(f"  [DB]    {series_name}: {n} rows written")
        total_written += n

    print(f"\n  Total rows written this run: {total_written}")

    validate(conn)

    conn.close()
    print(f"\n{'='*60}")
    print(f"[DONE]")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()