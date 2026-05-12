# ingestion/ais_ingestor.py
# Phase 2 — AIS WebSocket collector
# Connects to aisstream.io, subscribes to Persian Gulf bounding box,
# writes incoming tanker positions to vessel_positions table

import asyncio
import websockets
import json
import sqlite3
import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────

API_KEY  = os.getenv("AISSTREAM_API_KEY")
DB_PATH  = os.path.join(os.path.dirname(__file__), "../data/processed/gulf_data.db")
WS_URL   = "wss://stream.aisstream.io/v0/stream"

# World bounding box — confirmed working
BOUNDING_BOX = [[-90.0, -180.0], [90.0, 180.0]]

# Gulf box — switch to this once world box confirmed inserting
BOUNDING_BOX = [[22.0, 48.0], [30.0, 61.0]]

# AIS vessel type codes 80–89 = tanker class
# TANKER_CODES = set(range(80, 90))

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Database ─────────────────────────────────────────────────────────────────

def get_connection():
    return sqlite3.connect(DB_PATH)


def insert_position(conn, record: dict):
    conn.execute(
        """
        INSERT INTO vessel_positions
            (mmsi, vessel_type, latitude, longitude,
             speed_knots, heading, timestamp_utc, source)
        VALUES
            (:mmsi, :vessel_type, :latitude, :longitude,
             :speed_knots, :heading, :timestamp_utc, :source)
        """,
        record,
    )
    conn.commit()


def classify_ship_type(type_code) -> str:
    """
    Map AIS ITU ship type integer (0-99) to a human-readable label.
    Tankers are codes 80-89 per ITU standard — used for filtering in
    tanker_anomaly.py and get_dark_events / get_diversion_events.
    """
    if type_code is None:
        return "UNKNOWN"
    if 80 <= type_code <= 89:
        return "TANKER"
    if 70 <= type_code <= 79:
        return "CARGO"
    if 60 <= type_code <= 69:
        return "PASSENGER"
    if type_code in (30, 31, 32, 33, 52):
        return "FISHING_OR_TUG"
    return "OTHER"


def insert_vessel_registry(conn, mmsi: str, ship_name: str, ship_type: int, callsign: str):
    """
    Upsert one row into vessel_registry.
    MMSI is the primary key — updates ship_type and last_updated on conflict.
    first_seen is only written on INSERT, never overwritten.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO vessel_registry
            (mmsi, ship_name, ship_type, ship_type_label, callsign, first_seen, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(mmsi) DO UPDATE SET
            ship_type       = excluded.ship_type,
            ship_type_label = excluded.ship_type_label,
            last_updated    = excluded.last_updated
        """,
        (mmsi, ship_name, ship_type, classify_ship_type(ship_type), callsign, now, now)
    )
    conn.commit()

# ── Message parsing ───────────────────────────────────────────────────────────

def parse_message(raw: dict) -> dict | None:
    """
    Confirmed field locations from live message inspection:

    MetaData:
      - MMSI         → vessel identifier (integer)
      - ShipName     → vessel name (string)
      - latitude     → lowercase, decimal degrees
      - longitude    → lowercase, decimal degrees
      - time_utc     → timestamp string

    Message.PositionReport:
      - Sog          → speed over ground
      - TrueHeading  → heading in degrees
      - Cog          → course over ground

    ShipType is NOT present in PositionReport messages.
    All vessels are collected — tanker filtering done in models layer.
    """
    if raw.get("MessageType") != "PositionReport":
        return None

    meta   = raw.get("MetaData", {})
    report = raw.get("Message", {}).get("PositionReport", {})

    # Correct field names confirmed from live message
    mmsi      = meta.get("MMSI")
    lat       = meta.get("latitude")       # lowercase in MetaData
    lon       = meta.get("longitude")      # lowercase in MetaData
    timestamp = meta.get("time_utc")       # NOT TimeReceived
    speed     = report.get("Sog")
    heading   = report.get("TrueHeading")

    # Explicit None checks — do NOT use all([...])
    # because 0.0 is valid for lat/lon and fails truthiness check
    if mmsi is None or lat is None or lon is None or timestamp is None:
        return None

    # ShipType is absent in PositionReport messages
    # All vessels collected here — tanker filtering happens in tanker_anomaly.py
    return {
        "mmsi":          str(mmsi),
        "vessel_type":   None,
        "latitude":      float(lat),
        "longitude":     float(lon),
        "speed_knots":   float(speed)   if speed   is not None else None,
        "heading":       float(heading) if heading is not None else None,
        "timestamp_utc": timestamp,
        "source":        "aisstream",
    }

# ── WebSocket loop ────────────────────────────────────────────────────────────

async def stream():
    log.info("Connecting to aisstream.io ...")

    async with websockets.connect(WS_URL) as ws:

        subscription = {
            "APIKey":             API_KEY,
            "BoundingBoxes":      [BOUNDING_BOX],
            "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
        }
        await ws.send(json.dumps(subscription))
        log.info("Subscribed — waiting for vessel positions ...")

        conn  = get_connection()
        count = 0

        try:
            async for raw_message in ws:
                data   = json.loads(raw_message)
                msg_type = data.get("MessageType")

                # ── PositionReport — vessel position fix ──────────────────
                if msg_type == "PositionReport":
                    record = parse_message(data)
                    if record is None:
                        continue
                    insert_position(conn, record)
                    count += 1
                    if count % 50 == 0:
                        log.info(f"Inserted {count} vessel positions so far")

                # ── ShipStaticData — vessel type + name broadcast ─────────
                elif msg_type == "ShipStaticData":
                    meta   = data.get("MetaData", {})
                    static = data.get("Message", {}).get("ShipStaticData", {})
                    mmsi   = meta.get("MMSI")
                    if mmsi is None:
                        continue
                    ship_type  = static.get("Type")           # integer 0-99
                    ship_name  = (static.get("ShipName") or "").strip()
                    callsign   = (static.get("CallSign") or "").strip()
                    insert_vessel_registry(conn, str(mmsi), ship_name, ship_type, callsign)

        except websockets.exceptions.ConnectionClosed as e:
            log.warning(f"Connection closed: {e}")
        finally:
            conn.close()
            log.info(f"Done. Total positions inserted: {count}")


# ── Entry point ───────────────────────────────────────────────────────────────

def run():
    if not API_KEY:
        raise ValueError("AISSTREAM_API_KEY not found in .env")
    import time
    while True:
        try:
            asyncio.run(stream())
        except Exception as e:
            log.warning(f"Stream ended: {e} — reconnecting in 30 seconds")
            time.sleep(30)


if __name__ == "__main__":
    run()