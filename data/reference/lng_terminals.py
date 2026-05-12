# data/reference/lng_terminals.py
#
# Static reference file — US LNG export terminal nameplate capacities
#
# PURPOSE:
# Used by models/lng_rebalancing.py — get_terminal_utilization() —
# to compute utilization rate:
#   utilization = actual_volume_bcf / (nameplate_bcf_per_day * days_in_month)
#
# CANONICAL NAMES:
# These names match exactly what is stored in lng_export_volumes.terminal
# after eia_ingestor.py standardization. Any mismatch will cause a
# terminal to drop silently from the utilization calculation.
#
# SOURCES:
# All capacities verified against EIA primary sources:
# - EIA U.S. Liquefaction Capacity Workbook (2024)
# - EIA Today in Energy articles (facility-specific)
# - EIA Short-Term Energy Outlook, March 2026
# - EIA Today in Energy: "The 9th U.S. LNG export terminal, Golden Pass,
#   ships first cargo" (April 2026)
#
# UNITS: nominal baseload nameplate capacity in Bcf/d (billion cubic feet per day)
# Nominal = normal operating conditions, full trains operational
# This is NOT peak capacity (which can exceed nominal by ~10-15%)
#
# UPDATE POLICY:
# Update this file manually when:
# - A new terminal begins commercial operations
# - An existing terminal completes a capacity expansion
# - EIA revises published nameplate figures
# Last verified: May 10, 2026

LNG_TERMINALS = {
    # ── SABINE PASS, LA ─────────────────────────────────────────────────
    # Operator: Cheniere Energy
    # Trains: 6 full-scale trains
    # Largest US LNG export terminal by nominal capacity
    # Source: EIA — "nominal capacity of 3.6 Bcf/d" (explicitly stated)
    "Sabine Pass, LA": {
        "nameplate_bcfd": 3.60,
        "operator": "Cheniere Energy",
        "trains": 6,
        "status": "operational",
        "notes": "Largest US terminal. Train 6 added ~0.76 Bcf/d peak capacity."
    },

    # ── CORPUS CHRISTI, TX ──────────────────────────────────────────────
    # Operator: Cheniere Energy
    # Trains: Stages 1-2 (3 trains each) + Stage 3 (7 midscale trains, ramping)
    # Total nominal once all Stage 3 trains operational: 3.1 Bcf/d
    # As of early 2026: Trains 1-4 of Stage 3 operational, Train 5 completed March 2026
    # Source: EIA — "total nominal capacity of Corpus Christi LNG will be 3.1 Bcf/d"
    # NOTE: Capacity ramping through 2026 as Stage 3 trains come online.
    #       Using full 3.1 Bcf/d nameplate — utilization will appear lower
    #       until all trains are operational. This is correct behavior.
    "Corpus Christi, TX": {
        "nameplate_bcfd": 3.10,
        "operator": "Cheniere Energy",
        "trains": 13,  # Stages 1+2 (6 trains) + Stage 3 (7 midscale trains)
        "status": "operational — Stage 3 ramping",
        "notes": "Stage 3 Trains 1-4 operational by early 2026. Train 5 completed March 2026. Full capacity by late 2026."
    },

    # ── FREEPORT, TX ────────────────────────────────────────────────────
    # Operator: Freeport LNG Development
    # Trains: 3 full-scale trains
    # Source: EIA liquefaction capacity workbook
    "Freeport, TX": {
        "nameplate_bcfd": 2.14,
        "operator": "Freeport LNG Development",
        "trains": 3,
        "status": "operational",
        "notes": "Train 4 approved but not yet operational as of May 2026."
    },

    # ── PLAQUEMINES, LA ─────────────────────────────────────────────────
    # Operator: Venture Global LNG
    # Trains: 36 modular trains across 2 phases (Phase 1: 18 trains)
    # First cargo: December 2024
    # Source: EIA — "second-largest in the United States after Sabine Pass LNG,
    #         which has a nominal capacity of 3.6 Bcf/d" → Plaquemines = 2.6 Bcf/d
    # NOTE: Capacity still ramping through 2026 as trains commission sequentially.
    #       As of mid-2025, operating capacity was ~17 mtpa (trains 1-24).
    "Plaquemines, LA": {
        "nameplate_bcfd": 2.60,
        "operator": "Venture Global LNG",
        "trains": 36,  # Phase 1 (18) + Phase 2 (18), ramping
        "status": "operational — ramping",
        "notes": "First cargo Dec 2024. Commissioning of all trains through end of 2026. DOE approved 13% export increase March 2026."
    },

    # ── CAMERON, LA ─────────────────────────────────────────────────────
    # Operator: Sempra LNG
    # Trains: 3 full-scale trains
    # Source: EIA liquefaction capacity workbook
    # NOTE: Separate from Calcasieu Pass — confirmed by overlapping date ranges
    #       and volume data in lng_export_volumes audit (Step 1, Phase 3)
    "Cameron, LA": {
        "nameplate_bcfd": 1.70,
        "operator": "Sempra LNG",
        "trains": 3,
        "status": "operational",
        "notes": "Cameron LNG (Sempra). Distinct from Calcasieu Pass (Venture Global) — confirmed separate terminal in Phase 3 audit."
    },

    # ── CALCASIEU PASS, LA ──────────────────────────────────────────────
    # Operator: Venture Global LNG
    # Trains: 18 mid-scale modular trains (9 blocks × 2 trains)
    # Source: EIA — "10 mtpa nameplate" → converted to Bcf/d using EIA factor
    #         Each train: 0.56 mtpa or 0.07 Bcf/d (EIA liquefaction capacity workbook)
    # Formal commercial operation began April 2025 (delayed 3 years from actual ops)
    # Named variant "Cameron (Calcasieu Pass), LA" standardized to this name
    "Calcasieu Pass, LA": {
        "nameplate_bcfd": 1.20,
        "operator": "Venture Global LNG",
        "trains": 18,
        "status": "operational",
        "notes": "Began formal commercial operation April 2025. Named 'Cameron (Calcasieu Pass), LA' in EIA data — standardized in Phase 3 audit."
    },

    # ── COVE POINT, MD ──────────────────────────────────────────────────
    # Operator: Berkshire Hathaway Energy (formerly Dominion Energy)
    # Trains: 1 full-scale train
    # Source: EIA liquefaction capacity workbook
    "Cove Point, MD": {
        "nameplate_bcfd": 0.75,
        "operator": "Berkshire Hathaway Energy",
        "trains": 1,
        "status": "operational",
        "notes": "Only East Coast LNG export terminal. Single train."
    },

    # ── ELBA ISLAND, GA ─────────────────────────────────────────────────
    # Operator: Shell (all output contracted)
    # Trains: 10 small modular liquefaction units
    # Source: EIA — "10 small modular liquefaction units with a combined capacity of 0.33 Bcf/d"
    #         Each unit: 0.25 mtpa or 0.03 Bcf/d (EIA liquefaction capacity workbook)
    "Elba Island, GA": {
        "nameplate_bcfd": 0.33,
        "operator": "Shell",
        "trains": 10,  # small modular units
        "status": "operational",
        "notes": "Smallest operational terminal. All output contracted to Shell. Capacity optimization underway through 2027 (+0.4 mtpa)."
    },
}

# ────────────────────────────────────────────────────────────────────────
# TERMINALS NOT IN DATABASE — FOR REFERENCE ONLY
# ────────────────────────────────────────────────────────────────────────
# Golden Pass, TX — began exports April 23, 2026 (Train 1 only)
#   Nominal capacity (full build): 2.0 Bcf/d (3 trains × 0.7 Bcf/d)
#   Operator: QatarEnergy (70%) / ExxonMobil (30%)
#   NOT in lng_export_volumes — data stops Feb 2026, before first cargo
#   Will appear in database when EIA publishes April/May 2026 export data
#   Add to this file and to LNG_TERMINALS dict at that time.
# ────────────────────────────────────────────────────────────────────────

# Total nameplate capacity of terminals currently in database
TOTAL_NAMEPLATE_BCFD = sum(t["nameplate_bcfd"] for t in LNG_TERMINALS.values())

# Days per month lookup — used for monthly utilization calculation
# utilization = volume_bcf / (nameplate_bcfd * days_in_month)
DAYS_IN_MONTH = {
    "01": 31, "02": 28, "03": 31, "04": 30,
    "05": 31, "06": 30, "07": 31, "08": 31,
    "09": 30, "10": 31, "11": 30, "12": 31
}

# Leap year February override — apply when year is divisible by 4
DAYS_IN_MONTH_LEAP_FEB = 29


def get_nameplate(terminal_name):
    """
    Returns nameplate capacity in Bcf/d for a given terminal name.
    Returns None if terminal not found — caller must handle this case
    to avoid silent drops from utilization calculation.
    """
    terminal = LNG_TERMINALS.get(terminal_name)
    if terminal:
        return terminal["nameplate_bcfd"]
    return None


def get_days_in_month(period):
    """
    Returns number of days in a month given a YYYY-MM period string.
    Handles leap year February automatically.
    Example: get_days_in_month('2026-02') → 28
             get_days_in_month('2024-02') → 29
    """
    year, month = period.split("-")
    days = DAYS_IN_MONTH[month]
    # Leap year check for February
    if month == "02" and int(year) % 4 == 0:
        days = DAYS_IN_MONTH_LEAP_FEB
    return days


if __name__ == "__main__":
    print("US LNG Export Terminal Reference — Nameplate Capacities")
    print("=" * 60)
    for name, info in LNG_TERMINALS.items():
        print(f"{name:<25} {info['nameplate_bcfd']:>6.2f} Bcf/d  [{info['status']}]")
    print("-" * 60)
    print(f"{'TOTAL (8 terminals)':<25} {TOTAL_NAMEPLATE_BCFD:>6.2f} Bcf/d")
    print()
    print("Note: Golden Pass (2.0 Bcf/d) not included — first cargo")
    print("      April 2026, not yet in database as of May 2026.")