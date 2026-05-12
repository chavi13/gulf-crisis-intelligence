import requests
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import os
import re

load_dotenv()
API_KEY = os.getenv("EIA_API_KEY")
DB_PATH = "data/processed/gulf_data.db"

# ─────────────────────────────────────────────
# FIX 2 — Terminal name standardization mapping
# Converts all known EIA name variants to a
# single canonical name per physical terminal.
# Verified against EIA LNG facilities map
# (January 2026) and primary source data.
# ─────────────────────────────────────────────
TERMINAL_NAME_MAP = {
    # Typo variant — missing space after comma
    "Corpus Christi,TX":                "Corpus Christi, TX",
    # Venture Global facility — duoarea confirms
    # this is Calcasieu Pass, not Cameron LNG
    "Cameron (Calcasieu Pass), LA":     "Calcasieu Pass, LA",
    # Name variant — state written in full
    "Plaquemines, Louisiana":           "Plaquemines, LA",
}

# ─────────────────────────────────────────────
# FIX 3 — Terminals to exclude entirely
# These are either non-US facilities or
# small-scale local distribution terminals,
# confirmed via EIA duoarea codes (Z00 suffix)
# and absence from EIA LNG facilities map.
# They are not intercontinental export terminals
# and do not belong in a utilization calculation.
# ─────────────────────────────────────────────
EXCLUDED_TERMINALS = {
    "Altamira, Tamaulipas",     # Mexico — outside US export scope
    "Fort Lauderdale, FL",      # EIA duoarea YFLF-Z00 — local distribution
    "Niagara Falls, NY",        # EIA duoarea Z00 — local distribution
    "West Palm Beach, Florida", # EIA duoarea Z00 — local distribution
}


def fetch_lng_exports():
    all_rows = []
    offset = 0      # where API starts reading
    length = 500    # how many rows per request

    while True:     # keep asking API until there is no more data
        url = (
            "https://api.eia.gov/v2/natural-gas/move/poe2/data/"
            f"?api_key={API_KEY}"
            "&frequency=monthly"
            "&data[0]=value"
            "&start=2025-01"
            "&end=2026-05"          # FIX 4 — extended to capture crisis period
            "&sort[0][column]=period"
            "&sort[0][direction]=desc"
            f"&offset={offset}"
            f"&length={length}"
        )
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        rows = data.get("response", {}).get("data", [])

        if not rows:
            break

        all_rows.extend(rows)
        total = int(data.get("response", {}).get("total", 0))
        offset += length

        if offset >= total:
            break

    print(f"Total rows fetched: {len(all_rows)}")
    return all_rows


def extract_terminal(series_description):
    match = re.match(r"^(.+?)\s+Exports", series_description)
    if match:
        terminal = match.group(1).strip()
        terminal = terminal.replace("Liquefied Natural Gas", "").strip()
        terminal = terminal.replace(",  ", ", ").strip()
        return terminal
    return "unknown"


def standardize_terminal(terminal):
    # FIX 2 — Apply canonical name mapping.
    # If the terminal name is a known variant,
    # return the canonical version.
    # If it is not in the map, return as-is —
    # canonical names pass through unchanged.
    return TERMINAL_NAME_MAP.get(terminal, terminal)


def store_lng_exports(rows):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    fetched_at = datetime.now().isoformat()

    # FIX 1 — Removed: cursor.execute("DELETE FROM lng_export_volumes")
    # The DELETE + re-insert pattern caused duplicates when the script
    # ran multiple times and wiped valid data on every execution.
    # Replaced with INSERT OR REPLACE (UPSERT) below, which updates
    # existing rows and inserts new ones without creating duplicates.
    #
    # IMPORTANT: This requires a UNIQUE constraint on (date, terminal)
    # in the database schema. If that constraint does not exist,
    # run setupdb.py first to recreate the table with the constraint.

    inserted = 0
    skipped_process = 0
    skipped_units = 0
    skipped_aggregate = 0
    skipped_excluded = 0
    skipped_null = 0
    skipped_destination = 0  # FIX 5 — destination-specific rows

    for row in rows:
        period      = row.get("period")
        duoarea     = row.get("duoarea", "")
        process     = row.get("process-name", "")
        value       = row.get("value")
        units       = row.get("units", "")
        series_desc = row.get("series-description", "")

        # Only LNG exports
        if process != "Liquefied Natural Gas Exports":
            skipped_process += 1
            continue
        # Only volume rows
        if units != "MMCF":
            skipped_units += 1
            continue
        # Skip aggregate US total rows
        if duoarea == "NUS-Z00":
            skipped_aggregate += 1
            continue
        # Skip aggregate country-level rows
        if duoarea.startswith("NUS-"):
            skipped_aggregate += 1
            continue
        # Skip null or zero values
        if value is None or value == "0":
            skipped_null += 1
            continue

        # FIX 5 — Skip destination-specific rows, keep only terminal totals.
        # The EIA API returns one row per terminal-destination pair PLUS one
        # aggregate row per terminal with no destination.
        # Example destination row: "Sabine Pass, LA Liquefied Natural Gas Exports to Egypt"
        # Example aggregate row:   "Sabine Pass, LA Liquefied Natural Gas Exports"
        # We only want the aggregate row — it contains total terminal throughput.
        # Destination rows contain " to " in the description. Aggregate rows do not.
        if " to " in series_desc.lower() and "all countries" not in series_desc.lower():
            skipped_destination += 1
            continue

        try:
            raw_terminal = extract_terminal(series_desc)

            # FIX 2 — Standardize terminal name before storing
            terminal = standardize_terminal(raw_terminal)

            # FIX 3 — Skip excluded non-export terminals
            if terminal in EXCLUDED_TERMINALS:
                skipped_excluded += 1
                continue

            volume_bcf = float(value) / 1000

            # FIX 1 — INSERT OR REPLACE replaces DELETE + INSERT.
            # If a row with the same date and terminal already exists
            # (enforced by UNIQUE constraint), it is updated in place.
            # If it does not exist, it is inserted as a new row.
            # This means running the ingestor daily never creates duplicates.
            cursor.execute("""
                INSERT OR REPLACE INTO lng_export_volumes
                (date, terminal, volume_bcf, fetched_at)
                VALUES (?, ?, ?, ?)
            """, (period, terminal, volume_bcf, fetched_at))
            inserted += 1

        except Exception as e:
            print(f"  Row error: {e} — row: {row}")

    conn.commit()
    conn.close()

    # Detailed summary so you can verify each filter is working
    print(f"\n  Inserted/updated: {inserted}")
    print(f"  Skipped (wrong process): {skipped_process}")
    print(f"  Skipped (wrong units):   {skipped_units}")
    print(f"  Skipped (aggregate row): {skipped_aggregate}")
    print(f"  Skipped (excluded terminal): {skipped_excluded}")
    print(f"  Skipped (null/zero value):   {skipped_null}")
    print(f"  Skipped (destination rows):  {skipped_destination}")

    return inserted


if __name__ == "__main__":
    print("Fetching EIA LNG export data...")
    try:
        rows = fetch_lng_exports()
        n = store_lng_exports(rows)
        print(f"\nStored/updated {n} rows in lng_export_volumes")

        import pandas as pd
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("""
            SELECT date, terminal, volume_bcf
            FROM lng_export_volumes
            ORDER BY date DESC, volume_bcf DESC
            LIMIT 20
        """, conn)
        conn.close()
        print("\nMost recent LNG exports by terminal:")
        print(df.to_string(index=False))

        # Verify no duplicates remain
        conn = sqlite3.connect(DB_PATH)
        dup_df = pd.read_sql("""
            SELECT date, terminal, COUNT(*) as count
            FROM lng_export_volumes
            GROUP BY date, terminal
            HAVING COUNT(*) > 1
        """, conn)
        conn.close()
        if dup_df.empty:
            print("\nDuplicate check: PASSED — no duplicates found")
        else:
            print(f"\nDuplicate check: FAILED — {len(dup_df)} duplicate groups found")
            print(dup_df.to_string(index=False))

    except Exception as e:
        print(f"ERROR: {e}")