# Gulf Crisis Supply Intelligence System

A multi-module supply intelligence dashboard tracking tanker routing anomalies, LNG cargo rebalancing, and regional supply gap quantification during the 2026 Strait of Hormuz crisis.

**Live dashboard**: [gulf-crisis-intelligence.streamlit.app]([https://gulf-crisis-intelligence.streamlit.app])

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
External APIs (EIA, GIE AGSI+, yfinance, AISStream)
        │
        ▼
ingestion/          ← fetch and store raw data only
    eia_ingestor.py
    gie_ingestor.py
    prices_ingestor.py
    ais_ingestor.py  ← continuous background process
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

Tracks daily vessel transits through the Hormuz strait corridor using AIS position data. Computes a rolling 30-day baseline and flags z-score deviations above 2.0 as anomalous.

**Current reading (May 2026)**: 7.8% of normal. 8 ships/day vs. a pre-crisis baseline of 102.69. z-score of −22.2 — historically extreme. Recovery trend: +0.5 transits/day. At this rate, 50% of normal traffic would not resume for approximately 190 days. Mine clearance — not diplomacy — is the binding constraint: Iran confirmed sea mines in the strait on April 8, and mine clearance is a physical process independent of ceasefire status.

**Key metric**: `pct_of_normal` — daily transit count ÷ 30-day pre-crisis baseline × 100

**Anomaly threshold**: z-score > 2.0 → ANOMALY; > 3.0 → CRITICAL

### Module 2 — LNG Cargo Flow & Atlantic Basin Rebalancing

Tracks the JKM-TTF price spread as the primary cargo routing signal. When JKM exceeds TTF by more than $2.00/MMBtu, US LNG cargoes are economically incentivised toward Asia rather than Europe. Monitors US export terminal utilization (8 terminals via EIA) and European gas storage (GIE AGSI+ daily data) as demand proxies.

**Current reading (May 2026)**: Rebalancing score DEFICIT, confidence HIGH. JKM-TTF spread $1.198/MMBtu — below the $2.00 routing threshold, so routing signal is NEUTRAL. EU storage at 35.0%, 10.3 days behind seasonal pace. At current refill rate, the shortfall widens to ~15.7 days by mid-June, crossing the RED threshold. US terminal utilization at 113.6% — system running above nameplate capacity across 5 of 8 terminals.

**Key metric**: LNG Cargo Pull Score — composite of spread direction, spread magnitude vs. threshold, and storage trajectory

**Routing threshold**: $2.00/MMBtu JKM-TTF spread → Atlantic cargoes pull to Asia

### Module 3 — Supply Gap & Flow Model

Capacity accounting, not prediction. Takes the current Hormuz throughput (from Module 1), subtracts bypass pipeline capacity and IEA SPR release rate, and distributes the residual gap regionally using IEA destination share data.

**Formula**:
```
Normal Hormuz crude flow: 15.0 Mb/d (IEA)
× Current disruption: 7.8% flowing = 12.3 Mb/d disrupted volume
− Bypass capacity: 3.5–5.5 Mb/d available (IEA) → midpoint 4.5 Mb/d
− SPR release: 3.0 Mb/d total IEA (US Energy Secretary, CERAWeek March 23 2026)
= Net crude gap: ~6.3 Mb/d

Regional distribution (IEA destination shares):
  Asia:   80% crude → ~5.0 Mb/d shortfall → RED
  Europe:  4% crude → ~0.25 Mb/d shortfall → AMBER (disproportionate LNG exposure)
  US:     small crude importer from Hormuz → GREEN
```

**Risk labels**: RED = >15 days below seasonal norm; AMBER = 5–15 days; GREEN = within 5 days. These thresholds are documented analytical judgments, not industry standards.

---

## Data Sources

| Source | Data | Access | Lag |
|--------|------|--------|-----|
| EIA Open Data API | US LNG export volumes by terminal | Free API key | 6–8 weeks |
| GIE AGSI+ API | European gas storage by country, daily | Free API key | 1–2 days |
| yfinance | JKM futures, TTF futures, Brent crude | Free, no key | Same day |
| AISStream.io | Vessel position messages, Gulf region | Free API key | Near real-time |
| Kaggle AIS dataset | Historical AIS backfill (Jan–May 2026) | Free download | Static |
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
- **AIS vessel positions sparse**: Free-tier AISStream provides limited historical depth. Dark event detection logic is complete; output will populate as data accumulates. The transit index uses a Kaggle historical dataset as backfill.
- **No vessel type split**: AIS PositionReport messages do not include ShipType. The 7.8% pct_of_normal figure covers all vessel types, not tankers exclusively. LNG carriers and crude tankers may have been disrupted at different rates.
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
│   ├── ais_ingestor.py
│   ├── eia_ingestor.py
│   ├── gie_ingestor.py
│   ├── prices_ingestor.py
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
| May 2026 | Ship traffic still >90% below pre-crisis levels; mine clearance ongoing |
