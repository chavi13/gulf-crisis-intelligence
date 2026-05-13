"""
dashboard/app.py
----------------
Gulf Crisis Supply Intelligence System — Phase 5 Dashboard
Streamlit multi-tab dashboard reading from gulf_data.db.

Tabs:
    1. Overview      — thesis block + headline metrics from all three modules
    2. Tanker        — Hormuz transit anomaly index, recovery trend, AIS events
    3. LNG           — JKM-TTF spread, US utilization, European storage
    4. Supply Gap    — regional gap table, waterfall, assumptions

Run from project root:
    streamlit run dashboard/app.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Import all database queries ────────────────────────────────────────────────
from db import (
    check_db_connection,
    get_latest_tanker_metrics,
    get_latest_lng_metrics,
    get_latest_supply_gap_metrics,
    get_crisis_context,
    get_transit_history,
    get_anomaly_log_history,
    get_price_history,
    get_terminal_utilization,
    get_european_storage,
    get_storage_seasonal_baseline,
    get_storage_yoy_level,
    get_supply_gap_log_history,
)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG — must be the first Streamlit call
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Gulf Crisis Supply Intelligence",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════════════════════════════════════════════════════════════════════
# STYLING — dark terminal theme injected via markdown
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
/* ── Google Font import ─────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

/* ── Root variables ─────────────────────────────────────────────── */
:root {
    --bg-primary:    #0a0e1a;
    --bg-secondary:  #111827;
    --bg-card:       #1a2235;
    --bg-card-hover: #1e2a42;
    --border:        #2a3a55;
    --text-primary:  #e8edf5;
    --text-secondary:#8a9bb5;
    --text-muted:    #4a5a72;
    --accent-amber:  #f59e0b;
    --accent-red:    #ef4444;
    --accent-green:  #22c55e;
    --accent-blue:   #3b82f6;
    --accent-teal:   #14b8a6;
    --font-mono:     'IBM Plex Mono', monospace;
    --font-sans:     'IBM Plex Sans', sans-serif;
}

/* ── Global overrides ───────────────────────────────────────────── */
.stApp {
    background-color: var(--bg-primary);
    color: var(--text-primary);
    font-family: var(--font-sans);
}

/* Hide Streamlit branding */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
[data-testid="stSidebarCollapseButton"] { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }

/* Tighten top margin — default block-container leaves a large gap */
[data-testid="stHeader"] {
    display: none !important;
    height: 0 !important;
}
[data-testid="stDecoration"] {
    display: none !important;
}
section.main > div.block-container,
.main > div.block-container {
    padding-top: 0.75rem !important;
    padding-bottom: 2rem !important;
}

/* ── Sidebar ────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background-color: var(--bg-secondary);
    border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] * {
    color: var(--text-primary) !important;
}

/* ── Tabs — sticky bar while scrolling main content ───────────────── */
.stTabs [data-baseweb="tab-list"] {
    position: sticky;
    top: 0;
    z-index: 1000;
    background-color: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    gap: 0;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.45);
}
.stTabs [data-baseweb="tab"] {
    background-color: transparent;
    color: var(--text-secondary) !important;
    font-family: var(--font-sans);
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    padding: 0.75rem 1.5rem;
    border-bottom: 2px solid transparent;
}
.stTabs [aria-selected="true"] {
    color: var(--accent-amber) !important;
    border-bottom: 2px solid var(--accent-amber) !important;
    background-color: transparent !important;
}

/* ── Metric cards ───────────────────────────────────────────────── */
.metric-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    min-height: 160px;
    height: 100%;
    box-sizing: border-box;
    overflow: visible;
    display: flex;
    flex-direction: column;
}

.metric-label {
    font-family: var(--font-sans);
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-secondary);
    margin-bottom: 0.4rem;
}
.metric-value {
    font-family: var(--font-mono);
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.1;
}
.metric-sub {
    font-family: var(--font-sans);
    font-size: 0.88rem;
    color: var(--text-secondary);
    margin-top: 0.4rem;
    line-height: 1.4;
}
.metric-timestamp {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: auto;
    padding-top: 0.75rem;
}

/* ── Overview tab: Headline Metrics row (three cards, CSS Grid) ─── */
.headline-metrics-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1rem;
    align-items: stretch;
    margin-bottom: 1rem;
}
.headline-metrics-grid > .overview-headline-card {
    margin-bottom: 0;
    height: 100%;
    align-self: stretch;
}
/* ── Key Numbers: EU Storage — badge beside % value ─────────────── */
.key-numbers-storage-value-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 0.65rem;
    margin-top: 0.1rem;
}
.key-numbers-storage-value-row .metric-value {
    margin: 0;
    line-height: 1.1;
}
.key-numbers-storage-value-row .key-numbers-storage-badge {
    flex-shrink: 0;
    display: flex;
    align-items: center;
}

.overview-headline-card {
    min-height: 268px;
    height: 100%;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
}
.overview-headline-card .overview-headline-body {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    min-height: 0;
}
.overview-headline-card .metric-label {
    font-size: 0.88rem;
}
.overview-headline-card .metric-value {
    font-size: 1.12rem;
    line-height: 1.2;
}
.overview-headline-card .metric-value .headline-keyword {
    font-family: var(--font-mono);
    font-size: 1.48rem;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.15;
    letter-spacing: -0.02em;
}
.overview-headline-card .metric-sub {
    font-size: 0.95rem;
    line-height: 1.45;
}
.overview-headline-card .metric-timestamp {
    font-size: 0.82rem;
    margin-top: auto;
    padding-top: 0.85rem;
    flex-shrink: 0;
    align-self: stretch;
}
.overview-headline-card .overview-risk-table {
    font-size: 0.92rem;
}
.overview-headline-card .overview-risk-table tr:first-child td {
    font-size: 0.74rem;
}

.headline-mono-emphasis {
    font-family: var(--font-mono);
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--text-primary);
}

/* Headline Metrics — cards 1 & 2 only (must follow base .overview-headline-card rules) */
.headline-metrics-grid > .overview-headline-card:nth-child(-n+2) .metric-label {
    font-size: 0.92rem;
    margin-bottom: 0.45rem;
}
.headline-metrics-grid > .overview-headline-card:nth-child(-n+2) .metric-value {
    font-size: 1.2rem;
    line-height: 1.25;
}
.headline-metrics-grid > .overview-headline-card:nth-child(-n+2) .metric-value .headline-keyword {
    font-size: 1.56rem;
}
.headline-metrics-grid > .overview-headline-card:nth-child(-n+2) .metric-sub {
    font-size: 1.02rem;
    line-height: 1.55;
    margin-top: 0.5rem;
}
.headline-metrics-grid > .overview-headline-card:nth-child(-n+2) .metric-sub:first-of-type {
    margin-top: 0.35rem;
}
.headline-metrics-grid > .overview-headline-card:nth-child(-n+2) .metric-timestamp {
    font-size: 0.84rem;
    padding-top: 0.9rem;
}

/* Key Numbers — all four cards */
.key-numbers-card {
    min-height: 158px;
    height: 100%;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
}
.key-numbers-card .metric-label {
    font-size: 0.88rem;
    margin-bottom: 0.3rem;
    flex-shrink: 0;
    min-height: 2.4rem;
    display: flex;
    align-items: flex-start;
}
.key-numbers-card .key-numbers-value-slot {
    flex: 0 0 3.5rem;
    display: flex;
    align-items: flex-start;
    overflow: visible;
}
.key-numbers-card .metric-value,
.key-numbers-card .key-numbers-storage-value-row .metric-value {
    font-size: 1.62rem;
    line-height: 1.12;
}
.key-numbers-card .metric-sub {
    font-size: 1.02rem;
    line-height: 1.52;
    margin-top: 0.45rem;
    flex-shrink: 0;
}
.key-numbers-card .key-numbers-storage-value-row {
    margin-top: 0.12rem;
}

/* Tanker tab — Hormuz Transit Anomaly Index */
/* Primary signal card (left, dominant) */
.ta-primary-card {
    background: var(--bg-card);
    border: 1px solid rgba(239,68,68,0.35);
    background: linear-gradient(135deg, #1e1828 0%, #1a2235 100%);
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 0;
}
.ta-primary-card .ta-label {
    font-family: var(--font-sans);
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
}
.ta-primary-card .ta-number-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
}
.ta-primary-card .ta-big-value {
    font-family: var(--font-mono);
    font-size: 2.8rem;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1;
}
.ta-primary-card .ta-sub {
    font-family: var(--font-sans);
    font-size: 0.82rem;
    color: var(--text-secondary);
    line-height: 1.5;
    margin-top: 0.2rem;
}
.ta-primary-card .ta-sub + .ta-sub {
    margin-top: 0.2rem;
}

/* Secondary card (trend) */
.ta-secondary-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
}
.ta-secondary-card .ta-label {
    font-family: var(--font-sans);
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
}
.ta-secondary-card .ta-value {
    font-family: var(--font-mono);
    font-size: 1.35rem;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.25;
    margin-bottom: 0.5rem;
}
.ta-secondary-card .ta-sub {
    font-family: var(--font-sans);
    font-size: 0.82rem;
    color: var(--text-secondary);
    line-height: 1.5;
}

/* Small cards (operational + metadata, stacked right) */
.ta-small-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1.25rem;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.ta-small-card .ta-label {
    font-family: var(--font-sans);
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 0.35rem;
}
.ta-small-card .ta-value {
    font-family: var(--font-mono);
    font-size: 1.2rem;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.2;
    margin-bottom: 0.3rem;
}
.ta-small-card .ta-sub {
    font-family: var(--font-sans);
    font-size: 0.78rem;
    color: var(--text-secondary);
    line-height: 1.45;
}
.ta-small-card .ta-sub + .ta-sub {
    margin-top: 0.2rem;
}
/* Last updated — dimmer */
.ta-meta-card {
    background: transparent;
    border: 1px solid var(--border);
    opacity: 0.75;
}




/* Supply Gap tab — regional + extrapolation tables (pandas HTML) */
table.supply-gap-table {
    width: 100%;
    border-collapse: collapse;
}
table.supply-gap-table th,
table.supply-gap-table td {
    text-align: center !important;
    vertical-align: middle;
    padding: 0.5rem 0.65rem;
}


/* ── Thesis block ───────────────────────────────────────────────── */
.thesis-block {
    background: linear-gradient(135deg, #1a2235 0%, #0f172a 100%);
    border: 1px solid var(--accent-amber);
    border-left: 4px solid var(--accent-amber);
    border-radius: 8px;
    padding: 1.5rem 2rem;
    margin-bottom: 2rem;
}
.thesis-label {
    font-family: var(--font-sans);
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--accent-amber);
    margin-bottom: 0.75rem;
}
.thesis-text {
    font-family: var(--font-sans);
    font-size: 1.15rem;
    font-weight: 400;
    color: var(--text-primary);
    line-height: 1.7;
}

/* ── Risk badges ────────────────────────────────────────────────── */
.badge-red {
    display: inline-block;
    background: rgba(239,68,68,0.15);
    color: #ef4444;
    border: 1px solid rgba(239,68,68,0.4);
    border-radius: 4px;
    padding: 0.35rem 0.6rem;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.05em;
}
.badge-amber {
    display: inline-block;
    background: rgba(245,158,11,0.15);
    color: #f59e0b;
    border: 1px solid rgba(245,158,11,0.4);
    border-radius: 4px;
    padding: 0.35rem 0.6rem;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.05em;
}
.badge-green {
    display: inline-block;
    background: rgba(34,197,94,0.15);
    color: #22c55e;
    border: 1px solid rgba(34,197,94,0.4);
    border-radius: 4px;
    padding: 0.35rem 0.6rem;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.05em;
}
.badge-critical {
    display: inline-block;
    background: rgba(239,68,68,0.25);
    color: #ff6b6b;
    border: 1px solid rgba(239,68,68,0.6);
    border-radius: 4px;
    padding: 0.35rem 0.6rem;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.05em;
}

/* ── Section headers ────────────────────────────────────────────── */
.section-header {
    font-family: var(--font-sans);
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-secondary);
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
    margin-bottom: 1.25rem;
    margin-top: 2rem;
}

/* ── Interpretation box ─────────────────────────────────────────── */
.interpretation-box {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent-teal);
    border-radius: 6px;
    padding: 1rem 1.25rem;
    margin-top: 1.5rem;
}
.interpretation-label {
    font-family: var(--font-sans);
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--accent-teal);
    margin-bottom: 0.5rem;
}
.interpretation-text {
    font-family: var(--font-sans);
    font-size: 0.95rem;
    color: var(--text-secondary);
    line-height: 1.65;
}

/* ── Extrapolation table note ───────────────────────────────────── */
.extrapolation-note {
    font-family: var(--font-mono);
    font-size: 0.68rem;
    color: var(--accent-amber);
    letter-spacing: 0.04em;
    margin-bottom: 0.5rem;
}

/* ── Info note ──────────────────────────────────────────────────── */
.info-note {
    background: rgba(59,130,246,0.08);
    border: 1px solid rgba(59,130,246,0.25);
    border-radius: 6px;
    padding: 0.75rem 1rem;
    font-family: var(--font-sans);
    font-size: 0.9rem;
    color: var(--text-secondary);
    line-height: 1.5;
    margin-top: 0.75rem;
}

/* ── Streamlit dataframe overrides ──────────────────────────────── */
.stDataFrame {
    background: var(--bg-card) !important;
}

/* ── Divider ────────────────────────────────────────────────────── */
hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 1.5rem 0;
}

/* ── Sidebar toggle button — make it visible ────────────────────── */
button[kind="header"] {
    background-color: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    color: var(--accent-amber) !important;
    border-radius: 4px !important;
    opacity: 1 !important;
}
button[kind="header"]:hover {
    background-color: var(--bg-card-hover) !important;
    border-color: var(--accent-amber) !important;
}
[data-testid="collapsedControl"] {
    background-color: var(--bg-card) !important;
    border: 1px solid var(--accent-amber) !important;
    border-radius: 4px !important;
    color: var(--accent-amber) !important;
    opacity: 1 !important;
    visibility: visible !important;
}
[data-testid="collapsedControl"]:hover {
    background-color: var(--bg-card-hover) !important;
}
/* ── Sidebar toggle button ──────────────────────────────────────── */
[data-testid="stSidebarCollapseButton"] button {
    background-color: #1a2235 !important;
    border: 1px solid #f59e0b !important;
    border-radius: 4px !important;
    color: #f59e0b !important;
    opacity: 1 !important;
    visibility: visible !important;
}
[data-testid="stSidebarCollapseButton"] button svg {
    fill: #f59e0b !important;
    stroke: #f59e0b !important;
}

/* ── Custom hover tooltips ──────────────────────────────────────── */
.has-tooltip {
    position: relative;
    display: inline-block;
}
.has-tooltip .tooltip-text {
    visibility: hidden;
    opacity: 0;
    background: #1a2235;
    color: #e8edf5;
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 0.78rem;
    font-weight: 400;
    line-height: 1.5;
    border: 1px solid #2a3a55;
    border-radius: 6px;
    padding: 0.6rem 0.85rem;
    position: absolute;
    z-index: 99999;
    top: 120%;
    right: 0;
    width: 240px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.6);
    transition: opacity 0.15s ease;
    pointer-events: none;
    white-space: normal;
    word-wrap: break-word;
}
.has-tooltip:hover .tooltip-text {
    visibility: visible;
    opacity: 1;
}

/* ── Styled dropdown ────────────────────────────────────────────── */
details.info-dropdown {
    background: rgba(59,130,246,0.08);
    border: 1px solid rgba(59,130,246,0.25);
    border-radius: 6px;
    margin-top: 0.75rem;
}
details.info-dropdown summary {
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 0.88rem;
    font-weight: 600;
    color: #e8edf5;
    padding: 0.75rem 1rem;
    cursor: pointer;
    list-style: none;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
details.info-dropdown summary::-webkit-details-marker { display: none; }
details.info-dropdown summary::after {
    content: '▾';
    margin-left: auto;
    color: #8a9bb5;
    font-size: 0.9rem;
    transition: transform 0.2s;
}
details.info-dropdown[open] summary::after {
    transform: rotate(180deg);
}
details.info-dropdown .dropdown-body {
    padding: 0.75rem 1rem 1rem 1rem;
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 0.85rem;
    color: #8a9bb5;
    line-height: 1.7;
    border-top: 1px solid rgba(59,130,246,0.15);
}
/* ── Expander content background fix ───────────────────────────── */
div[data-testid="stExpander"] details {
    background-color: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
}
div[data-testid="stExpander"] div[role="region"] {
    background-color: var(--bg-card) !important;
}
div[data-testid="stExpander"] summary {
    color: var(--text-primary) !important;
    background-color: var(--bg-card) !important;
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def risk_badge(label: str) -> str:
    """Return an HTML risk badge with custom hover tooltip."""
    TOOLTIPS = {
        "RED":      "Severe disruption — transit or storage deficit exceeds emergency thresholds. Immediate market impact expected.",
        "AMBER":    "Meaningful disruption — conditions are 5–15 days behind required pace or significantly below normal. Monitoring required.",
        "GREEN":    "Within normal operating range — no significant disruption detected.",
        "CRITICAL": "Historically extreme disruption — z-score below -20, more than 90% below the pre-crisis baseline of 103 ships/day.",
    }
    if label is None:
        return '<span class="has-tooltip"><span class="badge-amber">UNKNOWN</span><span class="tooltip-text">Status unknown — data may not yet be available.</span></span>'
    label = label.upper()
    if label == "RED":
        return f'<span class="has-tooltip"><span class="badge-red">CRITICAL</span><span class="tooltip-text">{TOOLTIPS["RED"]}</span></span>'
    elif label == "AMBER":
        return f'<span class="has-tooltip"><span class="badge-amber">ELEVATED</span><span class="tooltip-text">{TOOLTIPS["AMBER"]}</span></span>'
    elif label == "GREEN":
        return f'<span class="has-tooltip"><span class="badge-green">STABLE</span><span class="tooltip-text">{TOOLTIPS["GREEN"]}</span></span>'
    elif label in ("CRITICAL", "YES"):
        return f'<span class="has-tooltip"><span class="badge-critical">CRITICAL</span><span class="tooltip-text">{TOOLTIPS["CRITICAL"]}</span></span>'
    else:
        return f'<span class="badge-amber">{label}</span>'



def fmt_timestamp(ts: str) -> str:
    """Format a logged_at ISO string to a readable label."""
    if ts is None:
        return "unknown"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%-d %b %Y %H:%M UTC")
    except Exception:
        return ts[:16]


def safe(val, fmt=None, fallback="—"):
    """Safely format a value, returning fallback if None."""
    if val is None:
        return fallback
    if fmt:
        return fmt.format(val)
    return val


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOAD — cached so queries run once per session, not on every interaction
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)  # refresh every 5 minutes
def load_all_data():
    """Load all data from the database in one call. Cached for 5 minutes."""
    return {
        "tanker":      get_latest_tanker_metrics(),
        "lng":         get_latest_lng_metrics(),
        "gap":         get_latest_supply_gap_metrics(),
        "crisis":      get_crisis_context(),
        "transit_df":  get_transit_history(),
        "anomaly_df":  get_anomaly_log_history(),
        "prices_df":   get_price_history(),
        "util_df":     get_terminal_utilization(),
        "storage_df":  get_european_storage(),
        "baseline_df": get_storage_seasonal_baseline(),
        "yoy_level":   get_storage_yoy_level(),
        "gap_log_df":  get_supply_gap_log_history(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE HEALTH CHECK — runs before anything is displayed
# ══════════════════════════════════════════════════════════════════════════════

db_status = check_db_connection()
if not db_status["ok"]:
    st.error(f"**Database connection failed.**\n\n{db_status['error']}")
    if db_status["tables_missing"]:
        st.error(f"Missing tables: {', '.join(db_status['tables_missing'])}")
    st.stop()

# Load all data
data = load_all_data()
tanker = data["tanker"]
lng    = data["lng"]
gap    = data["gap"]
crisis = data["crisis"]


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — Crisis Context (visible across all tabs)
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;
                    letter-spacing:0.15em;text-transform:uppercase;
                    color:#f59e0b;margin-bottom:0.25rem;">
            Gulf Crisis Intelligence
        </div>
        <div style="font-family:'IBM Plex Sans',sans-serif;font-size:1.1rem;
                    font-weight:600;color:#e8edf5;margin-bottom:1.5rem;">
            Supply Monitor
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="section-header" style="margin-top:0;">Crisis Context</div>
    """, unsafe_allow_html=True)

    # Dynamic values from crisis_context table
    mine_status   = crisis.get("mine_clearance_status") or "UNKNOWN"
    diplo_status  = crisis.get("diplomatic_status")     or "UNKNOWN"
    blockade      = crisis.get("us_blockade_active")
    notes         = crisis.get("notes")                 or ""
    as_of         = crisis.get("as_of_date")            or "—"
    updated       = crisis.get("last_updated")          or "—"

    # Map mine clearance status to badge colour
    mine_badge_class = (
        "badge-red"   if mine_status == "IN PROGRESS" else
        "badge-green" if mine_status == "COMPLETE"    else
        "badge-amber"
    )
    # Map diplomatic status to badge colour
    diplo_badge_class = (
        "badge-green" if diplo_status == "CEASEFIRE"                                    else
        "badge-red"   if diplo_status in ("ACTIVE CONFLICT", "CEASEFIRE COLLAPSED")     else
        "badge-amber"
    )
    blockade_badge = (
        '<span class="badge-red">ACTIVE</span>'   if blockade == 1 else
        '<span class="badge-green">INACTIVE</span>'
    )

    # Build badge HTML inline — avoids f-string CSS brace conflicts
    _mine_span    = f'<span style="display:inline-block;padding:0.2rem 0.6rem;border-radius:4px;font-family:monospace;font-size:0.75rem;font-weight:600;background:{"rgba(239,68,68,0.15)" if mine_status == "IN PROGRESS" else "rgba(34,197,94,0.15)" if mine_status == "COMPLETE" else "rgba(245,158,11,0.15)"};color:{"#ef4444" if mine_status == "IN PROGRESS" else "#22c55e" if mine_status == "COMPLETE" else "#f59e0b"};border:1px solid {"rgba(239,68,68,0.4)" if mine_status == "IN PROGRESS" else "rgba(34,197,94,0.4)" if mine_status == "COMPLETE" else "rgba(245,158,11,0.4)"};">{mine_status}</span>'
    _diplo_span   = f'<span style="display:inline-block;padding:0.2rem 0.6rem;border-radius:4px;font-family:monospace;font-size:0.75rem;font-weight:600;background:{"rgba(34,197,94,0.15)" if diplo_status == "CEASEFIRE" else "rgba(239,68,68,0.15)" if diplo_status in ("ACTIVE CONFLICT", "CEASEFIRE COLLAPSED") else "rgba(245,158,11,0.15)"};color:{"#22c55e" if diplo_status == "CEASEFIRE" else "#ef4444" if diplo_status in ("ACTIVE CONFLICT", "CEASEFIRE COLLAPSED") else "#f59e0b"};border:1px solid {"rgba(34,197,94,0.4)" if diplo_status == "CEASEFIRE" else "rgba(239,68,68,0.4)" if diplo_status in ("ACTIVE CONFLICT", "CEASEFIRE COLLAPSED") else "rgba(245,158,11,0.4)"};">{diplo_status}</span>'
    _block_span   = '<span style="display:inline-block;padding:0.2rem 0.6rem;border-radius:4px;font-family:monospace;font-size:0.75rem;font-weight:600;background:rgba(239,68,68,0.15);color:#ef4444;border:1px solid rgba(239,68,68,0.4);">ACTIVE</span>' if blockade == 1 else '<span style="display:inline-block;padding:0.2rem 0.6rem;border-radius:4px;font-family:monospace;font-size:0.75rem;font-weight:600;background:rgba(34,197,94,0.15);color:#22c55e;border:1px solid rgba(34,197,94,0.4);">INACTIVE</span>'

    _label_style  = "font-size:0.65rem;letter-spacing:0.1em;text-transform:uppercase;color:#4a5a72;"
    _sidebar_html = (
        '<div style="font-family:IBM Plex Sans,sans-serif;font-size:0.82rem;color:#8a9bb5;line-height:1.65;">'
        '<div style="margin-bottom:1rem;">'
        f'<div style="margin-bottom:0.6rem;"><span style="{_label_style}">Mine Clearance</span><br>' + _mine_span + '</div>'
        f'<div style="margin-bottom:0.6rem;"><span style="{_label_style}">Diplomatic Status</span><br>' + _diplo_span + '</div>'
        f'<div><span style="{_label_style}">US Naval Blockade</span><br>' + _block_span + '</div>'
        '</div>'
        f'<div style="color:#8a9bb5;font-size:0.8rem;line-height:1.6;">{notes}</div>'
        f'<div style="margin-top:0.75rem;font-size:0.62rem;color:#4a5a72;">As of {as_of} · Last updated {updated}</div>'
        '</div>'
    )
    st.markdown(_sidebar_html, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown("""
        <div class="section-header" style="margin-top:0;">Data Sources</div>
        <div style="font-family:'IBM Plex Sans',sans-serif;font-size:0.78rem;
                    color:#8a9bb5;line-height:1.8;">
            AIS transit data — Kaggle / IMF PortWatch<br>
            LNG prices — yfinance (JKM=F, TTF)<br>
            US LNG exports — EIA Open Data API<br>
            EU gas storage — GIE AGSI+<br>
            Supply gap assumptions — IEA Factsheet Feb 2026
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # Last pipeline run timestamp
    last_run = tanker.get("logged_at") or gap.get("logged_at") or "unknown"
    st.markdown(f"""
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;
                    color:#4a5a72;line-height:1.6;">
            PIPELINE LAST RUN<br>
            <span style="color:#8a9bb5;">{fmt_timestamp(last_run)}</span>
        </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN TABS
# ══════════════════════════════════════════════════════════════════════════════

tab_overview, tab_tanker, tab_gap, tab_lng = st.tabs([
    "⬡  Overview",
    "🚢  Tanker Module",
    "📊  Supply Gap",
    "🔥  LNG Module",
])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 1 — OVERVIEW
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab_overview:

    # ── Thesis block ──────────────────────────────────────────────────────────
    thesis_text = gap.get("summary_thesis") or "Pipeline running — thesis will appear after next daily run."

    st.markdown(f"""
        <div class="thesis-block">
            <div class="thesis-label">⬡ Current Market View</div>
            <div class="thesis-text">{thesis_text}</div>
        </div>
    """, unsafe_allow_html=True)

    # ── Three headline metric cards (CSS Grid — equal heights, aligned footers) ─
    st.markdown('<div class="section-header">Headline Metrics</div>', unsafe_allow_html=True)

    pct = safe(tanker.get("pct_of_normal"), "{:.1f}%")
    flag = "CRITICAL" if tanker.get("anomaly_flag") == 1 else "NORMAL"
    trend = safe(tanker.get("trend_direction"), fallback="—")
    ts = fmt_timestamp(tanker.get("logged_at"))
    baseline_ships = safe(tanker.get("baseline_30d"), "{:.0f}")

    score = safe(lng.get("rebalancing_score"), fallback="—")
    confidence = safe(lng.get("confidence"), fallback="—")
    routing = safe(lng.get("routing_signal"), fallback="—")
    util = safe(lng.get("us_utilization"), "{:.1f}%")
    ts2 = fmt_timestamp(lng.get("logged_at"))
    score_badge = risk_badge(
        "RED" if "CRITICAL" in str(score) else
        "AMBER" if score == "DEFICIT" else
        "GREEN"
    )
    score_kw = str(score) if score is not None else "—"
    if "balanced" in score_kw.lower():
        score_value_html = f'<span class="headline-keyword">{score_kw}</span>'
    else:
        score_value_html = score_kw

    asia_crude = gap.get("asia_crude_risk") or "—"
    asia_lng = gap.get("asia_lng_risk") or "—"
    eur_crude = gap.get("europe_crude_risk") or "—"
    eur_lng = gap.get("europe_lng_risk") or "—"
    ts3 = fmt_timestamp(gap.get("logged_at"))

    st.markdown(f"""
<div class="headline-metrics-grid">
    <div class="metric-card overview-headline-card">
        <div class="overview-headline-body">
            <div class="metric-label">Hormuz Transit Index</div>
            <div class="metric-value"><span class="headline-keyword">{pct}</span></div>
            <div class="metric-sub">of pre-crisis normal &nbsp;&nbsp; {risk_badge(flag)}</div>
            <div class="metric-sub">Trend &nbsp;<span class="headline-mono-emphasis">{trend}</span></div>
            <div class="metric-sub">{safe(tanker.get('transit_count'))} ships/day vs {baseline_ships} baseline</div>
        </div>
        <div class="metric-timestamp">Updated {ts}</div>
    </div>
    <div class="metric-card overview-headline-card">
        <div class="overview-headline-body">
            <div class="metric-label">LNG Rebalancing Score</div>
            <div class="metric-value">{score_value_html}</div>
            <div class="metric-sub">
                Confidence {confidence} &nbsp;·&nbsp; {score_badge}
            </div>
            <div class="metric-sub">Routing signal &nbsp;<span class="headline-mono-emphasis">{routing}</span></div>
            <div class="metric-sub">US utilization <span class="headline-mono-emphasis">{util}</span></div>
        </div>
        <div class="metric-timestamp">Updated {ts2}</div>
    </div>
    <div class="metric-card overview-headline-card">
        <div class="overview-headline-body">
            <div class="metric-label">Regional Risk Summary</div>
            <div style="margin-top:0.6rem;flex:1 1 auto;display:flex;flex-direction:column;min-height:0;">
                <table class="overview-risk-table" style="width:100%;border-collapse:collapse;font-family:'IBM Plex Sans',sans-serif;">
                    <tr style="color:#8a9bb5;letter-spacing:0.08em;text-transform:uppercase;">
                        <td style="padding:0.3rem 0;">Region</td>
                        <td style="padding:0.3rem 0;text-align:center;">Crude</td>
                        <td style="padding:0.3rem 0;text-align:center;">LNG</td>
                    </tr>
                    <tr>
                        <td style="padding:0.35rem 0;color:#e8edf5;">Asia</td>
                        <td style="padding:0.35rem 0;text-align:center;">{risk_badge(asia_crude)}</td>
                        <td style="padding:0.35rem 0;text-align:center;">{risk_badge(asia_lng)}</td>
                    </tr>
                    <tr>
                        <td style="padding:0.35rem 0;color:#e8edf5;">Europe</td>
                        <td style="padding:0.35rem 0;text-align:center;">{risk_badge(eur_crude)}</td>
                        <td style="padding:0.35rem 0;text-align:center;">{risk_badge(eur_lng)}</td>
                    </tr>
                    <tr>
                        <td style="padding:0.35rem 0;color:#e8edf5;">US</td>
                        <td style="padding:0.35rem 0;text-align:center;">{risk_badge("GREEN")}</td>
                        <td style="padding:0.35rem 0;text-align:center;">{risk_badge("GREEN")}</td>
                    </tr>
                </table>
            </div>
        </div>
        <div class="metric-timestamp">Updated {ts3}</div>
    </div>
</div>
""", unsafe_allow_html=True)

    # ── Key numbers row ───────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Key Numbers</div>', unsafe_allow_html=True)

    st.markdown(f"""
<div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1rem;align-items:stretch;margin-bottom:1rem;">
    <div class="metric-card key-numbers-card">
        <div class="metric-label">Net Crude Gap</div>
        <div class="key-numbers-value-slot"><div class="metric-value">{safe(gap.get("crude_gap_net_mbd"), "{:.2f}")}</div></div>
        <div class="metric-sub">Mb/d after bypass + SPR offsets</div>
    </div>
    <div class="metric-card key-numbers-card">
        <div class="metric-label">LNG Gap (Asia)</div>
        <div class="key-numbers-value-slot"><div class="metric-value">{safe(gap.get("asia_lng_gap_bcfd"), "{:.2f}")}</div></div>
        <div class="metric-sub">Bcf/d — no pipeline bypass available</div>
    </div>
    <div class="metric-card key-numbers-card">
        <div class="metric-label">EU Storage vs Seasonal</div>
        <div class="key-numbers-value-slot key-numbers-storage-value-row">
            <div class="metric-value">{safe(lng.get("storage_pct"), "{:.1f}%")}</div>
            <span class="key-numbers-storage-badge">{risk_badge(lng.get("storage_risk"))}</span>
        </div>
        <div class="metric-sub">{safe(lng.get("seasonal_deficit"), "{:.1f} pts")} below seasonal avg</div>
    </div>
    <div class="metric-card key-numbers-card">
        <div class="metric-label">US LNG Utilization</div>
        <div class="key-numbers-value-slot"><div class="metric-value">{safe(lng.get("us_utilization"), "{:.1f}%")}</div></div>
        <div class="metric-sub">System at maximum — no relief capacity</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 2 — TANKER MODULE (placeholder — charts added in Step 5)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab_tanker:
    import plotly.graph_objects as go

    # ── Crisis event dates (verified from hormuz-daily-transits.csv + blueprint) ──
    CRISIS_EVENTS = {
        "2026-02-28": "Disruption begins",
        "2026-03-02": "Strait declared closed",
        "2026-03-05": "P&I insurance withdrawn",
        "2026-03-12": "Brent peaks $126/bbl",
        "2026-03-20": "IEA 400M bbl SPR release",
        "2026-04-08": "Ceasefire agreed",
        "2026-04-13": "US naval blockade",
    }

    # ── Section 1 — Current reading metric card ───────────────────────────────
    st.markdown('<div class="section-header" style="margin-top:0.5rem;">Hormuz Transit Anomaly Index</div>', unsafe_allow_html=True)

    anchorage_count = tanker.get("anchorage_count") or 0
    anchorage_status = (
        "ELEVATED — possible Hormuz queue" if anchorage_count >= 15
        else f"{anchorage_count} vessels present" if anchorage_count > 0
        else "Accumulating — sparse data"
    )
    anchorage_badge = (
        risk_badge("RED")   if anchorage_count >= 15 else
        risk_badge("AMBER") if anchorage_count > 0   else
        risk_badge("GREEN")
    )
    _is_critical = tanker.get("anomaly_flag") == 1
    _flag_badge  = risk_badge("CRITICAL" if _is_critical else "NORMAL")
    st.markdown(f"""
<div style="display:grid;grid-template-columns:2fr 1.5fr 1fr;gap:1rem;align-items:stretch;margin-bottom:1.5rem;">
    <div class="ta-primary-card">
        <div class="ta-label">Hormuz Transit · Current Reading</div>
        <div class="ta-number-row">
            <span class="ta-big-value">{safe(tanker.get("pct_of_normal"), "{:.1f}%")}</span>
            {_flag_badge}
        </div>
        <div class="ta-sub">of pre-crisis normal &nbsp;·&nbsp; {safe(tanker.get("transit_count"))} ships/day vs {safe(tanker.get("baseline_30d"), "{:.0f}")} baseline</div>
        <div class="ta-sub">z-score {safe(tanker.get("z_score"), "{:.1f}")}</div>
    </div>
    <div class="ta-secondary-card">
        <div class="ta-label">7-Day Recovery Trend</div>
        <div class="ta-value">{safe(tanker.get("trend_direction"))}</div>
        <div class="ta-sub">Slope +{safe(tanker.get("trend_slope"), "{:.1f}")} transits/day</div>
    </div>
    <div style="display:flex;flex-direction:column;gap:0.75rem;">
        <div class="ta-small-card">
            <div class="ta-label">Fujairah Queue</div>
            <div class="ta-value">{anchorage_count} <span style="font-size:0.85rem;font-weight:400;color:var(--text-secondary);">vessels</span></div>
            <div class="ta-sub">{anchorage_badge} &nbsp;·&nbsp; {anchorage_status}</div>
        </div>
        <div class="ta-small-card ta-meta-card">
            <div class="ta-label">Data Last Updated</div>
            <div class="ta-value" style="font-size:0.95rem;">{fmt_timestamp(tanker.get("logged_at"))}</div>
            <div class="ta-sub">Kaggle · IMF PortWatch · Kpler</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    # ── Section 2 — Transit count chart ──────────────────────────────────────
    st.markdown('<div class="section-header">Daily Transit Count — Hormuz Strait</div>', unsafe_allow_html=True)

    transit_df = data["transit_df"]

    if not transit_df.empty:
        fig_transit = go.Figure()

        # Baseline reference line
        fig_transit.add_trace(go.Scatter(
            x=transit_df["date"],
            y=transit_df["baseline_30d"],
            name="Pre-crisis baseline",
            line=dict(color="#4a5a72", width=1.5, dash="dash"),
            hovertemplate="%{y:.0f} ships/day<extra>Baseline</extra>",
        ))

        # Actual transit count — color changes at crisis threshold
        fig_transit.add_trace(go.Scatter(
            x=transit_df["date"],
            y=transit_df["transit_count"],
            name="Daily transit count",
            line=dict(color="#f59e0b", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(245,158,11,0.08)",
            hovertemplate="%{x|%b %d, %Y}<br>%{y} ships<extra>Transits</extra>",
        ))

        # Crisis event vertical lines — numbered markers instead of rotated text
        for i, (date_str, label) in enumerate(CRISIS_EVENTS.items(), 1):
            fig_transit.add_shape(
                type="line",
                x0=date_str, x1=date_str,
                y0=0, y1=1,
                xref="x", yref="paper",
                line=dict(color="rgba(239,68,68,0.35)", width=1, dash="dot"),
            )
            fig_transit.add_annotation(
                x=date_str,
                y=0.97,
                xref="x", yref="paper",
                text=str(i),
                showarrow=False,
                font=dict(size=10, color="#ef4444", family="IBM Plex Mono"),
                bgcolor="rgba(10,14,26,0.85)",
                bordercolor="rgba(239,68,68,0.4)",
                borderwidth=1,
                borderpad=3,
                yanchor="top",
            )

        fig_transit.update_layout(
            plot_bgcolor="#0a0e1a",
            paper_bgcolor="#0a0e1a",
            font=dict(family="IBM Plex Sans", color="#8a9bb5", size=13),
            height=370,
            margin=dict(l=10, r=10, t=20, b=10),
            legend=dict(
                orientation="h",
                yanchor="bottom", y=1.01,
                xanchor="left", x=0,
                font=dict(size=11, color="#8a9bb5"),
                bgcolor="rgba(0,0,0,0)",
            ),
            xaxis=dict(
                gridcolor="#1a2235",
                linecolor="#2a3a55",
                tickfont=dict(size=12, family="IBM Plex Mono"),
            ),
            yaxis=dict(
                gridcolor="#1a2235",
                linecolor="#2a3a55",
                tickfont=dict(size=12, family="IBM Plex Mono"),
                title=dict(text="Ships / day", font=dict(size=11)),
            ),
            hovermode="x unified",
        )

        st.plotly_chart(fig_transit, use_container_width=True)

        # Numbered event legend
        st.markdown("""
            <div style="display:flex;flex-wrap:wrap;gap:0.5rem 1.5rem;margin-top:0.5rem;
                        font-family:'IBM Plex Sans',sans-serif;font-size:0.8rem;color:#8a9bb5;">
                <span><span style="color:#ef4444;font-family:'IBM Plex Mono',monospace;font-weight:600;">1</span> &nbsp;Disruption begins</span>
                <span><span style="color:#ef4444;font-family:'IBM Plex Mono',monospace;font-weight:600;">2</span> &nbsp;Strait declared closed</span>
                <span><span style="color:#ef4444;font-family:'IBM Plex Mono',monospace;font-weight:600;">3</span> &nbsp;P&amp;I insurance withdrawn</span>
                <span><span style="color:#ef4444;font-family:'IBM Plex Mono',monospace;font-weight:600;">4</span> &nbsp;Brent peaks $126/bbl</span>
                <span><span style="color:#ef4444;font-family:'IBM Plex Mono',monospace;font-weight:600;">5</span> &nbsp;IEA 400M bbl SPR release</span>
                <span><span style="color:#ef4444;font-family:'IBM Plex Mono',monospace;font-weight:600;">6</span> &nbsp;Ceasefire agreed</span>
                <span><span style="color:#ef4444;font-family:'IBM Plex Mono',monospace;font-weight:600;">7</span> &nbsp;US naval blockade</span>
            </div>
        """, unsafe_allow_html=True)

    else:
        st.markdown('<div class="info-note">Transit history data not available.</div>',
                    unsafe_allow_html=True)

    # ── Section 3 — AIS dark events & diversions ──────────────────────────────
    st.markdown('<div class="section-header">AIS Dark Events & Vessel Diversions</div>',
                unsafe_allow_html=True)

    dark_count = tanker.get("dark_events") or 0
    st.markdown(f"""
        <div class="interpretation-box">
            <div class="interpretation-label">Detection Status</div>
            <div class="interpretation-text">
                Dark event and diversion detection logic is active and running daily.
                <code>vessel_positions</code> is accumulating from aisstream.io —
                <strong style="color:#e8edf5;">{dark_count} dark events</strong> detected
                to date. This section will populate automatically as Gulf AIS coverage
                increases. The detection logic is complete and validated — the constraint
                is data volume, not methodology. At current recovery pace (~8 transits/day),
                meaningful vessel-level data is expected to accumulate within weeks.
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ── Section 4 — Trend extrapolation table ─────────────────────────────────
    st.markdown('<div class="section-header">Trend Extrapolation</div>', unsafe_allow_html=True)

    st.markdown("""
        <div class="extrapolation-note">
            ⚠ TREND EXTRAPOLATION — NOT A FORECAST.
            Based on current recovery slope under stated assumptions.
            Mine clearance status is the binding constraint — actual recovery
            may be slower if clearance is incomplete.
        </div>
    """, unsafe_allow_html=True)

    # Arithmetic extrapolation from current values
    current_count   = tanker.get("transit_count") or 0
    slope           = tanker.get("trend_slope") or 0.0
    baseline        = tanker.get("baseline_30d") or 102.69

    proj_2w  = max(0, current_count + slope * 14)
    proj_4w  = max(0, current_count + slope * 28)
    pct_2w   = round((proj_2w / baseline) * 100, 1)
    pct_4w   = round((proj_4w / baseline) * 100, 1)

    extrap_data = {
        "Timeframe":         ["Current (May 11)", "+2 weeks", "+4 weeks"],
        "Projected ships/day": [
            f"{current_count}",
            f"{proj_2w:.0f}",
            f"{proj_4w:.0f}",
        ],
        "% of Normal":       [
            f"{tanker.get('pct_of_normal', 0):.1f}%",
            f"{pct_2w:.1f}%",
            f"{pct_4w:.1f}%",
        ],
        "vs Baseline (103)": [
            f"−{baseline - current_count:.0f} ships/day",
            f"−{baseline - proj_2w:.0f} ships/day",
            f"−{baseline - proj_4w:.0f} ships/day",
        ],
    }
    st.dataframe(pd.DataFrame(extrap_data), hide_index=True, use_container_width=True)

    # ── Section 5 — Plain-English interpretation ──────────────────────────────
    st.markdown("""
        <div class="interpretation-box" style="margin-top:1.5rem;">
            <div class="interpretation-label">Analyst Interpretation</div>
            <div class="interpretation-text">
                Hormuz is operating at <strong style="color:#f59e0b;">7.8% of pre-crisis
                normal</strong> — 8 ships per day versus a baseline of 103.
                The z-score of −22.2 confirms this is a historically extreme deviation,
                not a routine fluctuation. The 7-day trend shows slow recovery at
                +0.5 transits/day, but this pace is structurally constrained by
                <strong style="color:#e8edf5;">mine clearance operations</strong>, which
                remain incomplete as of the latest data. A ceasefire was agreed April 8,
                but diplomatic resolution does not reopen the strait — physical mine
                clearance by US warships is the binding bottleneck. At the current
                recovery slope, the strait would reach 50% of normal in approximately
                <strong style="color:#e8edf5;">190 days</strong> — making an accelerated
                clearance timeline the single most important variable to monitor.
            </div>
        </div>
    """, unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 3 — LNG MODULE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab_lng:
    import plotly.graph_objects as go

    # ── Section 1 — Headline metric cards ─────────────────────────────────────
    st.markdown('<div class="section-header" style="margin-top:0.5rem;">LNG Rebalancing Score</div>', unsafe_allow_html=True)

    lc1, lc2, lc3 = st.columns(3)
    with lc1:
        score = safe(lng.get("rebalancing_score"), fallback="—")
        score_badge = risk_badge(
            "RED" if "CRITICAL" in str(score) else
            "AMBER" if score == "DEFICIT" else "GREEN"
        )
        st.markdown(f"""
            <div class="metric-card" style="height:160px;">
                <div class="metric-label">Rebalancing Score</div>
                <div class="metric-value" style="font-size:1.4rem;">{score}</div>
                <div class="metric-sub" style="margin-top:0.3rem;">{score_badge}</div>
                <div class="metric-sub">Confidence {safe(lng.get("confidence"))}</div>
            </div>
        """, unsafe_allow_html=True)
    with lc2:
        st.markdown(f"""
            <div class="metric-card" style="height:160px;">
                <div class="metric-label">JKM–TTF Spread (7-day avg)</div>
                <div class="metric-value" style="font-size:1.4rem;">
                    ${safe(lng.get("spread_7d"), "{:.3f}")}
                </div>
                <div class="metric-sub" style="margin-top:0.3rem;">
                    {risk_badge("GREEN" if safe(lng.get("routing_signal")) == "NEUTRAL" else "AMBER")}
                </div>
                <div class="metric-sub">
                    /MMBtu &nbsp;·&nbsp; routing signal:
                    <span style="font-family:'IBM Plex Mono',monospace;
                    color:#e8edf5;">{safe(lng.get("routing_signal"))}</span>
                    &nbsp;·&nbsp; threshold $2.00
                </div>
            </div>
        """, unsafe_allow_html=True)
    with lc3:
        st.markdown(f"""
            <div class="metric-card" style="height:160px;">
                <div class="metric-label">EU Storage Coverage</div>
                <div class="metric-value" style="font-size:1.4rem;">
                    {safe(lng.get("storage_pct"), "{:.1f}%")}
                </div>
                <div class="metric-sub" style="margin-top:0.3rem;">
                    {risk_badge(lng.get("storage_risk"))}
                </div>
                <div class="metric-sub">
                    {safe(lng.get("days_deficit"), "{:.1f} days")} behind required pace
                </div>
            </div>
        """, unsafe_allow_html=True)

    # ── Section 2 — JKM–TTF Spread Chart ──────────────────────────────────────
    st.markdown('<div class="section-header">JKM–TTF Spread — Cargo Routing Signal</div>', unsafe_allow_html=True)

    prices_df = data["prices_df"]

    # LNG crisis events relevant to the spread chart
    LNG_EVENTS = {
        "2026-03-01": "Ras Laffan attack",
        "2026-03-16": "JKM>TTF inflection",
        "2026-04-08": "Ceasefire",
        "2026-04-15": "Spread peaks",
        "2026-04-16": "Ceasefire collapse",
    }

    if not prices_df.empty:
        fig_spread = go.Figure()

        # JKM price line
        fig_spread.add_trace(go.Scatter(
            x=prices_df["date"],
            y=prices_df["JKM"],
            name="JKM (Asia)",
            line=dict(color="#f59e0b", width=2),
            hovertemplate="%{x|%b %d, %Y}<br>JKM $%{y:.2f}/MMBtu<extra></extra>",
        ))

        # TTF price line
        fig_spread.add_trace(go.Scatter(
            x=prices_df["date"],
            y=prices_df["TTF"],
            name="TTF (Europe)",
            line=dict(color="#3b82f6", width=2),
            hovertemplate="%{x|%b %d, %Y}<br>TTF $%{y:.2f}/MMBtu<extra></extra>",
        ))

        # Spread as filled area on secondary y-axis
        fig_spread.add_trace(go.Scatter(
            x=prices_df["date"],
            y=prices_df["spread"],
            name="JKM–TTF Spread",
            line=dict(color="#14b8a6", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(20,184,166,0.08)",
            yaxis="y2",
            hovertemplate="%{x|%b %d, %Y}<br>Spread $%{y:.2f}/MMBtu<extra></extra>",
        ))

        # $2 routing threshold line on secondary axis
        fig_spread.add_shape(
            type="line",
            x0=prices_df["date"].min(),
            x1=prices_df["date"].max(),
            y0=2.0, y1=2.0,
            xref="x", yref="y2",
            line=dict(color="rgba(239,68,68,0.5)", width=1, dash="dash"),
        )
        fig_spread.add_annotation(
            x=prices_df["date"].max(),
            y=2.0,
            xref="x", yref="y2",
            text="$2.00 routing threshold",
            showarrow=False,
            font=dict(size=9, color="#ef4444", family="IBM Plex Mono"),
            xanchor="right",
            yanchor="bottom",
        )

        # Crisis event vertical lines — numbered markers
        for i, (date_str, label) in enumerate(LNG_EVENTS.items(), 1):
            fig_spread.add_shape(
                type="line",
                x0=date_str, x1=date_str,
                y0=0, y1=1,
                xref="x", yref="paper",
                line=dict(color="rgba(239,68,68,0.3)", width=1, dash="dot"),
            )
            fig_spread.add_annotation(
                x=date_str, y=0.97,
                xref="x", yref="paper",
                text=str(i),
                showarrow=False,
                font=dict(size=10, color="#ef4444", family="IBM Plex Mono"),
                bgcolor="rgba(10,14,26,0.85)",
                bordercolor="rgba(239,68,68,0.4)",
                borderwidth=1,
                borderpad=3,
                yanchor="top",
            )

        fig_spread.update_layout(
            plot_bgcolor="#0a0e1a",
            paper_bgcolor="#0a0e1a",
            font=dict(family="IBM Plex Sans", color="#8a9bb5", size=13),
            height=350,
            margin=dict(l=10, r=60, t=20, b=10),
            legend=dict(
                orientation="h",
                yanchor="bottom", y=1.01,
                xanchor="left", x=0,
                font=dict(size=11, color="#8a9bb5"),
                bgcolor="rgba(0,0,0,0)",
            ),
            xaxis=dict(
                gridcolor="#1a2235",
                linecolor="#2a3a55",
                tickfont=dict(size=12, family="IBM Plex Mono"),
                range=["2025-05-01", prices_df["date"].max().strftime("%Y-%m-%d")],
            ),
            yaxis=dict(
                gridcolor="#1a2235",
                linecolor="#2a3a55",
                tickfont=dict(size=12, family="IBM Plex Mono"),
                title=dict(text="Price ($/MMBtu)", font=dict(size=11)),
            ),
            yaxis2=dict(
                overlaying="y",
                side="right",
                gridcolor="#1a2235",
                linecolor="#2a3a55",
                tickfont=dict(size=12, family="IBM Plex Mono"),
                title=dict(text="Spread ($/MMBtu)", font=dict(size=11)),
                showgrid=False,
            ),
            hovermode="x unified",
        )

        st.plotly_chart(fig_spread, use_container_width=True)

        # Numbered event legend
        st.markdown("""
            <div style="display:flex;flex-wrap:wrap;gap:0.5rem 1.5rem;margin-top:0.5rem;
                        font-family:'IBM Plex Sans',sans-serif;font-size:0.8rem;color:#8a9bb5;">
                <span><span style="color:#ef4444;font-family:'IBM Plex Mono',monospace;font-weight:600;">1</span> &nbsp;Ras Laffan attack</span>
                <span><span style="color:#ef4444;font-family:'IBM Plex Mono',monospace;font-weight:600;">2</span> &nbsp;JKM &gt; TTF inflection</span>
                <span><span style="color:#ef4444;font-family:'IBM Plex Mono',monospace;font-weight:600;">3</span> &nbsp;Ceasefire agreed</span>
                <span><span style="color:#ef4444;font-family:'IBM Plex Mono',monospace;font-weight:600;">4</span> &nbsp;Spread peaks $4.86</span>
                <span><span style="color:#ef4444;font-family:'IBM Plex Mono',monospace;font-weight:600;">5</span> &nbsp;Ceasefire collapse</span>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
            <div class="info-note">
                <strong style="color:#e8edf5;">How to read this chart:</strong>
                When the teal spread line crosses above the $2.00 red dashed threshold,
                US LNG cargoes are economically incentivised to route toward Asia rather
                than Europe. The spread peaked at $4.86/MMBtu on April 15 — nearly $5
                more per MMBtu to deliver to Tokyo than Rotterdam, more than covering
                the freight differential. The current NEUTRAL signal ($1.20 avg) means
                cargoes are transitioning back toward balance.
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
            <details class="info-dropdown">
                <summary>What is JKM–TTF and why does $2.00 matter?</summary>
                <div class="dropdown-body">
                    <b style="color:#e8edf5;">JKM (Japan-Korea Marker)</b> is the LNG price benchmark for Asia.
                    <b style="color:#e8edf5;">TTF (Title Transfer Facility)</b> is the gas price benchmark for Europe (Netherlands hub).
                    The spread is JKM minus TTF — how much more Asia is paying per unit of LNG than Europe.
                    <br><br>
                    <b style="color:#e8edf5;">Why $2.00?</b> Shipping LNG from the US Gulf to Tokyo costs ~$2/MMBtu more than to Rotterdam.
                    When the spread exceeds $2.00, the extra revenue from selling to Asia covers the extra freight — traders route cargoes east.
                    Below $2.00, Europe becomes the more economic destination.
                    <br><br>
                    <b style="color:#e8edf5;">Why it matters now:</b> The spread spiked to $4.86 in April 2026, pulling every flexible
                    US cargo to Asia. This starved Europe during its critical spring refill window, driving the storage
                    deficit now at 35% vs a seasonal average of ~52%.
                </div>
            </details>
        """, unsafe_allow_html=True)

    else:
        st.markdown('<div class="info-note">Price data not available.</div>',
                    unsafe_allow_html=True)

    # ── Section 3 — US Terminal Utilization ───────────────────────────────────
    st.markdown('<div class="section-header">US LNG Terminal Utilization</div>',
                unsafe_allow_html=True)

    util_df = data["util_df"]

    if not util_df.empty:
        latest_month = util_df["latest_month"].iloc[0] if "latest_month" in util_df.columns else "Feb 2026"

        fig_util = go.Figure()

        # Color bars by utilization: >100% amber, <100% blue
        bar_colors = [
            "#f59e0b" if u >= 100 else "#3b82f6"
            for u in util_df["utilization_pct"]
        ]

        fig_util.add_trace(go.Bar(
            x=util_df["utilization_pct"],
            y=util_df["terminal"],
            orientation="h",
            marker_color=bar_colors,
            text=[f"{u:.1f}%" for u in util_df["utilization_pct"]],
            textposition="outside",
            textfont=dict(size=12, family="IBM Plex Mono", color="#e8edf5"),
            hovertemplate="%{y}<br>Utilization: %{x:.1f}%<extra></extra>",
        ))

        # 100% nameplate line
        fig_util.add_shape(
            type="line",
            x0=100, x1=100,
            y0=-0.5, y1=len(util_df) - 0.5,
            xref="x", yref="y",
            line=dict(color="rgba(239,68,68,0.6)", width=1.5, dash="dash"),
        )
        fig_util.add_annotation(
            x=100, y=len(util_df) - 0.5,
            xref="x", yref="y",
            text="100% nameplate",
            showarrow=False,
            font=dict(size=9, color="#ef4444", family="IBM Plex Mono"),
            xanchor="left",
            yanchor="bottom",
            bgcolor="rgba(10,14,26,0.8)",
        )

        fig_util.update_layout(
            plot_bgcolor="#0a0e1a",
            paper_bgcolor="#0a0e1a",
            font=dict(family="IBM Plex Sans", color="#8a9bb5", size=13),
            height=280,
            margin=dict(l=10, r=80, t=10, b=10),
            xaxis=dict(
                gridcolor="#1a2235",
                linecolor="#2a3a55",
                tickfont=dict(size=12, family="IBM Plex Mono"),
                title=dict(text="Utilization (%)", font=dict(size=11)),
                range=[0, max(util_df["utilization_pct"]) * 1.15],
            ),
            yaxis=dict(
                gridcolor="#1a2235",
                linecolor="#2a3a55",
                tickfont=dict(size=12, family="IBM Plex Mono"),
            ),
        )

        st.plotly_chart(fig_util, use_container_width=True)

        st.markdown(f"""
            <div class="info-note">
                <strong style="color:#f59e0b;">Latest available data: {latest_month}.</strong>
                EIA publishes monthly LNG export data with a 6–8 week lag — crisis period
                data is not yet available. Five of eight terminals were already running
                above 100% nameplate capacity before the crisis began. US aggregate
                utilization of 113.6% means the system was already at maximum —
                there is no additional relief capacity available regardless of price signals.
            </div>
        """, unsafe_allow_html=True)

    else:
        st.markdown('<div class="info-note">Terminal utilization data not available.</div>',
                    unsafe_allow_html=True)

    # ── Section 4 — European Storage Coverage ─────────────────────────────────
    st.markdown('<div class="section-header">European Gas Storage — vs Seasonal Baseline</div>',
                unsafe_allow_html=True)

    storage_df  = data["storage_df"]
    baseline_df = data["baseline_df"]
    yoy_level   = data["yoy_level"]

    if not storage_df.empty and not baseline_df.empty:
        import numpy as np

        # Build seasonal baseline mapped to 2026 dates for overlay
        # Use day-of-year to align historical average with current year x-axis
        storage_2026 = storage_df[storage_df["date"].dt.year == 2026].copy()
        storage_2026["doy"] = storage_2026["date"].dt.dayofyear

        # baseline_df has column "day_of_year", storage_2026 has "doy"
        # rename baseline column to match before merging
        baseline_merged = storage_2026.merge(
            baseline_df.rename(columns={"day_of_year": "doy"}),
            on="doy",
            how="left"
        )

        fig_storage = go.Figure()

        # Full EU storage history (2020 onwards) — muted
        fig_storage.add_trace(go.Scatter(
            x=storage_df["date"],
            y=storage_df["pct_full"],
            name="EU storage (historical)",
            line=dict(color="#2a3a55", width=1),
            hovertemplate="%{x|%b %d, %Y}<br>%{y:.1f}%<extra>Historical</extra>",
        ))

        # 2026 current year — highlighted
        fig_storage.add_trace(go.Scatter(
            x=storage_2026["date"],
            y=storage_2026["pct_full"],
            name="EU storage 2026",
            line=dict(color="#f59e0b", width=2.5),
            hovertemplate="%{x|%b %d, %Y}<br>%{y:.1f}% full<extra>2026</extra>",
        ))

        # Seasonal baseline overlay
        if "avg_pct_full" in baseline_merged.columns:
            fig_storage.add_trace(go.Scatter(
                x=baseline_merged["date"],
                y=baseline_merged["avg_pct_full"],
                name="5yr seasonal avg (2020–2024)",
                line=dict(color="#8a9bb5", width=1.5, dash="dash"),
                hovertemplate="%{x|%b %d, %Y}<br>%{y:.1f}% avg<extra>Seasonal avg</extra>",
            ))

        # ── Year-on-year reference line: May 11, 2025 storage level ──────────
        yoy_pct  = yoy_level.get("pct_full")
        yoy_date = yoy_level.get("date")
        if yoy_pct is not None:
            fig_storage.add_shape(
                type="line",
                x0=storage_df["date"].min(),
                x1="2026-11-01",
                y0=yoy_pct, y1=yoy_pct,
                xref="x", yref="y",
                line=dict(color="rgba(167,139,250,0.6)", width=1.5, dash="dashdot"),
            )
            fig_storage.add_annotation(
                x="2026-11-01", y=yoy_pct,
                xref="x", yref="y",
                text=f"May 11 2025: {yoy_pct:.1f}%",
                showarrow=False,
                font=dict(size=9, color="#a78bfa", family="IBM Plex Mono"),
                xanchor="right",
                yanchor="bottom",
                bgcolor="rgba(10,14,26,0.8)",
            )

        # 90% EU November target reference line
        fig_storage.add_shape(
            type="line",
            x0=storage_df["date"].min(),
            x1="2026-11-01",
            y0=90, y1=90,
            xref="x", yref="y",
            line=dict(color="rgba(34,197,94,0.4)", width=1, dash="dot"),
        )
        fig_storage.add_annotation(
            x="2026-11-01", y=90,
            xref="x", yref="y",
            text="EU 90% target (Nov 1)",
            showarrow=False,
            font=dict(size=9, color="#22c55e", family="IBM Plex Mono"),
            xanchor="right",
            yanchor="bottom",
        )

        fig_storage.update_layout(
            plot_bgcolor="#0a0e1a",
            paper_bgcolor="#0a0e1a",
            font=dict(family="IBM Plex Sans", color="#8a9bb5", size=13),
            height=380,
            margin=dict(l=10, r=10, t=20, b=10),
            legend=dict(
                orientation="h",
                yanchor="bottom", y=1.01,
                xanchor="left", x=0,
                font=dict(size=11, color="#8a9bb5"),
                bgcolor="rgba(0,0,0,0)",
            ),
            xaxis=dict(
                gridcolor="#1a2235",
                linecolor="#2a3a55",
                tickfont=dict(size=12, family="IBM Plex Mono"),
            ),
            yaxis=dict(
                gridcolor="#1a2235",
                linecolor="#2a3a55",
                tickfont=dict(size=12, family="IBM Plex Mono"),
                title=dict(text="% full", font=dict(size=11)),
                range=[0, 105],
            ),
            hovermode="x unified",
        )

        st.plotly_chart(fig_storage, use_container_width=True)

        # Build yoy line info string for dropdown
        _yoy_pct_str = f"{yoy_pct:.1f}%" if yoy_pct is not None else "N/A"
        _current_storage = lng.get("storage_pct") or 0
        _yoy_gap_str = (
            f"{abs(yoy_pct - _current_storage):.1f} percentage points"
            if yoy_pct is not None else "N/A"
        )

        st.markdown(f"""
            <details class="info-dropdown">
                <summary>How to read this chart</summary>
                <div class="dropdown-body">
                    <div style="display:flex;flex-direction:column;gap:0.5rem;margin-bottom:0.85rem;">
                        <div style="display:flex;align-items:center;gap:0.75rem;">
                            <span style="display:inline-block;width:32px;height:3px;background:#f59e0b;border-radius:2px;flex-shrink:0;"></span>
                            <span>EU gas storage in 2026 (% of total capacity)</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:0.75rem;">
                            <span style="display:inline-block;width:32px;height:0;border-top:2px dashed #8a9bb5;flex-shrink:0;"></span>
                            <span>5-year seasonal average (2020–2024)</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:0.75rem;">
                            <span style="display:inline-block;width:32px;height:0;border-top:2px dotted #22c55e;flex-shrink:0;"></span>
                            <span style="color:#22c55e;">EU mandatory 90% target by November 1</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:0.75rem;">
                            <span style="display:inline-block;width:32px;height:0;border-top:2px dashed #a78bfa;flex-shrink:0;"></span>
                            <span style="color:#a78bfa;">May 11, 2025 storage level ({_yoy_pct_str}) — year-on-year reference</span>
                        </div>
                    </div>
                    <b style="color:#e8edf5;">Why November 1?</b> EU law requires storage at 90% before winter. This buffer covers
                    demand spikes and supply disruptions. Missing it means higher prices, potential rationing, and
                    greater vulnerability to geopolitical pressure. Currently 35% — 17 pts below seasonal average
                    and 10.3 days behind the required injection pace to meet the EU's 90% by November 1 mandate.
                    <br><br>
                    <b style="color:#a78bfa;">Year-on-year comparison:</b> Storage on the same date last year (May 11, 2025)
                    was {_yoy_pct_str} — the purple line shows how far below that 2025 level current storage sits.
                    The {_yoy_gap_str} gap reflects the compounded effect of the Hormuz crisis and the LNG cargo
                    pull toward Asia during the spring refill window.
                </div>
            </details>
        """, unsafe_allow_html=True)

    else:
        st.markdown('<div class="info-note">Storage data not available.</div>',
                    unsafe_allow_html=True)

    # ── Section 5 — Storage Trend Extrapolation ────────────────────────────────
    st.markdown('<div class="section-header">Storage Trend Extrapolation</div>',
                unsafe_allow_html=True)

    st.markdown("""
        <div class="extrapolation-note">
            ⚠ TREND EXTRAPOLATION — NOT A FORECAST.
            Based on current injection pace under stated assumptions.
        </div>
    """, unsafe_allow_html=True)

    days_deficit   = lng.get("days_deficit") or 0
    storage_pct    = lng.get("storage_pct") or 35.0
    seasonal_def   = lng.get("seasonal_deficit") or 17.0
    # Current pace from Phase 3: 0.2515 pct/day actual vs 0.3122 pct/day required
    actual_pace    = 0.2515
    required_pace  = 0.3122
    days_to_nov1   = 177  # from Phase 3 audit

    proj_pct_2w    = round(storage_pct + actual_pace * 14, 1)
    proj_pct_4w    = round(storage_pct + actual_pace * 28, 1)
    proj_deficit_2w = round(days_deficit + ((required_pace - actual_pace) * 14) / required_pace * 1, 1)
    proj_deficit_4w = round(days_deficit + ((required_pace - actual_pace) * 28) / required_pace * 1, 1)

    storage_extrap = {
        "Timeframe":          ["Current (May 11)", "+2 weeks", "+4 weeks"],
        "EU Storage (% full)": [f"{storage_pct:.1f}%", f"{proj_pct_2w:.1f}%", f"{proj_pct_4w:.1f}%"],
        "Days Behind Pace":    [f"{days_deficit:.1f}", f"{proj_deficit_2w:.1f}", f"{proj_deficit_4w:.1f}"],
        "Risk":                [
            risk_badge(lng.get("storage_risk") or "AMBER"),
            risk_badge("AMBER" if proj_deficit_2w < 15 else "RED"),
            risk_badge("AMBER" if proj_deficit_4w < 15 else "RED"),
        ],
    }
    st.markdown(
        pd.DataFrame(storage_extrap).to_html(escape=False, index=False, classes="supply-gap-table"),
        unsafe_allow_html=True,
    )

    # ── Section 6 — Analyst interpretation ────────────────────────────────────
    st.markdown("""
        <div class="interpretation-box" style="margin-top:1.5rem;">
            <div class="interpretation-label">Analyst Interpretation</div>
            <div class="interpretation-text">
                The JKM–TTF spread crossed the $2.00 cargo routing threshold on
                <strong style="color:#e8edf5;">March 16</strong> and peaked at
                $4.86/MMBtu on April 15 — the widest spread since the 2022 energy
                crisis. During this period every flexible US LNG cargo was
                economically pulled toward Asia, reducing Atlantic Basin supply to
                Europe during the critical spring refill window.
                <br><br>
                The ceasefire effect on April 16 collapsed the spread to $1.47 in a
                single day. The current NEUTRAL signal ($1.20 seven-day average) means
                cargoes are no longer decisively pulled east, but
                <strong style="color:#f59e0b;">the structural damage to European
                storage is already done</strong> — 17.2 percentage points below the
                seasonal average, 10.3 days behind the required injection pace to meet
                the EU's 90% by November 1 mandate. The US export system offers no
                additional relief: at 113.6% utilization, it was already running at
                maximum before the crisis began.
            </div>
        </div>
    """, unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 4 — SUPPLY GAP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab_gap:
    import plotly.graph_objects as go

    # ── Section 1 — Regional risk table ───────────────────────────────────────
    st.markdown('<div class="section-header" style="margin-top:0.5rem;">Regional Supply Gap — Current State</div>', unsafe_allow_html=True)

    gap_html_rows = [
        {
            "Region": "Asia",
            "Crude Gap (Mb/d)": f"{safe(gap.get('asia_crude_gap_mbd'), '{:.2f}')}",
            "Crude Risk": risk_badge(gap.get("asia_crude_risk")),
            "LNG Gap (Bcf/d)": f"{safe(gap.get('asia_lng_gap_bcfd'), '{:.2f}')}",
            "LNG Risk": risk_badge(gap.get("asia_lng_risk")),
        },
        {
            "Region": "Europe",
            "Crude Gap (Mb/d)": f"{safe(gap.get('europe_crude_gap_mbd'), '{:.2f}')}",
            "Crude Risk": risk_badge(gap.get("europe_crude_risk")),
            "LNG Gap (Bcf/d)": f"{safe(gap.get('europe_lng_gap_bcfd'), '{:.2f}')}",
            "LNG Risk": risk_badge(gap.get("europe_lng_risk")),
        },
        {
            "Region": "US",
            "Crude Gap (Mb/d)": "0.00",
            "Crude Risk": risk_badge("GREEN"),
            "LNG Gap (Bcf/d)": "0.00",
            "LNG Risk": risk_badge("GREEN"),
        },
    ]
    st.markdown(
        pd.DataFrame(gap_html_rows).to_html(escape=False, index=False, classes="supply-gap-table"),
        unsafe_allow_html=True,
    )

    # ── Section 2 — Crude gap waterfall chart ─────────────────────────────────
    st.markdown('<div class="section-header">Crude Supply Gap — Accounting Waterfall</div>',
                unsafe_allow_html=True)

    pct_normal     = gap.get("pct_of_normal") or 7.8
    normal_flow    = 15.0
    current_thru   = round(normal_flow * (pct_normal / 100), 2)
    disrupted      = round(normal_flow - current_thru, 2)
    bypass_offset  = 4.5
    spr_offset     = 3.0
    net_gap        = round(gap.get("crude_gap_net_mbd") or 6.33, 2)

    waterfall_labels = [
        "Normal Hormuz flow",
        "Currently transiting",
        "Disrupted volume",
        "Bypass pipelines offset",
        "IEA SPR release offset",
        "Net crude gap",
    ]
    waterfall_values = [
        normal_flow,
        -current_thru,
        disrupted,
        -bypass_offset,
        -spr_offset,
        net_gap,
    ]
    waterfall_measures = [
        "absolute",
        "relative",
        "total",
        "relative",
        "relative",
        "total",
    ]
    waterfall_colors = [
        "#3b82f6",   # normal flow — blue
        "#4a5a72",   # currently transiting — muted
        "#ef4444",   # disrupted — red
        "#22c55e",   # bypass offset — green
        "#22c55e",   # SPR offset — green
        "#f59e0b",   # net gap — amber
    ]

    fig_waterfall = go.Figure(go.Waterfall(
        orientation="v",
        measure=waterfall_measures,
        x=waterfall_labels,
        y=waterfall_values,
        text=[f"{abs(v):.2f}" for v in waterfall_values],
        textposition="outside",
        textfont=dict(size=11, family="IBM Plex Mono", color="#e8edf5"),
        connector=dict(line=dict(color="#2a3a55", width=1)),
        increasing=dict(marker=dict(color="#ef4444")),
        decreasing=dict(marker=dict(color="#22c55e")),
        totals=dict(marker=dict(color="#f59e0b")),
    ))

    fig_waterfall.update_layout(
        plot_bgcolor="#0a0e1a",
        paper_bgcolor="#0a0e1a",
        font=dict(family="IBM Plex Sans", color="#8a9bb5", size=13),
        height=380,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis=dict(
            gridcolor="#1a2235",
            linecolor="#2a3a55",
            tickfont=dict(size=12, family="IBM Plex Sans"),
        ),
        yaxis=dict(
            gridcolor="#1a2235",
            linecolor="#2a3a55",
            tickfont=dict(size=12, family="IBM Plex Mono"),
            title=dict(text="Mb/d", font=dict(size=11)),
        ),
        showlegend=False,
    )

    st.plotly_chart(fig_waterfall, use_container_width=True)

    st.markdown(f"""
        <div class="info-note">
            <strong style="color:#e8edf5;">How to read this chart:</strong>
            Normal Hormuz crude flow is 15.0 Mb/d (IEA 2025 baseline).
            At {pct_normal:.1f}% of normal, only {current_thru:.2f} Mb/d is currently
            transiting — leaving {disrupted:.2f} Mb/d disrupted.
            Bypass pipelines (Saudi East-West + UAE ADCOP) offset 4.5 Mb/d
            (IEA available capacity midpoint). The IEA coordinated SPR release
            offsets a further 3.0 Mb/d. The residual net gap is
            <strong style="color:#f59e0b;">{net_gap:.2f} Mb/d</strong> —
            of which Asia bears 80% ({safe(gap.get("asia_crude_gap_mbd"), "{:.2f}")} Mb/d)
            and Europe bears 4% ({safe(gap.get("europe_crude_gap_mbd"), "{:.2f}")} Mb/d).
        </div>
    """, unsafe_allow_html=True)

    # ── Section 3 — Trend extrapolation ───────────────────────────────────────
    st.markdown('<div class="section-header">Trend Extrapolation</div>',
                unsafe_allow_html=True)

    st.markdown("""
        <div class="extrapolation-note">
            ⚠ TREND EXTRAPOLATION — NOT A FORECAST.
            Based on current transit recovery rate and static bypass/SPR assumptions.
        </div>
    """, unsafe_allow_html=True)

    # Project forward using tanker recovery slope
    slope      = tanker.get("trend_slope") or 0.5
    baseline_t = tanker.get("baseline_30d") or 102.69

    def project_gap(days_forward):
        proj_count   = min(current_thru * (baseline_t / normal_flow) + slope * days_forward,
                          baseline_t)
        proj_pct     = min((proj_count / baseline_t) * 100, 100)
        proj_thru    = normal_flow * (proj_pct / 100)
        proj_disrupt = max(normal_flow - proj_thru, 0)
        proj_net     = max(proj_disrupt - bypass_offset - spr_offset, 0)
        proj_asia    = round(proj_net * 0.80, 2)
        proj_eur     = round(proj_net * 0.04, 2)
        return round(proj_net, 2), proj_asia, proj_eur, round(proj_pct, 1)

    net_2w, asia_2w, eur_2w, pct_2w = project_gap(14)
    net_4w, asia_4w, eur_4w, pct_4w = project_gap(28)

    gap_extrap = {
        "Timeframe":           ["Current (May 11)", "+2 weeks", "+4 weeks"],
        "Transit (% normal)":  [f"{pct_normal:.1f}%", f"{pct_2w:.1f}%", f"{pct_4w:.1f}%"],
        "Net Crude Gap (Mb/d)":[f"{net_gap:.2f}", f"{net_2w:.2f}", f"{net_4w:.2f}"],
        "Asia Gap (Mb/d)":     [f"{safe(gap.get('asia_crude_gap_mbd'), '{:.2f}')}", f"{asia_2w:.2f}", f"{asia_4w:.2f}"],
        "Europe Gap (Mb/d)":   [f"{safe(gap.get('europe_crude_gap_mbd'), '{:.2f}')}", f"{eur_2w:.2f}", f"{eur_4w:.2f}"],
    }
    st.markdown(
        pd.DataFrame(gap_extrap).to_html(escape=False, index=False, classes="supply-gap-table"),
        unsafe_allow_html=True,
    )

    # ── Section 4 — Assumptions expander ──────────────────────────────────────
    st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
    with st.expander("📋  Methodology & Assumptions", expanded=False):
        st.markdown("""
            <div style="font-family:'IBM Plex Sans',sans-serif;font-size:0.85rem;
                        color:#8a9bb5;line-height:1.8;">

            <div style="color:#f59e0b;font-weight:600;font-size:0.7rem;
                        letter-spacing:0.1em;text-transform:uppercase;
                        margin-bottom:0.75rem;">
                All assumptions verified against primary sources — May 2026
            </div>

            <b style="color:#e8edf5;">Normal Hormuz crude flow: 15.0 Mb/d</b><br>
            IEA Strait of Hormuz Factsheet, February 2026.
            "Nearly 15 mb/d of crude oil passed through Hormuz in 2025."
            Crude + condensate only — not total oil flows (20 Mb/d total).
            <br><br>

            <b style="color:#e8edf5;">Normal Hormuz LNG flow: 10.8 Bcf/d</b><br>
            IEA Factsheet, February 2026. Derived: 112 bcm/year × 35.3 / 365.
            <br><br>

            <b style="color:#e8edf5;">Bypass pipeline capacity: 3.5–5.5 Mb/d available
            (midpoint 4.5 Mb/d used)</b><br>
            IEA Factsheet, February 2026. Saudi East-West Pipeline: 3–5 Mb/d spare.
            UAE ADCOP: 0.7 Mb/d additional. Total IEA stated range: 3.5–5.5 Mb/d.
            <br><br>

            <b style="color:#e8edf5;">IPSA pipeline: EXCLUDED</b><br>
            Mothballed since 1990. Saudi Aramco confirmed "not in a stage to be utilised."
            Global Energy Monitor, January 2026. Design capacity of 1.65 Mb/d is
            irrelevant — pipeline is physically unusable.
            <br><br>

            <b style="color:#e8edf5;">Iran Goreh-Jask pipeline: EXCLUDED</b><br>
            IEA Factsheet: "pipeline and port effectively remain non-operational."
            One test load in late 2024 — no further exports since.
            <br><br>

            <b style="color:#e8edf5;">IEA SPR release rate: 3.0 Mb/d total
            (1.0–1.5 Mb/d US)</b><br>
            S&P Global CERAWeek, March 23, 2026. US Energy Secretary Chris Wright
            confirmed rate. First barrels flowed March 17.
            <br><br>

            <b style="color:#e8edf5;">Destination shares — crude:</b>
            Asia 80%, Europe 4%, Other 16%<br>
            IEA Factsheet: "80% destined for Asia" and "600 kb/d, just 4% of
            crude flows" to Europe.
            <br><br>

            <b style="color:#e8edf5;">Destination shares — LNG:</b>
            Asia 90%, Europe 10%<br>
            IEA Factsheet: "almost 90% destined to Asian market" and
            "share of Europe was just over 10%."
            <br><br>

            <b style="color:#e8edf5;">Risk label thresholds (analytical judgment):</b><br>
            RED: &gt;15 days below seasonal norm |
            AMBER: 5–15 days below seasonal norm |
            GREEN: within 5 days of seasonal norm.<br>
            These are documented judgment calls, not externally defined standards.
            The 15-day RED threshold is consistent with EU energy emergency
            framework alert-level guidance.
            <br><br>

            <b style="color:#e8edf5;">Known limitations:</b><br>
            • Asia crude and LNG risk labels are gap-based proxy estimates —
            no free-tier Asian storage data is available.<br>
            • Europe LNG risk uses real GIE AGSI+ storage data.<br>
            • Bypass pipeline capacity is static reference data — no live
            throughput feed available.<br>
            • Same pct_of_normal applied to both crude and LNG disruption —
            vessel-type split unavailable on free tier.<br>
            • SPR rate is the announced planned rate, not confirmed live delivery.

            </div>
        """, unsafe_allow_html=True)

    # ── Section 5 — Analyst interpretation ────────────────────────────────────
    st.markdown(f"""
        <div class="interpretation-box" style="margin-top:1.5rem;">
            <div class="interpretation-label">Analyst Interpretation</div>
            <div class="interpretation-text">
                The net crude supply gap of
                <strong style="color:#f59e0b;">{net_gap:.2f} Mb/d</strong>
                reflects the residual shortfall after all available offsets are applied —
                bypass pipelines (4.5 Mb/d) and the IEA coordinated SPR release
                (3.0 Mb/d) together cover roughly 54% of the disrupted volume, but
                cannot close the gap at current transit levels of {pct_normal:.1f}%
                of normal.
                <br><br>
                The regional distribution is asymmetric and analytically important:
                <strong style="color:#ef4444;">Asia bears 80%
                ({safe(gap.get("asia_crude_gap_mbd"), "{:.2f}")} Mb/d)</strong>
                of the crude impact because 80% of Hormuz crude was destined for
                Asian markets. Europe bears only 4%
                ({safe(gap.get("europe_crude_gap_mbd"), "{:.2f}")} Mb/d) of the
                crude impact — but faces a
                <strong style="color:#f59e0b;">disproportionate LNG impact
                ({safe(gap.get("europe_lng_gap_bcfd"), "{:.2f}")} Bcf/d)</strong>
                because Qatar LNG has no pipeline bypass capacity whatsoever.
                This asymmetry — Asia exposed on crude, Europe exposed on LNG —
                is what drives the divergence between oil and gas prices during
                the crisis, and is not visible unless you model the two commodity
                chains separately.
            </div>
        </div>
    """, unsafe_allow_html=True)