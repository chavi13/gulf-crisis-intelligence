"""
dashboard/db.py
---------------
All database queries for the Gulf Crisis Supply Intelligence dashboard.
This file is the only place that touches the database.
app.py imports from here — it never writes SQL directly.

Every function returns either:
  - A dict (for single-row metric reads)
  - A pandas DataFrame (for chart data)
  - A fallback value if the table is empty or query fails

Database path is absolute — matches the project location confirmed in Phase 5 planning.
"""

import sqlite3
import pandas as pd
from pathlib import Path

# ── Database path ──────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent.parent / "data" / "processed" / "gulf_data.db"


def _connect():
    """
    Open a read-only connection to the database.
    row_factory = sqlite3.Row lets us access columns by name (row["column"]).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# OVERVIEW & HEADLINE METRICS
# These three functions each return the latest single-row summary from one
# of the three module log tables. They are what the Overview tab displays.
# ══════════════════════════════════════════════════════════════════════════════

def get_latest_tanker_metrics() -> dict:
    """
    Read the most recent row from anomaly_log.
    Returns the Hormuz Transit Anomaly Index — the Phase 2 module output.

    Returns dict with keys:
        run_date, transit_count, baseline_30d, z_score, anomaly_flag,
        pct_of_normal, trend_direction, trend_slope, dark_events, logged_at
    Returns a dict of None values if the table is empty.
    """
    query = """
        SELECT
            run_date,
            transit_count,
            baseline_30d,
            z_score,
            anomaly_flag,
            pct_of_normal,
            trend_direction,
            trend_slope,
            dark_events,
            anchorage_count,
            logged_at
        FROM anomaly_log
        ORDER BY logged_at DESC
        LIMIT 1
    """
    try:
        with _connect() as conn:
            row = conn.execute(query).fetchone()
            if row is None:
                return {k: None for k in [
                    "run_date", "transit_count", "baseline_30d", "z_score",
                    "anomaly_flag", "pct_of_normal", "trend_direction",
                    "trend_slope", "dark_events", "anchorage_count", "logged_at"
                ]}
            return dict(row)
    except Exception as e:
        print(f"[db] get_latest_tanker_metrics error: {e}")
        return {k: None for k in [
            "run_date", "transit_count", "baseline_30d", "z_score",
            "anomaly_flag", "pct_of_normal", "trend_direction",
            "trend_slope", "dark_events", "anchorage_count", "logged_at"
        ]}


def get_latest_lng_metrics() -> dict:
    """
    Read the most recent row from lng_rebalancing_log.
    Returns the LNG Rebalancing Score — the Phase 3 module output.

    Returns dict with keys:
        run_date, rebalancing_score, confidence, routing_signal,
        us_utilization_pct, days_deficit, thesis, logged_at
    Returns a dict of None values if the table is empty.

    Note: the column in lng_rebalancing_log that stores days behind pace
    is named 'days_deficit' — confirmed in Phase 3 audit.
    """
    query = """
        SELECT
            run_date,
            rebalancing_score,
            confidence,
            routing_signal,
            us_utilization,
            spread_7d,
            jkm_price,
            ttf_price,
            storage_pct,
            seasonal_deficit,
            days_deficit,
            coverage_status,
            storage_risk,
            thesis,
            logged_at
        FROM lng_rebalancing_log
        ORDER BY logged_at DESC
        LIMIT 1
    """
    try:
        with _connect() as conn:
            row = conn.execute(query).fetchone()
            if row is None:
                return {k: None for k in [
                    "run_date", "rebalancing_score", "confidence",
                    "routing_signal", "us_utilization", "spread_7d",
                    "jkm_price", "ttf_price", "storage_pct",
                    "seasonal_deficit", "days_deficit", "coverage_status",
                    "storage_risk", "thesis", "logged_at"
                ]}
            return dict(row)
    except Exception as e:
        print(f"[db] get_latest_lng_metrics error: {e}")
        return {k: None for k in [
            "run_date", "rebalancing_score", "confidence",
            "routing_signal", "us_utilization", "spread_7d",
            "jkm_price", "ttf_price", "storage_pct",
            "seasonal_deficit", "days_deficit", "coverage_status",
            "storage_risk", "thesis", "logged_at"
        ]}


def get_latest_supply_gap_metrics() -> dict:
    """
    Read the most recent row from supply_gap_log.
    Returns the Regional Supply Gap Table — the Phase 4 module output.
    Also returns the programmatically generated thesis from _build_thesis().

    Returns dict with keys:
        run_date, pct_of_normal, crude_gap_net_mbd,
        asia_crude_gap_mbd, europe_crude_gap_mbd,
        lng_gap_bcfd, asia_lng_gap_bcfd, europe_lng_gap_bcfd,
        asia_crude_risk, europe_crude_risk, europe_lng_risk,
        asia_lng_risk, summary_thesis, logged_at
    Returns a dict of None values if the table is empty.
    """
    query = """
        SELECT
            run_date,
            pct_of_normal,
            crude_gap_net_mbd,
            asia_crude_gap_mbd,
            europe_crude_gap_mbd,
            lng_gap_bcfd,
            asia_lng_gap_bcfd,
            europe_lng_gap_bcfd,
            asia_crude_risk,
            europe_crude_risk,
            europe_lng_risk,
            asia_lng_risk,
            summary_thesis,
            logged_at
        FROM supply_gap_log
        ORDER BY logged_at DESC
        LIMIT 1
    """
    try:
        with _connect() as conn:
            row = conn.execute(query).fetchone()
            if row is None:
                return {k: None for k in [
                    "run_date", "pct_of_normal", "crude_gap_net_mbd",
                    "asia_crude_gap_mbd", "europe_crude_gap_mbd",
                    "lng_gap_bcfd", "asia_lng_gap_bcfd", "europe_lng_gap_bcfd",
                    "asia_crude_risk", "europe_crude_risk", "europe_lng_risk",
                    "asia_lng_risk", "summary_thesis", "logged_at"
                ]}
            return dict(row)
    except Exception as e:
        print(f"[db] get_latest_supply_gap_metrics error: {e}")
        return {k: None for k in [
            "run_date", "pct_of_normal", "crude_gap_net_mbd",
            "asia_crude_gap_mbd", "europe_crude_gap_mbd",
            "lng_gap_bcfd", "asia_lng_gap_bcfd", "europe_lng_gap_bcfd",
            "asia_crude_risk", "europe_crude_risk", "europe_lng_risk",
            "asia_lng_risk", "summary_thesis", "logged_at"
        ]}



# ══════════════════════════════════════════════════════════════════════════════
# CRISIS CONTEXT — GEOPOLITICAL STATUS
# ══════════════════════════════════════════════════════════════════════════════

def get_crisis_context() -> dict:
    """
    Read the current geopolitical status from crisis_context.
    This table is manually updated as the situation evolves.
    Replaces the static sidebar text used in the original Phase 5 implementation.

    Returns dict with keys:
        as_of_date, mine_clearance_status, mine_clearance_pct_estimate,
        mine_clearance_source, diplomatic_status, us_blockade_active,
        notes, last_updated
    Returns a dict of None values if the table is empty.
    """
    query = """
        SELECT
            as_of_date,
            mine_clearance_status,
            mine_clearance_pct_estimate,
            mine_clearance_source,
            diplomatic_status,
            us_blockade_active,
            notes,
            last_updated
        FROM crisis_context
        ORDER BY id DESC
        LIMIT 1
    """
    try:
        with _connect() as conn:
            row = conn.execute(query).fetchone()
            if row is None:
                return {k: None for k in [
                    "as_of_date", "mine_clearance_status",
                    "mine_clearance_pct_estimate", "mine_clearance_source",
                    "diplomatic_status", "us_blockade_active",
                    "notes", "last_updated"
                ]}
            return dict(row)
    except Exception as e:
        print(f"[db] get_crisis_context error: {e}")
        return {k: None for k in [
            "as_of_date", "mine_clearance_status",
            "mine_clearance_pct_estimate", "mine_clearance_source",
            "diplomatic_status", "us_blockade_active",
            "notes", "last_updated"
        ]}




def get_transit_history() -> pd.DataFrame:
    """
    Read all 125 rows from transit_events for the transit count chart.
    This is the Kaggle dataset loaded in Phase 2 — Jan 1 to May 5 2026.

    Returns DataFrame with columns:
        date (datetime), transit_count (int), baseline_30d (float)

    Sorted ascending by date so charts render left-to-right correctly.
    """
    query = """
        SELECT
            date,
            transit_count,
            baseline_30d
        FROM transit_events
        ORDER BY date ASC
    """
    try:
        with _connect() as conn:
            df = pd.read_sql_query(query, conn, parse_dates=["date"])
            return df
    except Exception as e:
        print(f"[db] get_transit_history error: {e}")
        return pd.DataFrame(columns=["date", "transit_count", "baseline_30d"])


def get_anomaly_log_history() -> pd.DataFrame:
    """
    Read all rows from anomaly_log for the 7-day trend display.
    Used in the Tanker tab recovery trend section.

    Returns DataFrame with columns:
        run_date (datetime), pct_of_normal, trend_direction,
        trend_slope, transit_count, anomaly_flag
    """
    query = """
        SELECT
            run_date,
            pct_of_normal,
            trend_direction,
            trend_slope,
            transit_count,
            anomaly_flag
        FROM anomaly_log
        ORDER BY run_date ASC
    """
    try:
        with _connect() as conn:
            df = pd.read_sql_query(query, conn, parse_dates=["run_date"])
            return df
    except Exception as e:
        print(f"[db] get_anomaly_log_history error: {e}")
        return pd.DataFrame(columns=[
            "run_date", "pct_of_normal", "trend_direction",
            "trend_slope", "transit_count", "anomaly_flag"
        ])


# ══════════════════════════════════════════════════════════════════════════════
# LNG MODULE — CHART DATA
# ══════════════════════════════════════════════════════════════════════════════

def get_price_history() -> pd.DataFrame:
    """
    Read JKM and TTF price series from price_data.
    Used for the JKM-TTF spread chart in the LNG tab.
    1,360 rows covering Jan 2025 to May 2026.

    Returns DataFrame with columns:
        date (datetime), JKM (float), TTF (float), spread (float)

    spread = JKM minus TTF, in $/MMBtu.
    Rows where either ticker is missing on a given date are dropped
    to avoid NaN artifacts on the chart.
    """
    query = """
        SELECT date, ticker, price
        FROM price_data
        WHERE ticker IN ('JKM', 'TTF')
        ORDER BY date ASC
    """
    try:
        with _connect() as conn:
            df = pd.read_sql_query(query, conn, parse_dates=["date"])

        # Pivot from long to wide: one column per ticker
        df_wide = df.pivot_table(index="date", columns="ticker", values="price")
        df_wide = df_wide.reset_index()
        df_wide.columns.name = None

        # Only keep rows where both JKM and TTF are present
        df_wide = df_wide.dropna(subset=["JKM", "TTF"])

        # Compute spread
        df_wide["spread"] = df_wide["JKM"] - df_wide["TTF"]

        return df_wide

    except Exception as e:
        print(f"[db] get_price_history error: {e}")
        return pd.DataFrame(columns=["date", "JKM", "TTF", "spread"])


def get_terminal_utilization() -> pd.DataFrame:
    """
    Read the latest month of LNG export data per terminal.
    Used for the US terminal utilization bar chart in the LNG tab.

    Returns the most recent available month (February 2026 due to EIA lag).
    Each row is one terminal with its utilization percentage.

    Returns DataFrame with columns:
        terminal (str), volume_bcf (float), utilization_pct (float)

    Nameplate capacities (bcf/day) used for utilization calculation
    are the verified values from lng_terminals.py (Phase 3).
    """
    # Nameplate capacities in bcf/day — from lng_terminals.py (Phase 3)
    NAMEPLATE = {
        "Sabine Pass, LA":      3.60,
        "Corpus Christi, TX":   3.10,
        "Plaquemines, LA":      2.60,
        "Freeport, TX":         2.14,
        "Cameron, LA":          1.70,
        "Calcasieu Pass, LA":   1.20,
        "Cove Point, MD":       0.75,
        "Elba Island, GA":      0.33,
    }

    # Get the most recent month available across all terminals
    latest_month_query = """
        SELECT MAX(SUBSTR(date, 1, 7)) as latest_month
        FROM lng_export_volumes
    """

    terminal_query = """
        SELECT terminal, SUM(volume_bcf) as volume_bcf
        FROM lng_export_volumes
        WHERE SUBSTR(date, 1, 7) = ?
        GROUP BY terminal
        ORDER BY volume_bcf DESC
    """

    try:
        with _connect() as conn:
            row = conn.execute(latest_month_query).fetchone()
            latest_month = row["latest_month"] if row else None

            if latest_month is None:
                return pd.DataFrame(columns=["terminal", "volume_bcf", "utilization_pct"])

            df = pd.read_sql_query(terminal_query, conn, params=(latest_month,))

        # Calculate days in that month for utilization
        year, month = int(latest_month[:4]), int(latest_month[5:7])
        import calendar
        days_in_month = calendar.monthrange(year, month)[1]

        def calc_utilization(row):
            nameplate = NAMEPLATE.get(row["terminal"])
            if nameplate is None:
                return None
            capacity_bcf = nameplate * days_in_month
            return round((row["volume_bcf"] / capacity_bcf) * 100, 1)

        df["utilization_pct"] = df.apply(calc_utilization, axis=1)
        df["latest_month"] = latest_month
        return df

    except Exception as e:
        print(f"[db] get_terminal_utilization error: {e}")
        return pd.DataFrame(columns=["terminal", "volume_bcf", "utilization_pct"])


def get_european_storage() -> pd.DataFrame:
    """
    Read EU aggregate gas storage levels from gas_storage_levels.
    2,321 rows covering 2020-01-01 to 2026-05-09.
    Used for the European storage coverage chart in the LNG tab.

    Returns DataFrame with columns:
        date (datetime), pct_full (float)

    Only EU aggregate rows (country = 'EU') are returned.
    Sorted ascending by date.
    """
    query = """
        SELECT date, pct_full
        FROM gas_storage_levels
        WHERE country = 'EU'
        ORDER BY date ASC
    """
    try:
        with _connect() as conn:
            df = pd.read_sql_query(query, conn, parse_dates=["date"])
            return df
    except Exception as e:
        print(f"[db] get_european_storage error: {e}")
        return pd.DataFrame(columns=["date", "pct_full"])


def get_storage_seasonal_baseline() -> pd.DataFrame:
    """
    Compute the 5-year seasonal average (2020-2024) for EU storage.
    Used as the baseline overlay on the European storage chart.

    Returns DataFrame with columns:
        day_of_year (int, 1-366), avg_pct_full (float)

    Methodology: same as Phase 3 — excludes 2025 to avoid partial-year skew.
    Joined to the current year's dates in app.py for chart overlay.
    """
    query = """
        SELECT
            CAST(STRFTIME('%j', date) AS INTEGER) as day_of_year,
            ROUND(AVG(pct_full), 2) as avg_pct_full
        FROM gas_storage_levels
        WHERE country = 'EU'
          AND STRFTIME('%Y', date) BETWEEN '2020' AND '2024'
        GROUP BY day_of_year
        ORDER BY day_of_year ASC
    """
    try:
        with _connect() as conn:
            df = pd.read_sql_query(query, conn)
            return df
    except Exception as e:
        print(f"[db] get_storage_seasonal_baseline error: {e}")
        return pd.DataFrame(columns=["day_of_year", "avg_pct_full"])


def get_storage_yoy_level() -> dict:
    """
    Fetch the EU aggregate gas storage level for May 11, 2025.
    Used as a year-on-year reference line on the EU storage chart (item 11).

    Returns dict with keys:
        date (str), pct_full (float or None)

    Falls back to the nearest available date within ±7 days of May 11, 2025
    if the exact date is missing (weekends, public holidays).
    Returns {"date": None, "pct_full": None} if no data found in window.
    """
    # Try exact date first, then nearest within ±7 days
    query = """
        SELECT date, pct_full
        FROM gas_storage_levels
        WHERE country = 'EU'
          AND date BETWEEN '2025-05-04' AND '2025-05-18'
        ORDER BY ABS(JULIANDAY(date) - JULIANDAY('2025-05-11')) ASC
        LIMIT 1
    """
    try:
        with _connect() as conn:
            row = conn.execute(query).fetchone()
            if row is None:
                return {"date": None, "pct_full": None}
            return {"date": row["date"], "pct_full": row["pct_full"]}
    except Exception as e:
        print(f"[db] get_storage_yoy_level error: {e}")
        return {"date": None, "pct_full": None}


# ══════════════════════════════════════════════════════════════════════════════
# SUPPLY GAP MODULE — CHART DATA
# ══════════════════════════════════════════════════════════════════════════════

def get_supply_gap_log_history() -> pd.DataFrame:
    """
    Read all rows from supply_gap_log.
    Used to show how the gap model output has evolved over daily runs.

    Returns DataFrame with columns:
        run_date (datetime), crude_gap_net_mbd, asia_crude_risk,
        europe_lng_risk, pct_of_normal
    """
    query = """
        SELECT
            run_date,
            crude_gap_net_mbd,
            asia_crude_risk,
            europe_lng_risk,
            pct_of_normal
        FROM supply_gap_log
        ORDER BY run_date ASC
    """
    try:
        with _connect() as conn:
            df = pd.read_sql_query(query, conn, parse_dates=["run_date"])
            return df
    except Exception as e:
        print(f"[db] get_supply_gap_log_history error: {e}")
        return pd.DataFrame(columns=[
            "run_date", "crude_gap_net_mbd", "asia_crude_risk",
            "europe_lng_risk", "pct_of_normal"
        ])


# ══════════════════════════════════════════════════════════════════════════════
# CONNECTION HEALTH CHECK
# ══════════════════════════════════════════════════════════════════════════════

def check_db_connection() -> dict:
    """
    Verify the database exists and all expected tables are present.
    Called once at app startup — surfaces a clear error if something is wrong
    rather than letting queries fail silently downstream.

    Returns dict with keys:
        ok (bool), tables_found (list), tables_missing (list), error (str or None)
    """
    expected_tables = [
        "transit_events",
        "anomaly_log",
        "lng_export_volumes",
        "gas_storage_levels",
        "price_data",
        "lng_rebalancing_log",
        "supply_gap_log",
        "vessel_registry",
        "crisis_context",
    ]

    if not DB_PATH.exists():
        return {
            "ok": False,
            "tables_found": [],
            "tables_missing": expected_tables,
            "error": f"Database file not found at: {DB_PATH}"
        }

    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            found = [r["name"] for r in rows]
            missing = [t for t in expected_tables if t not in found]
            return {
                "ok": len(missing) == 0,
                "tables_found": found,
                "tables_missing": missing,
                "error": None
            }
    except Exception as e:
        return {
            "ok": False,
            "tables_found": [],
            "tables_missing": expected_tables,
            "error": str(e)
        }