# ingestion/load_kaggle_ais.py
# Loads Kaggle Hormuz crisis CSV into transit_events table
# Computes 30-day rolling baseline and z-score from daily_ship_transits

import sqlite3
import pandas as pd
import os

CSV_PATH = os.path.join(os.path.dirname(__file__), "../data/raw/strait_of_hormuz_shipping_disruption_2026 (1).csv")
DB_PATH  = os.path.join(os.path.dirname(__file__), "../data/processed/gulf_data.db")

def load():
    # ── Load CSV ──────────────────────────────────────────────────────────────
    df = pd.read_csv(CSV_PATH)
    print(f"Loaded {len(df)} rows from CSV")

    # ── Keep only columns we need ─────────────────────────────────────────────
    df = df[["date", "daily_ship_transits"]].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

    # ── Compute 30-day rolling baseline (pre-crisis average) ──────────────────
    # Use only pre-crisis rows (before Feb 28) to build the baseline
    pre_crisis = df[df["date"] < "2026-02-28"]["daily_ship_transits"]
    baseline_mean = pre_crisis.mean()
    baseline_std  = pre_crisis.std()

    print(f"Pre-crisis baseline mean: {baseline_mean:.1f} transits/day")
    print(f"Pre-crisis baseline std:  {baseline_std:.1f}")

    df["baseline_30d"] = round(baseline_mean, 2)

    # ── Compute z-score ───────────────────────────────────────────────────────
    # z = (current - mean) / std
    # Negative z-score = below baseline = crisis signal
    df["z_score"] = ((df["daily_ship_transits"] - baseline_mean) / baseline_std).round(4)

    # ── Anomaly flag: True if z-score below -1.5 ─────────────────────────────
    df["anomaly_flag"] = (df["z_score"] < -1.5).astype(int)
    df["transit_count"] = df["daily_ship_transits"]

    # ── Insert into database ──────────────────────────────────────────────────
    conn = sqlite3.connect(DB_PATH)

    # Clear existing rows to avoid duplicates
    conn.execute("DELETE FROM transit_events")
    conn.commit()

    inserted = 0
    for _, row in df.iterrows():
        conn.execute(
            """
            INSERT INTO transit_events
                (date, transit_count, baseline_30d, z_score, anomaly_flag)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                row["date"],
                int(row["transit_count"]),
                float(row["baseline_30d"]),
                float(row["z_score"]),
                int(row["anomaly_flag"]),
            )
        )
        inserted += 1

    conn.commit()
    conn.close()
    print(f"Inserted {inserted} rows into transit_events")

    # ── Quick sanity check ────────────────────────────────────────────────────
    conn = sqlite3.connect(DB_PATH)
    crisis = conn.execute(
        "SELECT date, transit_count, z_score, anomaly_flag FROM transit_events WHERE date = '2026-03-04'"
    ).fetchone()
    print(f"\nSanity check — March 4 (crisis day):")
    print(f"  Date: {crisis[0]}")
    print(f"  Transits: {crisis[1]}")
    print(f"  Z-score: {crisis[2]}")
    print(f"  Anomaly flag: {crisis[3]}")
    conn.close()

if __name__ == "__main__":
    load()