# ================================================================
# SUPPLY GAP CONSTANTS — supply_gap_constants.py
# All values verified against primary sources, May 2026
# ================================================================

# --- Normal Hormuz Flow ---
HORMUZ_NORMAL_CRUDE_MBD = 15.0
# IEA Strait of Hormuz Factsheet February 2026
# "nearly 15 mb/d of crude oil passed through Hormuz in 2025"
# Crude + condensate only — NOT total oil flows

HORMUZ_NORMAL_TOTAL_OIL_MBD = 20.0
# IEA Strait of Hormuz Factsheet February 2026
# "nearly 20 mb/d of oil exported via the Strait in 2025"
# Includes crude + condensate + petroleum products

HORMUZ_NORMAL_LNG_BCFD = 10.8
# IEA Strait of Hormuz Factsheet February 2026
# Derived: 112 bcm/year × 35.3 / 365 = 10.8 bcf/day
# "just over 112 bcm in 2025, almost 20% of global LNG trade"

# --- Bypass Pipeline Capacity ---
BYPASS_PIPELINES = {
    "UAE ADCOP": {
        "nameplate_mbd": 1.5,
        "current_capacity_mbd": 1.8,
        "currently_used_mbd": 1.1,
        "additional_available_mbd": 0.7,
        # IEA: "leaving room for up to 700 kb/d of additional volumes"
        "source": "IEA Strait of Hormuz Factsheet February 2026"
    },
    "Saudi East-West Pipeline": {
        "design_capacity_mbd": 5.0,
        "reported_capacity_mbd": 7.0,
        "currently_used_mbd": 2.0,
        "spare_capacity_low_mbd": 3.0,
        "spare_capacity_high_mbd": 5.0,
        # IEA: "leaving between 3 and 5 mb/d of spare capacity"
        "source": "IEA Strait of Hormuz Factsheet February 2026"
    },
    "IPSA": {
        "design_capacity_mbd": 1.65,
        "status": "MOTHBALLED — excluded from bypass total",
        # Global Energy Monitor January 2026
        # "taken out of operation in 1990"
        # Saudi Aramco: "not in a stage to be utilised"
        # "As of 2026, no significant updates regarding revival"
        "source": "Global Energy Monitor January 2026"
    },
    "Iran Goreh-Jask": {
        "reported_capacity_mbd": 1.0,
        "status": "NON-OPERATIONAL — excluded from bypass total",
        # IEA: "pipeline and port effectively remain non-operational"
        # IEA: "not considered a viable crude export option"
        "source": "IEA Strait of Hormuz Factsheet February 2026"
    }
}
US_LNG_AGGREGATE_UTILIZATION = 1.136   # 113.6% — from Phase 3 lng_rebalancing.py verified output
US_LNG_TOTAL_EXPORTS_BCFD = 17.5       # 490.5 bcf / 28 days Feb 2026 — Phase 3 verified

TOTAL_BYPASS_AVAILABLE_MBD_LOW = 3.5
TOTAL_BYPASS_AVAILABLE_MBD_HIGH = 5.5
TOTAL_BYPASS_AVAILABLE_MBD_MID = (TOTAL_BYPASS_AVAILABLE_MBD_LOW + TOTAL_BYPASS_AVAILABLE_MBD_HIGH) / 2
# IEA Strait of Hormuz Factsheet February 2026
# "estimated 3.5 to 5.5 mb/d of available capacity"
# Only Saudi EWP and UAE ADCOP counted
# IPSA and Iran Goreh-Jask both excluded

# --- Crude Destination Shares ---
CRUDE_DESTINATION_SHARES = {
    "Asia": 0.80,
    # IEA Factsheet: "80% destined for Asia" — total oil flows
    "Europe": 0.04,
    # IEA Factsheet: "600 kb/d, just 4% of crude flows routed to Europe"
    "Other": 0.16
}
# Source: IEA Strait of Hormuz Factsheet February 2026

# --- LNG Destination Shares ---
LNG_DESTINATION_SHARES = {
    "Asia": 0.90,
    # IEA Factsheet: "almost 90% destined to Asian market"
    "Europe": 0.10,
    # IEA Factsheet: "share of Europe was just over 10%"
}
# Source: IEA Strait of Hormuz Factsheet February 2026

# --- SPR Release ---
SPR_US_RELEASE_RATE_MBD_LOW = 1.0
SPR_US_RELEASE_RATE_MBD_HIGH = 1.5
# S&P Global March 23 2026 — CERAWeek interview
# US Energy Secretary Chris Wright:
# "US SPR to release at rate of 1 million-1.5 million b/d"

SPR_IEA_TOTAL_RATE_MBD = 3.0
# S&P Global March 23 2026 — CERAWeek interview
# Wright: "total IEA coordinated releases should reach 3 million b/d"
# Part of IEA 400 million barrel commitment announced March 11 2026

SPR_RELEASE_START_DATE = "2026-03-17"
# S&P Global March 23 2026
# "first barrels began to flow March 17 2026"

# --- Risk Label Thresholds ---
RISK_THRESHOLDS = {
    "RED": 15,     # >15 days below seasonal norm — rationing risk
    "AMBER": 5,    # 5-15 days below seasonal norm — elevated risk
    "GREEN": 0     # within 5 days — within normal variation
}
# Analytical judgment — documented as judgment call in README
# No external source — thresholds chosen based on EU energy
# emergency framework guidance for storage deficit severity