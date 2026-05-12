"""
models/lng_rebalancing.py

LNG Cargo Flow & Atlantic Basin Rebalancing Module
Phase 3 — Gulf Crisis Supply Intelligence System

PURPOSE:
Measures the Atlantic Basin LNG market response to the 2026 Strait of
Hormuz disruption. Specifically:
  1. Whether US export terminals are running at capacity (utilization)
  2. Which direction US cargoes are being pulled (JKM-TTF spread)
  3. Whether Europe is on track for its winter storage target (coverage)
  4. The overall Atlantic Basin rebalancing state (composite score)

OUTPUT:
Prints a formatted summary to terminal and logs one row to
lng_rebalancing_log table in the database after every run.

READS FROM:
  - lng_export_volumes    (EIA — US LNG exports by terminal, monthly)
  - price_data            (yfinance — JKM, TTF, BRENT, HH daily prices)
  - gas_storage_levels    (GIE AGSI — EU aggregate storage, daily)

WRITES TO:
  - lng_rebalancing_log   (one row per run — daily via run_all.py)

DEPENDENCIES:
  - data/reference/lng_terminals.py (nameplate capacities)
  - Phase 3 data integrity fixes must be complete before running
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, date
import sys
import os

# Add project root to path so reference imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.reference.lng_terminals import LNG_TERMINALS, get_nameplate, get_days_in_month

DB_PATH = "data/processed/gulf_data.db"

# ─────────────────────────────────────────────────────────────────────────────
# PRICE UNITS REFERENCE
# TTF and JKM are in $/MMBtu. BRENT is in $/barrel. HH is in $/MMBtu.
# NEVER compare raw prices across tickers without checking units first.
# This dictionary is referenced in every function that reads price_data.
# ─────────────────────────────────────────────────────────────────────────────
PRICE_UNITS = {
    "JKM":   "$/MMBtu",   # Japan Korea Marker — Asian LNG benchmark
    "TTF":   "$/MMBtu",   # Title Transfer Facility — European gas benchmark
    "HH":    "$/MMBtu",   # Henry Hub — US natural gas benchmark
    "BRENT": "$/barrel",  # Brent crude oil — incomparable to gas prices as raw number
}

# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICAL THRESHOLDS
# All thresholds are judgment calls — documented here and in README.
# ─────────────────────────────────────────────────────────────────────────────

# Cargo routing threshold — $/MMBtu
# The approximate freight cost differential between routing a US LNG cargo
# to Asia (Tokyo) vs Europe (Rotterdam). When JKM-TTF spread exceeds this,
# the economics decisively favor routing to Asia.
# Historical basis: ~$2-3/MMBtu under normal freight conditions.
# Source: Phase 3 framework analysis, consistent with industry literature.
CARGO_ROUTING_THRESHOLD = 2.0

# Storage deficit thresholds — days behind required injection pace
# Used by get_lng_rebalancing_score() to classify European storage risk.
# These are judgment calls — documented here and defensible when explained.
# RED:   more than 30 days behind required pace → serious winter supply risk
# AMBER: 10-30 days behind → elevated risk, monitoring required
# GREEN: within 10 days of required pace → broadly on track
STORAGE_DEFICIT_HIGH     = 30   # days — RED threshold
STORAGE_DEFICIT_MODERATE = 10   # days — AMBER threshold

# Utilization thresholds — percentage of nameplate capacity
# Used to assess whether US export system has spare capacity to help Europe.
UTILIZATION_HIGH    = 90.0  # % — near maximum, limited spare capacity
UTILIZATION_NORMAL  = 75.0  # % — normal operating range

# EU winter storage target
# EU mandate: member states must reach 90% storage capacity by November 1
# each year as a buffer against winter supply shortages.
EU_WINTER_TARGET_PCT  = 90.0
EU_WINTER_TARGET_DATE = "11-01"  # November 1 — MM-DD format

# Seasonal baseline window
# Number of years of historical data used to compute seasonal average.
# Requires gas_storage_levels to have data going back this far.
# After Phase 3 GIE backfill: data available from 2020-01-01.
SEASONAL_BASELINE_YEARS = 5

# Rolling window for injection pace calculation
# Number of days used to compute the current injection rate.
# 14 days smooths out daily noise while remaining responsive to trends.
INJECTION_PACE_WINDOW_DAYS = 14

# Rolling window for spread calculation
# Number of trading days used to compute rolling average JKM-TTF spread.
# Row-based window — not calendar-based — so weekends/holidays don't distort.
SPREAD_ROLLING_WINDOW = 7


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION STUBS
# Each function will be built in its own step (Steps 11-15).
# Stubs are here so the file is importable and main() can be tested.
# ─────────────────────────────────────────────────────────────────────────────

def get_terminal_utilization():
    """
    Computes monthly US LNG export terminal utilization rates.

    Reads: lng_export_volumes (actual monthly exports by terminal)
    Joins: LNG_TERMINALS reference (nameplate capacities)
    Returns: dict with utilization rate, trend, and per-terminal breakdown
    """
    conn = sqlite3.connect(DB_PATH)

    # Read all terminal volume data
    df = pd.read_sql("""
        SELECT date, terminal, volume_bcf
        FROM lng_export_volumes
        ORDER BY date DESC
    """, conn)
    conn.close()

    if df.empty:
        return {"error": "No data in lng_export_volumes"}

    # ── Per-terminal utilization ──────────────────────────────────────────
    # For each row: utilization = volume_bcf / (nameplate_bcfd * days_in_month)
    # NOTE: utilization can exceed 100% — terminals push beyond nameplate
    # during peak crisis conditions. This is real, not a data error.
    # We report the raw figure and flag when above 100%.
    records = []
    for _, row in df.iterrows():
        terminal = row["terminal"]
        date     = row["date"]
        volume   = row["volume_bcf"]

        nameplate = get_nameplate(terminal)
        if nameplate is None:
            # Terminal not in reference file — skip silently
            # This should not happen if TERMINAL_NAME_MAP is correct
            continue

        days = get_days_in_month(date)
        max_possible = nameplate * days
        utilization  = (volume / max_possible) * 100

        records.append({
            "date":        date,
            "terminal":    terminal,
            "volume_bcf":  round(volume, 3),
            "nameplate":   nameplate,
            "days":        days,
            "max_bcf":     round(max_possible, 1),
            "utilization": round(utilization, 1)
        })

    terminal_df = pd.DataFrame(records)

    if terminal_df.empty:
        return {"error": "No terminals matched nameplate reference"}

    # ── Latest month aggregate ────────────────────────────────────────────
    # Get the most recent month that has data
    latest_date = terminal_df["date"].max()
    latest_df   = terminal_df[terminal_df["date"] == latest_date]

    # Total US utilization for latest month
    # Sum actual volumes across all terminals
    # Sum nameplate × days across all terminals
    total_volume   = latest_df["volume_bcf"].sum()
    total_max      = latest_df["max_bcf"].sum()
    us_utilization = round((total_volume / total_max) * 100, 1)

    # ── 4-month trend ─────────────────────────────────────────────────────
    # Compute aggregate US utilization for each available month
    # Use last 4 months to show direction of trend
    monthly = (
        terminal_df.groupby("date")
        .apply(lambda g: round((g["volume_bcf"].sum() / g["max_bcf"].sum()) * 100, 1))
        .reset_index()
    )
    monthly.columns = ["date", "us_utilization"]
    monthly = monthly.sort_values("date", ascending=False).head(4)

    # Trend direction — compare most recent to oldest in window
    if len(monthly) >= 2:
        newest = monthly.iloc[0]["us_utilization"]
        oldest = monthly.iloc[-1]["us_utilization"]
        delta  = newest - oldest
        if delta > 5:
            trend = "RISING"
        elif delta < -5:
            trend = "FALLING"
        else:
            trend = "STABLE"
    else:
        trend = "INSUFFICIENT DATA"

    # ── Above nameplate flag ──────────────────────────────────────────────
    above_nameplate = latest_df[latest_df["utilization"] > 100]["terminal"].tolist()

    return {
        "latest_date":      latest_date,
        "us_utilization":   us_utilization,
        "trend":            trend,
        "monthly_trend":    monthly.to_dict("records"),
        "terminal_detail":  latest_df[["terminal", "volume_bcf", "utilization"]].to_dict("records"),
        "above_nameplate":  above_nameplate,
        "total_volume_bcf": round(total_volume, 1),
    }



def get_jkm_ttf_spread():
    """
    Computes the JKM-TTF price spread and cargo routing signal.

    Reads: price_data (JKM and TTF daily prices)
    Units: both in $/MMBtu — directly comparable (see PRICE_UNITS)
    Returns: dict with current spread, rolling average, routing flag

    Note: Uses row-based rolling window (SPREAD_ROLLING_WINDOW trading days)
    not calendar-based, so weekend/holiday gaps do not distort the average.
    A 7-row window = 7 trading days regardless of calendar gaps.
    """
    conn = sqlite3.connect(DB_PATH)

    # Read JKM and TTF price series
    # EU aggregate filter note: not applicable here — price_data has no
    # country aggregation issue. Each ticker is a single global benchmark.
    jkm_df = pd.read_sql("""
        SELECT date, price as jkm
        FROM price_data
        WHERE ticker = 'JKM'
        ORDER BY date ASC
    """, conn)

    ttf_df = pd.read_sql("""
        SELECT date, price as ttf
        FROM price_data
        WHERE ticker = 'TTF'
        ORDER BY date ASC
    """, conn)

    conn.close()

    if jkm_df.empty or ttf_df.empty:
        return {"error": "JKM or TTF data missing from price_data"}

    # ── Merge on date ─────────────────────────────────────────────────────
    # Inner join — only dates where both JKM and TTF exist
    # Weekend/holiday gaps are naturally excluded since neither series
    # has prices on those days. Row-based windows therefore equal
    # trading-day windows automatically.
    df = pd.merge(jkm_df, ttf_df, on="date", how="inner")
    df = df.sort_values("date").reset_index(drop=True)

    # ── Daily spread ──────────────────────────────────────────────────────
    # Spread = JKM - TTF, both in $/MMBtu (see PRICE_UNITS)
    # Positive spread → JKM > TTF → Asia paying more → cargoes go east
    # Negative spread → TTF > JKM → Europe paying more → cargoes go west
    df["spread"] = df["jkm"] - df["ttf"]

    # ── Rolling average spread ────────────────────────────────────────────
    # SPREAD_ROLLING_WINDOW = 7 trading days (row-based, not calendar-based)
    # Smooths daily volatility so a single spike doesn't distort the signal
    df["spread_7d"] = df["spread"].rolling(window=SPREAD_ROLLING_WINDOW).mean()

    # ── Current readings ──────────────────────────────────────────────────
    latest         = df.iloc[-1]
    latest_date    = latest["date"]
    latest_jkm     = round(latest["jkm"], 3)
    latest_ttf     = round(latest["ttf"], 3)
    latest_spread  = round(latest["spread"], 3)
    rolling_spread = round(latest["spread_7d"], 3) if not pd.isna(latest["spread_7d"]) else None

    # ── Routing signal ────────────────────────────────────────────────────
    # CARGO_ROUTING_THRESHOLD = $2.0/MMBtu
    # Represents approximate freight cost differential between
    # US Gulf Coast → Tokyo vs US Gulf Coast → Rotterdam
    # When spread exceeds threshold: Asia wins the economics → ASIA signal
    # When spread below threshold: Europe competitive → EUROPE signal
    # Uses rolling average for signal stability — daily prices are noisy
    spread_for_signal = rolling_spread if rolling_spread is not None else latest_spread

    if spread_for_signal > CARGO_ROUTING_THRESHOLD:
        routing_signal = "ASIA"
        routing_note   = f"JKM exceeds TTF by ${spread_for_signal:.2f}/MMBtu — above ${CARGO_ROUTING_THRESHOLD} routing threshold. US cargoes incentivized toward Asia."
    elif spread_for_signal < -CARGO_ROUTING_THRESHOLD:
        routing_signal = "EUROPE"
        routing_note   = f"TTF exceeds JKM by ${abs(spread_for_signal):.2f}/MMBtu — US cargoes incentivized toward Europe."
    else:
        routing_signal = "NEUTRAL"
        routing_note   = f"Spread of ${spread_for_signal:.2f}/MMBtu is within the ${CARGO_ROUTING_THRESHOLD} routing threshold — no strong directional pull."

    # ── Crisis inflection point ───────────────────────────────────────────
    # Identify when spread first crossed above CARGO_ROUTING_THRESHOLD
    # This is the date US cargoes began routing decisively toward Asia
    above_threshold = df[df["spread"] > CARGO_ROUTING_THRESHOLD]
    if not above_threshold.empty:
        inflection_date = above_threshold.iloc[0]["date"]
    else:
        inflection_date = None

    # ── Peak spread ───────────────────────────────────────────────────────
    peak_spread = round(df["spread"].max(), 3)
    peak_date   = df.loc[df["spread"].idxmax(), "date"]

    # ── Last 7 trading days detail ────────────────────────────────────────
    recent = df.tail(SPREAD_ROLLING_WINDOW)[["date", "jkm", "ttf", "spread"]].copy()
    recent["jkm"]    = recent["jkm"].round(3)
    recent["ttf"]    = recent["ttf"].round(3)
    recent["spread"] = recent["spread"].round(3)

    return {
        "latest_date":      latest_date,
        "jkm":              latest_jkm,
        "ttf":              latest_ttf,
        "spread":           latest_spread,
        "spread_7d_avg":    rolling_spread,
        "routing_signal":   routing_signal,
        "routing_note":     routing_note,
        "inflection_date":  inflection_date,
        "peak_spread":      peak_spread,
        "peak_date":        peak_date,
        "recent_7d":        recent.to_dict("records"),
        "units":            PRICE_UNITS["JKM"],
    }


def get_european_storage_coverage():
    """
    Computes European gas storage coverage vs seasonal norm and EU winter target.

    Reads: gas_storage_levels (EU aggregate daily pct_full)

    QUERY DISCIPLINE — EU aggregate vs country rows:
    Every query in this function explicitly filters on country = 'EU'.
    Never mixes EU aggregate with individual country rows.
    The EU aggregate already includes all country values — summing both
    would double-count and make storage appear twice as full as reality.

    DATE HANDLING:
    gas_storage_levels uses YYYY-MM-DD format (daily).
    When monthly aggregation is needed, SUBSTR(date, 1, 7) extracts YYYY-MM.
    This is different from lng_export_volumes which uses YYYY-MM directly.

    Returns: dict with current pct_full, seasonal deficit, days behind target
    """
    conn = sqlite3.connect(DB_PATH)

    # ── Current storage level ─────────────────────────────────────────────
    # Always filter country = 'EU' explicitly — see query discipline note above
    current_df = pd.read_sql("""
        SELECT date, pct_full, storage_twh
        FROM gas_storage_levels
        WHERE country = 'EU'
        ORDER BY date DESC
        LIMIT 1
    """, conn)

    if current_df.empty:
        conn.close()
        return {"error": "No EU storage data available"}

    latest_date  = current_df.iloc[0]["date"]
    current_pct  = round(current_df.iloc[0]["pct_full"], 2)
    current_twh  = round(current_df.iloc[0]["storage_twh"], 2)

    # ── Seasonal baseline ─────────────────────────────────────────────────
    # Extract month-day from current date to find the same calendar position
    # in prior years. This gives us the 5-year average for "this time of year."
    # SEASONAL_BASELINE_YEARS = 5 — uses 2020-2024 as the baseline window.
    # We exclude 2025 from the baseline because it is partially in the
    # current year and would skew the average.
    month_day = latest_date[5:]  # Extract MM-DD from YYYY-MM-DD

    baseline_df = pd.read_sql(f"""
        SELECT SUBSTR(date, 1, 4) as year, pct_full
        FROM gas_storage_levels
        WHERE country = 'EU'
        AND SUBSTR(date, 6) = '{month_day}'
        AND SUBSTR(date, 1, 4) IN ('2020', '2021', '2022', '2023', '2024')
        ORDER BY year
    """, conn)

    if baseline_df.empty:
        # Fallback: use ±3 days around the same calendar date
        baseline_df = pd.read_sql(f"""
            SELECT SUBSTR(date, 1, 4) as year, AVG(pct_full) as pct_full
            FROM gas_storage_levels
            WHERE country = 'EU'
            AND SUBSTR(date, 6) BETWEEN
                date('{latest_date}', '-3 days', '+0 years')
                AND date('{latest_date}', '+3 days', '+0 years')
            AND SUBSTR(date, 1, 4) IN ('2020', '2021', '2022', '2023', '2024')
            GROUP BY year
        """, conn)

    seasonal_avg = round(baseline_df["pct_full"].mean(), 2) if not baseline_df.empty else None
    seasonal_deficit = round(seasonal_avg - current_pct, 2) if seasonal_avg is not None else None

    # ── Injection pace — current rate ─────────────────────────────────────
    # Rate of change over last INJECTION_PACE_WINDOW_DAYS = 14 days
    # Positive = storage filling, negative = still drawing down
    pace_df = pd.read_sql(f"""
        SELECT date, pct_full
        FROM gas_storage_levels
        WHERE country = 'EU'
        ORDER BY date DESC
        LIMIT {INJECTION_PACE_WINDOW_DAYS}
    """, conn)
    conn.close()

    pace_df = pace_df.sort_values("date").reset_index(drop=True)

    if len(pace_df) >= 2:
        pct_change    = pace_df.iloc[-1]["pct_full"] - pace_df.iloc[0]["pct_full"]
        days_in_window = (pd.to_datetime(pace_df.iloc[-1]["date"]) -
                          pd.to_datetime(pace_df.iloc[0]["date"])).days
        actual_pace   = round(pct_change / days_in_window, 4) if days_in_window > 0 else 0
    else:
        actual_pace = 0

    # ── Required injection pace ───────────────────────────────────────────
    # EU mandate: reach EU_WINTER_TARGET_PCT (90%) by November 1
    # Calculate how many days remain until November 1 of this year
    today         = pd.to_datetime(latest_date)
    current_year  = today.year
    target_date   = pd.to_datetime(f"{current_year}-{EU_WINTER_TARGET_DATE}")

    # If we're past November 1 this year, target is next year's November 1
    if today >= target_date:
        target_date = pd.to_datetime(f"{current_year + 1}-{EU_WINTER_TARGET_DATE}")

    days_to_target   = (target_date - today).days
    gap_to_target    = EU_WINTER_TARGET_PCT - current_pct
    required_pace    = round(gap_to_target / days_to_target, 4) if days_to_target > 0 else 0

    # ── Days-of-coverage deficit ──────────────────────────────────────────
    # How many days behind the required injection pace are we?
    # If actual_pace >= required_pace: on track (positive number = surplus days)
    # If actual_pace < required_pace: behind (negative number = deficit days)
    pace_shortfall = required_pace - actual_pace
    if pace_shortfall > 0:
        # Days behind: shortfall × days remaining
        days_deficit = round(pace_shortfall * days_to_target, 1)
        coverage_status = "BEHIND"
    else:
        days_deficit = round(abs(pace_shortfall) * days_to_target, 1)
        coverage_status = "AHEAD"

    # ── Risk label ────────────────────────────────────────────────────────
    # RED/AMBER/GREEN based on days behind required pace
    # Thresholds: STORAGE_DEFICIT_HIGH = 30 days, STORAGE_DEFICIT_MODERATE = 10 days
    if coverage_status == "BEHIND":
        if days_deficit >= STORAGE_DEFICIT_HIGH:
            risk_label = "RED"
            risk_note  = f"Storage is {days_deficit} days behind required injection pace — serious winter supply risk."
        elif days_deficit >= STORAGE_DEFICIT_MODERATE:
            risk_label = "AMBER"
            risk_note  = f"Storage is {days_deficit} days behind required injection pace — elevated risk, monitoring required."
        else:
            risk_label = "GREEN"
            risk_note  = f"Storage is {days_deficit} days behind required pace — broadly on track."
    else:
        risk_label = "GREEN"
        risk_note  = f"Storage is {days_deficit} days ahead of required injection pace — on track for November target."

    return {
        "latest_date":      latest_date,
        "current_pct":      current_pct,
        "current_twh":      current_twh,
        "seasonal_avg":     seasonal_avg,
        "seasonal_deficit": seasonal_deficit,
        "actual_pace_per_day":   actual_pace,
        "required_pace_per_day": required_pace,
        "days_to_target":   days_to_target,
        "gap_to_target_pct": round(gap_to_target, 2),
        "days_deficit":     days_deficit,
        "coverage_status":  coverage_status,
        "risk_label":       risk_label,
        "risk_note":        risk_note,
        "target_date":      target_date.strftime("%Y-%m-%d"),
        "target_pct":       EU_WINTER_TARGET_PCT,
    }


def get_lng_rebalancing_score(utilization, spread, storage):
    """
    Synthesizes the three module outputs into a single labeled state.

    Inputs: outputs from get_terminal_utilization(), get_jkm_ttf_spread(),
            get_european_storage_coverage()
    Returns: dict with score label, confidence, and plain-English thesis

    SCORING LOGIC:
    Three signals feed into the score:
      1. US utilization — is the relief valve open or maxed out?
      2. Routing signal — are cargoes going east or west?
      3. Storage risk   — is Europe on track for winter?

    The score reflects the Atlantic Basin rebalancing state:
      CRITICAL DEFICIT — system under maximum stress
      DEFICIT          — meaningful supply gap, elevated risk
      BALANCED         — market finding equilibrium
      SURPLUS          — supply exceeds demand, comfortable

    All thresholds are documented judgment calls.
    """

    # ── Guard against errors in upstream functions ────────────────────────
    if "error" in utilization or "error" in spread or "error" in storage:
        return {
            "score":      "UNKNOWN",
            "confidence": "LOW",
            "thesis":     "One or more data sources returned an error — score cannot be computed.",
            "signals":    {}
        }

    # ── Extract key signals ───────────────────────────────────────────────
    us_util        = utilization.get("us_utilization", 0)
    routing        = spread.get("routing_signal", "NEUTRAL")
    storage_risk   = storage.get("risk_label", "GREEN")
    days_deficit   = storage.get("days_deficit", 0)
    coverage       = storage.get("coverage_status", "AHEAD")
    seasonal_def   = storage.get("seasonal_deficit", 0)
    spread_val     = spread.get("spread_7d_avg", 0)
    inflection     = spread.get("inflection_date")
    peak_spread    = spread.get("peak_spread", 0)

    # ── Score logic ───────────────────────────────────────────────────────
    # CRITICAL DEFICIT: all three signals pointing to maximum stress
    # - US terminals maxed out (>100% utilization)
    # - Cargoes routing to Asia (spread above threshold)
    # - Europe seriously behind on storage (RED risk label)
    if (us_util > UTILIZATION_HIGH and
        routing == "ASIA" and
        storage_risk == "RED"):
        score = "CRITICAL DEFICIT"
        confidence = "HIGH"

    # DEFICIT: two or more signals pointing to stress
    # - US terminals at high utilization AND either Asia routing or Amber/Red storage
    # - OR: Asia routing AND storage behind
    elif (us_util > UTILIZATION_HIGH and
          (routing == "ASIA" or storage_risk in ("RED", "AMBER"))):
        score = "DEFICIT"
        confidence = "HIGH"

    elif (routing == "ASIA" and
          storage_risk in ("RED", "AMBER")):
        score = "DEFICIT"
        confidence = "MEDIUM"

    elif (us_util > UTILIZATION_HIGH and
          coverage == "BEHIND" and
          days_deficit >= STORAGE_DEFICIT_MODERATE):
        score = "DEFICIT"
        confidence = "MEDIUM"

    # BALANCED: mixed signals — some stress but system coping
    # - Routing transitioning (NEUTRAL) with moderate storage deficit
    # - OR: utilization high but storage roughly on track
    elif (routing == "NEUTRAL" and
          storage_risk == "AMBER"):
        score = "BALANCED"
        confidence = "MEDIUM"

    elif (routing in ("NEUTRAL", "EUROPE") and
          storage_risk == "GREEN" and
          us_util > UTILIZATION_NORMAL):
        score = "BALANCED"
        confidence = "MEDIUM"

    # SURPLUS: all signals pointing to comfortable supply state
    elif (routing == "EUROPE" and
          storage_risk == "GREEN" and
          coverage == "AHEAD"):
        score = "SURPLUS"
        confidence = "HIGH"

    # Default — mixed signals that don't fit above categories
    else:
        score = "BALANCED"
        confidence = "LOW"

    # ── Plain-English thesis ──────────────────────────────────────────────
    # This is what the dashboard displays as the "Current Market View"
    # It must commit to a position — not just describe the data
    # One or two sentences maximum

    if score == "CRITICAL DEFICIT":
        thesis = (
            f"The Atlantic Basin is under maximum supply stress — US terminals at {us_util}% utilization "
            f"with cargoes routing to Asia and European storage {days_deficit} days behind required pace."
        )
    elif score == "DEFICIT" and routing == "ASIA":
        thesis = (
            f"Supply rebalancing remains incomplete — US terminals at {us_util}% utilization are maxed out "
            f"while the Asia routing signal pulls cargoes east, leaving Europe {days_deficit} days behind "
            f"its November storage target."
        )
    elif score == "DEFICIT":
        thesis = (
            f"Atlantic Basin in deficit — US export capacity is near maximum at {us_util}% utilization "
            f"and European storage is {days_deficit} days behind required injection pace "
            f"({storage.get('current_pct')}% vs {storage.get('seasonal_avg')}% seasonal average)."
        )
    elif score == "BALANCED" and routing == "NEUTRAL":
        thesis = (
            f"Market transitioning toward balance — cargo routing signal has returned to neutral "
            f"(7-day spread ${spread_val:.2f}/MMBtu) but European storage remains {days_deficit} days "
            f"behind the November 90% target, reflecting damage from the peak crisis period."
        )
    elif score == "BALANCED":
        thesis = (
            f"Atlantic Basin broadly balanced — routing signal neutral, US utilization at {us_util}%, "
            f"European storage tracking within acceptable range of seasonal norms."
        )
    else:
        thesis = (
            f"Atlantic Basin in surplus — cargoes routing toward Europe, storage on track, "
            f"US utilization at {us_util}%."
        )

    return {
        "score":      score,
        "confidence": confidence,
        "thesis":     thesis,
        "signals": {
            "us_utilization":  us_util,
            "routing_signal":  routing,
            "storage_risk":    storage_risk,
            "days_deficit":    days_deficit,
            "spread_7d":       spread_val,
            "seasonal_deficit": seasonal_def,
        }
    }


def log_to_db(utilization, spread, storage, score):
    """
    Writes one row to lng_rebalancing_log table after every run.
    Table must exist — created in setupdb.py (Step 16).

    One row per run. This table is what the Phase 5 dashboard reads
    to show historical trend of the LNG Rebalancing Score over time.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO lng_rebalancing_log (
                run_date,
                latest_lng_date,
                us_utilization,
                routing_signal,
                spread_7d,
                jkm_price,
                ttf_price,
                storage_pct,
                storage_twh,
                seasonal_deficit,
                days_deficit,
                coverage_status,
                storage_risk,
                rebalancing_score,
                confidence,
                thesis,
                logged_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date.today().isoformat(),
            utilization.get("latest_date"),
            utilization.get("us_utilization"),
            spread.get("routing_signal"),
            spread.get("spread_7d_avg"),
            spread.get("jkm"),
            spread.get("ttf"),
            storage.get("current_pct"),
            storage.get("current_twh"),
            storage.get("seasonal_deficit"),
            storage.get("days_deficit"),
            storage.get("coverage_status"),
            storage.get("risk_label"),
            score.get("score"),
            score.get("confidence"),
            score.get("thesis"),
            datetime.now().isoformat()
        ))
        conn.commit()
        print("✅ Run logged to lng_rebalancing_log table")
    except Exception as e:
        print(f"  Log error: {e}")
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 52)
    print("   LNG CARGO FLOW & ATLANTIC BASIN MODULE")
    print("=" * 52)
    print(f"   Run date: {date.today().isoformat()}")
    print("=" * 52)

    # Step 11 — Terminal utilization
    print("\n[1/4] Computing terminal utilization...")
    utilization = get_terminal_utilization()

    # Step 12 — JKM-TTF spread
    print("\n[2/4] Computing JKM-TTF spread...")
    spread = get_jkm_ttf_spread()

    # Step 13 — European storage coverage
    print("\n[3/4] Computing European storage coverage...")
    storage = get_european_storage_coverage()

    # Step 14 — Rebalancing score
    print("\n[4/4] Computing LNG Rebalancing Score...")
    score = get_lng_rebalancing_score(utilization, spread, storage)

    # Step 15 — Log to database
    log_to_db(utilization, spread, storage, score)

    print("\n" + "=" * 52)
    print("   Run complete.")
    print("=" * 52)


if __name__ == "__main__":
    main()