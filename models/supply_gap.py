"""
supply_gap.py — Phase 4: Supply Gap & Flow Model
=================================================
Capacity accounting model. Reads from existing database tables.
Does NOT call any external API. Does NOT re-fetch any data.

Formula:
    Normal Hormuz flow
    - What is actually getting through   (from Phase 2 anomaly_log)
    = Disrupted volume

    Disrupted volume
    - Bypass pipeline capacity           (hard-coded reference data)
    - SPR release rate                   (hard-coded reference data)
    = Residual gap

    Residual gap × Destination share = Regional gap per region

Output: supply_gap_log table row + printed summary on each daily run.
"""

import sqlite3
import sys
import os
from datetime import datetime, date, timezone

# Allow imports from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.reference.supply_gap_constants import (
    HORMUZ_NORMAL_CRUDE_MBD,
    HORMUZ_NORMAL_LNG_BCFD,
    TOTAL_BYPASS_AVAILABLE_MBD_MID,
    TOTAL_BYPASS_AVAILABLE_MBD_LOW,
    TOTAL_BYPASS_AVAILABLE_MBD_HIGH,
    CRUDE_DESTINATION_SHARES,
    LNG_DESTINATION_SHARES,
    SPR_IEA_TOTAL_RATE_MBD,
    SPR_RELEASE_START_DATE,
    RISK_THRESHOLDS,
    US_LNG_AGGREGATE_UTILIZATION,
    US_LNG_TOTAL_EXPORTS_BCFD,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "gulf_data.db")

def _get_db():
    """Return a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ================================================================
# FUNCTION 1
# ================================================================

def get_crude_supply_gap():
    """
    Calculate the net residual crude supply gap and distribute regionally.
    Reads pct_of_normal from anomaly_log (Phase 2 output).

    Steps:
        A. Read pct_of_normal from anomaly_log
        B. current_throughput = HORMUZ_NORMAL_CRUDE_MBD × (pct_of_normal / 100)
           disrupted_volume   = HORMUZ_NORMAL_CRUDE_MBD - current_throughput
        C. gap_after_bypass   = disrupted_volume - bypass_midpoint
        D. gap_after_spr      = gap_after_bypass - SPR_IEA_TOTAL_RATE_MBD
           (SPR only applied if today >= SPR_RELEASE_START_DATE)
        E. Distribute net gap regionally using CRUDE_DESTINATION_SHARES

    Returns: dict with all intermediate values and regional gaps.
    """
    # --- Step A: read disruption level from Phase 2 ---
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT pct_of_normal FROM anomaly_log ORDER BY logged_at DESC LIMIT 1"
        ).fetchone()

        if row and row["pct_of_normal"] is not None:
            pct_of_normal = float(row["pct_of_normal"])
        else:
            # Fallback: compute pct_of_normal from transit_events directly.
            # Used only when anomaly_log is empty (e.g. first run before
            # tanker_anomaly.py has executed).
            # transit_events uses n_tanker (not transit_count).
            # Baseline = full-year 2025 average, computed inline — same
            # logic as tanker_anomaly.py get_latest_index().
            latest_row = conn.execute("""
                SELECT n_tanker FROM transit_events
                ORDER BY date DESC LIMIT 1
            """).fetchone()
            baseline_row = conn.execute("""
                SELECT AVG(n_tanker) as baseline
                FROM transit_events
                WHERE date >= '2025-01-01' AND date < '2026-01-01'
            """).fetchone()
            if latest_row and baseline_row and baseline_row["baseline"]:
                current  = float(latest_row["n_tanker"] or 0)
                baseline = float(baseline_row["baseline"])
                pct_of_normal = round((current / baseline) * 100, 1) if baseline > 0 else 0.0
            else:
                pct_of_normal = 0.0
            print("  WARNING: anomaly_log empty — fell back to transit_events")
    finally:
        conn.close()

    # --- Step B: throughput and disrupted volume ---
    current_throughput = HORMUZ_NORMAL_CRUDE_MBD * (pct_of_normal / 100)
    disrupted_volume   = HORMUZ_NORMAL_CRUDE_MBD - current_throughput

    # --- Step C: bypass pipeline offset ---
    # Use IEA midpoint (3.5-5.5 Mb/d range → 4.5 Mb/d midpoint)
    # Cap at disrupted_volume — bypass cannot offset more than what is disrupted
    bypass_applied   = min(TOTAL_BYPASS_AVAILABLE_MBD_MID, disrupted_volume)
    gap_after_bypass = disrupted_volume - bypass_applied

    # --- Step D: SPR offset ---
    # Only apply if SPR release has actually started (confirmed March 17 2026)
    spr_start = datetime.strptime(SPR_RELEASE_START_DATE, "%Y-%m-%d").date()
    if date.today() >= spr_start:
        spr_applied = min(SPR_IEA_TOTAL_RATE_MBD, gap_after_bypass)
    else:
        spr_applied = 0.0
        print("  NOTE: SPR release not yet started — offset not applied")

    # Floor at zero — offsets cannot create a surplus in this model
    net_crude_gap = max(0.0, gap_after_bypass - spr_applied)

    # --- Step E: regional distribution ---
    asia_crude_gap   = net_crude_gap * CRUDE_DESTINATION_SHARES["Asia"]
    europe_crude_gap = net_crude_gap * CRUDE_DESTINATION_SHARES["Europe"]
    other_crude_gap  = net_crude_gap * CRUDE_DESTINATION_SHARES["Other"]
    # US is not Hormuz-dependent for crude — net importer from Atlantic Basin
    us_crude_gap     = 0.0

    return {
        "pct_of_normal":      round(pct_of_normal,      1),
        "current_throughput": round(current_throughput,  2),
        "disrupted_volume":   round(disrupted_volume,    2),
        "bypass_applied":     round(bypass_applied,      2),
        "bypass_range":       f"{TOTAL_BYPASS_AVAILABLE_MBD_LOW}–{TOTAL_BYPASS_AVAILABLE_MBD_HIGH} Mb/d (IEA)",
        "spr_applied":        round(spr_applied,         2),
        "net_crude_gap":      round(net_crude_gap,       2),
        "asia_crude_gap":     round(asia_crude_gap,      2),
        "europe_crude_gap":   round(europe_crude_gap,    2),
        "other_crude_gap":    round(other_crude_gap,     2),
        "us_crude_gap":       us_crude_gap,
    }


# ================================================================
# FUNCTION 2
# ================================================================

def get_lng_supply_gap():
    """
    Calculate the LNG supply gap and distribute regionally.
    Reads pct_of_normal from anomaly_log and routing signal from
    lng_rebalancing_log (Phase 3 output).

    Key difference from crude gap:
        - No bypass offset  -- LNG has zero pipeline bypass capacity
        - No SPR equivalent -- there is no coordinated LNG reserve release

    Formula:
        lng_offline    = HORMUZ_NORMAL_LNG_BCFD x (1 - pct_of_normal / 100)
        asia_lng_gap   = lng_offline x LNG_DESTINATION_SHARES["Asia"]
        europe_lng_gap = lng_offline x LNG_DESTINATION_SHARES["Europe"]

    The routing signal does NOT change the physical gap arithmetic.
    It adds narrative context for the dashboard interpretation layer only.

    Returns: dict with gap values, routing signal, and narrative context.
    """
    # --- Read pct_of_normal from anomaly_log (same source as crude gap) ---
    conn = _get_db()
    try:
        
        row = conn.execute(
            "SELECT pct_of_normal FROM anomaly_log ORDER BY logged_at DESC LIMIT 1"
        ).fetchone()
        pct_of_normal = float(row[0]) if row else 0.0


        # --- Read routing signal and days_deficit from lng_rebalancing_log ---
        # Column name is days_deficit — confirmed in Phase 3 audit and setupdb.py schema.
        row = conn.execute(
            "SELECT routing_signal, days_deficit FROM lng_rebalancing_log ORDER BY logged_at DESC LIMIT 1"
        ).fetchone()
        routing_signal = row["routing_signal"] if (row and row["routing_signal"]) else "NEUTRAL"
        days_deficit   = float(row["days_deficit"]) if (row and row["days_deficit"]) else None

    finally:
        conn.close()

    # --- LNG gap arithmetic ---
    lng_offline    = HORMUZ_NORMAL_LNG_BCFD * (1 - pct_of_normal / 100)
    asia_lng_gap   = lng_offline * LNG_DESTINATION_SHARES["Asia"]
    europe_lng_gap = lng_offline * LNG_DESTINATION_SHARES["Europe"]

    # --- Routing context narrative (dashboard only, not used in arithmetic) ---
    if routing_signal == "ASIA":
        routing_context = (
            "US cargoes pulled east -- Europe losing both Qatari LNG "
            "and Atlantic Basin supply simultaneously."
        )
    elif routing_signal == "NEUTRAL":
        routing_context = (
            "Routing transitioning -- US LNG beginning to rebalance toward "
            "Europe as JKM-TTF spread falls below threshold."
        )
    else:  # EUROPE
        routing_context = (
            "US cargoes flowing preferentially toward Europe -- "
            "Atlantic Basin rebalancing partially offsetting storage deficit."
        )

    return {
        "pct_of_normal":         round(pct_of_normal,  1),
        "lng_offline":           round(lng_offline,     2),
        "asia_lng_gap":          round(asia_lng_gap,    2),
        "europe_lng_gap":        round(europe_lng_gap,  2),
        "routing_signal":        routing_signal,
        "routing_context":       routing_context,
        "days_deficit":          days_deficit,
        "us_utilization_pct":    round(US_LNG_AGGREGATE_UTILIZATION * 100, 1),
        "us_total_exports_bcfd": US_LNG_TOTAL_EXPORTS_BCFD,
    }


# ================================================================
# FUNCTION 3
# ================================================================

def get_regional_risk_labels(crude_gap, lng_gap):
    """
    Assign RED / AMBER / GREEN risk labels per region per commodity.

    Thresholds (from RISK_THRESHOLDS constant):
        RED    > 15 days below seasonal norm
        AMBER    5-15 days below seasonal norm
        GREEN  < 5 days below seasonal norm

    Europe LNG  -- uses days_deficit from Phase 3 directly (real GIE data)
    Asia LNG    -- uses gap magnitude proxy (no free-tier Asian storage data)
    Crude       -- uses cumulative drain estimate over crisis duration
    US          -- GREEN for both (net exporter, not Hormuz-dependent)

    NOTE: Asia and crude shortfall figures are ESTIMATES, not real storage
    measurements. Documented as such in README. In an interview: "For Europe
    I used real GIE storage data. For Asia I used a proxy based on gap
    magnitude and crisis duration, and I documented that distinction."

    Args:
        crude_gap: dict returned by get_crude_supply_gap()
        lng_gap:   dict returned by get_lng_supply_gap()

    Returns:
        dict with RED/AMBER/GREEN per region per commodity, plus
        the days-shortfall estimate that produced each label.
    """

    def apply_label(days_shortfall):
        """Apply threshold rules to a days-shortfall figure."""
        if days_shortfall is None:
            return "UNKNOWN"
        if days_shortfall > RISK_THRESHOLDS["RED"]:
            return "RED"
        elif days_shortfall > RISK_THRESHOLDS["AMBER"]:
            return "AMBER"
        else:
            return "GREEN"

    # ---- EUROPE LNG ----
    # Best data we have: Phase 3 computed days_deficit from real GIE storage.
    # 10.7 days behind → AMBER (between 5 and 15 day threshold)
    europe_lng_days = lng_gap["days_deficit"]   # may be None if Phase 3 log empty
    europe_lng_risk = apply_label(europe_lng_days)

    # ---- ASIA LNG ----
    # No free-tier Asian LNG storage data available.
    # Proxy: IEA states LNG via Hormuz = 27% of Asia's total LNG imports.
    # Assume 30% of gap is absorbed by fuel switching and spot reallocation.
    # Remaining 70% is a real shortfall. Accumulate over crisis duration.
    # Express as days-equivalent at Asia's normal daily LNG consumption.
    crisis_start          = date(2026, 3, 4)
    crisis_days           = max(1, (date.today() - crisis_start).days)
    # Derived from two IEA-verified figures:
    #   - Normal LNG via Hormuz: 10.8 Bcf/d (IEA Factsheet Feb 2026)
    #   - 90% of that goes to Asia: 10.8 x 0.90 = 9.72 Bcf/d
    #   - IEA states LNG via Hormuz = 27% of Asia's total LNG imports
    #   - Therefore: 9.72 / 0.27 = 36.0 Bcf/d Asia total imports
    asia_total_imports_bcfd = 36.0
    effective_gap_bcfd    = lng_gap["asia_lng_gap"] * 0.70
    cumulative_bcf        = effective_gap_bcfd * crisis_days
    asia_lng_days         = cumulative_bcf / asia_total_imports_bcfd   # days-equivalent shortfall
    asia_lng_risk         = apply_label(asia_lng_days)

    # ---- CRUDE RISK ----
    # Estimate cumulative crude drain on regional reserves over crisis duration.
    # Net crude gap after bypass + SPR is already computed in crude_gap.
    # Each region's share of that gap has been drawing down strategic reserves
    # since the crisis began.

    # Asia crude:
    # IEA Asia-Oceania SPR commitment: 108.6 Mb over the release period.
    # Approximate daily Asia SPR offset: ~1.5 Mb/d for IEA Asia members.
    # (Non-IEA Asia — China, India — drawing from own reserves at unknown rate.)
    asia_daily_net = max(0.0, crude_gap["asia_crude_gap"] - 1.5)
    asia_crude_cumulative = asia_daily_net * crisis_days
    # Express as days-equivalent at Asia's normal Hormuz crude import rate (~12 Mb/d)
    asia_crude_days = asia_crude_cumulative / 12.0
    asia_crude_risk = apply_label(asia_crude_days)

    # Europe crude:
    # Europe's crude exposure is small (4% share → ~0.25 Mb/d gap).
    # IEA Europe SPR release: 107.5 Mb committed → ~1.65 Mb/d.
    # The SPR release comfortably covers Europe's small crude gap.
    # Net daily Europe crude shortfall is effectively zero.
    europe_daily_net  = max(0.0, crude_gap["europe_crude_gap"] - 1.65)
    europe_crude_days = (europe_daily_net * crisis_days) / 0.6   # normal Europe Hormuz imports ~0.6 Mb/d
    europe_crude_risk = apply_label(europe_crude_days)

    return {
        "Asia": {
            "crude":          asia_crude_risk,
            "crude_days_est": round(asia_crude_days,  1),
            "lng":            asia_lng_risk,
            "lng_days_est":   round(asia_lng_days,    1),
        },
        "Europe": {
            "crude":           europe_crude_risk,
            "crude_days_est":  round(europe_crude_days,  1),
            "lng":             europe_lng_risk,
            "lng_days_behind": round(europe_lng_days, 1) if europe_lng_days is not None else "N/A",
        },
        "US": {
            "crude": "GREEN",
            "lng":   "GREEN",
        }
    }


# ================================================================
# FUNCTION 4
# ================================================================

def get_supply_gap_summary():
    """
    Master function. Calls the three functions above, combines their
    outputs, and generates a single committed thesis statement.
    Returns the full summary dict that gets logged and displayed.

    This is what gets passed to log_to_db() and read by Phase 5 dashboard.
    """
    # --- Call the three functions in order ---
    crude_gap   = get_crude_supply_gap()
    lng_gap     = get_lng_supply_gap()
    risk_labels = get_regional_risk_labels(crude_gap, lng_gap)

    # --- Read trend direction from anomaly_log (Phase 2) ---
    # Used in thesis to describe whether recovery is underway
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT trend_direction, trend_slope FROM anomaly_log ORDER BY logged_at DESC LIMIT 1"
        ).fetchone()
        trend_direction = row["trend_direction"] if row else "UNKNOWN"
        trend_slope     = float(row["trend_slope"]) if (row and row["trend_slope"]) else None
    finally:
        conn.close()

    # --- Build the committed thesis ---
    thesis = _build_thesis(crude_gap, lng_gap, risk_labels, trend_direction)

    return {
        "run_date":        str(date.today()),
        "crude_gap":       crude_gap,
        "lng_gap":         lng_gap,
        "risk_labels":     risk_labels,
        "trend_direction": trend_direction,
        "trend_slope":     trend_slope,
        "summary_thesis":  thesis,
    }


def _label_to_display(label):
    """Convert internal RED/AMBER/GREEN labels to display vocabulary."""
    mapping = {"RED": "CRITICAL", "AMBER": "ELEVATED", "GREEN": "STABLE"}
    return mapping.get(label, label)


def _build_thesis(crude_gap, lng_gap, risk_labels, trend_direction):
    """
    Generate a single committed thesis statement from current signal states.
    Uses if/elif on risk label combinations -- must commit to a position.

    A thesis that hedges all possibilities is not an intelligence output.
    All display labels use CRITICAL/ELEVATED/STABLE vocabulary.
    """
    asia_crude  = risk_labels["Asia"]["crude"]
    asia_lng    = risk_labels["Asia"]["lng"]
    europe_lng  = risk_labels["Europe"]["lng"]
    net_gap     = crude_gap["net_crude_gap"]
    pct_normal  = crude_gap["pct_of_normal"]
    routing     = lng_gap["routing_signal"]
    us_util     = lng_gap["us_utilization_pct"]
    days_behind = lng_gap["days_deficit"]

    # Display labels -- CRITICAL/ELEVATED/STABLE
    asia_crude_d = _label_to_display(asia_crude)
    asia_lng_d   = _label_to_display(asia_lng)
    europe_lng_d = _label_to_display(europe_lng)

    # Recovery note -- appended to all thesis variants
    if trend_direction in ("RECOVERING", "RECOVERING SLOWLY"):
        recovery = (
            f"Transit recovery underway ({trend_direction.lower()}) "
            f"but mine clearance remains the binding constraint on normalisation speed."
        )
    elif trend_direction == "FLAT":
        recovery = "Transit count flat -- no recovery visible despite ceasefire."
    else:
        recovery = "Transit count worsening -- disruption deepening."

    # Main thesis -- committed position based on risk label combination
    if asia_crude == "RED" and europe_lng == "RED":
        thesis = (
            f"Crisis at maximum severity: Hormuz at {pct_normal}% of normal, "
            f"net crude gap {net_gap:.1f} Mb/d after bypass and SPR offsets. "
            f"Asia faces acute crude shortage ({asia_crude_d}); Europe faces critical LNG deficit ({europe_lng_d}). "
            f"{recovery}"
        )

    elif asia_lng == "RED" and europe_lng in ("RED", "AMBER"):
        thesis = (
            f"LNG market under acute stress: Asia at {asia_lng_d} LNG risk "
            f"with Hormuz supplying 27% of Asian imports now offline. "
            f"Europe at {europe_lng_d} LNG risk -- storage {days_behind:.1f} days "
            f"behind required injection pace. "
            f"US system maxed at {us_util:.0f}% utilisation -- no additional relief available. "
            f"{recovery}"
        )

    elif asia_crude in ("RED", "AMBER") and europe_lng in ("RED", "AMBER"):
        thesis = (
            f"Disruption impact distributed but significant: net crude gap {net_gap:.1f} Mb/d "
            f"with Asia at {asia_crude_d} crude risk and Europe at {europe_lng_d} LNG risk. "
            f"Routing signal {routing} -- "
            f"{'Atlantic Basin cargoes returning toward Europe.' if routing == 'NEUTRAL' else 'US cargoes still pulled east, compounding Europe deficit.'} "
            f"{recovery}"
        )

    elif asia_crude == "AMBER" and europe_lng == "GREEN":
        thesis = (
            f"Disruption moderating: Asia crude at {asia_crude_d}, Europe LNG risk resolved to {europe_lng_d}. "
            f"Net crude gap {net_gap:.1f} Mb/d persists but storage deficits are closing. "
            f"{recovery}"
        )

    elif asia_crude == "GREEN" and europe_lng == "GREEN":
        thesis = (
            f"Supply gap resolving: Hormuz at {pct_normal}% of normal, "
            f"net crude gap {net_gap:.1f} Mb/d, both Asia crude and Europe LNG at {_label_to_display('GREEN')}. "
            f"Monitor mine clearance as the final structural constraint on full normalisation."
        )

    else:
        # Catch-all for any combination not explicitly covered above
        thesis = (
            f"Asymmetric disruption: Asia crude {asia_crude_d}, Asia LNG {asia_lng_d}, "
            f"Europe LNG {europe_lng_d}. Net crude gap {net_gap:.1f} Mb/d at "
            f"{pct_normal}% Hormuz throughput. "
            f"{recovery}"
        )

    return thesis


# ================================================================
# LOG TO DB
# ================================================================

def log_to_db(summary):
    """
    Writes one row per run into supply_gap_log.
    """
    conn = _get_db()
    cursor = conn.cursor()

    try:
        crude = summary["crude_gap"]
        lng   = summary["lng_gap"]
        risk  = summary["risk_labels"]

        cursor.execute("""
            INSERT OR REPLACE INTO supply_gap_log (
                run_date,

                pct_of_normal,
                crude_disrupted_mbd,
                bypass_used_mbd,
                spr_offset_mbd,
                crude_gap_net_mbd,

                asia_crude_gap_mbd,
                europe_crude_gap_mbd,
                us_crude_gap_mbd,

                lng_gap_bcfd,
                asia_lng_gap_bcfd,
                europe_lng_gap_bcfd,

                routing_signal,

                asia_crude_risk,
                asia_lng_risk,
                europe_crude_risk,
                europe_lng_risk,
                us_crude_risk,
                us_lng_risk,

                trend_direction,
                trend_slope,

                summary_thesis,
                logged_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            summary["run_date"],

            crude["pct_of_normal"],
            crude["disrupted_volume"],
            crude["bypass_applied"],
            crude["spr_applied"],
            crude["net_crude_gap"],

            crude["asia_crude_gap"],
            crude["europe_crude_gap"],
            crude["us_crude_gap"],

            lng["lng_offline"],
            lng["asia_lng_gap"],
            lng["europe_lng_gap"],

            lng["routing_signal"],

            risk["Asia"]["crude"],
            risk["Asia"]["lng"],
            risk["Europe"]["crude"],
            risk["Europe"]["lng"],
            risk["US"]["crude"],
            risk["US"]["lng"],

            summary["trend_direction"],
            summary["trend_slope"],

            summary["summary_thesis"],
            datetime.utcnow().isoformat()
        ))

        conn.commit()

    finally:
        conn.close()

# ================================================================
# MAIN
# ================================================================

if __name__ == "__main__":
    print("\n⏳ Running supply gap model...")
    summary = get_supply_gap_summary()
    print(summary)
    log_to_db(summary)