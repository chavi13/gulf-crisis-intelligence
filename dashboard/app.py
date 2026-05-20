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
    get_vessel_mix_latest,
    get_vessel_mix_history,
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
    /* Backgrounds */
    --bg-primary:    #0a0e1a;
    --bg-secondary:  #111827;
    --bg-card:       #1a2235;
    --bg-card-hover: #1e2a42;
    --border:        #2a3a55;
    /* Text */
    --text-primary:  #e8edf5;
    --text-secondary:#8a9bb5;
    --text-muted:    #4a5a72;
    /* Accents */
    --accent-amber:  #f59e0b;
    --accent-red:    #ef4444;
    --accent-green:  #22c55e;
    --accent-blue:   #3b82f6;
    --accent-teal:   #14b8a6;
    /* Fonts */
    --font-mono:     'IBM Plex Mono', monospace;
    --font-sans:     'IBM Plex Sans', sans-serif;
    /* ── Type scale (4 steps — use only these) ──────────────────── */
    --text-xs:   0.75rem;   /* badges, timestamps, labels, captions  */
    --text-sm:   0.85rem;   /* body copy, sub-text, table cells      */
    --text-base: 1rem;      /* metric values, card body default      */
    --text-lg:   1.2rem;    /* secondary headline values             */
    /* headline-keyword (.ta-big-value) deliberately oversized at 2.8rem — one-off */
}

/* ── Global overrides ───────────────────────────────────────────── */
.stApp {
    background-color: var(--bg-primary);
    color: var(--text-primary);
    font-family: var(--font-sans);
}

/* Hide Streamlit branding */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
header    { visibility: hidden; }

/* ── Tighten top margin — kill ALL top spacing ──────────────────── */
[data-testid="stHeader"]     { display: none !important; height: 0 !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stMarkdownContainer"] { height: 100%; }
section.main > div.block-container,
.main > div.block-container {
    padding-top: 0 !important;
    padding-bottom: 2rem !important;
    max-width: 100% !important;
}
.stApp > div:first-child { padding-top: 0 !important; }
section.main { padding-top: 0 !important; }
div[data-testid="stAppViewContainer"] > section > div:first-child { padding-top: 0 !important; }
div[data-testid="stAppViewBlockContainer"] { padding-top: 0 !important; }
div[data-testid="stVerticalBlock"] > div:first-child { padding-top: 0 !important; }
/* Reduce gap above tab bar */
div[data-testid="stTabs"] { margin-top: 0 !important; padding-top: 0 !important; }
.stTabs { margin-top: 0 !important; padding-top: 0 !important; }

/* ── Sticky tabs — fix for Streamlit's inner scroll container ────── */
div[data-testid="stAppViewContainer"] {
    overflow: visible !important;
}
section.main {
    overflow: visible !important;
}
.stTabs [data-baseweb="tab-list"] {
    position: -webkit-sticky;
    position: sticky;
    top: 0;
    z-index: 9999;
    background-color: var(--bg-secondary) !important;
    border-bottom: 1px solid var(--border);
    gap: 0;
    box-shadow: 0 4px 16px rgba(0,0,0,0.6);
    margin-top: 0 !important;
    padding-top: 0 !important;
    width: 100%;
}
.stTabs [data-baseweb="tab"] {
    background-color: transparent;
    color: var(--text-secondary) !important;
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    padding: 0.75rem 1.5rem;
    border-bottom: 2px solid transparent;
    transition: color 0.2s ease, border-bottom-color 0.2s ease; /* ✦ ANIMATION — smooth tab colour shift */
}
.stTabs [aria-selected="true"] {
    color: var(--accent-amber) !important;
    border-bottom: 2px solid var(--accent-amber) !important;
    background-color: transparent !important;
}
.stTabs [data-baseweb="tab-panel"] {
    padding-top: 1rem !important;
}

/* ✦ ANIMATION — fade-in when tab content loads */
@keyframes fadein {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
}
.stTabs [data-baseweb="tab-panel"] > div {
    animation: fadein 0.3s ease forwards;
}

section[data-testid="stSidebar"] {
    background-color: var(--bg-secondary);
    border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] * {
    color: var(--text-primary) !important;
}

/* ── Sidebar toggle — all selectors in one block ────────────────── */
/* NOTE: these data-testid selectors target Streamlit internals and  */
/* may silently break on Streamlit upgrades. Non-critical styling.   */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"] button,
button[kind="header"] {
    background-color: var(--bg-card) !important;
    border: 1px solid var(--accent-amber) !important;
    border-radius: 4px !important;
    color: var(--accent-amber) !important;
    opacity: 1 !important;
    visibility: visible !important;
}
[data-testid="collapsedControl"]:hover,
[data-testid="stSidebarCollapseButton"] button:hover,
button[kind="header"]:hover {
    background-color: var(--bg-card-hover) !important;
}
[data-testid="stSidebarCollapseButton"] button svg {
    fill: var(--accent-amber) !important;
    stroke: var(--accent-amber) !important;
}

/* ══════════════════════════════════════════════════════════════════
   CARD SYSTEM
   Base class: .card
   Modifiers:
     .card--primary   — tanker anomaly hero card (red tint border, subtle gradient)
     .card--sm        — compact card (less padding, no min-height)
     .card--muted     — transparent background, reduced opacity (meta/last-updated)
     .card--headline  — tall overview headline cards (min-height 268px)
     .card--kpi       — key-numbers row cards (larger metric value, min-height 158px)
   ══════════════════════════════════════════════════════════════════ */
.card {
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
    transition: transform 0.2s ease, box-shadow 0.2s ease; /* ✦ ANIMATION — hover lift */
}
.card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
}

/* Primary — tanker anomaly hero (red-tint border, dark gradient) */
.card--primary {
    border-color: rgba(239,68,68,0.35);
    background: linear-gradient(135deg, #1e1828 0%, #1a2235 100%);
    gap: 0;
}

/* Small — compact operational cards */
.card--sm {
    padding: 1rem 1.25rem;
    min-height: unset;
    justify-content: center;
}

/* Muted — last-updated / metadata card */
.card--muted {
    background: transparent;
    opacity: 0.75;
}

/* Headline — tall Overview cards */
.card--headline {
    min-height: unset;
}
.card--headline .card-body {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    min-height: 0;
}

/* KPI — key-numbers row cards */
.card--kpi {
    min-height: unset;
}
.card--kpi .card-label {
    margin-bottom: 0.3rem;
    flex-shrink: 0;
    min-height: 3.2rem;
    display: flex;
    align-items: flex-start;
}
.card--kpi .card-value-slot {
    flex: 0 0 3.5rem;
    display: flex;
    align-items: flex-start;
    overflow: visible;
}
.card--kpi .card-value {
    font-size: 1.62rem;
    line-height: 1.12;
}
.card--kpi .card-sub {
    font-size: var(--text-base);
    line-height: 1.52;
    margin-top: 0.45rem;
    flex-shrink: 0;
}
.card--kpi .kpi-storage-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 0.65rem;
    margin-top: 0.12rem;
}
.card--kpi .kpi-storage-row .card-value {
    margin: 0;
    line-height: 1.1;
}
.card--kpi .kpi-storage-row .kpi-storage-badge {
    flex-shrink: 0;
    display: flex;
    align-items: center;
}

/* ── Card typography elements ───────────────────────────────────── */
.card-label {
    font-family: var(--font-sans);
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-secondary);
    margin-bottom: 0.4rem;
}
.card-value {
    font-family: var(--font-mono);
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.1;
}
.card-value .headline-keyword {
    font-family: var(--font-mono);
    font-size: 1.48rem;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.15;
    letter-spacing: -0.02em;
}
.card-sub {
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    margin-top: 0.4rem;
    line-height: 1.4;
}
.card-timestamp {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-muted);
    margin-top: auto;
    padding-top: 0.75rem;
}

/* Headline card type overrides */
.card--headline .card-label  { font-size: var(--text-sm); }
.card--headline .card-value  { font-size: var(--text-lg); line-height: 1.2; }
.card--headline .card-value .headline-keyword { font-size: 1.48rem; }
.card--headline .card-sub    { font-size: var(--text-sm); line-height: 1.45; }
.card--headline .card-timestamp { padding-top: 0.85rem; flex-shrink: 0; align-self: stretch; }
.card--headline .overview-risk-table { font-size: var(--text-sm); }
.card--headline .overview-risk-table tr:first-child td { font-size: var(--text-xs); }

/* Headline cards 1 & 2 (larger emphasis — nth-child via grid parent) */
.headline-metrics-grid > .card--headline:nth-child(-n+2) .card-label  { font-size: var(--text-sm); margin-bottom: 0.45rem; }
.headline-metrics-grid > .card--headline:nth-child(-n+2) .card-value  { font-size: var(--text-lg); line-height: 1.25; }
.headline-metrics-grid > .card--headline:nth-child(-n+2) .card-value .headline-keyword { font-size: 1.56rem; }
.headline-metrics-grid > .card--headline:nth-child(-n+2) .card-sub    { font-size: var(--text-base); line-height: 1.55; margin-top: 0.5rem; }
.headline-metrics-grid > .card--headline:nth-child(-n+2) .card-sub:first-of-type { margin-top: 0.35rem; }
.headline-metrics-grid > .card--headline:nth-child(-n+2) .card-timestamp { padding-top: 0.9rem; }

/* Tanker card typography (reuses .card base + .card--primary / .card--sm) */
.card-ta-label {
    font-family: var(--font-sans);
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
}
.card--sm .card-ta-label { color: var(--text-muted); }
.card-ta-number-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
}
.card-ta-big-value {
    font-family: var(--font-mono);
    font-size: 2.8rem;   /* intentional one-off — hero number */
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1;
}
.card-ta-value {
    font-family: var(--font-mono);
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.25;
    margin-bottom: 0.5rem;
}
.card--sm .card-ta-value { font-size: var(--text-base); }
.card-ta-sub {
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    line-height: 1.5;
    margin-top: 0.2rem;
}
.card-ta-sub + .card-ta-sub { margin-top: 0.2rem; }

/* Headline metrics grid layout */
.headline-metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem;
    align-items: stretch;
    margin-bottom: 1rem;
}
.headline-metrics-grid > .card--headline {
    margin-bottom: 0;
    align-self: stretch;
}

/* Backward-compat aliases so existing HTML in this file still renders */
/* These map old class names → new card system classes */
.metric-card       { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem 1.5rem; margin-bottom: 1rem; min-height: 160px; height: 100%; box-sizing: border-box; overflow: visible; display: flex; flex-direction: column; }
.metric-label      { font-family: var(--font-sans); font-size: var(--text-xs); font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 0.4rem; }
.metric-value      { font-family: var(--font-mono); font-size: var(--text-base); font-weight: 600; color: var(--text-primary); line-height: 1.1; }
.metric-sub        { font-family: var(--font-sans); font-size: var(--text-sm); color: var(--text-secondary); margin-top: 0.4rem; line-height: 1.4; }
.metric-timestamp  { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--text-muted); margin-top: auto; padding-top: 0.75rem; }
.headline-mono-emphasis { font-family: var(--font-mono); font-size: var(--text-base); font-weight: 600; color: var(--text-primary); }

/* Supply Gap tab — regional + extrapolation tables (pandas HTML) */
table.supply-gap-table { width: 100%; border-collapse: collapse; }
table.supply-gap-table th,
table.supply-gap-table td { text-align: center !important; vertical-align: middle; padding: 0.5rem 0.65rem; }

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
    font-size: var(--text-xs);
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

/* ✦ ANIMATION — blinking terminal cursor (append ▌ span inside thesis-text in Python) */
@keyframes blink {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0; }
}
.thesis-cursor {
    animation: blink 1s step-end infinite;
    color: var(--accent-amber);
    font-weight: 300;
}

/* ── Risk badges ────────────────────────────────────────────────── */
.badge-red, .badge-amber, .badge-green, .badge-critical {
    display: inline-block;
    border-radius: 4px;
    padding: 0.35rem 0.6rem;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.05em;
}
.badge-red      { background: rgba(239,68,68,0.15);  color: #ef4444; border: 1px solid rgba(239,68,68,0.4);  }
.badge-amber    { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.4); }
.badge-green    { background: rgba(34,197,94,0.15);  color: #22c55e; border: 1px solid rgba(34,197,94,0.4);  }
.badge-critical { background: rgba(239,68,68,0.25);  color: #ff6b6b; border: 1px solid rgba(239,68,68,0.6);
                  animation: pulse-critical 2s ease-in-out infinite; } /* ✦ ANIMATION — pulsing glow */

/* ✦ ANIMATION — pulse keyframe for critical badge */
@keyframes pulse-critical {
    0%, 100% { box-shadow: 0 0 4px rgba(239,68,68,0.4); }
    50%       { box-shadow: 0 0 14px rgba(239,68,68,0.85); }
}

/* ── Section headers ────────────────────────────────────────────── */
.section-header {
    font-family: var(--font-sans);
    font-size: var(--text-xs);
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
    border-radius: 0 6px 6px 0;
    padding: 1rem 1.25rem;
    margin-top: 1.5rem;
}
.interpretation-label {
    font-family: var(--font-sans);
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--accent-teal);
    margin-bottom: 0.5rem;
}
.interpretation-text {
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    line-height: 1.65;
}

/* ── Extrapolation note ─────────────────────────────────────────── */
.extrapolation-note {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
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
    font-size: var(--text-sm);
    color: var(--text-secondary);
    line-height: 1.5;
    margin-top: 0.75rem;
}

/* ── Streamlit dataframe override ───────────────────────────────── */
.stDataFrame { background: var(--bg-card) !important; }

/* ── Vessel mix checkboxes ──────────────────────────────────────── */
/* Target the actual label node Streamlit renders */
div[data-testid="stCheckbox"] [data-testid="stWidgetLabel"] p,
div[data-testid="stCheckbox"] [data-testid="stWidgetLabel"] {
    color: #e8edf5 !important;
    font-family: var(--font-sans) !important;
    font-size: var(--text-sm) !important;
    font-weight: 600 !important;
}
/* Checked state — amber label */
div[data-testid="stCheckbox"]:has(input:checked) [data-testid="stWidgetLabel"] p,
div[data-testid="stCheckbox"]:has(input:checked) [data-testid="stWidgetLabel"] {
    color: var(--accent-amber) !important;
}

/* ── Divider ────────────────────────────────────────────────────── */
hr { border: none; border-top: 1px solid var(--border); margin: 1.5rem 0; }

/* ── Custom hover tooltips ──────────────────────────────────────── */
.has-tooltip { position: relative; display: inline-block; }
.has-tooltip .tooltip-text {
    visibility: hidden;
    opacity: 0;
    background: #2a3a55;
    color: #e8edf5;
    font-family: var(--font-sans);
    font-size: var(--text-xs);
    font-weight: 400;
    line-height: 1.5;
    text-transform: none;
    letter-spacing: normal;
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
.has-tooltip:hover .tooltip-text { visibility: visible; opacity: 1; }

/* ── Styled dropdown ────────────────────────────────────────────── */
details.info-dropdown {
    background: rgba(59,130,246,0.08);
    border: 1px solid rgba(59,130,246,0.25);
    border-radius: 6px;
    margin-top: 0.75rem;
}
details.info-dropdown summary {
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-primary);
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
    color: var(--text-secondary);
    font-size: var(--text-sm);
    transition: transform 0.2s;
}
details.info-dropdown[open] summary::after { transform: rotate(180deg); }
details.info-dropdown .dropdown-body {
    padding: 0.75rem 1rem 1rem 1rem;
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    line-height: 1.7;
    border-top: 1px solid rgba(59,130,246,0.15);
}

/* ── Expander content background fix ───────────────────────────── */
div[data-testid="stExpander"] details    { background-color: var(--bg-card) !important; border: 1px solid var(--border) !important; border-radius: 6px !important; }
div[data-testid="stExpander"] div[role="region"] { background-color: var(--bg-card) !important; }
div[data-testid="stExpander"] summary    { color: var(--text-primary) !important; background-color: var(--bg-card) !important; }

/* ── Pill toggles — vessel type & timeline ──────────────────────── */
div[data-testid="stButton"] button {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 20px !important;
    color: var(--text-secondary) !important;
    font-family: var(--font-sans) !important;
    font-size: var(--text-xs) !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em !important;
    padding: 0.3rem 0.9rem !important;
    transition: all 0.15s ease !important;
    white-space: nowrap !important;
}
div[data-testid="stButton"] button:hover {
    border-color: var(--accent-amber) !important;
    color: var(--accent-amber) !important;
    background: rgba(245,158,11,0.08) !important;
}
/* Active pill — set via a data attribute trick using key naming */
div[data-testid="stButton"].pill-active button {
    background: rgba(245,158,11,0.15) !important;
    border-color: var(--accent-amber) !important;
    color: var(--accent-amber) !important;
}

/* ── Signal breakdown panel (DEFICIT / LNG confidence explainer) ── */
details.signal-panel {
    margin-top: 0.6rem;
    border-radius: 6px;
    overflow: hidden;
}
details.signal-panel summary {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    font-family: var(--font-sans);
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-secondary);
    cursor: pointer;
    list-style: none;
    padding: 0;
    user-select: none;
}
details.signal-panel summary::-webkit-details-marker { display: none; }
details.signal-panel summary .signal-chevron {
    font-size: 0.6rem;
    color: var(--text-muted);
    transition: transform 0.18s ease;
    display: inline-block;
}
details.signal-panel[open] summary .signal-chevron { transform: rotate(90deg); }
details.signal-panel summary:hover { color: var(--text-primary); }

.signal-panel-body {
    margin-top: 0.55rem;
    background: rgba(10,14,26,0.6);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.7rem 0.9rem;
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.3s ease, padding 0.3s ease;
    padding-top: 0;
    padding-bottom: 0;
}
details.signal-panel[open] .signal-panel-body {
    max-height: 300px;
    padding: 0.7rem 0.9rem;
}
.signal-row {
    display: grid;
    grid-template-columns: 1.1rem 1fr auto;
    align-items: start;
    gap: 0 0.55rem;
    padding: 0.32rem 0;
    border-bottom: 1px solid rgba(42,58,85,0.5);
    font-family: var(--font-sans);
    font-size: var(--text-xs);
    line-height: 1.45;
}
.signal-row:last-child { border-bottom: none; }
.signal-check-on  { color: #f59e0b; font-size: 0.8rem; margin-top: 0.05rem; }
.signal-check-off { color: #4a5a72; font-size: 0.8rem; margin-top: 0.05rem; }
.signal-text { color: var(--text-secondary); }
.signal-text strong { color: var(--text-primary); font-family: var(--font-mono); font-weight: 600; }
.signal-outcome {
    font-family: var(--font-mono);
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    white-space: nowrap;
    padding: 0.15rem 0.45rem;
    border-radius: 3px;
}
.signal-outcome--stress {
    color: #f59e0b;
    background: rgba(245,158,11,0.12);
    border: 1px solid rgba(245,158,11,0.3);
}
.signal-outcome--neutral {
    color: #4a5a72;
    background: rgba(74,90,114,0.1);
    border: 1px solid rgba(74,90,114,0.25);
}
.signal-outcome--easing {
    color: #22c55e;
    background: rgba(34,197,94,0.1);
    border: 1px solid rgba(34,197,94,0.25);
}
.signal-panel-footer {
    margin-top: 0.55rem;
    font-family: var(--font-sans);
    font-size: 0.68rem;
    color: var(--text-muted);
    letter-spacing: 0.04em;
}
.signal-panel-footer strong { color: var(--text-secondary); }

/* ── Download button — amber ────────────────────────────────────── */
[data-testid="stDownloadButton"] > button {
    background-color: #f59e0b !important;
    color: #0a0e1a !important;
    border: none !important;
    font-weight: 600 !important;
    width: 100% !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background-color: #d97706 !important;
    color: #0a0e1a !important;
}

@media (max-width: 768px) {
    section[data-testid="stSidebar"] { display: none !important; }

    .main .block-container {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        max-width: 100% !important;
    }
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 2px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] { font-size: 0.72rem !important; padding: 5px 7px !important; }

    /* Overview 3-col headline cards → stack */
    .headline-metrics-grid {
        grid-template-columns: 1fr !important;
    }
    /* Overview 4-col KPI row → 2x2 */
    .kpi-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }
    /* Tanker 3-col → stack */
    .tanker-grid {
        grid-template-columns: 1fr !important;
    }
    /* Risk table: stop clipping */
    .overview-risk-table { width: 100% !important; font-size: 0.7rem !important; }
    .overview-risk-table td { padding: 3px 4px !important; }
    /* Fix horizontal bleed */
    div[data-testid="stAppViewContainer"] {
        overflow-x: hidden !important;
    }
    section.main {
        overflow-x: hidden !important;
    }
    .vessel-mix-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
}
}

/* ── Scenario toggle active state ───────────────────────────────── */
div[data-testid="stButton"] button[data-active="true"] {
    background: rgba(245,158,11,0.15) !important;
    border-color: var(--accent-amber) !important;
    color: var(--accent-amber) !important;
}

</style>
""", unsafe_allow_html=True)



# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def risk_badge(label: str) -> str:
    """
    Unified badge function — one vocabulary for all three card types.
    RED/AMBER/GREEN from DB map to CRITICAL/ELEVATED/STABLE for display.
    Also accepts CRITICAL/ELEVATED/STABLE/NORMAL directly.
    """
    TOOLTIPS = {
        "CRITICAL": "Severe disruption — conditions exceed emergency thresholds. Immediate market impact expected.",
        "ELEVATED": "Meaningful disruption — conditions are behind required pace or significantly below normal. Active monitoring required.",
        "STABLE":   "Within normal operating range — no significant disruption detected.",
    }
    if label is None:
        return '<span class="has-tooltip"><span class="badge-amber">UNKNOWN</span><span class="tooltip-text">Status unknown — data may not yet be available.</span></span>'
    label = label.upper()
    if label in ("RED", "CRITICAL"):
        tip = TOOLTIPS["CRITICAL"]
        return f'<span class="has-tooltip"><span class="badge-critical">CRITICAL</span><span class="tooltip-text">{tip}</span></span>'
    elif label in ("AMBER", "ELEVATED"):
        tip = TOOLTIPS["ELEVATED"]
        return f'<span class="has-tooltip"><span class="badge-amber">ELEVATED</span><span class="tooltip-text">{tip}</span></span>'
    elif label in ("GREEN", "STABLE", "NORMAL"):
        tip = TOOLTIPS["STABLE"]
        return f'<span class="has-tooltip"><span class="badge-green">STABLE</span><span class="tooltip-text">{tip}</span></span>'
    else:
        return f'<span class="badge-amber">{label}</span>'


def europe_crude_badge(label: str) -> str:
    """
    Specialised badge for Europe crude risk only.
    Adds fragility caveat to STABLE tooltip — Europe's crude gap is covered
    by contingent US SPR crude exports, not structural protection.
    Falls back to risk_badge() for non-STABLE labels.
    """
    if label is None or label.upper() not in ("GREEN", "STABLE", "NORMAL"):
        return risk_badge(label)
    tip = (
        "Europe receives only 4% of Hormuz crude (IEA Factsheet, Feb 2026) — a structural fact. "
        "The residual 0.25 Mb/d crude gap is currently covered by US SPR crude exports to Europe "
        "(~0.17 Mb/d observed through May 8 — 9 of 11 Mb of US SPR crude exported went to Europe, "
        "per IEA OMR/Kpler, May 13 2026). "
        "This is a contingent crisis response, not permanent structural protection: "
        "it depends on US export capacity staying high, freight economics remaining favourable, "
        "and SPR drawdown continuing. If any of those change, Europe's crude coverage narrows."
    )
    return f'<span class="has-tooltip"><span class="badge-green">STABLE</span><span class="tooltip-text" style="width:300px;">{tip}</span></span>'


def transit_badge(pct_of_normal) -> str:
    """Maps pct_of_normal to CRITICAL/ELEVATED/STABLE badge."""
    if pct_of_normal is None:
        return risk_badge(None)
    if pct_of_normal < 25:
        return risk_badge("CRITICAL")
    elif pct_of_normal <= 75:
        return risk_badge("ELEVATED")
    else:
        return risk_badge("STABLE")


def lng_score_badge(score: str) -> str:
    """Maps LNG rebalancing score to unified badge."""
    if score is None or score == "—":
        return risk_badge(None)
    s = str(score).upper()
    if s == "CRITICAL":
        return risk_badge("CRITICAL")
    elif s in ("ELEVATED", "DEFICIT"):
        return risk_badge("ELEVATED")
    elif s in ("STABLE", "BALANCED"):
        return risk_badge("STABLE")
    return f'<span class="badge-amber">{score}</span>'


def score_badge_fn(score: str) -> str:
    """Legacy alias — routes through lng_score_badge."""
    return lng_score_badge(score)


def render_signal_panel(lng: dict, panel_id: str = "signals") -> str:
    """
    Build the expandable signal breakdown panel for the LNG Market State card.

    Three signals drive the DEFICIT / confidence label:
      1. US utilization  > 90%  → no spare export capacity
      2. EU storage days_deficit → AMBER or RED pace shortfall
      3. Routing signal          → NEUTRAL or ASIA (not yet routing to Europe)

    When all three are stressed → HIGH confidence.
    When one eases (e.g. routing turns EUROPE) → MEDIUM confidence.

    Uses a native HTML <details> element so it works inside st.markdown
    without any Streamlit widget overhead.
    """
    util         = lng.get("us_utilization")    or 0.0
    days_def     = lng.get("days_deficit")       or 0.0
    routing      = (lng.get("routing_signal")    or "NEUTRAL").upper()
    storage_risk = (lng.get("storage_risk")      or "GREEN").upper()
    confidence   = (lng.get("confidence")        or "—").upper()
    score        = (lng.get("rebalancing_score") or "—").upper()
    storage_pct  = lng.get("storage_pct")        or 0.0
    seasonal_def = lng.get("seasonal_deficit")   or 0.0

    # ── Signal 1: US utilization ──────────────────────────────────────────────
    sig1_on = util > 90.0
    sig1_check = "signal-check-on" if sig1_on else "signal-check-off"
    sig1_icon  = "&#9745;" if sig1_on else "&#9744;"
    sig1_outcome_cls = "signal-outcome--stress" if sig1_on else "signal-outcome--easing"
    sig1_outcome_txt = "no spare capacity" if sig1_on else "capacity headroom"
    sig1_text = (
        f"<strong>{util:.1f}%</strong> US utilization "
        f"<span style='color:#4a5a72;'>&rarr; above 90% threshold</span>"
    )

    # ── Signal 2: EU storage pace ─────────────────────────────────────────────
    sig2_on = storage_risk in ("AMBER", "RED", "ELEVATED", "CRITICAL")
    sig2_check = "signal-check-on" if sig2_on else "signal-check-off"
    sig2_icon  = "&#9745;" if sig2_on else "&#9744;"
    sig2_outcome_cls = "signal-outcome--stress" if sig2_on else "signal-outcome--easing"
    # Map internal DB vocabulary (RED/AMBER/GREEN) to display vocabulary
    _risk_display = {"RED": "CRITICAL", "AMBER": "ELEVATED", "GREEN": "STABLE",
                     "CRITICAL": "CRITICAL", "ELEVATED": "ELEVATED", "STABLE": "STABLE"}
    sig2_outcome_txt = f"{_risk_display.get(storage_risk, storage_risk)} risk" if sig2_on else "on pace"
    sig2_text = (
        f"<strong>{storage_pct:.1f}%</strong> EU storage, "
        f"<strong>{days_def:.1f} days</strong> behind pace "
        f"<span style='color:#4a5a72;'>&rarr; {seasonal_def:.1f} % below seasonal avg</span>"
    )

    # ── Signal 3: Routing signal ──────────────────────────────────────────────
    sig3_on = routing in ("NEUTRAL", "ASIA")
    sig3_check = "signal-check-on" if sig3_on else "signal-check-off"
    sig3_icon  = "&#9745;" if sig3_on else "&#9744;"
    if routing == "ASIA":
        sig3_outcome_cls = "signal-outcome--stress"
        sig3_outcome_txt = "routing to Asia"
    elif routing == "NEUTRAL":
        sig3_outcome_cls = "signal-outcome--stress"
        sig3_outcome_txt = "not yet to Europe"
    else:
        sig3_outcome_cls = "signal-outcome--easing"
        sig3_outcome_txt = "routing to Europe"
    sig3_text = (
        f"Routing signal <strong>{routing}</strong> "
        f"<span style='color:#4a5a72;'>&rarr; JKM&ndash;TTF spread below $2.00 threshold</span>"
    )

    # ── Confidence footer ─────────────────────────────────────────────────────
    signals_stressed = sum([sig1_on, sig2_on, sig3_on])
    if signals_stressed == 3:
        conf_note = "All three signals in stress direction &mdash; <strong>HIGH</strong> confidence."
    elif signals_stressed == 2:
        conf_note = "Two of three signals stressed &mdash; <strong>MEDIUM</strong> confidence."
    elif signals_stressed == 1:
        conf_note = "One signal stressed &mdash; <strong>LOW</strong> confidence."
    else:
        conf_note = "No signals stressed &mdash; score may be revising."

    return f"""<details class="signal-panel" id="{panel_id}">
  <summary>
    <span class="signal-chevron">&#9654;</span>
    Why {score}&nbsp;&middot;&nbsp;{confidence} confidence
  </summary>
  <div class="signal-panel-body">
    <div class="signal-row">
      <span class="{sig1_check}">{sig1_icon}</span>
      <span class="signal-text">{sig1_text}</span>
      <span class="signal-outcome {sig1_outcome_cls}">{sig1_outcome_txt}</span>
    </div>
    <div class="signal-row">
      <span class="{sig2_check}">{sig2_icon}</span>
      <span class="signal-text">{sig2_text}</span>
      <span class="signal-outcome {sig2_outcome_cls}">{sig2_outcome_txt}</span>
    </div>
    <div class="signal-row">
      <span class="{sig3_check}">{sig3_icon}</span>
      <span class="signal-text">{sig3_text}</span>
      <span class="signal-outcome {sig3_outcome_cls}">{sig3_outcome_txt}</span>
    </div>
    <div class="signal-panel-footer">{conf_note}</div>
  </div>
</details>"""


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


def _status_span(text: str, color: str, bg: str, border: str) -> str:
    """Return a styled inline badge span."""
    return (
        f'<span style="display:inline-block;padding:0.2rem 0.6rem;border-radius:4px;'
        f'font-family:monospace;font-size:0.75rem;font-weight:600;'
        f'background:{bg};color:{color};border:1px solid {border};">'
        f'{text}</span>'
    )


def render_sidebar(crisis: dict) -> str:
    """Build sidebar status HTML. Returns a string for st.markdown(unsafe_allow_html=True)."""
    mine_status  = crisis.get("mine_clearance_status") or "UNKNOWN"
    diplo_status = crisis.get("diplomatic_status")     or "UNKNOWN"
    blockade     = crisis.get("us_blockade_active")
    as_of        = crisis.get("as_of_date")            or "—"
    updated      = crisis.get("last_updated")          or "—"

    if mine_status == "COMPLETE":
        mine_span = _status_span(mine_status, "#22c55e", "rgba(34,197,94,0.15)", "rgba(34,197,94,0.4)")
    elif mine_status == "IN PROGRESS":
        mine_span = _status_span(mine_status, "#ef4444", "rgba(239,68,68,0.15)", "rgba(239,68,68,0.4)")
    else:
        mine_span = _status_span(mine_status, "#f59e0b", "rgba(245,158,11,0.15)", "rgba(245,158,11,0.4)")

    if diplo_status == "CEASEFIRE":
        diplo_span = _status_span(diplo_status, "#22c55e", "rgba(34,197,94,0.15)", "rgba(34,197,94,0.4)")
    elif diplo_status in ("ACTIVE CONFLICT", "CEASEFIRE COLLAPSED"):
        diplo_span = _status_span(diplo_status, "#ef4444", "rgba(239,68,68,0.15)", "rgba(239,68,68,0.4)")
    else:
        diplo_span = _status_span(diplo_status, "#f59e0b", "rgba(245,158,11,0.15)", "rgba(245,158,11,0.4)")

    if blockade == 1:
        block_span = _status_span("ACTIVE",   "#ef4444", "rgba(239,68,68,0.15)", "rgba(239,68,68,0.4)")
    else:
        block_span = _status_span("INACTIVE", "#22c55e", "rgba(34,197,94,0.15)", "rgba(34,197,94,0.4)")

    lbl = "font-size:0.65rem;letter-spacing:0.1em;text-transform:uppercase;color:#4a5a72;"
    return (
        '<div style="font-family:IBM Plex Sans,sans-serif;font-size:0.82rem;'
        'color:#8a9bb5;line-height:1.65;">'
        f'<div style="margin-bottom:0.6rem;"><span style="{lbl}">Mine Clearance</span><br>{mine_span}</div>'
        f'<div style="margin-bottom:0.6rem;"><span style="{lbl}">Diplomatic Status</span><br>{diplo_span}</div>'
        f'<div style="margin-bottom:1rem;"><span style="{lbl}">US Naval Blockade</span><br>{block_span}</div>'
        f'<div style="font-size:0.62rem;color:#4a5a72;">As of {as_of} · Updated {updated}</div>'
        '</div>'
    )


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOAD — cached so queries run once per session, not on every interaction
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)  # refresh every 5 minutes
def load_all_data():
    """Load all data from the database in one call. Cached for 5 minutes."""
    return {
        "tanker":        get_latest_tanker_metrics(),
        "lng":           get_latest_lng_metrics(),
        "gap":           get_latest_supply_gap_metrics(),
        "crisis":        get_crisis_context(),
        "transit_df":    get_transit_history(),
        "anomaly_df":    get_anomaly_log_history(),
        "prices_df":     get_price_history(),
        "util_df":       get_terminal_utilization(),
        "storage_df":    get_european_storage(),
        "baseline_df":   get_storage_seasonal_baseline(),
        "yoy_level":     get_storage_yoy_level(),
        "gap_log_df":    get_supply_gap_log_history(),
        "vessel_mix":    get_vessel_mix_latest(),
        "vessel_mix_df": get_vessel_mix_history(),
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
        <div style="font-family:'IBM Plex Sans',sans-serif;font-size:1rem;
                    font-weight:600;color:#e8edf5;margin-bottom:1.5rem;
                    padding-bottom:0.75rem;border-bottom:1px solid #2a3a55;">
            Gulf Crisis Supply Intelligence
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="section-header" style="margin-top:0;">Crisis Status</div>
    """, unsafe_allow_html=True)

    st.markdown(render_sidebar(crisis), unsafe_allow_html=True)

    if crisis.get("notes"):
        with st.expander("📋  Analyst Notes", expanded=False):
            st.markdown(f"""
                <div style="font-family:'IBM Plex Sans',sans-serif;font-size:0.82rem;
                            color:#8a9bb5;line-height:1.65;">
                    {crisis.get("notes")}
                </div>
            """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown("""
        <div class="section-header" style="margin-top:0;">Data Sources</div>
        <div style="font-family:'IBM Plex Sans',sans-serif;font-size:0.78rem;
                    color:#8a9bb5;line-height:1.8;">
            AIS transit data — IMF PortWatch<br>
            LNG prices — yfinance (JKM=F, TTF)<br>
            US LNG exports — EIA Open Data API<br>
            EU gas storage — GIE AGSI+<br>
            Supply gap assumptions — IEA Factsheet Feb 2026
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Weekly Report download ────────────────────────────────────────────
    st.markdown("""
        <div class="section-header" style="margin-top:0;">Weekly Report</div>
    """, unsafe_allow_html=True)

    if st.button("📄 Generate PDF Report", use_container_width=True):
        with st.spinner("Building report..."):
            try:
                _proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if _proj_root not in sys.path:
                    sys.path.insert(0, _proj_root)
                from reports.generate_report import build_report_bytes
                pdf_bytes = build_report_bytes()
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                st.download_button(
                    label="⬇ Download Report",
                    data=pdf_bytes,
                    file_name=f"gulf_crisis_weekly_{date_str}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except ImportError as e:
                st.error(f"Missing dependency: {e}\n\nRun: pip install reportlab plotly kaleido")
            except Exception as e:
                st.error(f"Report generation failed: {e}")

    # ── Past Reports archive ──────────────────────────────────────────────
    from pathlib import Path as _Path
    _archive_dir = _Path(__file__).resolve().parent.parent / "reports" / "archive"
    if _archive_dir.exists():
        _past = sorted(_archive_dir.glob("gulf_crisis_weekly_*.pdf"), reverse=True)
        if _past:
            st.markdown("""
                <div style="font-family:'IBM Plex Sans',sans-serif;font-size:0.75rem;
                            color:#8a9bb5;margin-top:0.75rem;margin-bottom:0.4rem;">
                    Past Reports
                </div>
            """, unsafe_allow_html=True)
            for _pdf in _past[:8]:
                _label = _pdf.stem.replace("gulf_crisis_weekly_", "")
                with open(_pdf, "rb") as _f:
                    st.download_button(
                        label=f"⬇ {_label}",
                        data=_f.read(),
                        file_name=_pdf.name,
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"past_report_{_label}",
                    )

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
    "🚢  Vessel Transits",
    "📊  Supply Gap",
    "🔥  LNG Cargo Flows",
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
            <div class="thesis-text">
                <span id="typewriter-target"></span><span class="thesis-cursor">▌</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    import streamlit.components.v1 as components
    components.html(f"""
        <script>
        (function() {{
            const text = {repr(thesis_text)};
            function tryType() {{
                const el = window.parent.document.getElementById('typewriter-target');
                if (!el) {{ setTimeout(tryType, 100); return; }}
                let i = 0;
                function type() {{
                    if (i < text.length) {{
                        el.textContent += text[i++];
                        setTimeout(type, 18);
                    }}
                }}
                type();
            }}
            setTimeout(tryType, 400);
        }})();
        </script>
    """, height=0)

    

    # ── Consolidated metrics row — 4 KPI cards below thesis block ────────────

    pct = safe(tanker.get("pct_of_normal"), "{:.1f}%")
    pct_val = tanker.get("pct_of_normal")
    trend = safe(tanker.get("trend_direction"), fallback="—")
    ts = fmt_timestamp(tanker.get("logged_at"))
    baseline_ships = safe(tanker.get("baseline_annual"), "{:.0f}")

    score = safe(lng.get("rebalancing_score"), fallback="—")
    confidence = safe(lng.get("confidence"), fallback="—")
    routing = safe(lng.get("routing_signal"), fallback="—")
    util = safe(lng.get("us_utilization"), "{:.1f}%")
    ts2 = fmt_timestamp(lng.get("logged_at"))
    _transit_badge = transit_badge(pct_val)
    _lng_badge = lng_score_badge(lng.get("rebalancing_score"))

    asia_crude = gap.get("asia_crude_risk") or "—"
    asia_lng   = gap.get("asia_lng_risk")   or "—"
    eur_crude  = gap.get("europe_crude_risk") or "—"
    eur_lng    = gap.get("europe_lng_risk")   or "—"
    ts3        = fmt_timestamp(gap.get("logged_at"))
    # US is a Hormuz importer of last resort only — not meaningfully exposed
    # to a Hormuz closure. Hardcoded GREEN is analytically correct but must be
    # revisited if a US domestic supply shock scenario is added to the model.
    US_CRUDE_RISK = "GREEN"
    US_LNG_RISK   = "GREEN"

    st.markdown(f"""
<div class="headline-metrics-grid">
    <div class="card card--headline">
        <div class="card-body">
            <div class="card-label">Hormuz Transit Index</div>
            <div class="card-value"><span class="headline-keyword">{pct}</span></div>
            <div class="card-sub">of pre-crisis normal &nbsp;&nbsp; {_transit_badge}</div>
            <div class="card-sub">Trend &nbsp;<span class="headline-mono-emphasis">{trend}</span></div>
            <div class="card-sub">{safe(tanker.get('transit_count'))} ships/day vs {baseline_ships} baseline (full-year 2025)</div>
        </div>
        <div class="card-timestamp">Updated {ts}</div>
    </div>
    <div class="card card--headline">
        <div class="card-body">
            <div class="card-label">LNG Market State</div>
            <div class="card-value"><span class="headline-keyword">{score}</span></div>
            <div class="card-sub">
                {_lng_badge} &nbsp;·&nbsp; Confidence {confidence}
            </div>
            <div class="card-sub">Routing signal &nbsp;<span class="headline-mono-emphasis">{routing}</span></div>
            <div class="card-sub">US utilization <span class="headline-mono-emphasis">{util}</span></div>
            {render_signal_panel(lng, panel_id="signals_overview")}
        </div>
        <div class="card-timestamp">Updated {ts2}</div>
    </div>
    <div class="card card--headline">
        <div class="card-body">
            <div class="card-label">Regional Risk Summary</div>
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
                        <td style="padding:0.35rem 0;text-align:center;">{risk_badge(US_CRUDE_RISK)}</td>
                        <td style="padding:0.35rem 0;text-align:center;">{risk_badge(US_LNG_RISK)}</td>
                    </tr>
                </table>
            </div>
        </div>
        <div class="card-timestamp">Updated {ts3}</div>
    </div>
</div>
""", unsafe_allow_html=True)

    # ── Supply gap KPIs ───────────────────────────────────────────────────────

    st.markdown(f"""
<div class="kpi-grid" style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1rem;align-items:stretch;margin-bottom:1rem;">
    <div class="card card--kpi">
        <div class="card-label" style="display:flex;align-items:center;gap:0.35rem;">Net Crude Gap</div>
        <div class="card-value-slot"><div class="card-value" data-countup="{gap.get('crude_gap_net_mbd') or 0}" data-decimals="2" data-suffix="">{safe(gap.get("crude_gap_net_mbd"), "{:.2f}")}</div></div>
        <div class="card-sub">Mb/d after bypass + SPR offsets</div>
    </div>
    <div class="card card--kpi">
        <div class="card-label" style="display:flex;align-items:center;gap:0.35rem;">LNG Gap (Asia)<span class="has-tooltip" style="cursor:help;flex-shrink:0;"><span style="font-size:0.75rem;color:var(--text-muted);">ⓘ</span><span class="tooltip-text" style="width:260px;">Volume of LNG that would normally transit Hormuz to Asia daily, now offline. Derived: 10.8 Bcf/d normal Hormuz LNG flow (IEA 2025) × 90% Asia destination share × ~96% disruption rate. Bcf/d = billion cubic feet per day, the standard US gas flow unit.</span></span></div>
        <div class="card-value-slot"><div class="card-value" data-countup="{gap.get('asia_lng_gap_bcfd') or 0}" data-decimals="2" data-suffix="">{safe(gap.get("asia_lng_gap_bcfd"), "{:.2f}")}</div></div>
        <div class="card-sub">Bcf/d — no pipeline bypass available</div>
    </div>
    <div class="card card--kpi">
        <div class="card-label" style="display:flex;align-items:center;gap:0.35rem;">EU Storage vs Seasonal<span class="has-tooltip" style="cursor:help;flex-shrink:0;white-space:nowrap;"><span style="font-size:0.75rem;color:var(--text-muted);">ⓘ</span><span class="tooltip-text" style="width:260px;">EU gas storage vs the 5-year seasonal average (2020–2024) for this calendar date. Not a fixed target — shows how far below where Europe normally is at this time of year. Normal mid-May storage is ~51–53%; current is ~36%.</span></span></div>
        <div class="card-value-slot kpi-storage-row" style="align-items:flex-start;">
            <div class="card-value" data-countup="{lng.get('storage_pct') or 0}" data-decimals="1" data-suffix="%">{safe(lng.get("storage_pct"), "{:.1f}%")}</div>
            <span class="kpi-storage-badge">{risk_badge(lng.get("storage_risk"))}</span>
        </div>
        <div class="card-sub">{safe(lng.get("seasonal_deficit"), "{:.1f} %")} below seasonal avg</div>
    </div>
    <div class="card card--kpi">
        <div class="card-label" style="display:flex;align-items:center;gap:0.35rem;">US export terminal utilization<span class="has-tooltip" style="cursor:help;flex-shrink:0;"><span style="font-size:0.75rem;color:var(--text-muted);">ⓘ</span><span class="tooltip-text" style="width:260px;">Actual LNG exports as % of nameplate liquefaction capacity across 8 US terminals (EIA data, Feb 2026). Above 100% means terminals are exceeding their design baseline — less maintenance downtime, trains at peak output. No spare capacity remains to offset the Hormuz LNG loss.</span></span></div>
        <div class="card-value-slot"><div class="card-value" data-countup="{lng.get('us_utilization') or 0}" data-decimals="1" data-suffix="%">{safe(lng.get("us_utilization"), "{:.1f}%")}</div></div>
        <div class="card-sub">System at maximum — no relief capacity</div>
<div class="card-sub" style="margin-top:0.25rem;color:var(--text-muted);font-size:0.62rem;">Latest available: Feb 2026 (EIA 6–8 week lag)</div>
    </div>
</div>
""", unsafe_allow_html=True)
    
import streamlit.components.v1 as components
components.html("""
<script>
(function() {
    function animateCountUp(el) {
        var target   = parseFloat(el.dataset.countup);
        var decimals = parseInt(el.dataset.decimals || "0");
        var suffix   = el.dataset.suffix || "";
        var duration = 900;
        var start    = performance.now();
        function step(now) {
            var progress = Math.min((now - start) / duration, 1);
            var ease     = 1 - Math.pow(1 - progress, 3);
            el.textContent = (target * ease).toFixed(decimals) + suffix;
            if (progress < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    }
    function tryAnimate() {
        var els = window.parent.document.querySelectorAll("[data-countup]");
        if (els.length === 0) { setTimeout(tryAnimate, 100); return; }
        els.forEach(animateCountUp);
    }
    tryAnimate();
})();
</script>
""", height=0)


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
        "2026-04-16": "Ceasefire collapse",
    }

    # ── Section 1 — Current reading metric card ───────────────────────────────
    st.markdown('<div class="section-header" style="margin-top:0.5rem;">Hormuz Transit Anomaly Index</div>', unsafe_allow_html=True)
    # ── Static Hormuz strait map — chokepoint marker ─────────────────────────
    _map_pct = tanker.get("pct_of_normal") or 0
    _dot_color = (
        "#ef4444" if _map_pct < 30 else
        "#f59e0b" if _map_pct < 70 else
        "#22c55e"
    )
    _risk_label = (
        "CRITICAL — strait effectively closed"   if _map_pct < 30 else
        "ELEVATED — significant disruption"       if _map_pct < 70 else
        "STABLE — near-normal traffic"
    )

    import streamlit.components.v1 as components
    components.html(f"""
    <div style="margin-bottom:1.5rem;">
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;
                    letter-spacing:0.1em;text-transform:uppercase;color:#4a5a72;
                    margin-bottom:0.4rem;">
            Strait of Hormuz — Chokepoint Status
            <span style="color:#2a3a55;margin:0 0.5rem;">|</span>
            <span style="color:{_dot_color};">{_map_pct:.1f}% of normal · {_risk_label}</span>
        </div>

        <svg viewBox="0 0 700 200" width="100%" xmlns="http://www.w3.org/2000/svg"
             style="background:#0a0e1a;border:1px solid #1a2235;border-radius:8px;">

            <!-- Water body Persian Gulf -->
            <path d="M 0 60 Q 100 40 200 55 Q 280 65 320 80
                       Q 340 88 360 95 Q 380 100 400 95
                       Q 420 90 440 85 Q 480 75 520 78
                       Q 560 82 600 88 Q 650 95 700 100
                       L 700 200 L 0 200 Z"
                  fill="#0d1f35" opacity="0.9"/>

            <!-- Gulf of Oman -->
            <path d="M 480 0 Q 540 10 600 30 Q 650 50 700 70
                       L 700 200 L 480 200 Z"
                  fill="#0d1f35" opacity="0.7"/>

            <!-- Iran top -->
            <path d="M 0 0 L 700 0 L 700 55 Q 620 25 540 18
                       Q 460 12 400 20 Q 340 28 300 40
                       Q 250 52 200 48 Q 120 42 60 30 Z"
                  fill="#111827"/>

            <!-- Arabia / UAE bottom -->
            <path d="M 0 200 L 0 130 Q 80 120 160 128
                       Q 240 136 300 140 Q 340 142 370 138
                       Q 400 133 430 128 Q 460 122 490 118
                       L 490 200 Z"
                  fill="#111827"/>

            <!-- Musandam peninsula Oman -->
            <path d="M 430 128 Q 455 108 470 90 Q 478 76 482 60
                       Q 484 50 488 42 Q 492 30 498 20
                       L 510 0 L 700 0 L 700 70
                       Q 650 50 600 30 Q 540 10 490 118 Z"
                  fill="#111827"/>

            <!-- Strait channel dotted line -->
            <line x1="320" y1="88" x2="490" y2="60"
                  stroke="#1e3a5f" stroke-width="1" stroke-dasharray="5,4"/>

            <!-- Outbound flow arrow (Gulf to Oman) -->
            <g opacity="0.45">
                <line x1="340" y1="100" x2="440" y2="82"
                      stroke="#f59e0b" stroke-width="1.5" stroke-linecap="round"/>
                <polygon points="440,82 433,78 434,86" fill="#f59e0b"/>
            </g>

            <!-- Inbound flow arrow (Oman to Gulf) -->
            <g opacity="0.35">
                <line x1="460" y1="92" x2="360" y2="110"
                      stroke="#14b8a6" stroke-width="1.5" stroke-linecap="round"/>
                <polygon points="360,110 367,106 368,114" fill="#14b8a6"/>
            </g>

            <!-- Chokepoint pulsing dot -->
            <circle cx="430" cy="85" r="5"
                    fill="{_dot_color}" opacity="0.9">
                <animate attributeName="r"
                         values="5;10;5" dur="2.5s" repeatCount="indefinite"/>
                <animate attributeName="opacity"
                         values="0.9;0.2;0.9" dur="2.5s" repeatCount="indefinite"/>
            </circle>
            <circle cx="430" cy="85" r="4" fill="{_dot_color}" opacity="0.6"/>

            <!-- Key ports -->
            <circle cx="500" cy="122" r="3" fill="#3b82f6" opacity="0.7"/>
            <text x="506" y="132" font-family="IBM Plex Sans" font-size="8"
                  fill="#3b82f6" opacity="0.8">Fujairah</text>

            <circle cx="415" cy="48" r="3" fill="#8a9bb5" opacity="0.6"/>
            <text x="421" y="47" font-family="IBM Plex Sans" font-size="8"
                  fill="#8a9bb5" opacity="0.7">Bandar Abbas</text>

            <circle cx="55" cy="148" r="3" fill="#8a9bb5" opacity="0.5"/>
            <text x="62" y="148" font-family="IBM Plex Sans" font-size="8"
                  fill="#8a9bb5" opacity="0.6">Ras Laffan (Qatar)</text>

            <!-- Region labels -->
            <text x="160" y="170" font-family="IBM Plex Sans" font-size="11"
                  fill="#1e3a5f" letter-spacing="1">PERSIAN GULF</text>
            <text x="560" y="48" font-family="IBM Plex Sans" font-size="10"
                  fill="#1e3a5f" letter-spacing="1">GULF OF OMAN</text>
            <text x="260" y="28" font-family="IBM Plex Sans" font-size="9"
                  fill="#1a2f4a">IRAN</text>
            <text x="140" y="155" font-family="IBM Plex Sans" font-size="9"
                  fill="#1a2f4a">UAE / ARABIA</text>
            <text x="520" y="158" font-family="IBM Plex Sans" font-size="9"
                  fill="#1a2f4a">OMAN</text>
            <text x="375" y="72" font-family="IBM Plex Mono" font-size="8"
                  fill="#2a4a6a" text-anchor="middle" letter-spacing="0.5">
                STRAIT OF HORMUZ
            </text>

            <!-- Legend -->
            <circle cx="16" cy="16" r="5" fill="{_dot_color}" opacity="0.85">
                <animate attributeName="opacity"
                         values="0.85;0.3;0.85" dur="2.5s" repeatCount="indefinite"/>
            </circle>
            <text x="26" y="20" font-family="IBM Plex Sans" font-size="8"
                  fill="#4a5a72">Chokepoint status</text>

            <line x1="10" y1="32" x2="22" y2="32"
                  stroke="#f59e0b" stroke-width="1.5" opacity="0.6"/>
            <polygon points="22,32 19,29.5 19,34.5" fill="#f59e0b" opacity="0.6"/>
            <text x="26" y="36" font-family="IBM Plex Sans" font-size="8"
                  fill="#4a5a72">Outbound flow</text>

            <line x1="10" y1="46" x2="22" y2="46"
                  stroke="#14b8a6" stroke-width="1.5" opacity="0.5"/>
            <polygon points="10,46 13,43.5 13,48.5" fill="#14b8a6" opacity="0.5"/>
            <text x="26" y="50" font-family="IBM Plex Sans" font-size="8"
                  fill="#4a5a72">Inbound flow</text>

            <circle cx="16" cy="60" r="3" fill="#3b82f6" opacity="0.7"/>
            <text x="26" y="64" font-family="IBM Plex Sans" font-size="8"
                  fill="#4a5a72">Key port</text>
        </svg>

        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;
                    color:#2a3a55;margin-top:0.3rem;">
            Chokepoint status colour driven by live transit index.
            Geography and port positions are reference data.
        </div>
    </div>
    """, height=240)

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
    _flag_badge  = transit_badge(tanker.get("pct_of_normal"))
    st.markdown(f"""
<div class="tanker-grid" style="display:grid;grid-template-columns:2fr 1.5fr 1fr;gap:1rem;align-items:stretch;margin-bottom:1.5rem;">
    <div class="card card--primary">
        <div class="card-ta-label">Hormuz Transit · Current Reading</div>
        <div class="card-ta-number-row">
            <span class="card-ta-big-value" data-countup="{tanker.get('pct_of_normal') or 0}" data-decimals="1" data-suffix="%">{safe(tanker.get("pct_of_normal"), "{:.1f}%")}</span>
            {_flag_badge}
        </div>
        <div class="card-ta-sub">of pre-crisis normal &nbsp;·&nbsp; {safe(tanker.get("transit_count"))} ships/day vs {safe(tanker.get("baseline_annual"), "{:.0f}")} baseline (full-year 2025)</div>
<div class="card-ta-sub" style="margin-top:0.75rem;color:#8a9bb5;">Hormuz carries ~20% of global oil supply. At {safe(tanker.get("pct_of_normal"), "{:.1f}%")} of normal traffic, the strait is effectively closed to commercial shipping.</div>
        <div class="card-ta-sub" style="margin-top:0.4rem;color:#4a5a72;">{(datetime.now(timezone.utc).date() - datetime(2026, 2, 28, tzinfo=timezone.utc).date()).days} days since crisis began — 28 Feb 2026</div>    </div>
    <div class="card" style="min-height:unset;">
        <div class="card-ta-label">7-Day Recovery Trend</div>
        <div class="card-ta-value">{safe(tanker.get("trend_direction"))}</div>
                <div class="card-ta-sub" style="margin-top:0.75rem;color:#8a9bb5;">At peak in 2024, Hormuz handled 93 ships/day across all vessel types. Today's count of {safe(tanker.get("transit_count"))} is the lowest sustained level since records began in 2019.</div>
    </div>
    <div style="display:flex;flex-direction:column;justify-content:space-between;min-height:320px;">
        <div class="card card--sm">
            <div class="card-ta-label">Fujairah Queue</div>
            <div class="card-ta-value">{anchorage_count} <span style="font-size:var(--text-sm);font-weight:400;color:var(--text-secondary);">vessels</span></div>
            <div class="card-ta-sub">{anchorage_badge}</div>
            <div class="card-ta-sub" style="margin-top:0.4rem;">{anchorage_status}</div>
        </div>
        <div class="card card--sm card--muted">
            <div class="card-ta-label">Data Last Updated</div>
            <div class="card-ta-value">{fmt_timestamp(tanker.get("logged_at"))}</div>
            <div class="card-ta-sub">Kaggle · IMF PortWatch · Kpler</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    # ── Section 2 — Transit count chart ──────────────────────────────────────
    st.markdown('<div class="section-header">Daily Transit Count — Hormuz Strait</div>', unsafe_allow_html=True)

    transit_df = data["transit_df"]

    if not transit_df.empty:
        fig_transit = go.Figure()

        # Merge crisis events into transit_df for hover display
        crisis_events_df = pd.DataFrame([
            {"date": pd.Timestamp(k), "event": f"⚑ {v}"}
            for k, v in CRISIS_EVENTS.items()
        ])
        transit_df = transit_df.merge(crisis_events_df, on="date", how="left")
        transit_df["event"] = transit_df["event"].fillna("")

        # Baseline reference line
        fig_transit.add_trace(go.Scatter(
            x=transit_df["date"],
            y=transit_df["baseline_annual"],
            name="Pre-crisis baseline",
            line=dict(color="#4a5a72", width=1.5, dash="dash"),
            hovertemplate="%{y:.0f} ships/day<extra>Baseline</extra>",
        ))

        # Actual transit count with event hover
        fig_transit.add_trace(go.Scatter(
            x=transit_df["date"],
            y=transit_df["transit_count"],
            name="Daily transit count",
            line=dict(color="#f59e0b", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(245,158,11,0.08)",
            customdata=transit_df["event"],
            hovertemplate="<b>%{x|%b %d, %Y}</b><br>%{y} ships/day<br>%{customdata}<extra></extra>",
        ))

        # Crisis event vertical lines — numbered markers instead of rotated text
        _crisis_keys = list(CRISIS_EVENTS.keys())
        for i, (date_str, label) in enumerate(CRISIS_EVENTS.items(), 1):
            _xanchor = "left" if date_str == _crisis_keys[0] else ("right" if date_str == _crisis_keys[-1] else "center")
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
                xanchor=_xanchor,
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
                tickformat="%b %d",
                dtick=7*24*60*60*1000,
                tick0="2026-02-28",
            ),
            yaxis=dict(
                gridcolor="#1a2235",
                linecolor="#2a3a55",
                tickfont=dict(size=12, family="IBM Plex Mono"),
                title=dict(text="Ships / day", font=dict(size=11)),
            ),
            hovermode="closest",
        )

        # Numbered event legend — generated from CRISIS_EVENTS dict
        legend_spans = "".join(
            f'<span><span style="color:#ef4444;font-family:\'IBM Plex Mono\',monospace;font-weight:600;">{i}</span> &nbsp;{label}</span>'
            for i, (_, label) in enumerate(CRISIS_EVENTS.items(), 1)
        )
        st.markdown(f"""
            <div style="display:flex;flex-wrap:wrap;gap:0.5rem 1.5rem;margin-top:0.5rem;
                        font-family:'IBM Plex Sans',sans-serif;font-size:0.8rem;color:#8a9bb5;">
                {legend_spans}
            </div>
        """, unsafe_allow_html=True)

    else:
        st.markdown('<div class="info-note">Transit history data not available.</div>',
                    unsafe_allow_html=True)

    # ── Section 3 — AIS dark events & diversions ──────────────────────────────
    dark_count = tanker.get("dark_events") or 0
    st.markdown(f"""
        <div class="info-note">
            AIS vessel data: accumulating ({dark_count} events). Section activates when coverage is sufficient.
        </div>
    """, unsafe_allow_html=True)

    # ── Section 4 — Vessel Mix Panel ──────────────────────────────────────────
    st.markdown('<div class="section-header">Vessel Mix — Disruption by Type</div>',
                unsafe_allow_html=True)

    vessel_mix    = data["vessel_mix"]
    vessel_mix_df = data["vessel_mix_df"]

    # ── 4a — Vessel type metric cards ─────────────────────────────────────────
    # One card per vessel type. Color-coded: red border if anomaly, green if normal.
    # Layout: 5 type cards + 1 total card = 6 across one row.

    VESSEL_TYPES = [
        ("Tanker",        "n_tanker",        "baseline_tanker",        "pct_normal_tanker",        "z_score_tanker",        "anomaly_flag_tanker"),
        ("Container",     "n_container",     "baseline_container",     "pct_normal_container",     "z_score_container",     "anomaly_flag_container"),
        ("Dry Bulk",      "n_dry_bulk",      "baseline_dry_bulk",      "pct_normal_dry_bulk",      "z_score_dry_bulk",      "anomaly_flag_dry_bulk"),
        ("RoRo",          "n_roro",          "baseline_roro",          "pct_normal_roro",          "z_score_roro",          "anomaly_flag_roro"),
        ("General Cargo", "n_general_cargo", "baseline_general_cargo", "pct_normal_general_cargo", "z_score_general_cargo", "anomaly_flag_general_cargo"),
        ("ALL VESSELS",   "n_total",         "baseline_total",         "pct_normal_total",         "z_score_total",         "anomaly_flag_total"),
    ]

    if vessel_mix:
        cards_html = '<div class="vessel-mix-grid" style="display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:0.65rem;margin-bottom:1.5rem;">'
        for label, n_key, b_key, pct_key, z_key, flag_key in VESSEL_TYPES:
            today     = vessel_mix.get(n_key)
            baseline  = vessel_mix.get(b_key)
            pct       = vessel_mix.get(pct_key)
            z         = vessel_mix.get(z_key)
            is_anomaly= vessel_mix.get(flag_key) == 1
            is_total  = (label == "ALL VESSELS")

            # Border and background: standard border for all, teal for total
            if is_total:
                border_color = "rgba(20,184,166,0.45)"
                bg_color     = "rgba(20,184,166,0.06)"
                label_color  = "#14b8a6"
            else:
                border_color = "var(--border, #2a3a55)"
                bg_color     = "#1e2840"   # slightly lighter than --bg-card
                label_color  = "#8a9bb5"

            status_text  = "⚠ ANOMALY" if is_anomaly else "NORMAL"
            status_color = "#f59e0b"   if is_anomaly else "#22c55e"

            today_str    = str(today)    if today    is not None else "—"
            baseline_str = f"{baseline:.1f}" if baseline is not None else "—"
            pct_str      = f"{pct:.1f}%" if pct      is not None else "—"
            z_str        = f"{z:+.2f}"   if z        is not None else "—"

            # ALL VESSELS gets slightly more padding and bolder label to stand out
            extra_style = "padding:1rem 1.1rem;" if is_total else "padding:0.85rem 0.9rem;"

            cards_html += f"""
            <div style="background:{bg_color};border:1px solid {border_color};
                        border-radius:8px;{extra_style}
                        font-family:'IBM Plex Sans',sans-serif;">
                <div style="font-size:0.65rem;font-weight:600;letter-spacing:0.1em;
                            text-transform:uppercase;color:{label_color};margin-bottom:0.6rem;">
                    {label}
                </div>
                <div style="display:flex;justify-content:space-between;align-items:baseline;
                            margin-bottom:0.28rem;">
                    <span style="font-size:0.68rem;color:#4a5a72;min-width:4rem;">Today</span>
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:0.85rem;
                                font-weight:600;color:#e8edf5;">{today_str}</span>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:baseline;
                            margin-bottom:0.28rem;">
                    <span style="font-size:0.68rem;color:#4a5a72;min-width:4rem;">Baseline</span>
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;
                                color:#6a7a94;">{baseline_str}</span>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:baseline;
                            margin-bottom:0.28rem;">
                    <span style="font-size:0.68rem;color:#4a5a72;min-width:4rem;">% Normal</span>
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;
                                color:#e8edf5;">{pct_str}</span>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:baseline;
                            margin-bottom:0.55rem;">
                    <span style="font-size:0.68rem;color:#4a5a72;min-width:4rem;">Z-Score</span>
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;
                                color:#6a7a94;">{z_str}</span>
                </div>
                <div style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;
                            font-weight:600;color:{status_color};">
                    {status_text}
                </div>
            </div>"""

        cards_html += "</div>"
        st.markdown(cards_html, unsafe_allow_html=True)

        # Latest date label under the cards
        mix_date = vessel_mix.get("latest_date") or "—"
        st.markdown(f"""
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;
                        color:#4a5a72;margin-top:-0.75rem;margin-bottom:1.25rem;">
                Baseline: full-year 2025 daily average &nbsp;·&nbsp;
                Latest data: {mix_date} &nbsp;·&nbsp; Source: IMF PortWatch
            </div>
        """, unsafe_allow_html=True)

    else:
        st.markdown('<div class="info-note">Vessel mix data not available.</div>',
                    unsafe_allow_html=True)

    # ── 4b — Vessel Mix Collapse Chart (grouped bar) ───────────────────────────
    # Two bars per vessel type: baseline (muted) vs today (bright).
    # Immediately shows which vessel types collapsed and which held on.

    if vessel_mix:
        st.markdown('<div class="section-header">Today vs Pre-Crisis Baseline — By Vessel Type</div>',
                    unsafe_allow_html=True)

        bar_labels    = ["Tanker", "Container", "Dry Bulk", "RoRo", "Gen. Cargo", "Total"]
        baseline_vals = [
            vessel_mix.get("baseline_tanker")        or 0,
            vessel_mix.get("baseline_container")     or 0,
            vessel_mix.get("baseline_dry_bulk")      or 0,
            vessel_mix.get("baseline_roro")          or 0,
            vessel_mix.get("baseline_general_cargo") or 0,
            vessel_mix.get("baseline_total")         or 0,
        ]
        today_vals = [
            vessel_mix.get("n_tanker")        or 0,
            vessel_mix.get("n_container")     or 0,
            vessel_mix.get("n_dry_bulk")      or 0,
            vessel_mix.get("n_roro")          or 0,
            vessel_mix.get("n_general_cargo") or 0,
            vessel_mix.get("n_total")         or 0,
        ]

        fig_bar = go.Figure()

        fig_bar.add_trace(go.Bar(
            name="2025 Baseline (avg/day)",
            x=bar_labels,
            y=baseline_vals,
            marker_color="rgba(74,90,114,0.55)",
            marker_line=dict(color="rgba(74,90,114,0.8)", width=1),
            hovertemplate="%{x}<br>Baseline: %{y:.1f} ships/day<extra></extra>",
        ))

        fig_bar.add_trace(go.Bar(
            name="Today",
            x=bar_labels,
            y=today_vals,
            marker_color=[
                "#f59e0b" if vessel_mix.get(f"anomaly_flag_{k}") == 1 else "#22c55e"
                if k != "total" else "#14b8a6"
                for k in ["tanker", "container", "dry_bulk", "roro",
                          "general_cargo", "total"]
            ],
            marker_line=dict(color="rgba(255,255,255,0.1)", width=1),
            hovertemplate="%{x}<br>Today: %{y} ships<extra></extra>",
        ))

        fig_bar.update_layout(
            barmode="group",
            bargap=0.25,
            bargroupgap=0.08,
            plot_bgcolor="#0a0e1a",
            paper_bgcolor="#0a0e1a",
            font=dict(family="IBM Plex Sans", color="#8a9bb5", size=13),
            height=320,
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
                tickfont=dict(size=12, family="IBM Plex Sans"),
            ),
            yaxis=dict(
                gridcolor="#1a2235",
                linecolor="#2a3a55",
                tickfont=dict(size=12, family="IBM Plex Mono"),
                title=dict(text="Ships / day", font=dict(size=11)),
            ),
        )

        st.plotly_chart(fig_bar, use_container_width=True)

    # ── 4c — Historical Multi-Line Chart ──────────────────────────────────────
    # Vessel type toggles (inline pill buttons) — default Tanker only.
    # Timeline toggles — default 2026 only.
    # All 7 crisis events annotated when visible in selected range.

    if not vessel_mix_df.empty:
        st.markdown('<div class="section-header">Historical Transit by Vessel Type</div>',
                    unsafe_allow_html=True)

        VM_LINES = {
            "Tanker":        ("n_tanker",        "#f59e0b"),
            "Container":     ("n_container",     "#3b82f6"),
            "Dry Bulk":      ("n_dry_bulk",      "#8b5cf6"),
            "RoRo":          ("n_roro",          "#14b8a6"),
            "General Cargo": ("n_general_cargo", "#f97316"),
            "Total":         ("n_total",         "#e8edf5"),
        }

        TIMELINE_OPTIONS = {
            "2026":       "2026-01-01",
            "2025–2026":  "2025-01-01",
            "2023–2026":  "2023-01-01",
            "All (2019+)":"2019-01-01",
        }

        # ── Vessel type checkboxes ────────────────────────────────────────────
        st.markdown("""
            <div style="font-family:'IBM Plex Sans',sans-serif;font-size:0.65rem;
                        font-weight:600;letter-spacing:0.1em;text-transform:uppercase;
                        color:#4a5a72;margin-bottom:0.4rem;">Vessel Type</div>
        """, unsafe_allow_html=True)

        active_types = []
        type_cols = st.columns([1.5, 1.7, 1.5, 1.3, 2, 1.3, 4])
        for i, (vtype, (_, col_color)) in enumerate(VM_LINES.items()):
            with type_cols[i]:
                checked = st.checkbox(vtype, value=(vtype == "Tanker"), key=f"vmix_type_{vtype}")
                if checked:
                    active_types.append(vtype)

        if not active_types:
            active_types = ["Tanker"]

        # ── Timeline checkboxes ───────────────────────────────────────────────
        st.markdown("""
            <div style="font-family:'IBM Plex Sans',sans-serif;font-size:0.65rem;
                        font-weight:600;letter-spacing:0.1em;text-transform:uppercase;
                        color:#4a5a72;margin-top:0.75rem;margin-bottom:0.4rem;">Timeline</div>
        """, unsafe_allow_html=True)

        selected_timeline = "2026"
        tl_cols = st.columns([1.2, 1.6, 1.6, 1.7, 6])
        for i, tl_label in enumerate(TIMELINE_OPTIONS.keys()):
            with tl_cols[i]:
                if st.checkbox(tl_label, value=(tl_label == "2026"), key=f"vmix_tl_{tl_label}"):
                    selected_timeline = tl_label

       

        from datetime import date as _date
        date_from = TIMELINE_OPTIONS[selected_timeline]
        _min_date = pd.to_datetime(date_from).date()
        _max_date = vessel_mix_df["date"].max().date() if not vessel_mix_df.empty else _date.today()

        tanker_slider_range = st.slider(
            "Date range",
            min_value=_min_date,
            max_value=_max_date,
            value=(_min_date, _max_date),
            format="MMM YYYY",
            label_visibility="collapsed",
            key="tanker_date_range",
        )
        _t_from, _t_to = tanker_slider_range
        plot_df = vessel_mix_df[
            (vessel_mix_df["date"] >= pd.Timestamp(_t_from)) &
            (vessel_mix_df["date"] <= pd.Timestamp(_t_to))
        ].copy()
        # Merge crisis events for hover display
        crisis_events_df = pd.DataFrame([
            {"date": pd.Timestamp(k), "event": f"⚑ {v}"}
            for k, v in CRISIS_EVENTS.items()
        ])
        plot_df = plot_df.merge(crisis_events_df, on="date", how="left")
        plot_df["event"] = plot_df["event"].fillna("")

        # ── Build chart ───────────────────────────────────────────────────────
        fig_hist = go.Figure()

        for idx, line_label in enumerate(active_types):
            col, color = VM_LINES[line_label]
            is_total = (col == "n_total")
            # Show event label only on first trace to avoid repetition in unified hover
            if idx == 0:
                fig_hist.add_trace(go.Scatter(
                    x=plot_df["date"],
                    y=plot_df[col],
                    name=line_label,
                    line=dict(color=color, width=2.5 if is_total else 2, dash="dot" if is_total else "solid"),
                    customdata=plot_df["event"],
                    hovertemplate=f"<b>%{{x|%b %d, %Y}}</b><br>{line_label}: %{{y}}<br><span style='color:#ef4444'>%{{customdata}}</span><extra></extra>",
                ))
            else:
                fig_hist.add_trace(go.Scatter(
                    x=plot_df["date"],
                    y=plot_df[col],
                    name=line_label,
                    line=dict(color=color, width=2.5 if is_total else 2, dash="dot" if is_total else "solid"),
                    hovertemplate=f"{line_label}: %{{y}}<extra></extra>",
                ))

        # Crisis event annotations — only render if date is in visible range
        for i, (date_str, label) in enumerate(CRISIS_EVENTS.items(), 1):
            if _t_from <= pd.Timestamp(date_str).date() <= _t_to:

                fig_hist.add_shape(
                    type="line",
                    x0=date_str, x1=date_str,
                    y0=0, y1=1,
                    xref="x", yref="paper",
                    line=dict(color="rgba(239,68,68,0.35)", width=1, dash="dot"),
                )
                fig_hist.add_annotation(
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

        fig_hist.update_layout(
            plot_bgcolor="#0a0e1a",
            paper_bgcolor="#0a0e1a",
            font=dict(family="IBM Plex Sans", color="#8a9bb5", size=13),
            height=400,
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
                tickformat="%b %d",
                dtick=7*24*60*60*1000,
                tick0="2026-02-28",
            ),
            yaxis=dict(
                gridcolor="#1a2235",
                linecolor="#2a3a55",
                tickfont=dict(size=12, family="IBM Plex Mono"),
                title=dict(text="Ships / day", font=dict(size=11)),
            ),
            hovermode="x unified",
        )

        st.plotly_chart(fig_hist, use_container_width=True)

        # Numbered event legend — only for visible events
        visible_events = [(i, label) for i, (date_str, label) in enumerate(CRISIS_EVENTS.items(), 1) if _t_from <= pd.Timestamp(date_str).date() <= _t_to
]
        if visible_events:
            legend_spans = "".join(
                f'<span><span style="color:#ef4444;font-family:\'IBM Plex Mono\',monospace;font-weight:600;">{i}</span> &nbsp;{label}</span>'
                for i, label in visible_events
            )
            st.markdown(f"""
                <div style="display:flex;flex-wrap:wrap;gap:0.5rem 1.5rem;margin-top:0.5rem;
                            font-family:'IBM Plex Sans',sans-serif;font-size:0.8rem;color:#8a9bb5;">
                    {legend_spans}
                </div>
            """, unsafe_allow_html=True)

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
    baseline        = tanker.get("baseline_annual") or 53.2

    proj_2w  = max(0, current_count + slope * 14)
    proj_4w  = max(0, current_count + slope * 28)
    pct_2w   = round((proj_2w / baseline) * 100, 1)
    pct_4w   = round((proj_4w / baseline) * 100, 1)

    _today_label = datetime.now(timezone.utc).strftime("%b %-d")
    extrap_data = {
        "Timeframe":         [f"Current ({_today_label})", "+2 weeks", "+4 weeks"],
        "Projected ships/day": [
            f"{current_count}",
            f"{proj_2w:.0f}",
            f"{proj_4w:.0f}",
        ],
        "% of Normal":       [
            f"{(tanker.get('pct_of_normal') or 0):.1f}%",
            f"{pct_2w:.1f}%",
            f"{pct_4w:.1f}%",
        ],
        "vs Baseline (103)": [
            f"−{baseline - current_count:.0f} ships/day",
            f"−{baseline - proj_2w:.0f} ships/day",
            f"−{baseline - proj_4w:.0f} ships/day",
        ],
    }
    st.markdown(
        pd.DataFrame(extrap_data).to_html(escape=False, index=False, classes="supply-gap-table"),
        unsafe_allow_html=True,
    )

    # ── Section 5 — Plain-English interpretation ──────────────────────────────
    _days_to_50pct = round((baseline * 0.5 - current_count) / slope) if slope > 0 else None
    _days_str = f"approximately <strong style=\"color:#e8edf5;\">{_days_to_50pct} days</strong>" if _days_to_50pct else "an indeterminate period"
    st.markdown(f"""
        <div class="interpretation-box" style="margin-top:1.5rem;">
            <div class="interpretation-label">Analyst Interpretation</div>
            <div class="interpretation-text">
                Hormuz is operating at <strong style="color:#f59e0b;">{safe(tanker.get("pct_of_normal"), "{:.1f}%")} of pre-crisis
                normal</strong> — {safe(tanker.get("transit_count"))} ships per day versus a baseline of {safe(tanker.get("baseline_annual"), "{:.0f}")}.
                The z-score of {safe(tanker.get("z_score"), "{:.1f}")} confirms this is a historically extreme deviation,
                not a routine fluctuation. The 7-day trend shows slow recovery at
                +{safe(tanker.get("trend_slope"), "{:.1f}")} transits/day, but this pace is structurally constrained by
                <strong style="color:#e8edf5;">mine clearance operations</strong>, which
                remain incomplete as of the latest data. A ceasefire was agreed April 8,
                but diplomatic resolution does not reopen the strait — physical mine
                clearance by US warships is the binding bottleneck. At the current
                recovery slope, the strait would reach 50% of normal in {_days_str} —
                making an accelerated clearance timeline the single most important variable to monitor.
            </div>
        </div>
    """, unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 3 — LNG MODULE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab_lng:
    import plotly.graph_objects as go

    # ── Section 1 — Headline metric cards ─────────────────────────────────────
    st.markdown('<div class="section-header" style="margin-top:0.5rem;">LNG Market State</div>', unsafe_allow_html=True)

    lc1, lc2, lc3 = st.columns(3)
    with lc1:
        score = safe(lng.get("rebalancing_score"), fallback="—")
        _lng_tab_badge = lng_score_badge(lng.get("rebalancing_score"))
        st.markdown(f"""
            <div class="card card--kpi" style="min-height:220px;">
                <div class="card-label">LNG Market State</div>
                <div class="card-value-slot"><div class="card-value" style="font-size:var(--text-lg);">{score}</div></div>
                <div class="card-sub" style="margin-top:0.3rem;">{_lng_tab_badge}</div>
                <div class="card-sub">Confidence {safe(lng.get("confidence"))}</div>
                {render_signal_panel(lng, panel_id="signals_lng_tab")}
            </div>
        """, unsafe_allow_html=True)
    with lc2:
        st.markdown(f"""
            <div class="card card--kpi" style="min-height:220px;">
                <div class="card-label">JKM–TTF Spread (7-day avg)</div>
                <div class="card-value-slot"><div class="card-value" style="font-size:var(--text-lg);">${safe(lng.get("spread_7d"), "{:.3f}")} <span style="font-family:'IBM Plex Sans',sans-serif;font-size:var(--text-xs);color:var(--text-muted);font-weight:400;">/MMBtu</span></div></div>
                <div class="card-sub" style="margin-top:0.3rem;">
                    {risk_badge("GREEN" if safe(lng.get("routing_signal")) == "NEUTRAL" else "AMBER")}
                </div>
                <div class="card-sub" style="margin-top:0.45rem;">
                    Routing signal: <span style="font-family:'IBM Plex Mono',monospace;color:#e8edf5;font-weight:600;">{safe(lng.get("routing_signal"))}</span>
                </div>
                <div class="card-sub" style="margin-top:0.2rem;">
                    Threshold <span style="font-family:'IBM Plex Mono',monospace;color:#e8edf5;">$2.00</span>/MMBtu
                </div>
            </div>
        """, unsafe_allow_html=True)
    with lc3:
        st.markdown(f"""
            <div class="card card--kpi" style="min-height:220px;">
                <div class="card-label">EU Storage Coverage</div>
                <div class="card-value-slot"><div class="card-value" style="font-size:var(--text-lg);">{safe(lng.get("storage_pct"), "{:.1f}%")}</div></div>
                <div class="card-sub" style="margin-top:0.3rem;">
                    {risk_badge(lng.get("storage_risk"))}
                </div>
                <div class="card-sub" style="margin-top:0.45rem;">
                    {safe(lng.get("days_deficit"), "{:.1f} days")} behind required pace
                </div>
                <div class="card-sub" style="margin-top:0.2rem;">
                    {safe(lng.get("seasonal_deficit"), "{:.1f}%")} below seasonal avg
                </div>
            </div>
        """, unsafe_allow_html=True)

    # ── Section 2 — JKM–TTF Spread Chart ──────────────────────────────────────
    st.markdown('<div class="section-header">JKM–TTF Spread — Cargo Routing Signal</div>', unsafe_allow_html=True)

    prices_df = data["prices_df"]

    # LNG crisis events relevant to the spread chart
    LNG_EVENTS = {
        "2026-03-01": "Ras Laffan attack",
        "2026-03-02": "Strait declared closed",
        "2026-03-05": "P&I insurance withdrawn",
        "2026-03-16": "JKM>TTF inflection",
        "2026-04-08": "Ceasefire agreed",
        "2026-04-13": "US naval blockade",
        "2026-04-15": "Spread peaks",
        "2026-04-16": "Ceasefire collapse",
    }

    if not prices_df.empty:

        # ── Date range slider ─────────────────────────────────────────────────
        from datetime import date
        prices_df["date"] = pd.to_datetime(prices_df["date"])
        min_date = prices_df["date"].min().date()
        max_date = prices_df["date"].max().date()

        _default_start = max(min_date, date(2026, 2, 15))
        slider_range = st.slider(
            "Date range",
            min_value=min_date,
            max_value=max_date,
            value=(_default_start, max_date),
            format="MMM D, YYYY",
            label_visibility="collapsed",
        )
        date_from_s, date_to_s = slider_range
        filtered_prices = prices_df[
            (prices_df["date"].dt.date >= date_from_s) &
            (prices_df["date"].dt.date <= date_to_s)
        ]

        # Merge event labels into filtered prices for hover display.
        # Snap weekend dates to the next available trading day so the label
        # actually lands on a data point (e.g. Mar 01 Sun -> Mar 02 Mon).
        _trading_dates = set(prices_df["date"])
        def _snap_to_trading_day(ts):
            while ts not in _trading_dates:
                ts += pd.Timedelta(days=1)
            return ts

        events_df = pd.DataFrame([
            {"date": _snap_to_trading_day(pd.Timestamp(k)), "event": f"⚑ {v}"}
            for k, v in LNG_EVENTS.items()
        ])
        # If two events snap to the same date, combine them
        events_df = events_df.groupby("date")["event"].apply(lambda x: "  ".join(x)).reset_index()
        filtered_prices = filtered_prices.merge(events_df, on="date", how="left")
        filtered_prices["event"] = filtered_prices["event"].fillna("")

        fig_spread = go.Figure()

        # JKM price line — include event in hover when present
        fig_spread.add_trace(go.Scatter(
            x=filtered_prices["date"],
            y=filtered_prices["JKM"],
            name="JKM (Asia)",
            customdata=filtered_prices["event"],
            line=dict(color="#f59e0b", width=2),
            hovertemplate="%{x|%b %d, %Y}<br>JKM $%{y:.2f}/MMBtu<br><span style='color:#ef4444'>%{customdata}</span><extra></extra>",
        ))

        # TTF price line
        fig_spread.add_trace(go.Scatter(
            x=filtered_prices["date"],
            y=filtered_prices["TTF"],
            name="TTF (Europe)",
            line=dict(color="#3b82f6", width=2),
            hovertemplate="%{x|%b %d, %Y}<br>TTF $%{y:.2f}/MMBtu<extra></extra>",
        ))

        # Spread as filled area on secondary y-axis
        fig_spread.add_trace(go.Scatter(
            x=filtered_prices["date"],
            y=filtered_prices["spread"],
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
            x0=filtered_prices["date"].min(),
            x1=filtered_prices["date"].max(),
            y0=2.0, y1=2.0,
            xref="x", yref="y2",
            line=dict(color="rgba(239,68,68,0.5)", width=1, dash="dash"),
        )
        fig_spread.add_annotation(
            x=filtered_prices["date"].max(),
            y=2.0,
            xref="x", yref="y2",
            text="$2.00 routing threshold",
            showarrow=False,
            font=dict(size=9, color="#ef4444", family="IBM Plex Mono"),
            xanchor="right",
            yanchor="bottom",
        )

        # Only show event annotations within the selected date range
        visible_lng_events = {
            k: v for k, v in LNG_EVENTS.items()
            if date_from_s <= date.fromisoformat(k) <= date_to_s
        }

        # Stagger y positions to prevent overlap on clustered dates
        y_positions = [0.97, 0.82, 0.67, 0.97, 0.82, 0.67, 0.97, 0.82]

        _visible_keys = list(visible_lng_events.keys())
        for i, (date_str, label) in enumerate(visible_lng_events.items(), 1):
            y_pos = y_positions[(i - 1) % len(y_positions)]
            _xanchor = "left" if date_str == _visible_keys[0] else ("right" if date_str == _visible_keys[-1] else "center")
            fig_spread.add_shape(
                type="line",
                x0=date_str, x1=date_str,
                y0=0, y1=1,
                xref="x", yref="paper",
                line=dict(color="rgba(239,68,68,0.3)", width=1, dash="dot"),
            )
            fig_spread.add_annotation(
                x=date_str, y=y_pos,
                xref="x", yref="paper",
                text=str(i),
                showarrow=False,
                font=dict(size=10, color="#ef4444", family="IBM Plex Mono"),
                bgcolor="rgba(10,14,26,0.85)",
                bordercolor="rgba(239,68,68,0.4)",
                borderwidth=1,
                borderpad=3,
                yanchor="top",
                xanchor=_xanchor,
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
                tickformat="%b %d",
                dtick=7*24*60*60*1000,
                tick0="2026-02-28",
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

        # Numbered event legend — only show visible events
        if visible_lng_events:
            lng_legend_spans = "".join(
                f'<span><span style="color:#ef4444;font-family:\'IBM Plex Mono\',monospace;font-weight:600;">{i}</span> &nbsp;{label}</span>'
                for i, (_, label) in enumerate(visible_lng_events.items(), 1)
            )
            st.markdown(f"""
                <div style="display:flex;flex-wrap:wrap;gap:0.5rem 1.5rem;margin-top:0.5rem;
                            font-family:'IBM Plex Sans',sans-serif;font-size:0.8rem;color:#8a9bb5;">
                    {lng_legend_spans}
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

        show_full_history = st.toggle("Show full storage history (2020–)", value=False, key="storage_history_toggle")
        storage_hist_display = storage_df if show_full_history else storage_df[storage_df["date"].dt.year >= 2024]

        fig_storage = go.Figure()

        # Historical trace — muted, shown only when toggle is on
        if show_full_history:
            fig_storage.add_trace(go.Scatter(
                x=storage_hist_display["date"],
                y=storage_hist_display["pct_full"],
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
                    greater vulnerability to geopolitical pressure. Currently 35% — 17 % below seasonal average
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

    _today_label_lng = datetime.now(timezone.utc).strftime("%b %-d")
    storage_extrap = {
        "Timeframe":          [f"Current ({_today_label_lng})", "+2 weeks", "+4 weeks"],
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
    BYPASS_SCENARIOS = {
        "Optimistic (5.5 Mb/d)": 5.5,
        "Midpoint — IEA (4.5 Mb/d)": 4.5,
        "Pessimistic (3.5 Mb/d)": 3.5,
    }

    if "bypass_scenario" not in st.session_state:
        st.session_state.bypass_scenario = "Midpoint — IEA (4.5 Mb/d)"

    st.markdown('<div class="card-label">Bypass pipeline capacity assumption</div>',
                unsafe_allow_html=True)

    cols = st.columns([1.5, 1.5, 1.5, 4])

    for i, (label, val) in enumerate(BYPASS_SCENARIOS.items()):
        with cols[i]:
            if st.button(label, key=f"bypass_{i}"):
                st.session_state.bypass_scenario = label
                st.rerun()

    active_label = st.session_state.bypass_scenario
    st.markdown(f"""
        <script>
        (function() {{
            const btns = window.parent.document.querySelectorAll(
                '[data-testid="stButton"] button'
            );
            btns.forEach(b => {{
                if (b.innerText.trim() === {active_label!r}) {{
                    b.setAttribute('data-active', 'true');
                }} else {{
                    b.removeAttribute('data-active');
                }}
            }});
        }})();
        </script>
    """, unsafe_allow_html=True)

    bypass_offset = BYPASS_SCENARIOS[st.session_state.bypass_scenario]


    # ── Pre-compute gap variables (used by both interpretation box and waterfall)
    pct_normal     = gap.get("pct_of_normal") or 7.8
    normal_flow    = 15.0
    current_thru   = round(normal_flow * (pct_normal / 100), 2)
    disrupted      = round(normal_flow - current_thru, 2)
#    bypass_offset  = 4.5 
    spr_offset     = 3.0
    net_gap = round(max(disrupted - bypass_offset - spr_offset, 0), 2)
    asia_crude_gap  = round(net_gap * 0.80, 2)
    europe_crude_gap = round(net_gap * 0.04, 2)


    # ── Analyst interpretation — top of tab ───────────────────────────────────
    st.markdown(f"""
        <div class="interpretation-box" style="margin-bottom:1.5rem;">
            <div class="interpretation-label">Analyst Interpretation</div>
            <div class="interpretation-text">
                The net crude supply gap of
                <strong style="color:#f59e0b;">{net_gap:.2f} Mb/d</strong>
                reflects the residual shortfall after all available offsets are applied —
                f"bypass pipelines ({bypass_offset} Mb/d)" and the IEA coordinated SPR release
                (3.0 Mb/d) together cover roughly f"{round((bypass_offset + spr_offset) / disrupted * 100):.0f}%" of the disrupted volume, but
                cannot close the gap at current transit levels of {pct_normal:.1f}%
                of normal.
                <br><br>
                The regional distribution is asymmetric and analytically important:
                <strong style="color:#ef4444;">Asia bears 80%
                ({asia_crude_gap:.2f} Mb/d)</strong>
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

    # ── Section 2 — Crude gap waterfall chart (before regional table) ─────────
    st.markdown('<div class="section-header">Crude Supply Gap — Accounting Waterfall</div>',
                unsafe_allow_html=True)

    # Variables already computed at top of tab_gap block — no re-computation needed
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
            Bypass pipelines (Saudi East-West + UAE ADCOP) offset {bypass_offset} Mb/d
            (IEA available capacity midpoint). The IEA coordinated SPR release
            offsets a further 3.0 Mb/d. The residual net gap is
            <strong style="color:#f59e0b;">{net_gap:.2f} Mb/d</strong> —
            of which Asia bears 80% ({safe(gap.get("asia_crude_gap_mbd"), "{:.2f}")} Mb/d)
            and Europe bears 4% ({europe_crude_gap:.2f} Mb/d).
        </div>
    """, unsafe_allow_html=True)

    # ── Section 1 — Regional risk table (after waterfall — numbers follow the visual) ──
    st.markdown('<div class="section-header">Regional Supply Gap — Current State</div>', unsafe_allow_html=True)

    gap_html_rows = [
        {
            "Region": "Asia",
            "Crude Gap (Mb/d)": f"{asia_crude_gap:.2f}",
            "Crude Risk": risk_badge(gap.get("asia_crude_risk")),
            "LNG Gap (Bcf/d)": f"{safe(gap.get('asia_lng_gap_bcfd'), '{:.2f}')}",
            "LNG Risk": risk_badge(gap.get("asia_lng_risk")),
        },
        {
            "Region": "Europe",
            "Crude Gap (Mb/d)": f"{europe_crude_gap:.2f}",
            "Crude Risk": europe_crude_badge(gap.get("europe_crude_risk")),
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
    baseline_t = tanker.get("baseline_annual") or 53.2

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

    _today_label_gap = datetime.now(timezone.utc).strftime("%b %-d")
    gap_extrap = {
        "Timeframe":           [f"Current ({_today_label_gap})", "+2 weeks", "+4 weeks"],
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

            <b style="color:#e8edf5;">IEA SPR release: 426 Mb total committed; 3.0 Mb/d announced rate
            (1.0–1.5 Mb/d US)</b><br>
            Total confirmed at 426 Mb — IEA collective action Excel, March 19 2026
            (supersedes preliminary 412 Mb from March 15 press release).
            Regional breakdown: Americas 199.7 Mb, Asia-Oceania 108.7 Mb, Europe 117.6 Mb.
            Announced rate: S&amp;P Global CERAWeek, March 23 2026 (US Energy Secretary Wright).
            Actual observed: 164 Mb released in first 52 days (avg 3.15 Mb/d);
            April government stock rate 2.1 Mb/d (IEA OMR, May 13 2026).
            Release is front-loaded, not a flat daily rate. First barrels flowed March 17.
            <br><br>

            <b style="color:#e8edf5;">Europe crude gap — coverage mechanism:</b><br>
            Europe's 117.6 Mb SPR contribution is primarily refined products (gasoline,
            middle distillates), not crude. Europe's 0.25 Mb/d crude gap is covered by
            US SPR crude exports to Europe (~0.17 Mb/d observed through May 8 —
            9 of 11 Mb of US SPR crude exported went to Europe, per IEA OMR/Kpler).
            Europe's own confirmed crude SPR component is 18.72 Mb floor
            (France/Germany/Netherlands crude breakdown marked "details not yet available"
            in IEA Excel). Coverage is contingent on US exports continuing, not structural.
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
            CRITICAL: &gt;15 days below seasonal norm |
            ELEVATED: 5–15 days below seasonal norm |
            STABLE: within 5 days of seasonal norm.<br>
            These are documented judgment calls, not externally defined standards.
            The 15-day CRITICAL threshold is consistent with EU energy emergency
            framework alert-level guidance.
            <br><br>

            <b style="color:#e8edf5;">Known limitations:</b><br>
            • Asia crude and LNG risk labels are gap-based proxy estimates —
            no free-tier Asian storage data is available.<br>
            • Europe LNG risk uses real GIE AGSI+ storage data.<br>
            • Bypass pipeline capacity is static reference data — no live
            throughput feed available.<br>
            • IMF PortWatch <code>n_tanker</code> counts all tanker types (crude, LNG,
            product, chemical) in one bucket — crude and LNG carrier disruption rates
            cannot be separated on the free tier. Both gap calculations use the same
            pct_of_normal, which is a documented assumption.<br>
            • Europe STABLE crude label depends on continued US SPR crude exports to
            Europe. If US exports slow or SPR drawdown ends, coverage narrows.
            The 4% Hormuz destination share is structural; the coverage mechanism is not.<br>
            • SPR release is front-loaded, not a flat daily rate. Europe-specific
            daily crude release rate is not published by the IEA.

            </div>
        """, unsafe_allow_html=True)

    # ── Section 5 — Analyst interpretation ────────────────────────────────────