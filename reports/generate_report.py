"""
reports/generate_report.py
--------------------------
Gulf Crisis Supply Intelligence System — Weekly PDF Report Generator

Generates a 3-page PDF snapshot of current supply intelligence:
  Page 1 — Market thesis + headline metrics (tanker, LNG, supply gap)
  Page 2 — Charts: transit trend, JKM-TTF spread, EU storage vs seasonal
  Page 3 — Regional risk table + trend extrapolation + data sources

Usage (standalone):
    python reports/generate_report.py
    → writes reports/gulf_crisis_weekly_YYYY-MM-DD.pdf

Usage (from Streamlit download button):
    from reports.generate_report import build_report_bytes
    pdf_bytes = build_report_bytes()
    st.download_button("Download Weekly Report", pdf_bytes, file_name="...", mime="application/pdf")

Requires: reportlab, plotly, kaleido, pandas
All data is read from gulf_data.db via dashboard/db.py — same source as the dashboard.
"""

import sys, os
from pathlib import Path
from datetime import datetime, timezone
from io import BytesIO

import pandas as pd

# ── Import db.py from dashboard/ ──────────────────────────────────────────────
# Supports being run from project root OR from reports/ subdirectory
_HERE = Path(__file__).resolve().parent
for candidate in [_HERE.parent / "dashboard", _HERE / "dashboard"]:
    if candidate.exists():
        sys.path.insert(0, str(candidate))
        break

from db import (
    get_latest_tanker_metrics,
    get_latest_lng_metrics,
    get_latest_supply_gap_metrics,
    get_crisis_context,
    # NOTE: get_transit_history() is NOT imported.
    # It reads transit_count + baseline_annual from transit_events —
    # those columns were removed in Phase 6 when Kaggle CSV was replaced
    # by PortWatch. transit_events now stores n_tanker, n_total, etc.
    # The chart uses get_vessel_mix_history() + get_anomaly_log_history() instead.
    get_anomaly_log_history,
    get_price_history,
    get_european_storage,
    get_storage_seasonal_baseline,
    get_vessel_mix_latest,
    get_vessel_mix_history,
)

# ── ReportLab + Plotly imports — preserve original error for diagnosis ───────
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, Image, PageBreak, KeepTogether,
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
except ImportError as _rl_err:
    raise ImportError(f"reportlab import failed: {_rl_err}") from _rl_err

import plotly.graph_objects as go

# ══════════════════════════════════════════════════════════════════════════════
# COLOUR PALETTE — mirrors dashboard CSS variables
# ══════════════════════════════════════════════════════════════════════════════

# Light-mode palette — reliable across all PDF viewers
# Dark PDFs require background canvas tricks that fail in some renderers.
BG_PRIMARY   = colors.white
BG_SECONDARY = colors.HexColor("#f1f5f9")
BG_CARD      = colors.HexColor("#f8fafc")
BORDER       = colors.HexColor("#cbd5e1")
TEXT_PRIMARY = colors.HexColor("#0f172a")
TEXT_SEC     = colors.HexColor("#475569")
TEXT_MUTED   = colors.HexColor("#94a3b8")
AMBER        = colors.HexColor("#b45309")   # darker amber — readable on white
RED          = colors.HexColor("#dc2626")
GREEN        = colors.HexColor("#16a34a")
BLUE         = colors.HexColor("#1d4ed8")
TEAL         = colors.HexColor("#0f766e")

# ══════════════════════════════════════════════════════════════════════════════
# PARAGRAPH STYLES
# ══════════════════════════════════════════════════════════════════════════════

def _styles():
    return {
        "report_title": ParagraphStyle(
            "report_title",
            fontName="Helvetica-Bold",
            fontSize=20,
            textColor=TEXT_PRIMARY,
            spaceAfter=2,
            spaceBefore=0,
            leading=28,
            alignment=TA_LEFT,
        ),
        "report_subtitle": ParagraphStyle(
            "report_subtitle",
            fontName="Helvetica",
            fontSize=8,
            textColor=TEXT_SEC,
            spaceAfter=10,
            spaceBefore=4,
            leading=14,
            alignment=TA_LEFT,
        ),
        "section_header": ParagraphStyle(
            "section_header",
            fontName="Helvetica-Bold",
            fontSize=7,
            textColor=AMBER,
            spaceBefore=14,
            spaceAfter=3,
            letterSpacing=1.5,
        ),
        "thesis_text": ParagraphStyle(
            "thesis_text",
            fontName="Helvetica",
            fontSize=9,
            textColor=TEXT_PRIMARY,
            leading=14,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=8,
            textColor=TEXT_SEC,
            leading=13,
            spaceAfter=5,
        ),
        "metric_value": ParagraphStyle(
            "metric_value",
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=AMBER,
            spaceAfter=1,
            alignment=TA_CENTER,
        ),
        "metric_label": ParagraphStyle(
            "metric_label",
            fontName="Helvetica",
            fontSize=7,
            textColor=TEXT_SEC,
            spaceAfter=0,
            alignment=TA_CENTER,
        ),
        "metric_sub": ParagraphStyle(
            "metric_sub",
            fontName="Helvetica",
            fontSize=7,
            textColor=TEXT_MUTED,
            spaceAfter=0,
            alignment=TA_CENTER,
        ),
        "table_cell": ParagraphStyle(
            "table_cell",
            fontName="Helvetica",
            fontSize=8,
            textColor=TEXT_PRIMARY,
            leading=11,
        ),
        "table_header": ParagraphStyle(
            "table_header",
            fontName="Helvetica-Bold",
            fontSize=7,
            textColor=AMBER,
            leading=10,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName="Helvetica",
            fontSize=7,
            textColor=TEXT_MUTED,
            alignment=TA_CENTER,
        ),
        "warning": ParagraphStyle(
            "warning",
            fontName="Helvetica-Oblique",
            fontSize=7,
            textColor=AMBER,
            spaceAfter=4,
        ),
        "page_label": ParagraphStyle(
            "page_label",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=TEXT_SEC,
            spaceBefore=8,
            spaceAfter=2,
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _safe(val, fmt="{:.2f}", fallback="N/A"):
    """
    Format a numeric value safely.

    Returns fallback only if val is genuinely None (field missing from DB row
    because the model hasn't run yet, or the table is empty).

    Does NOT catch TypeError silently — if val is an unexpected type (e.g. a
    string where a float is expected, which would indicate a schema mismatch),
    we let it surface so the error is visible rather than masked as 'N/A'.
    """
    if val is None:
        return fallback
    try:
        return fmt.format(float(val))
    except (ValueError, TypeError) as e:
        # Log schema-type mismatches explicitly — don't swallow them
        print(f"[report/_safe] Cannot format value={val!r} with fmt={fmt!r}: {e}")
        return fallback


def _risk_color(label):
    """Return ReportLab color for a risk label string."""
    mapping = {
        "RED":      RED,
        "AMBER":    AMBER,
        "GREEN":    GREEN,
        "CRITICAL": RED,
        "ELEVATED": AMBER,
        "STABLE":   GREEN,
    }
    return mapping.get(str(label).upper(), TEXT_SEC)


def _badge_cell(label, S):
    """Return a Paragraph with a badge-style risk label."""
    c = _risk_color(label)
    return Paragraph(
        f'<font color="{c.hexval()}">'
        f'<b>{str(label).upper() if label else "N/A"}</b></font>',
        S["table_cell"],
    )


def _hr():
    return HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6, spaceBefore=14)


def _section(title, S):
    return [
        Spacer(1, 4),
        Paragraph(title.upper(), S["section_header"]),
        _hr(),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# CHART RENDERERS — return BytesIO PNG via kaleido
# ══════════════════════════════════════════════════════════════════════════════

_CHART_BG    = "#ffffff"
_CHART_PAPER = "#f8fafc"
_CHART_GRID  = "#e2e8f0"
_FONT_COLOR  = "#475569"
_CRISIS_DATE = "2026-03-01"

def _fig_to_image(fig, width_mm=170, height_mm=55):
    """Render a Plotly figure to a ReportLab Image flowable."""
    px_scale = 3
    w_px = int(width_mm / 25.4 * 96 * px_scale)
    h_px = int(height_mm / 25.4 * 96 * px_scale)
    img_bytes = fig.to_image(format="png", width=w_px, height=h_px, scale=1)
    buf = BytesIO(img_bytes)
    return Image(buf, width=width_mm * mm, height=height_mm * mm)


def _chart_layout(fig, title="", height_mm=55):
    fig.update_layout(
        title=dict(text=title, font=dict(color="#f59e0b", size=11), x=0.01, xanchor="left"),
        paper_bgcolor=_CHART_PAPER,
        plot_bgcolor=_CHART_BG,
        font=dict(color=_FONT_COLOR, size=9),
        margin=dict(l=40, r=20, t=30 if title else 10, b=30),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=_FONT_COLOR, size=8),
            orientation="h", yanchor="bottom", y=1.02,
        ),
        xaxis=dict(gridcolor=_CHART_GRID, zeroline=False),
        yaxis=dict(gridcolor=_CHART_GRID, zeroline=False),
    )
    return fig


def build_transit_chart():
    """
    Transit count vs baseline line chart with crisis annotation.

    Data sources:
      - n_total from transit_events via get_vessel_mix_history()
        (Phase 6 schema: transit_events stores n_tanker, n_total, etc.
         The old transit_count + baseline_annual columns were removed
         when Kaggle CSV was replaced by PortWatch in Phase 6.)
      - baseline_annual from anomaly_log via get_anomaly_log_history()
        (baseline is computed by tanker_anomaly.py and stored there —
         it is NOT stored in transit_events any more.)

    Bug fixed: previous version called get_transit_history() which read
    transit_count and baseline_annual from transit_events — columns that
    no longer exist in the Phase 6 schema. This caused a silent schema
    error masked by the fallback empty DataFrame return.
    """
    # Raw daily totals — all 2,687 rows from PortWatch
    transit_df = get_vessel_mix_history()
    # Computed baseline (one row per anomaly model run)
    anomaly_df = get_anomaly_log_history()

    if transit_df.empty:
        return None

    fig = go.Figure()

    # ── Daily total transits (n_total) ─────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=transit_df["date"],
        y=transit_df["n_total"],
        name="Daily Transits (all types)",
        line=dict(color="#3b82f6", width=1.5),
        fill="tozeroy",
        fillcolor="rgba(59,130,246,0.08)",
    ))

    # ── Tanker-only line for signal clarity ────────────────────────────────
    if "n_tanker" in transit_df.columns and transit_df["n_tanker"].notna().any():
        fig.add_trace(go.Scatter(
            x=transit_df["date"],
            y=transit_df["n_tanker"],
            name="Tanker Transits",
            line=dict(color="#b45309", width=1.2),
        ))

    # ── 2025 pre-crisis baseline (from anomaly_log.baseline_annual) ────────
    # baseline_annual is a single computed value (53.1/day) stored in each
    # anomaly_log row — draw as a flat reference line using the latest value.
    if not anomaly_df.empty and "pct_of_normal" in anomaly_df.columns:
        # Get baseline_annual if exposed, otherwise approximate from pct_of_normal + transit_count
        # anomaly_log stores transit_count (= n_tanker, not n_total) so baseline here is tanker baseline
        latest_anomaly = anomaly_df.iloc[-1]
        pct = latest_anomaly.get("pct_of_normal")
        tc  = latest_anomaly.get("transit_count")
        if pct and tc and pct > 0:
            baseline_val = round(tc / (pct / 100), 1)
            fig.add_shape(
                type="line",
                x0=transit_df["date"].min(), x1=transit_df["date"].max(),
                y0=baseline_val, y1=baseline_val,
                line=dict(color="#22c55e", width=1, dash="dash"),
            )
            fig.add_annotation(
                x=transit_df["date"].max(), y=baseline_val,
                text=f"Tanker baseline {baseline_val}/day (2025)",
                showarrow=False,
                font=dict(color="#22c55e", size=8),
                xanchor="right", yanchor="bottom",
            )

    # ── Crisis onset marker ────────────────────────────────────────────────
    fig.add_shape(type="line", x0=_CRISIS_DATE, x1=_CRISIS_DATE,
                  y0=0, y1=1, yref="paper",
                  line=dict(color="#ef4444", width=1, dash="dot"))
    fig.add_annotation(x=_CRISIS_DATE, y=0.95, yref="paper",
                       text="Crisis onset Mar 1", showarrow=False,
                       font=dict(color="#ef4444", size=8), xanchor="left")

    _chart_layout(fig, "Hormuz Daily Transits — All Types vs Tanker Baseline")
    return fig


def build_spread_chart():
    """JKM-TTF spread chart."""
    df = get_price_history()
    if df.empty:
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["JKM"],
        name="JKM (Asia)", line=dict(color="#b45309", width=1.5),
    ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["TTF"],
        name="TTF (Europe)", line=dict(color="#1d4ed8", width=1.5),
    ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["spread"],
        name="JKM-TTF Spread", line=dict(color="#0f766e", width=1, dash="dot"),
    ))
    fig.add_shape(type="line", x0=_CRISIS_DATE, x1=_CRISIS_DATE,
                  y0=0, y1=1, yref="paper",
                  line=dict(color="#ef4444", width=1, dash="dot"))
    _chart_layout(fig, "JKM vs TTF Prices & Spread ($/MMBtu)")
    fig.update_yaxes(ticksuffix=" $")
    return fig


def build_storage_chart():
    """EU gas storage vs 5-year seasonal baseline."""
    storage_df = get_european_storage()
    baseline_df = get_storage_seasonal_baseline()
    if storage_df.empty:
        return None

    fig = go.Figure()

    # Seasonal baseline overlay — map day_of_year back to current-year dates
    if not baseline_df.empty:
        from datetime import date
        current_year = datetime.now().year
        def doy_to_date(doy):
            try:
                return date(current_year, 1, 1).replace() if doy < 1 else \
                       pd.Timestamp(f"{current_year}-01-01") + pd.Timedelta(days=int(doy)-1)
            except Exception:
                return None
        baseline_df["date"] = baseline_df["day_of_year"].apply(doy_to_date)
        baseline_df = baseline_df.dropna(subset=["date"])
        fig.add_trace(go.Scatter(
            x=baseline_df["date"], y=baseline_df["avg_pct_full"],
            name="5yr Avg (2020-24)", line=dict(color="#16a34a", width=1, dash="dash"),
        ))

    # Last 18 months of actual storage
    cutoff = pd.Timestamp.now() - pd.DateOffset(months=18)
    recent = storage_df[storage_df["date"] >= cutoff]
    fig.add_trace(go.Scatter(
        x=recent["date"], y=recent["pct_full"],
        name="EU Storage (% full)", line=dict(color="#1d4ed8", width=1.5),
        fill="tozeroy", fillcolor="rgba(29,78,216,0.06)",
    ))

    _chart_layout(fig, "EU Gas Storage vs Seasonal Baseline (%)")
    fig.update_yaxes(ticksuffix="%", range=[0, 100])
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# PAGE BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def _build_page1(story, S, tanker, lng, gap, crisis, report_date):
    """Page 1: header, thesis, headline metrics, LNG metrics."""

    # ── Report header ──────────────────────────────────────────────────────────
    story.append(Paragraph("Gulf Crisis Supply Intelligence", S["report_title"]))
    # Format raw ISO timestamp to readable form e.g. "2026-05-19 07:26 UTC"
    raw_ts = tanker.get("logged_at") or ""
    try:
        ts_clean = raw_ts[:16].replace("T", " ") + " UTC" if raw_ts else "unknown"
    except Exception:
        ts_clean = raw_ts
    story.append(Paragraph(
        f"Weekly Situation Report  ·  {report_date}  ·  Pipeline last run: {ts_clean}",
        S["report_subtitle"]
    ))
    story.append(Spacer(1, 4))
    story.append(_hr())

    # ── Crisis context summary ─────────────────────────────────────────────────
    if crisis and crisis.get("as_of_date"):
        mine_pct = _safe(crisis.get("mine_clearance_pct_estimate"), "{:.0f}")
        mine_status = crisis.get("mine_clearance_status") or "Unknown"
        diplo = crisis.get("diplomatic_status") or "Unknown"
        context_text = (
            f"<b>Crisis Context (as of {crisis['as_of_date']}):</b> "
            f"Mine clearance {mine_pct}% complete — {mine_status}. "
            f"Diplomatic status: {diplo}. "
            "Mine clearance — not diplomacy — remains the binding constraint on recovery speed."
        )
        story += _section("Geopolitical Status", S)
        story.append(Paragraph(context_text, S["body"]))

    # ── Market thesis block ────────────────────────────────────────────────────
    story += _section("Current Market View", S)
    thesis = gap.get("summary_thesis") or lng.get("thesis") or "No thesis available."
    story.append(Table(
        [[Paragraph(thesis, S["thesis_text"])]],
        colWidths=[170 * mm],
        style=TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), BG_CARD),
            ("LEFTPADDING",  (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING",   (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
            ("LINEAFTER",    (0, 0), (0, -1), 3, AMBER),   # left amber border
            ("BOX",          (0, 0), (-1, -1), 0.5, BORDER),
        ])
    ))

    # ── Headline metrics — 4 cards in a row ───────────────────────────────────
    story += _section("Headline Metrics", S)

    pct_normal   = _safe(tanker.get("pct_of_normal"), "{:.1f}")
    trend_dir    = tanker.get("trend_direction") or "N/A"
    lng_score    = lng.get("rebalancing_score") or "N/A"
    lng_conf     = lng.get("confidence") or ""
    net_gap      = _safe(gap.get("crude_gap_net_mbd"), "{:.2f}")
    eu_storage   = _safe(lng.get("storage_pct"), "{:.1f}")
    storage_risk = lng.get("storage_risk") or "N/A"

    def _card(value, label, sub=""):
        return [
            Paragraph(value, S["metric_value"]),
            Paragraph(label, S["metric_label"]),
            Paragraph(sub,   S["metric_sub"]),
        ]

    card_data = [[
        _card(f"{pct_normal}%",   "Hormuz Transit Index",    trend_dir),
        _card(lng_score,          "LNG Market State",         lng_conf),
        _card(f"{net_gap} Mb/d",  "Net Crude Gap",            "after bypass + SPR"),
        _card(f"{eu_storage}%",   "EU Gas Storage",           storage_risk),
    ]]
    metrics_table = Table(
        card_data,
        colWidths=[42.5 * mm] * 4,
        style=TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), BG_CARD),
            ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
            ("LINEAFTER",     (0, 0), (2, -1),  0.5, BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    story.append(metrics_table)
    story.append(Spacer(1, 6))

    # ── LNG detail metrics ─────────────────────────────────────────────────────
    story += _section("LNG Module — Key Numbers", S)

    jkm   = _safe(lng.get("jkm_price"),       "{:.2f}")
    ttf   = _safe(lng.get("ttf_price"),        "{:.2f}")
    sprd  = _safe(lng.get("spread_7d"),        "{:.2f}")
    util  = _safe(lng.get("us_utilization"),   "{:.1f}")
    days  = _safe(lng.get("days_deficit"),     "{:.1f}")
    route = lng.get("routing_signal") or "N/A"

    lng_rows = [
        [Paragraph("Metric", S["table_header"]),
         Paragraph("Value",  S["table_header"]),
         Paragraph("Metric", S["table_header"]),
         Paragraph("Value",  S["table_header"])],
        [Paragraph("JKM Price", S["table_cell"]),
         Paragraph(f"${jkm}/MMBtu", S["table_cell"]),
         Paragraph("US LNG Utilization", S["table_cell"]),
         Paragraph(f"{util}%", S["table_cell"])],
        [Paragraph("TTF Price", S["table_cell"]),
         Paragraph(f"${ttf}/MMBtu", S["table_cell"]),
         Paragraph("Routing Signal", S["table_cell"]),
         Paragraph(route, S["table_cell"])],
        [Paragraph("JKM-TTF Spread (7d avg)", S["table_cell"]),
         Paragraph(f"${sprd}/MMBtu", S["table_cell"]),
         Paragraph("EU Storage Days Deficit", S["table_cell"]),
         Paragraph(f"{days} days", S["table_cell"])],
    ]
    lng_table = Table(
        lng_rows,
        colWidths=[52 * mm, 33 * mm, 52 * mm, 33 * mm],
        style=TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  BG_SECONDARY),
            ("BACKGROUND",    (0, 1), (-1, -1), BG_CARD),
            ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID",     (0, 0), (-1, -1), 0.3, BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ])
    )
    story.append(lng_table)

    # ── Tanker vessel mix ──────────────────────────────────────────────────────
    story += _section("Vessel Mix — Current vs Pre-Crisis Baseline (2025)", S)
    vm = get_vessel_mix_latest()
    if vm:
        vessel_types = [
            ("Tanker",       "n_tanker",       "pct_normal_tanker"),
            ("Container",    "n_container",    "pct_normal_container"),
            ("Dry Bulk",     "n_dry_bulk",     "pct_normal_dry_bulk"),
            ("RoRo",         "n_roro",         "pct_normal_roro"),
            ("General Cargo","n_general_cargo","pct_normal_general_cargo"),
            ("Total",        "n_total",        "pct_normal_total"),
        ]
        vm_header = [Paragraph(h, S["table_header"]) for h in
                     ["Vessel Type", "Today", "Baseline (2025)", "% of Normal"]]
        vm_rows = [vm_header]
        for label, count_key, pct_key in vessel_types:
            today_n   = _safe(vm.get(count_key), "{:.0f}")
            baseline_k = count_key.replace("n_", "baseline_")
            base_n    = _safe(vm.get(baseline_k), "{:.1f}")
            pct       = vm.get(pct_key)
            pct_str   = _safe(pct, "{:.1f}") + "%" if pct is not None else "N/A"
            pct_color = RED if (pct or 0) < 20 else (AMBER if (pct or 0) < 50 else GREEN)
            vm_rows.append([
                Paragraph(label,   S["table_cell"]),
                Paragraph(today_n, S["table_cell"]),
                Paragraph(base_n,  S["table_cell"]),
                Paragraph(f'<font color="{pct_color.hexval()}"><b>{pct_str}</b></font>',
                          S["table_cell"]),
            ])
        vm_table = Table(
            vm_rows,
            colWidths=[45 * mm, 30 * mm, 50 * mm, 45 * mm],
            style=TableStyle([
                ("BACKGROUND",    (0, 0), (-1, 0),  BG_SECONDARY),
                ("BACKGROUND",    (0, 1), (-1, -1), BG_CARD),
                ("BACKGROUND",    (0, len(vm_rows)-1), (-1, -1), BG_SECONDARY),
                ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
                ("INNERGRID",     (0, 0), (-1, -1), 0.3, BORDER),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ])
        )
        story.append(vm_table)


def _build_page2(story, S):
    """Page 2: charts."""
    story.append(PageBreak())
    story.append(Paragraph("Charts — Market Intelligence", S["report_title"]))
    story.append(Paragraph(
        "Visual summary of transit disruption, LNG price dynamics, and European gas storage.",
        S["report_subtitle"]
    ))
    story.append(_hr())

    charts = [
        ("Hormuz Transit Disruption", build_transit_chart),
        ("JKM vs TTF Price Spread",   build_spread_chart),
        ("EU Gas Storage vs Seasonal Baseline", build_storage_chart),
    ]

    for title, builder in charts:
        story += _section(title, S)
        try:
            fig = builder()
            if fig is not None:
                story.append(_fig_to_image(fig, width_mm=170, height_mm=58))
            else:
                story.append(Paragraph("Chart data not available.", S["body"]))
        except Exception as e:
            story.append(Paragraph(f"Chart render error: {e}", S["body"]))
        story.append(Spacer(1, 6))


def _build_page3(story, S, gap, tanker, report_date):
    """Page 3: regional risk table, trend extrapolation, data sources."""
    story.append(PageBreak())
    story.append(Paragraph("Regional Risk & Trend Extrapolation", S["report_title"]))
    story.append(Paragraph(
        "Supply gap model output and short-term trend projections.",
        S["report_subtitle"]
    ))
    story.append(_hr())

    # ── Regional risk table ────────────────────────────────────────────────────
    story += _section("Regional Supply Gap — Current State", S)

    risk_header = [Paragraph(h, S["table_header"]) for h in
                   ["Region", "Crude Gap (Mb/d)", "Crude Risk",
                    "LNG Gap (Bcf/d)", "LNG Risk"]]
    risk_rows = [risk_header]

    regions = [
        ("Asia",
         gap.get("asia_crude_gap_mbd"),  gap.get("asia_crude_risk"),
         gap.get("asia_lng_gap_bcfd"),   gap.get("asia_lng_risk")),
        ("Europe",
         gap.get("europe_crude_gap_mbd"), gap.get("europe_crude_risk"),
         gap.get("europe_lng_gap_bcfd"),  gap.get("europe_lng_risk")),
        ("US",
         0.00, "GREEN",
         0.00, "GREEN"),
    ]
    for region, c_gap, c_risk, l_gap, l_risk in regions:
        risk_rows.append([
            Paragraph(region,               S["table_cell"]),
            Paragraph(_safe(c_gap, "{:.2f}"), S["table_cell"]),
            _badge_cell(c_risk, S),
            Paragraph(_safe(l_gap, "{:.2f}"), S["table_cell"]),
            _badge_cell(l_risk, S),
        ])

    risk_table = Table(
        risk_rows,
        colWidths=[28 * mm, 36 * mm, 30 * mm, 36 * mm, 30 * mm],
        style=TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  BG_SECONDARY),
            ("BACKGROUND",    (0, 1), (-1, -1), BG_CARD),
            ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID",     (0, 0), (-1, -1), 0.3, BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ])
    )
    story.append(risk_table)

    # ── Trend extrapolation ────────────────────────────────────────────────────
    story += _section("Trend Extrapolation (Not a Forecast)", S)
    story.append(Paragraph(
        "⚠ TREND EXTRAPOLATION — NOT A FORECAST. "
        "Based on current transit recovery rate and static bypass/SPR assumptions.",
        S["warning"]
    ))

    slope       = tanker.get("trend_slope") or 0.5
    pct_normal  = tanker.get("pct_of_normal") or 0.0
    baseline_t  = tanker.get("baseline_annual") or 53.2
    normal_flow = 15.0
    bypass_offset = 4.5
    spr_offset    = 3.0
    current_thru  = normal_flow * (pct_normal / 100)

    def _project(days_fwd):
        proj_pct  = min(pct_normal + (slope * days_fwd / baseline_t * 100), 100)
        proj_thru = normal_flow * (proj_pct / 100)
        proj_dis  = max(normal_flow - proj_thru, 0)
        proj_net  = max(proj_dis - bypass_offset - spr_offset, 0)
        return round(proj_net, 2), round(proj_net * 0.80, 2), round(proj_net * 0.04, 2), round(proj_pct, 1)

    net_now = max(normal_flow - current_thru - bypass_offset - spr_offset, 0)
    net_2w, asia_2w, eur_2w, pct_2w = _project(14)
    net_4w, asia_4w, eur_4w, pct_4w = _project(28)

    today_label = datetime.now(timezone.utc).strftime("%b %-d")
    ext_header = [Paragraph(h, S["table_header"]) for h in
                  ["Timeframe", "Transit (% normal)", "Net Crude Gap (Mb/d)",
                   "Asia Gap (Mb/d)", "Europe Gap (Mb/d)"]]
    ext_rows = [
        ext_header,
        [Paragraph(f"Current ({today_label})", S["table_cell"]),
         Paragraph(f"{pct_normal:.1f}%", S["table_cell"]),
         Paragraph(f"{net_now:.2f}", S["table_cell"]),
         Paragraph(_safe(gap.get("asia_crude_gap_mbd"), "{:.2f}"), S["table_cell"]),
         Paragraph(_safe(gap.get("europe_crude_gap_mbd"), "{:.2f}"), S["table_cell"])],
        [Paragraph("+2 weeks", S["table_cell"]),
         Paragraph(f"{pct_2w:.1f}%", S["table_cell"]),
         Paragraph(f"{net_2w:.2f}", S["table_cell"]),
         Paragraph(f"{asia_2w:.2f}", S["table_cell"]),
         Paragraph(f"{eur_2w:.2f}", S["table_cell"])],
        [Paragraph("+4 weeks", S["table_cell"]),
         Paragraph(f"{pct_4w:.1f}%", S["table_cell"]),
         Paragraph(f"{net_4w:.2f}", S["table_cell"]),
         Paragraph(f"{asia_4w:.2f}", S["table_cell"]),
         Paragraph(f"{eur_4w:.2f}", S["table_cell"])],
    ]
    ext_table = Table(
        ext_rows,
        colWidths=[34 * mm, 38 * mm, 36 * mm, 32 * mm, 30 * mm],
        style=TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  BG_SECONDARY),
            ("BACKGROUND",    (0, 1), (-1, -1), BG_CARD),
            ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID",     (0, 0), (-1, -1), 0.3, BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ])
    )
    story.append(ext_table)

    # ── Key assumptions ────────────────────────────────────────────────────────
    story += _section("Key Assumptions", S)
    assumptions = [
        "Normal Hormuz crude flow: 15.0 Mb/d (IEA Factsheet, Feb 2026)",
        "Bypass pipeline capacity: 4.5 Mb/d midpoint (IEA range 3.5–5.5 Mb/d)",
        "IEA SPR release: 3.0 Mb/d announced rate (actual Apr 2026: ~2.1 Mb/d)",
        "Destination shares — Crude: Asia 80%, Europe 4%, Other 16%",
        "Destination shares — LNG: Asia 90%, Europe 10%",
        "Vessel-type split unavailable on free AIS tier — same pct_of_normal applied to crude and LNG",
        "Asia risk labels are gap-based proxy estimates (no free-tier Asian storage data)",
    ]
    for a in assumptions:
        story.append(Paragraph(f"• {a}", S["body"]))

    # ── Data sources ───────────────────────────────────────────────────────────
    story += _section("Data Sources", S)
    sources = [
        ("Tanker/Transit",   "IMF PortWatch API — chokepoint6 (Hormuz) daily transit counts"),
        ("LNG Prices",       "yfinance — JKM futures (LNG=F), TTF futures (TTE=F)"),
        ("LNG Exports",      "EIA Open Data API — US terminal monthly volumes (6-wk lag)"),
        ("EU Gas Storage",   "GIE AGSI+ API — EU aggregate daily storage levels"),
        ("Supply Gap Model", "IEA Hormuz Factsheet (Feb 2026) + SPR IEA collective action data"),
    ]
    for label, desc in sources:
        story.append(Paragraph(
            f'<b><font color="{AMBER.hexval()}">{label}:</font></b> {desc}',
            S["body"]
        ))

    # ── Footer ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 12))
    story.append(_hr())
    story.append(Paragraph(
        f"Gulf Crisis Supply Intelligence System  ·  Generated {report_date}  ·  "
        "Trend extrapolations are not forecasts. Not for trading or investment decisions.",
        S["footer"]
    ))


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINTS
# ══════════════════════════════════════════════════════════════════════════════

def build_report_bytes() -> bytes:
    """
    Build the weekly PDF report and return as bytes.
    Called from the Streamlit download button.
    """
    report_date = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # Pull all data
    tanker = get_latest_tanker_metrics()
    lng    = get_latest_lng_metrics()
    gap    = get_latest_supply_gap_metrics()
    try:
        crisis = get_crisis_context()
    except Exception:
        crisis = {}

    S = _styles()
    buf = BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Gulf Crisis Supply Intelligence — {report_date}",
        author="Gulf Crisis Supply Intelligence System",
    )

    story = []
    _build_page1(story, S, tanker, lng, gap, crisis, report_date)
    _build_page2(story, S)
    _build_page3(story, S, gap, tanker, report_date)

    doc.build(story)
    return buf.getvalue()


def generate_report_file(output_dir: str = "reports") -> Path:
    """
    Generate the PDF and save to disk. Used by run_all.py or cron.
    Returns the path to the written file.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = out_dir / f"gulf_crisis_weekly_{date_str}.pdf"
    out_path.write_bytes(build_report_bytes())
    print(f"[report] Written: {out_path}")
    return out_path


if __name__ == "__main__":
    path = generate_report_file()
    print(f"Report saved to: {path}")