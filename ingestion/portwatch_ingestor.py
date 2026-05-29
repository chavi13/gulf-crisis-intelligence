"""
ingestion/portwatch_ingestor.py

Replaces: load_kaggle_ais.py
Source:   IMF PortWatch — Daily Chokepoints Data (ArcGIS FeatureServer)
Targets:  transit_events       (Strait of Hormuz — chokepoint6)
          suez_transit_events  (Suez Canal       — chokepoint1)

What it does:
  - Calls the PortWatch ArcGIS API for both chokepoints
  - Paginates through all records (1000 rows per call)
  - Writes all vessel type counts + tonnage into the appropriate table
  - On subsequent runs: only inserts rows that don't already exist (INSERT OR IGNORE)
  - Runs automatically via run_all.py daily scheduler

Data returned per row:
  date, n_tanker, n_container, n_dry_bulk, n_roro, n_general_cargo,
  n_total, capacity_tanker, capacity_total

Coverage: Jan 1 2019 → ~4 days ago (updated every Tuesday 9 AM ET)

To add a third strait in future: add one entry to CHOKEPOINTS dict only.
"""

import requests
import sqlite3
import os
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed', 'gulf_data.db')

# ArcGIS FeatureServer endpoint — confirmed from REST Services Directory
API_URL = (
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest"
    "/services/Daily_Chokepoints_Data/FeatureServer/0/query"
)

# Fields we want — matches transit_events schema exactly
FIELDS = (
    "date,"
    "n_tanker,"
    "n_container,"
    "n_dry_bulk,"
    "n_roro,"
    "n_general_cargo,"
    "n_total,"
    "capacity_tanker,"
    "capacity"          # this is capacity_total in the API (alias: capacity)
)

BATCH_SIZE = 1000       # ArcGIS max records per call

# ── Chokepoint registry ───────────────────────────────────────────────────────
# To add a new strait: add one entry here. No other code changes needed.
#   chokepoint_id : the portid value used in the PortWatch API WHERE clause
#   display_name  : used in print statements only
#   table         : the DB table to write into

CHOKEPOINTS = {
    "hormuz": {
        "chokepoint_id": "chokepoint6",
        "display_name" : "Strait of Hormuz",
        "table"        : "transit_events",
    },
    "suez": {
        "chokepoint_id": "chokepoint1",
        "display_name" : "Suez Canal",
        "table"        : "suez_transit_events",
    },
}


# ── Step 1: Fetch all records for one chokepoint from PortWatch ───────────────

def fetch_portwatch_data(chokepoint_id, display_name):
    """
    Fetches all daily transit records for the given chokepoint.
    Paginates in batches of 1000 until all records are retrieved.
    Returns a list of dicts, one per day.
    """
    all_records = []
    offset = 0

    print(f"[PortWatch] Starting fetch for {display_name} ({chokepoint_id})...")

    while True:
        params = {
            "where"           : f"portid='{chokepoint_id}'",
            "outFields"       : FIELDS,
            "f"               : "json",
            "resultOffset"    : offset,
            "resultRecordCount": BATCH_SIZE,
            "orderByFields"   : "date ASC",   # oldest first
        }

        try:
            response = requests.get(API_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"[PortWatch] ERROR — API call failed at offset {offset}: {e}")
            break

        # Check for API-level errors
        if "error" in data:
            print(f"[PortWatch] ERROR — API returned error: {data['error']}")
            break

        features = data.get("features", [])
        if not features:
            # No more records
            break

        for feature in features:
            all_records.append(feature["attributes"])

        print(f"[PortWatch] [{display_name}] Fetched {len(all_records)} records so far...")

        # If we got fewer than BATCH_SIZE, we've reached the end
        if len(features) < BATCH_SIZE:
            break

        offset += BATCH_SIZE

    print(f"[PortWatch] [{display_name}] Total records fetched: {len(all_records)}")
    return all_records


# ── Step 2: Parse a raw API record into a clean dict ─────────────────────────

def parse_record(record):
    """
    Converts one raw API attributes dict into a clean dict
    matching the transit_events schema.

    The API returns date as milliseconds since epoch (Unix timestamp in ms).
    We convert this to YYYY-MM-DD string.
    """
    # Convert date → YYYY-MM-DD string
    # API may return either:
    #   - a string already in YYYY-MM-DD format  e.g. "2026-05-10"
    #   - epoch milliseconds as an integer        e.g. 1746835200000
    date_raw = record.get("date")
    if date_raw is None:
        return None

    if isinstance(date_raw, str):
        # Already a date string — take the first 10 chars (strip any time part)
        date_str = date_raw[:10]
    else:
        # Epoch milliseconds → YYYY-MM-DD
        date_str = datetime.fromtimestamp(
            date_raw / 1000, tz=timezone.utc
        ).strftime("%Y-%m-%d")

    return {
        "date"            : date_str,
        "n_tanker"        : record.get("n_tanker"),
        "n_container"     : record.get("n_container"),
        "n_dry_bulk"      : record.get("n_dry_bulk"),
        "n_roro"          : record.get("n_roro"),
        "n_general_cargo" : record.get("n_general_cargo"),
        "n_total"         : record.get("n_total"),
        "capacity_tanker" : record.get("capacity_tanker"),
        "capacity_total"  : record.get("capacity"),   # API field name is 'capacity'
    }


# ── Step 3: Write records to transit_events ───────────────────────────────────

def write_to_db(records, table_name):
    """
    Inserts records into the given table (transit_events or suez_transit_events).
    Uses INSERT OR IGNORE so re-runs are safe — existing dates are skipped.
    (date is PRIMARY KEY in both tables — duplicates are silently ignored)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    inserted = 0
    skipped  = 0

    for record in records:
        parsed = parse_record(record)
        if parsed is None:
            skipped += 1
            continue

        try:
            cursor.execute(f"""
                INSERT OR IGNORE INTO {table_name} (
                    date,
                    n_tanker,
                    n_container,
                    n_dry_bulk,
                    n_roro,
                    n_general_cargo,
                    n_total,
                    capacity_tanker,
                    capacity_total
                ) VALUES (
                    :date,
                    :n_tanker,
                    :n_container,
                    :n_dry_bulk,
                    :n_roro,
                    :n_general_cargo,
                    :n_total,
                    :capacity_tanker,
                    :capacity_total
                )
            """, parsed)

            if cursor.rowcount == 1:
                inserted += 1
            else:
                skipped += 1   # date already exists — PRIMARY KEY conflict

        except sqlite3.Error as e:
            print(f"[PortWatch] DB ERROR on {parsed.get('date')}: {e}")

    conn.commit()
    conn.close()

    return inserted, skipped


# ── Step 4: Verify what we loaded ─────────────────────────────────────────────

def verify_load(table_name, display_name):
    """
    Prints a quick summary of what is now in the given table.
    Checks row count, date range, and a sample of the latest rows.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    total = cursor.fetchone()[0]

    cursor.execute(f"SELECT MIN(date), MAX(date) FROM {table_name}")
    min_date, max_date = cursor.fetchone()

    cursor.execute(f"""
        SELECT date, n_tanker, n_container, n_dry_bulk, n_total, capacity_tanker
        FROM {table_name}
        ORDER BY date DESC
        LIMIT 5
    """)
    latest = cursor.fetchall()

    conn.close()

    print(f"\n[PortWatch] ── Verification: {display_name} ─────────────")
    print(f"  Total rows : {total}")
    print(f"  Date range : {min_date} → {max_date}")
    print(f"  Latest 5 rows (date | tanker | container | dry_bulk | total | tanker_capacity):")
    for row in latest:
        print(f"    {row[0]} | {row[1]:>4} tankers | {row[2]:>4} containers | "
              f"{row[3]:>4} dry_bulk | {row[4]:>4} total | {row[5]:>10} TEU")
    print(f"[PortWatch] ───────────────────────────────────────────\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n[PortWatch] {'='*50}")
    print(f"[PortWatch] Starting PortWatch ingestor")
    print(f"[PortWatch] Source  : IMF PortWatch ArcGIS API")
    print(f"[PortWatch] Chokepoints : {len(CHOKEPOINTS)} ({', '.join(c['display_name'] for c in CHOKEPOINTS.values())})")
    print(f"[PortWatch] Target  : {DB_PATH}")
    print(f"[PortWatch] {'='*50}\n")

    for key, config in CHOKEPOINTS.items():
        chokepoint_id = config["chokepoint_id"]
        display_name  = config["display_name"]
        table         = config["table"]

        print(f"[PortWatch] ── {display_name} ({chokepoint_id}) → {table}")

        # 1. Fetch from API
        raw_records = fetch_portwatch_data(chokepoint_id, display_name)

        if not raw_records:
            print(f"[PortWatch] No records returned for {display_name}. Skipping.")
            continue

        # 2. Write to DB
        inserted, skipped = write_to_db(raw_records, table)
        print(f"[PortWatch] Inserted : {inserted} new rows")
        print(f"[PortWatch] Skipped  : {skipped} (already exist or null date)")

        # 3. Verify
        verify_load(table, display_name)

    print("[PortWatch] Done.")


if __name__ == "__main__":
    main()