import subprocess
import sys
from datetime import datetime

scripts = [
    # Phase 1 — market data ingestion
    "ingestion/eia_ingestor.py",
    "ingestion/gie_ingestor.py",
    "ingestion/prices_ingestor.py",

    # Phase 2 — vessel intelligence
    # Note: ais_ingestor.py is NOT here — it runs continuously as a separate
    # background process. It cannot be run as a one-shot daily script.
    "models/tanker_anomaly.py",

    # Phase 3 — LNG cargo flow & Atlantic Basin rebalancing
    "models/lng_rebalancing.py",

    # Phase 4 — supply gap & flow model
    # Must run AFTER tanker_anomaly.py and lng_rebalancing.py
    # Reads from anomaly_log and lng_rebalancing_log which those scripts write
    "models/supply_gap.py",
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

print("\n=== Done ===")