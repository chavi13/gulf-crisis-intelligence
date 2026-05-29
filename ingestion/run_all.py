import subprocess
import sys
from datetime import datetime

scripts = [
    # Phase 1 — market data ingestion
    "ingestion/eia_ingestor.py",
    "ingestion/gie_ingestor.py",
    "ingestion/prices_ingestor.py",

    # Phase 2 — vessel intelligence
    # ais_ingestor.py runs continuously as a separate background process.
    # portwatch_ingestor.py runs daily — fetches latest chokepoint6 transit
    # counts from IMF PortWatch API and upserts new rows into transit_events.
    "ingestion/portwatch_ingestor.py",

    # Phase 2b — refinery utilization + inventory (EIA weekly)
    # Must run before model scripts in case models eventually read refinery_data.
    # Safe to run daily — EIA only publishes new data on Wednesdays, so most
    # days this script will find nothing new and exit cleanly.
    "ingestion/eia_refinery_ingestor.py",

    "models/tanker_anomaly.py",

    # Phase 3 — LNG cargo flow & Atlantic Basin rebalancing
    "models/lng_rebalancing.py",

    # Phase 4 — supply gap & flow model
    # Must run AFTER tanker_anomaly.py and lng_rebalancing.py
    # Reads from anomaly_log and lng_rebalancing_log which those scripts write
    "models/supply_gap.py",

    # Phase 5 — Brent realized volatility
    # Must run AFTER prices_ingestor.py so it reads the freshest Brent prices.
    # Rewrites all rows in volatility_log on every run (INSERT OR REPLACE) —
    # thresholds are percentile-based and recalculate across full history each time.
    "models/volatility_tracker.py",
]

print(f"=== Daily ingestion run: {datetime.now().isoformat()} ===")

for script in scripts:
    print(f"\nRunning {script}...")
    result = subprocess.run([sys.executable, script], capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout.strip())
        print("  [OK]")
    else:
        print("  [FAILED]")
        print(result.stderr.strip())

# ── Weekly PDF report — generate every Monday ─────────────────────────────────
if datetime.now().weekday() == 0:   # 0 = Monday
    print("\nGenerating weekly PDF report...")
    try:
        from reports.generate_report import generate_report_file
        path = generate_report_file(output_dir="reports/archive")
        print(f"  [OK] {path}")
    except Exception as e:
        print(f"  [FAILED] Report generation error: {e}")

print("\n=== Done ===")