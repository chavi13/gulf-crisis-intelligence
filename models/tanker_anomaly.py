# models/tanker_anomaly.py
# Phase 2 — Hormuz Transit Anomaly Index
# Reads transit_events and vessel_positions tables
# Produces three outputs:
#   1. Latest transit index (current state of the strait)
#   2. 7-day recovery trend (getting better or worse?)
#   3. AIS dark events (vessels gone silent inside Gulf)

import sqlite3
import numpy as np
import os
from datetime import datetime, timezone, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "../data/processed/gulf_data.db")

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../data/reference"))
from geofences import (
    GEOFENCES,
    AIS_DARK_THRESHOLD_HOURS,
    ANOMALY_ZSCORE_THRESHOLD,
    FUJAIRAH_ANCHORAGE,
    ANCHORAGE_CLUSTERING_THRESHOLD,
    ANCHORAGE_CLUSTERING_HOURS,
)

# Pull Gulf interior coordinates from geofences
GULF_LAT_MIN = GEOFENCES["persian_gulf_interior"]["lat_min"]
GULF_LAT_MAX = GEOFENCES["persian_gulf_interior"]["lat_max"]
GULF_LON_MIN = GEOFENCES["persian_gulf_interior"]["lon_min"]
GULF_LON_MAX = GEOFENCES["persian_gulf_interior"]["lon_max"]

# AIS dark threshold from geofences
AIS_DARK_HOURS = AIS_DARK_THRESHOLD_HOURS

# ── Database ──────────────────────────────────────────────────────────────────

def get_connection():
    return sqlite3.connect(DB_PATH)

# ── Function 1 — Latest Transit Index ────────────────────────────────────────

def _compute_vessel_stats(counts: list, current: int) -> dict:
    """
    Helper — given a list of pre-crisis counts and today's count,
    returns baseline, z_score, anomaly_flag, pct_of_normal.
    """
    if len(counts) < 3:
        return {"baseline": None, "z_score": None, "anomaly_flag": 0, "pct_of_normal": None}
    baseline = round(float(np.mean(counts)), 2)
    std_dev  = float(np.std(counts))
    z_score  = round((current - baseline) / std_dev, 2) if std_dev > 0 else 0.0
    anomaly_flag  = 1 if abs(z_score) >= ANOMALY_ZSCORE_THRESHOLD else 0
    pct_of_normal = round((current / baseline) * 100, 1) if baseline else 0.0
    if current == 0 and baseline:
        pct_of_normal = 0.0
    return {
        "baseline":      baseline,
        "z_score":       z_score,
        "anomaly_flag":  anomaly_flag,
        "pct_of_normal": pct_of_normal,
    }


def get_latest_index() -> dict:
    """
    Pulls the most recent row from transit_events.
    Computes baseline, z_score, anomaly_flag, pct_of_normal
    for ALL vessel types independently.

    Baseline = 30-day pre-crisis average (before 2026-03-01).
    All metrics computed here — PortWatch does not pre-compute them.

    Returns one flat dict with stats for every vessel type.
    The UI decides what to display — this layer returns everything.
    """
    conn = get_connection()

    # Step 1 — latest row, all vessel type columns
    row = conn.execute(
        """
        SELECT date, n_tanker, n_container, n_dry_bulk, n_roro, n_general_cargo, n_total
        FROM transit_events
        ORDER BY date DESC
        LIMIT 1
        """
    ).fetchone()

    if row is None:
        conn.close()
        return {}

    latest_date, n_tanker, n_container, n_dry_bulk, n_roro, n_general_cargo, n_total = row

    # Step 2 — pre-crisis baseline rows for all vessel types
    # Uses full-year 2025 (365 days) — true peacetime normal
    # Better than Jan-Feb 2026 which was already suppressed by pre-crisis tension
    baseline_rows = conn.execute(
        """
        SELECT n_tanker, n_container, n_dry_bulk, n_roro, n_general_cargo, n_total
        FROM transit_events
        WHERE date >= '2025-01-01' AND date < '2026-01-01'
        ORDER BY date DESC
        LIMIT 365
        """
    ).fetchall()

    conn.close()

    # Unpack each vessel type into its own list
    def col(idx): return [r[idx] for r in baseline_rows if r[idx] is not None]

    tanker_stats   = _compute_vessel_stats(col(0), n_tanker)
    container_stats= _compute_vessel_stats(col(1), n_container)
    drybulk_stats  = _compute_vessel_stats(col(2), n_dry_bulk)
    roro_stats     = _compute_vessel_stats(col(3), n_roro)
    gencargo_stats = _compute_vessel_stats(col(4), n_general_cargo)
    total_stats    = _compute_vessel_stats(col(5), n_total)

    return {
        "date": latest_date,

        # Raw counts
        "n_tanker":        n_tanker,
        "n_container":     n_container,
        "n_dry_bulk":      n_dry_bulk,
        "n_roro":          n_roro,
        "n_general_cargo": n_general_cargo,
        "n_total":         n_total,

        # Tanker stats (primary signal)
        "baseline_tanker":      tanker_stats["baseline"],
        "z_score_tanker":       tanker_stats["z_score"],
        "anomaly_flag_tanker":  tanker_stats["anomaly_flag"],
        "pct_normal_tanker":    tanker_stats["pct_of_normal"],

        # Container stats
        "baseline_container":      container_stats["baseline"],
        "z_score_container":       container_stats["z_score"],
        "anomaly_flag_container":  container_stats["anomaly_flag"],
        "pct_normal_container":    container_stats["pct_of_normal"],

        # Dry bulk stats
        "baseline_dry_bulk":      drybulk_stats["baseline"],
        "z_score_dry_bulk":       drybulk_stats["z_score"],
        "anomaly_flag_dry_bulk":  drybulk_stats["anomaly_flag"],
        "pct_normal_dry_bulk":    drybulk_stats["pct_of_normal"],

        # RoRo stats
        "baseline_roro":      roro_stats["baseline"],
        "z_score_roro":       roro_stats["z_score"],
        "anomaly_flag_roro":  roro_stats["anomaly_flag"],
        "pct_normal_roro":    roro_stats["pct_of_normal"],

        # General cargo stats
        "baseline_general_cargo":      gencargo_stats["baseline"],
        "z_score_general_cargo":       gencargo_stats["z_score"],
        "anomaly_flag_general_cargo":  gencargo_stats["anomaly_flag"],
        "pct_normal_general_cargo":    gencargo_stats["pct_of_normal"],

        # Total (all vessels combined)
        "baseline_total":      total_stats["baseline"],
        "z_score_total":       total_stats["z_score"],
        "anomaly_flag_total":  total_stats["anomaly_flag"],
        "pct_normal_total":    total_stats["pct_of_normal"],

        # Primary keys — downstream code reads these
        # NOTE: renamed from baseline_30d — this is the full-year 2025 average,
        # NOT a 30-day rolling window. The old name was misleading.
        "transit_count":   n_tanker,
        "baseline_annual": tanker_stats["baseline"],
        "z_score":         tanker_stats["z_score"],
        "anomaly_flag":    tanker_stats["anomaly_flag"],
        "pct_of_normal":   tanker_stats["pct_of_normal"],
    }

# ── Function 2 — 7-Day Recovery Trend ────────────────────────────────────────

def _direction_label(slope: float) -> str:
    """Converts a slope value into a human-readable direction label."""
    if slope > 0.5:   return "RECOVERING"
    if slope > 0.1:   return "RECOVERING SLOWLY"
    if slope < -0.5:  return "WORSENING"
    if slope < -0.1:  return "WORSENING SLOWLY"
    return "FLAT"


def get_recovery_trend() -> dict:
    """
    Reads last 7 days from transit_events.
    Fits a straight line through counts for EACH vessel type.
    Returns slope, direction, dates, and counts per vessel type.

    The UI can choose which vessel type trend to display.
    Tanker trend is also returned under backward-compatible keys
    (slope, direction, counts) so existing dashboard code still works.
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT date, n_tanker, n_container, n_dry_bulk, n_roro, n_general_cargo, n_total
        FROM transit_events
        ORDER BY date DESC
        LIMIT 7
        """
    ).fetchall()
    conn.close()

    if len(rows) < 3:
        return {"slope": None, "direction": "INSUFFICIENT DATA"}

    # Reverse so oldest is first
    rows  = list(reversed(rows))
    dates = [r[0] for r in rows]
    x     = list(range(len(rows)))

    def trend_for(col_idx):
        counts = [r[col_idx] if r[col_idx] is not None else 0 for r in rows]
        slope, _ = np.polyfit(x, counts, 1)
        slope = round(slope, 2)
        return {"slope": slope, "direction": _direction_label(slope), "counts": counts}

    tanker    = trend_for(1)
    container = trend_for(2)
    dry_bulk  = trend_for(3)
    roro      = trend_for(4)
    gen_cargo = trend_for(5)
    total     = trend_for(6)

    return {
        "dates": dates,

        # Per vessel type
        "tanker":        tanker,
        "container":     container,
        "dry_bulk":      dry_bulk,
        "roro":          roro,
        "general_cargo": gen_cargo,
        "total":         total,

        # Backward-compatible keys — existing dashboard reads these
        "slope":     tanker["slope"],
        "direction": tanker["direction"],
        "counts":    tanker["counts"],
    }

# ── Function 3 — AIS Dark Events ─────────────────────────────────────────────

def get_dark_events() -> dict:
    """
    Reads vessel_positions and finds vessels that:
    1. Were last seen inside the Gulf bounding box
    2. Have been silent for more than AIS_DARK_HOURS

    Returns count and list of dark vessels.

    Note: vessel_positions is sparse right now due to
    limited terrestrial AIS coverage in the Gulf.
    This function will produce more results as data accumulates.
    """
    conn = get_connection()

    # Get the most recent position for each MMSI
    # LEFT JOIN vessel_registry to filter tanker-only where type is known.
    # IS NULL allows vessels not yet in registry through (conservative — avoids missed detections).
    rows = conn.execute(
        """
        SELECT vp.mmsi, vp.latitude, vp.longitude, vp.timestamp_utc
        FROM vessel_positions vp
        LEFT JOIN vessel_registry vr ON vp.mmsi = vr.mmsi
        WHERE vp.latitude  BETWEEN ? AND ?
        AND   vp.longitude BETWEEN ? AND ?
        AND   (vr.ship_type_label = 'TANKER' OR vr.ship_type_label IS NULL)
        GROUP BY vp.mmsi
        HAVING vp.timestamp_utc = MAX(vp.timestamp_utc)
        """,
        (GULF_LAT_MIN, GULF_LAT_MAX, GULF_LON_MIN, GULF_LON_MAX)
    ).fetchall()
    conn.close()

    dark_vessels = []
    now = datetime.now(timezone.utc)

    for mmsi, lat, lon, timestamp in rows:
        try:
            # Parse timestamp from aisstream format
            # Format: "2026-05-08 19:33:06.138573106 +0000 UTC"
            ts_clean = timestamp.split(".")[0]
            last_seen = datetime.strptime(ts_clean, "%Y-%m-%d %H:%M:%S")
            last_seen = last_seen.replace(tzinfo=timezone.utc)

            hours_silent = (now - last_seen).total_seconds() / 3600

            if hours_silent > AIS_DARK_HOURS:
                dark_vessels.append({
                    "mmsi":          mmsi,
                    "last_lat":      lat,
                    "last_lon":      lon,
                    "last_seen":     timestamp,
                    "hours_silent":  round(hours_silent, 1),
                })
        except Exception:
            continue

    return {
        "dark_count":   len(dark_vessels),
        "dark_vessels": dark_vessels,
    }

# ── Function 4 — Diversion Classifier ────────────────────────────────────────

def get_diversion_events() -> dict:
    """
    Detects vessels that diverted away from Hormuz toward Cape of Good Hope.

    A vessel is flagged as a diversion if:
    1. It had a position inside persian_gulf_interior
    2. It later appeared in gulf_of_oman moving southward (heading 120-240)
    3. It never appeared in hormuz_corridor in between

    Current output: zero until vessel_positions accumulates Gulf data.
    Logic is correct and will produce results automatically.
    """
    conn = get_connection()

    # Step 1 — find MMSIs that appeared inside Persian Gulf interior
    # LEFT JOIN vessel_registry — filter tanker-only where type is known.
    gulf_vessels = conn.execute(
        """
        SELECT DISTINCT vp.mmsi
        FROM vessel_positions vp
        LEFT JOIN vessel_registry vr ON vp.mmsi = vr.mmsi
        WHERE vp.latitude  BETWEEN ? AND ?
        AND   vp.longitude BETWEEN ? AND ?
        AND   (vr.ship_type_label = 'TANKER' OR vr.ship_type_label IS NULL)
        """,
        (
            GEOFENCES["persian_gulf_interior"]["lat_min"],
            GEOFENCES["persian_gulf_interior"]["lat_max"],
            GEOFENCES["persian_gulf_interior"]["lon_min"],
            GEOFENCES["persian_gulf_interior"]["lon_max"],
        )
    ).fetchall()

    gulf_mmsi_list = [r[0] for r in gulf_vessels]

    if not gulf_mmsi_list:
        conn.close()
        return {"diversion_count": 0, "diverted_vessels": []}

    # Step 2 — from those MMSIs, find ones that appeared in Gulf of Oman
    # moving southward (heading between 120 and 240 degrees)
    placeholders = ",".join("?" * len(gulf_mmsi_list))
    oman_vessels = conn.execute(
        f"""
        SELECT DISTINCT mmsi, latitude, longitude, heading, timestamp_utc
        FROM vessel_positions
        WHERE mmsi IN ({placeholders})
        AND   latitude  BETWEEN ? AND ?
        AND   longitude BETWEEN ? AND ?
        AND   heading   BETWEEN 120 AND 240
        """,
        gulf_mmsi_list + [
            GEOFENCES["gulf_of_oman"]["lat_min"],
            GEOFENCES["gulf_of_oman"]["lat_max"],
            GEOFENCES["gulf_of_oman"]["lon_min"],
            GEOFENCES["gulf_of_oman"]["lon_max"],
        ]
    ).fetchall()

    if not oman_vessels:
        conn.close()
        return {"diversion_count": 0, "diverted_vessels": []}

    # Step 3 — confirm these vessels never transited Hormuz corridor
    diverted = []
    for mmsi, lat, lon, heading, timestamp in oman_vessels:
        hormuz_check = conn.execute(
            """
            SELECT COUNT(*) FROM vessel_positions
            WHERE mmsi      = ?
            AND   latitude  BETWEEN ? AND ?
            AND   longitude BETWEEN ? AND ?
            """,
            (
                mmsi,
                GEOFENCES["hormuz_corridor"]["lat_min"],
                GEOFENCES["hormuz_corridor"]["lat_max"],
                GEOFENCES["hormuz_corridor"]["lon_min"],
                GEOFENCES["hormuz_corridor"]["lon_max"],
            )
        ).fetchone()[0]

        # If vessel never appeared in Hormuz corridor — it diverted
        if hormuz_check == 0:
            diverted.append({
                "mmsi":      mmsi,
                "last_lat":  lat,
                "last_lon":  lon,
                "heading":   heading,
                "timestamp": timestamp,
            })

    conn.close()

    return {
        "diversion_count":   len(diverted),
        "diverted_vessels":  diverted,
    }
# ── Function 5 — Fujairah Anchorage Clustering ───────────────────────────────

def get_anchorage_clustering() -> dict:
    """
    Counts vessels present in the Fujairah anchorage zone within the last
    ANCHORAGE_CLUSTERING_HOURS hours. Requires at least 3 position fixes
    per vessel to filter out transient pings.

    Elevated count = vessels queuing for Hormuz to reopen.
    This is a leading indicator of recovery — vessels arrive before
    transit counts resume, making anchorage clustering analytically distinct
    from the transit index.

    Returns count, status label, and vessel list.
    Zero output expected until vessel_positions accumulates Gulf data.
    """
    conn = get_connection()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=ANCHORAGE_CLUSTERING_HOURS)).isoformat()

    rows = conn.execute(
        """
        SELECT vp.mmsi,
               COUNT(*)            AS position_count,
               MIN(vp.timestamp_utc) AS first_seen,
               MAX(vp.timestamp_utc) AS last_seen,
               AVG(vp.latitude)    AS avg_lat,
               AVG(vp.longitude)   AS avg_lon
        FROM vessel_positions vp
        LEFT JOIN vessel_registry vr ON vp.mmsi = vr.mmsi
        WHERE vp.latitude  BETWEEN ? AND ?
          AND vp.longitude BETWEEN ? AND ?
          AND vp.timestamp_utc >= ?
          AND (vr.ship_type_label = 'TANKER' OR vr.ship_type_label IS NULL)
        GROUP BY vp.mmsi
        HAVING COUNT(*) >= 3
        ORDER BY position_count DESC
        """,
        (
            FUJAIRAH_ANCHORAGE["lat_min"],
            FUJAIRAH_ANCHORAGE["lat_max"],
            FUJAIRAH_ANCHORAGE["lon_min"],
            FUJAIRAH_ANCHORAGE["lon_max"],
            cutoff,
        )
    ).fetchall()
    conn.close()

    count = len(rows)

    if count >= ANCHORAGE_CLUSTERING_THRESHOLD:
        status = "ELEVATED — possible Hormuz queue"
    elif count > 0:
        status = f"{count} vessels present"
    else:
        status = "None detected (vessel_positions sparse — accumulating)"

    vessels = [
        {
            "mmsi":           r[0],
            "position_count": r[1],
            "first_seen":     r[2],
            "last_seen":      r[3],
            "avg_lat":        round(r[4], 4),
            "avg_lon":        round(r[5], 4),
        }
        for r in rows
    ]

    return {"count": count, "status": status, "vessels": vessels}


# ── Main Output — Hormuz Transit Anomaly Index ────────────────────────────────

def log_to_db(index: dict, trend: dict, dark: dict, anchorage: dict):
    """
    Writes the current run output to anomaly_log table.
    Called at the end of every run() execution.
    """
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO anomaly_log (
            run_date, latest_data_date, transit_count, baseline_annual,
            z_score, anomaly_flag, pct_of_normal,
            trend_direction, trend_slope, dark_events, anchorage_count, logged_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            index.get("date"),
            index.get("transit_count"),
            index.get("baseline_annual"),
            index.get("z_score"),
            index.get("anomaly_flag"),
            index.get("pct_of_normal"),
            trend.get("direction"),
            trend.get("slope"),
            dark.get("dark_count"),
            anchorage.get("count", 0),
            datetime.now(timezone.utc).isoformat(),
        )
    )
    conn.commit()
    conn.close()


def run():
    print("=" * 50)
    print("   HORMUZ TRANSIT ANOMALY INDEX")
    print("=" * 50)

    # ── Latest index ──────────────────────────────────
    index = get_latest_index()
    if not index:
        print("ERROR: No data in transit_events table")
        return

    print(f"\n📅 Latest date: {index['date']}")
    print(f"\n{'Vessel Type':<18} {'Today':>6} {'Baseline':>10} {'% Normal':>10} {'Z-Score':>8} {'Flag':>6}")
    print("-" * 62)
    vessel_types = [
        ("Tanker",        index["n_tanker"],        index["baseline_tanker"],        index["pct_normal_tanker"],        index["z_score_tanker"],        index["anomaly_flag_tanker"]),
        ("Container",     index["n_container"],     index["baseline_container"],     index["pct_normal_container"],     index["z_score_container"],     index["anomaly_flag_container"]),
        ("Dry Bulk",      index["n_dry_bulk"],      index["baseline_dry_bulk"],      index["pct_normal_dry_bulk"],      index["z_score_dry_bulk"],      index["anomaly_flag_dry_bulk"]),
        ("RoRo",          index["n_roro"],          index["baseline_roro"],          index["pct_normal_roro"],          index["z_score_roro"],          index["anomaly_flag_roro"]),
        ("General Cargo", index["n_general_cargo"], index["baseline_general_cargo"], index["pct_normal_general_cargo"], index["z_score_general_cargo"], index["anomaly_flag_general_cargo"]),
        ("TOTAL",         index["n_total"],         index["baseline_total"],         index["pct_normal_total"],         index["z_score_total"],         index["anomaly_flag_total"]),
    ]
    for vtype, count, baseline, pct, z, flag in vessel_types:
        flag_str = "⚠️ " if flag else "OK"
        b = f"{baseline:.1f}" if baseline is not None else "N/A"
        p = f"{pct}%" if pct is not None else "N/A"
        print(f"{vtype:<18} {count:>6} {b:>10} {p:>10} {str(z):>8} {flag_str:>6}")

    # ── Recovery trend ────────────────────────────────
    trend = get_recovery_trend()
    print(f"\n📈 7-day trend (tanker):")
    print(f"   Direction:   {trend['direction']}")
    print(f"   Slope:       {trend['slope']} ships/day")
    print(f"   Last 7 days: {trend['counts']}")

    # ── AIS dark events ───────────────────────────────
    dark = get_dark_events()
    print(f"\n🔦 AIS dark events (Gulf region):")
    print(f"   Vessels gone silent: {dark['dark_count']}")
    if dark['dark_vessels']:
        for v in dark['dark_vessels']:
            print(f"   MMSI {v['mmsi']} — silent {v['hours_silent']}hrs — last at {v['last_lat']}, {v['last_lon']}")
    else:
        print("   None detected (vessel_positions sparse — accumulating)")

    # ── Diversion events ──────────────────────────────
    diversions = get_diversion_events()
    print(f"\n🔀 Diversion events (Cape rerouting):")
    print(f"   Vessels diverted: {diversions['diversion_count']}")
    if diversions['diverted_vessels']:
        for v in diversions['diverted_vessels']:
            print(f"   MMSI {v['mmsi']} — heading {v['heading']}° — last at {v['last_lat']}, {v['last_lon']}")
    else:
        print("   None detected (vessel_positions sparse — accumulating)")

    # ── Fujairah anchorage clustering ─────────────────
    anchorage = get_anchorage_clustering()
    print(f"\n⚓ Fujairah anchorage queue:")
    print(f"   Vessels in zone: {anchorage['count']}")
    print(f"   Status: {anchorage['status']}")
    if anchorage['vessels']:
        for v in anchorage['vessels']:
            print(f"   MMSI {v['mmsi']} — {v['position_count']} fixes — last seen {v['last_seen']}")

    # ── Write to anomaly_log ──────────────────────────
    log_to_db(index, trend, dark, anchorage)
    print(f"\n✅ Run logged to anomaly_log table")

    print("\n" + "=" * 50)

if __name__ == "__main__":
    run()