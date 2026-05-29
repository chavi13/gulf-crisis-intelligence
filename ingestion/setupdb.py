import sqlite3
import os

DB_PATH = "data/processed/gulf_data.db"
os.makedirs("data/processed", exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Table 1: vessel positions from AIS
cursor.execute("""
    CREATE TABLE IF NOT EXISTS vessel_positions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        mmsi        TEXT,
        vessel_name TEXT,
        latitude    REAL,
        longitude   REAL,
        speed_knots REAL,
        heading     REAL,
        vessel_type TEXT,
        timestamp_utc TEXT,
        source      TEXT,
        fetched_at  TEXT
    )
""")

# Table 2: daily transit events (computed from positions)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS transit_events (
        date              TEXT PRIMARY KEY,
        n_tanker          INTEGER,
        n_container       INTEGER,
        n_dry_bulk        INTEGER,
        n_roro            INTEGER,
        n_general_cargo   INTEGER,
        n_total           INTEGER,
        capacity_tanker   INTEGER,
        capacity_total    INTEGER
    )
""")

# Table 3: LNG export volumes from EIA
# UNIQUE(date, terminal) — prevents duplicate rows when ingestor
# runs multiple times. INSERT OR REPLACE in eia_ingestor.py
# depends on this constraint to update existing rows instead
# of creating duplicates.
cursor.execute("""
    CREATE TABLE IF NOT EXISTS lng_export_volumes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        terminal TEXT NOT NULL,
        volume_bcf REAL,
        fetched_at TEXT,
        UNIQUE(date, terminal)
    )
""")

# Table 4: European gas storage from GIE
# UNIQUE(date, country) — prevents duplicate rows when ingestor
# runs multiple times. Same UPSERT pattern as lng_export_volumes.
cursor.execute("""
    CREATE TABLE IF NOT EXISTS gas_storage_levels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        country TEXT NOT NULL,
        storage_twh REAL,
        pct_full REAL,
        fetched_at TEXT,
        UNIQUE(date, country)
    )
""")

# Table 5: price data (TTF, Brent, HH, JKM when available)
# UNIQUE(date, ticker) — prevents duplicate rows when ingestor
# runs multiple times. Same UPSERT pattern as above.
cursor.execute("""
    CREATE TABLE IF NOT EXISTS price_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        ticker TEXT NOT NULL,
        price REAL,
        fetched_at TEXT,
        UNIQUE(date, ticker)
    )
""")

# Table 6: anomaly log — records each daily run of tanker_anomaly.py
# DROP + recreate to add anchorage_count column (safe — rows repopulate on next daily run)
cursor.execute("DROP TABLE IF EXISTS anomaly_log")
cursor.execute("""
    CREATE TABLE anomaly_log (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        run_date         TEXT,
        latest_data_date TEXT,
        transit_count    INTEGER,
        baseline_annual     REAL,
        z_score          REAL,
        anomaly_flag     INTEGER,
        pct_of_normal    REAL,
        trend_direction  TEXT,
        trend_slope      REAL,
        dark_events      INTEGER,
        anchorage_count  INTEGER DEFAULT 0,
        logged_at        TEXT
    )
""")

# Table 7: LNG rebalancing log — records each daily run of lng_rebalancing.py
cursor.execute("""
    CREATE TABLE IF NOT EXISTS lng_rebalancing_log (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        run_date            TEXT,
        latest_lng_date     TEXT,
        us_utilization      REAL,
        routing_signal      TEXT,
        spread_7d           REAL,
        jkm_price           REAL,
        ttf_price           REAL,
        storage_pct         REAL,
        storage_twh         REAL,
        seasonal_deficit    REAL,
        days_deficit        REAL,
        coverage_status     TEXT,
        storage_risk        TEXT,
        rebalancing_score   TEXT,
        confidence          TEXT,
        thesis              TEXT,
        logged_at           TEXT
    )
""")

# Table 8: Supply gap log — records daily supply disruption + routing outputs
cursor.execute("""
    CREATE TABLE IF NOT EXISTS supply_gap_log (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        run_date             TEXT UNIQUE,         -- one row per day

        -- Core supply disruption inputs
        pct_of_normal        REAL,
        crude_disrupted_mbd  REAL,
        bypass_used_mbd      REAL,
        spr_offset_mbd       REAL,
        crude_gap_net_mbd    REAL,

        -- Regional crude allocation
        asia_crude_gap_mbd   REAL,
        europe_crude_gap_mbd REAL,
        us_crude_gap_mbd     REAL,

        -- LNG imbalance
        lng_gap_bcfd         REAL,
        asia_lng_gap_bcfd    REAL,
        europe_lng_gap_bcfd  REAL,

        -- Routing + risk signals
        routing_signal       TEXT,
        asia_crude_risk      TEXT,
        asia_lng_risk        TEXT,
        europe_crude_risk    TEXT,
        europe_lng_risk      TEXT,
        us_crude_risk        TEXT,
        us_lng_risk          TEXT,

        -- Context from anomaly system
        trend_direction      TEXT,
        trend_slope          REAL,

        -- Narrative layer
        summary_thesis       TEXT,

        -- Metadata
        logged_at            TEXT
    )
""")

# Table 9: vessel registry — built from ShipStaticData AIS messages
# Stores MMSI → ship type mapping for tanker filtering in anomaly detection.
# MMSI is the primary key — one row per vessel, updated on each static broadcast.
cursor.execute("""
    CREATE TABLE IF NOT EXISTS vessel_registry (
        mmsi             TEXT PRIMARY KEY,
        ship_name        TEXT,
        ship_type        INTEGER,
        ship_type_label  TEXT,
        callsign         TEXT,
        first_seen       TEXT,
        last_updated     TEXT
    )
""")

# Table 10: crisis context — structured record of current geopolitical status.
# Updated manually as the situation evolves. Replaces static sidebar text in dashboard.
cursor.execute("""
    CREATE TABLE IF NOT EXISTS crisis_context (
        id                          INTEGER PRIMARY KEY,
        as_of_date                  TEXT NOT NULL,
        mine_clearance_status       TEXT NOT NULL,
        mine_clearance_pct_estimate REAL,
        mine_clearance_source       TEXT,
        diplomatic_status           TEXT,
        us_blockade_active          INTEGER DEFAULT 0,
        notes                       TEXT,
        last_updated                TEXT
    )
""")

# Seed crisis_context with current known state if not already present
cursor.execute("SELECT COUNT(*) FROM crisis_context")
if cursor.fetchone()[0] == 0:
    cursor.execute("""
        INSERT INTO crisis_context VALUES (
            1, '2026-04-13',
            'IN PROGRESS', NULL,
            'US Navy mine clearance operations — no public completion timeline',
            'CEASEFIRE', 1,
            'Ceasefire agreed April 8. US naval blockade of Iranian ports began April 13. Mine clearance ongoing — structural constraint on transit recovery independent of diplomatic status.',
            '2026-05-11'
        )
    """)

# Table 11: refinery data — EIA weekly refinery utilization + inventory levels
# series_id distinguishes between the four EIA series stored in this table:
#   - refinery utilization rate (% of operable capacity)
#   - US crude stocks (thousand barrels)
#   - US gasoline stocks (thousand barrels)
#   - US distillate stocks (thousand barrels)
# UNIQUE(date, series_id) — prevents duplicate rows on re-run
cursor.execute("""
    CREATE TABLE IF NOT EXISTS refinery_data (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT NOT NULL,
        series_id   TEXT NOT NULL,
        series_name TEXT NOT NULL,
        value       REAL,
        unit        TEXT,
        fetched_at  TEXT DEFAULT (datetime('now')),
        UNIQUE(date, series_id)
    )
""")
print("  refinery_data        — EIA refinery utilization + crude/product inventories")

# Table 12: Suez Canal transit events — PortWatch (mirrors transit_events exactly)
# Kept separate from transit_events (Hormuz) so existing anomaly logic is never touched.
cursor.execute("""
    CREATE TABLE IF NOT EXISTS suez_transit_events (
        date              TEXT PRIMARY KEY,
        n_tanker          INTEGER,
        n_container       INTEGER,
        n_dry_bulk        INTEGER,
        n_roro            INTEGER,
        n_general_cargo   INTEGER,
        n_total           INTEGER,
        capacity_tanker   INTEGER,
        capacity_total    INTEGER
    )
""")

print("  suez_transit_events  — PortWatch Suez Canal daily transit counts")

# Table 13: volatility log — daily Brent realized volatility + shock detection
# One row per day. Written by models/volatility_tracker.py.
# vol_regime: LOW / MEDIUM / HIGH / SHOCK
# shock_flag: 1 if today's vol is more than 2x the 90-day average, else 0
cursor.execute("""
    CREATE TABLE IF NOT EXISTS volatility_log (
        id                          INTEGER PRIMARY KEY AUTOINCREMENT,
        date                        TEXT NOT NULL UNIQUE,
        brent_price                 REAL,
        daily_return                REAL,
        realized_vol_20d            REAL,
        realized_vol_20d_annualized REAL,
        vol_90d_avg                 REAL,
        vol_ratio                   REAL,
        vol_regime                  TEXT,
        shock_flag                  INTEGER DEFAULT 0,
        computed_at                 TEXT DEFAULT (datetime('now'))
    )
""")
print("  volatility_log       — daily Brent realized volatility and shock regime")

conn.commit()
conn.close()

print("Database schema verified at:", DB_PATH)
print("Tables:")
print("  vessel_positions     — AIS vessel position data")
print("  transit_events       — daily Hormuz transit index")
print("  lng_export_volumes   — EIA LNG exports by terminal (UNIQUE: date, terminal)")
print("  gas_storage_levels   — GIE European gas storage (UNIQUE: date, country)")
print("  price_data           — commodity prices TTF/Brent/HH/JKM (UNIQUE: date, ticker)")
print("  anomaly_log          — daily tanker anomaly module run log (incl. anchorage_count)")
print("  lng_rebalancing_log  — daily LNG rebalancing module run log")
print("  supply_gap_log       — daily supply gap model run log")
print("  vessel_registry      — MMSI → ship type lookup (from ShipStaticData messages)")
print("  crisis_context       — structured geopolitical status record (manually updated)")
print("  refinery_data        — EIA refinery utilization + crude/product inventories")
print("  suez_transit_events  — PortWatch Suez Canal daily transit counts")
print("  volatility_log       — daily Brent realized volatility and shock regime")