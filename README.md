# Gulf Crisis Supply Intelligence System

*Last updated: May 19, 2026*

A multi-module supply intelligence dashboard tracking tanker routing anomalies, LNG cargo rebalancing, and regional supply gap quantification during the 2026 Strait of Hormuz crisis.

**Live dashboard**: [gulf-crisis-intelligence.streamlit.app](https://gulf-crisis-intelligence.streamlit.app)

---

## What This Is

This is not a price prediction tool. It is a physical supply intelligence system — built to answer the question a commodities analyst or risk desk actually cares about: *who is exposed, by how much, and is it getting better or worse?*

The system produces three named metrics updated daily:

- **Hormuz Transit Anomaly Index** — daily tanker transits as a percentage of pre-crisis baseline, with z-score deviation and recovery trend
- **LNG Cargo Pull Score** — direction and strength of Atlantic Basin LNG rebalancing, driven by JKM-TTF spread vs. a $2.00/MMBtu routing threshold
- **Regional Supply Gap Table** — net crude and LNG shortfall by region (Asia, Europe, US) after accounting for bypass pipeline capacity and IEA SPR releases

Each metric has a defined methodology, a validated output, and a plain-English interpretation. The dashboard synthesises all three into a committed "Current Market View" thesis at the top of the Overview tab.

---

## System Architecture

```
External APIs (EIA, GIE AGSI+, yfinance, AISStream, IMF PortWatch)
        │
        ▼
ingestion/          ← fetch and store raw data only
    eia_ingestor.py
    gie_ingestor.py
    prices_ingestor.py
    ais_ingestor.py       ← continuous background process
    portwatch_ingestor.py ← weekly Hormuz transit counts (replaces Kaggle CSV)
        │
        ▼
data/processed/gulf_data.db   ← SQLite, 7 tables
        │
        ▼
models/             ← read from DB, compute metrics, write back
    tanker_anomaly.py
    lng_rebalancing.py
    supply_gap.py
        │
        ▼
dashboard/
    db.py           ← all SQL queries, single data access layer
    app.py          ← Streamlit UI, four tabs, read-only
```

Ingestion and model logic are strictly separated. Ingestion scripts never compute metrics; model scripts never fetch data. This means API failures don't corrupt analytical outputs, and metric logic can be changed without re-fetching data.

---

## The Three Modules

### Module 1 — Tanker Routing & AIS Anomaly Detection

Tracks daily vessel transits through the Hormuz strait corridor using AIS position data. Computes a full-year 2025 daily average baseline and flags z-score deviations above 1.5 as anomalous. Transit data sourced from IMF PortWatch ArcGIS API (2,687 rows, Jan 2019–present), which replaced the static Kaggle CSV in Phase 6.

**Current reading (May 2026)**: 3.8% of normal. 2 ships/day vs. a pre-crisis baseline of 53. z-score of −4.5. Recovery trend: +0.3 transits/day. The ceasefire collapsed on April 16 and the US naval blockade announced April 13 remains active — both are suppressing the limited recovery that had been underway. Mine clearance — not diplomacy — is the binding constraint: Iran confirmed sea mines in the strait on April 8, and mine clearance is a physical process independent of ceasefire status.

**Key metric**: `pct_of_normal` — daily transit count ÷ full-year 2025 daily average baseline × 100

**Anomaly threshold**: z-score > 1.5 → ANOMALY

### Module 2 — LNG Cargo Flow & Atlantic Basin Rebalancing

Tracks the JKM-TTF price spread as the primary cargo routing signal. When JKM exceeds TTF by more than $2.00/MMBtu, US LNG cargoes are economically incentivised toward Asia rather than Europe. Monitors US export terminal utilization (8 terminals via EIA) and European gas storage (GIE AGSI+ daily data) as demand proxies.

**Current reading (May 2026)**: Rebalancing score ELEVATED, confidence HIGH. JKM-TTF spread $1.219/MMBtu — below the $2.00 routing threshold, so routing signal is NEUTRAL. EU storage at 35.8%, 13.1 days behind seasonal pace. At current refill rate, the shortfall widens to ~15.7 days by mid-June, crossing the CRITICAL threshold. EU storage pace is deteriorating — 2.8 days behind pace added in 4 days (May 12→16). US terminal utilization at 113.6% — system running above nameplate capacity across 5 of 8 terminals.

**Key metric**: LNG Cargo Pull Score — composite of spread direction, spread magnitude vs. threshold, and storage trajectory

**Routing threshold**: $2.00/MMBtu JKM-TTF spread → Atlantic cargoes pull to Asia

### Module 3 — Supply Gap & Flow Model

Capacity accounting, not prediction. Takes the current Hormuz throughput (from Module 1), subtracts bypass pipeline capacity and IEA SPR release rate, and distributes the residual gap regionally using IEA destination share data.

**Formula**:
```
Normal Hormuz crude flow: 15.0 Mb/d (IEA)
× Current disruption: 3.8% flowing = ~14.4 Mb/d disrupted volume
− Bypass capacity: 3.5–5.5 Mb/d available (IEA) → midpoint 4.5 Mb/d
− SPR release: 3.0 Mb/d total IEA (US Energy Secretary, CERAWeek March 23 2026)
= Net crude gap: ~6.93 Mb/d

Regional distribution (IEA destination shares):
  Asia:   80% crude → ~5.0 Mb/d shortfall → CRITICAL
  Europe:  4% crude → ~0.25 Mb/d shortfall → ELEVATED (disproportionate LNG exposure)
  US:     small crude importer from Hormuz → STABLE
```

**EU storage risk labels** (applied to days-behind-pace metric): CRITICAL = >15 days below seasonal norm; ELEVATED = 5–15 days; STABLE = within 5 days. These thresholds are documented analytical judgments, not industry standards. Regional crude/LNG risk labels (Asia, Europe, US) are derived separately from gap magnitude relative to estimated total imports.

---

## Data Sources

| Source | Data | Access | Lag |
|--------|------|--------|-----|
| EIA Open Data API | US LNG export volumes by terminal | Free API key | 6–8 weeks |
| GIE AGSI+ API | European gas storage by country, daily | Free API key | 1–2 days |
| yfinance | JKM futures, TTF futures, Brent crude | Free, no key | Same day |
| AISStream.io | Vessel position messages, Gulf region | Free API key | Near real-time |
| IMF PortWatch ArcGIS API | Hormuz daily transit counts by vessel type, Jan 2019–present | Free, no key | ~4 days |
| Kaggle AIS dataset | Historical AIS backfill (Jan–May 2026) — static snapshot, retired as primary transit source | Free download | Static |
| IEA Strait of Hormuz Factsheet | Baseline flow figures, destination shares, bypass capacity | Public PDF | Feb 2026 |

---

## Key Assumptions & Limitations

**Assumptions locked in `data/reference/supply_gap_constants.py`** — all sourced from primary documents, not news articles.

| Assumption | Value | Source |
|-----------|-------|--------|
| Normal Hormuz crude flow | 15.0 Mb/d | IEA Factsheet Feb 2026 |
| Normal Hormuz LNG flow | 10.8 Bcf/d | IEA Factsheet Feb 2026 |
| Bypass capacity range | 3.5–5.5 Mb/d | IEA Factsheet Feb 2026 |
| Asia crude destination share | 80% | IEA Factsheet Feb 2026 |
| Europe crude destination share | 4% | IEA Factsheet Feb 2026 |
| Asia LNG destination share | 90% | IEA Factsheet Feb 2026 |
| IEA SPR release rate | 3.0 Mb/d total | S&P Global CERAWeek, March 23 2026 |
| IPSA pipeline | EXCLUDED — mothballed since 1990 | Global Energy Monitor Jan 2026 |
| Iran Goreh-Jask pipeline | EXCLUDED — non-operational | IEA Factsheet Feb 2026 |

**Known limitations:**

- **EIA publication lag**: `lng_export_volumes` data stops at February 2026. Crisis-period US export data is not yet published. Terminal utilization chart reflects pre-crisis state only — labeled clearly in the dashboard.
- **AIS vessel positions sparse**: Free-tier AISStream provides limited historical depth. Dark event detection logic is complete; output will populate as data accumulates. The transit index uses IMF PortWatch API data (2,687 rows, Jan 2019–present) — Kaggle CSV retired in Phase 6.
- **No vessel-level data from PortWatch**: IMF PortWatch provides aggregate daily counts by vessel type only — no MMSI, vessel names, or individual positions. Vessel type breakdown (tanker, container, dry bulk, RoRo, general cargo) is available; individual vessel tracking is not.
- **Asia risk labels are proxy estimates**: No free-tier Asian LNG or crude storage data is available. Asia risk labels are derived from gap magnitude relative to estimated total imports, not measured storage. Europe uses real GIE AGSI+ data.
- **Bypass pipeline data is static**: No live throughput feed exists for the Saudi East-West Pipeline or UAE ADCOP. Model uses IEA's stated available capacity range and documents this explicitly.
- **SPR rate is announced, not confirmed live**: The 3.0 Mb/d IEA total release is the planned rate. Actual delivery lags 2–4 weeks from announcement.

---

## Repository Structure

```
gulf-crisis-intelligence/
├── data/
│   ├── processed/gulf_data.db     ← SQLite database (committed as static snapshot)
│   └── reference/
│       ├── supply_gap_constants.py ← all verified hard-coded constants
│       ├── geofences.py            ← Hormuz strait polygon definitions
│       └── lng_terminals.py        ← terminal nameplate capacities
├── ingestion/
│   ├── ais_ingestor.py             ← continuous background process
│   ├── eia_ingestor.py
│   ├── gie_ingestor.py
│   ├── prices_ingestor.py
│   ├── portwatch_ingestor.py       ← IMF PortWatch transit data (replaces Kaggle CSV)
│   ├── run_all.py                  ← daily scheduler
│   └── setupdb.py                  ← schema initialisation
├── models/
│   ├── tanker_anomaly.py
│   ├── lng_rebalancing.py
│   └── supply_gap.py
├── dashboard/
│   ├── db.py                       ← all SQL queries, single data access layer
│   └── app.py                      ← Streamlit dashboard
├── .github/workflows/
│   └── daily_update.yml            ← GitHub Actions: runs daily at 06:00 UTC
├── requirements.txt
└── README.md
```

---

## Dashboard Features

The Streamlit dashboard (`dashboard/app.py`) has four tabs — Overview, Vessel Transits, Supply Gap, LNG Cargo Flows— with the following notable features:

**Signal breakdown panel** — The LNG Market State card includes an expandable "Why ELEVATED · HIGH confidence" panel showing the three signals that produced the score (US utilization threshold, EU storage pace, routing signal), each with a checkbox indicating whether it is stressed. Confidence level is derived automatically from how many signals are in the stress direction.

**Interactive tooltips** — Three KPI cards (LNG Gap, EU Storage, US Utilization) include ⓘ tooltip icons explaining the methodology behind each metric.

**Date range slider** — The JKM–TTF spread chart includes a draggable date range slider. Narrowing to a specific period (e.g. March 2026) spreads out clustered event annotations for readability. The event legend below the chart filters to match the selected range. The Vessel Transits tab includes the same slider, linked to the timeline checkbox selection.
**Event hover tooltips** — Hovering on any date in the JKM–TTF chart that coincides with a crisis event shows the event name in the price tooltip (e.g. `⚑ Strait declared closed`).

**Vessel type checkboxes** — The Historical Transit chart allows toggling individual vessel types (Tanker, Container, Dry Bulk, RoRo, General Cargo, Total) and timeline range via checkboxes.

**Cross-module event consistency** — Crisis events are now consistent across the Tanker and LNG charts. Shared geopolitical events (Strait declared closed, P&I insurance withdrawn, Ceasefire agreed, US naval blockade, Ceasefire collapse) appear on both charts. Module-specific events (Brent peaks, SPR release on tanker; JKM inflection, Spread peaks on LNG) remain separate.

**Hormuz chokepoint map** — A static SVG map of the Strait of Hormuz on the Vessel Transits tab showing the chokepoint location, key ports (Fujairah, Bandar Abbas, Ras Laffan), and flow direction arrows. The pulsing status dot is colour-coded red/amber/green directly from the live transit index.

---

## Running Locally

```bash
git clone https://github.com/chavi13/gulf-crisis-intelligence.git
cd gulf-crisis-intelligence
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Add API keys
cp .env.example .env   # fill in EIA_API_KEY, GIE_API_KEY, AISSTREAM_API_KEY

# Run ingestion + models
python ingestion/run_all.py

# Launch dashboard
streamlit run dashboard/app.py
```

---

## Automated Daily Updates

A GitHub Actions workflow (`.github/workflows/daily_update.yml`) runs the full ingestion and model pipeline at 06:00 UTC daily. On completion it commits the updated `gulf_data.db` to the repository. Streamlit Cloud detects the commit and redeploys automatically. No manual intervention required.

---

## Crisis Timeline

| Date | Event |
|------|-------|
| 2026-02-28 | Disruption begins |
| 2026-03-02 | Strait declared closed |
| 2026-03-05 | P&I insurance withdrawn — commercial shipping halts |
| 2026-03-12 | Brent peaks at $126/bbl |
| 2026-03-20 | IEA coordinates 400M bbl SPR release |
| 2026-04-08 | Ceasefire agreed |
| 2026-04-13 | US naval blockade of Iranian ports announced |
| 2026-04-15 | JKM–TTF spread peaks at $4.86/MMBtu |
| 2026-04-16 | Ceasefire collapse — diplomatic progress reset |
| May 2026 | Ship traffic still >96% below pre-crisis levels; mine clearance ongoing; US naval blockade active |
