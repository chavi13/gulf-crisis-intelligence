import requests
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import os
import time

load_dotenv()
API_KEY = os.getenv("GIE_API_KEY")
DB_PATH = "data/processed/gulf_data.db"

def fetch_storage(from_date="2020-01-01", to_date=None):
    if to_date is None:
        to_date = datetime.utcnow().strftime("%Y-%m-%d")

    url = "https://agsi.gie.eu/api"
    headers = {"x-key": API_KEY}

    all_rows = []
    page = 1

    while True:
        params = {
            "type": "eu",
            "from": from_date,
            "to": to_date,
            "size": 500,
            "page": page
        }
        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        rows = data.get("data", [])
        total = int(data.get("total", 0))
        last_page = int(data.get("last_page", 1))

        all_rows.extend(rows)
        print(f"  Page {page}/{last_page} — {len(rows)} rows fetched ({len(all_rows)} total)")

        if page >= last_page:
            break

        page += 1
        time.sleep(0.5)  # respectful pause between requests

    print(f"  API reports {total} total rows available")
    return {"data": all_rows}

def store_storage(data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    fetched_at = datetime.utcnow().isoformat()

    rows = data.get("data", [])

    # FIX 1 — Removed plain INSERT, replaced with INSERT OR REPLACE.
    # Previous code inserted every row blindly on every run,
    # causing up to 5 duplicate rows per date per country.
    # INSERT OR REPLACE checks the UNIQUE(date, country) constraint:
    # if a row for that date and country already exists, it updates it.
    # if it does not exist, it inserts it as a new row.
    # This means running the ingestor daily never creates duplicates.

    inserted = 0
    skipped_missing = 0

    for row in rows:
        date    = row.get("gasDayStart")
        pct     = row.get("full")
        storage = row.get("gasInStorage")
        country = row.get("name", "EU")

        # Skip rows missing date or pct_full — these are not usable
        if not date or pct is None:
            skipped_missing += 1
            continue

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO gas_storage_levels
                (date, country, storage_twh, pct_full, fetched_at)
                VALUES (?, ?, ?, ?, ?)
            """, (date, country, storage, float(pct), fetched_at))
            inserted += 1

        except Exception as e:
            print(f"  Row error: {e} — row: {row}")

    conn.commit()
    conn.close()

    # FIX 2 — Detailed summary so you can verify the ingestor
    # is working correctly on every run
    print(f"\n  Inserted/updated: {inserted}")
    print(f"  Skipped (missing date or pct): {skipped_missing}")

    return inserted


if __name__ == "__main__":
    print("Fetching GIE gas storage data...")
    try:
        data = fetch_storage()
        n = store_storage(data)
        print(f"\nStored/updated {n} rows in gas_storage_levels")

        import pandas as pd
        conn = sqlite3.connect(DB_PATH)

        # Show most recent storage levels
        df = pd.read_sql("""
            SELECT date, country, pct_full, storage_twh
            FROM gas_storage_levels
            ORDER BY date DESC
            LIMIT 5
        """, conn)
        print("\nMost recent storage levels:")
        print(df.to_string(index=False))

        # FIX 2 — Duplicate check on every run
        dup_df = pd.read_sql("""
            SELECT date, country, COUNT(*) as count
            FROM gas_storage_levels
            GROUP BY date, country
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