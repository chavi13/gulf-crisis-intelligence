# data/reference/geofences.py
# Geographic bounding boxes for Phase 2 AIS anomaly detection
# Used by tanker_anomaly.py and ais_ingestor.py

GEOFENCES = {

    # The narrow strait itself
    # A vessel counts as a transit when it enters and exits this box
    "hormuz_corridor": {
        "lat_min": 25.8,
        "lat_max": 26.8,
        "lon_min": 56.2,
        "lon_max": 57.5,
    },

    # Broader Persian Gulf interior
    # Used for AIS dark detection — if a vessel was last seen here
    # and stops transmitting, it is flagged
    "persian_gulf_interior": {
        "lat_min": 22.0,
        "lat_max": 30.0,
        "lon_min": 48.0,
        "lon_max": 57.5,
    },

    # Gulf of Oman — south of the strait
    # A vessel appearing here after being in the Gulf interior
    # without transiting Hormuz is flagged as a diversion candidate
    "gulf_of_oman": {
        "lat_min": 22.0,
        "lat_max": 25.8,
        "lon_min": 56.0,
        "lon_max": 61.0,
    },

    # Bounding box sent to aisstream.io WebSocket subscription
    # Wider than the others — captures everything we care about
    "aisstream_subscription_box": {
        "lat_min": 22.0,
        "lat_max": 30.0,
        "lon_min": 48.0,
        "lon_max": 61.0,
    },

}

# AIS vessel type codes 80–89 = tanker class
TANKER_TYPE_CODES = list(range(80, 90))

# AIS dark threshold in hours
AIS_DARK_THRESHOLD_HOURS = 6

# Anomaly flag threshold — z-score below this triggers anomaly
ANOMALY_ZSCORE_THRESHOLD = -1.5

# Baseline window in days
BASELINE_WINDOW_DAYS = 30

# Fujairah anchorage zone — vessels waiting here are queuing for Hormuz to reopen
# Elevated count is a leading indicator of recovery: vessels arrive before transits resume
FUJAIRAH_ANCHORAGE = {
    "lat_min": 25.0,
    "lat_max": 25.4,
    "lon_min": 56.2,
    "lon_max": 56.5,
}

# Minimum vessels in anchorage zone to trigger ELEVATED status
ANCHORAGE_CLUSTERING_THRESHOLD = 15

# Vessel must have been present in the zone within this many hours to be counted
ANCHORAGE_CLUSTERING_HOURS = 24