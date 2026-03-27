"""
================================================================
 MINE SAFETY SMART HELMET - Python Flask Backend
 Features: REST API, AI analysis, MongoDB storage, alerts
================================================================
"""

import os
import time
import math
import logging
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure

# ─── CONFIG ──────────────────────────────────────────────────
MONGO_URI     = os.getenv("MONGO_URI", "mongodb+srv://son17july2006_db_user:m8KVGi6MLaQG7vwc@cluster0.ww44vj4.mongodb.net/?appName=Cluster0")
DB_NAME       = "mineDB"
COLLECTION    = "helmetData"
PORT          = int(os.getenv("PORT", 5000))

# ─── THRESHOLDS ──────────────────────────────────────────────
GAS_SAFE      = 300
GAS_DANGER    = 600
TEMP_MAX      = 40.0        # °C
HR_MIN        = 50          # BPM
HR_MAX        = 120         # BPM
HR_CRITICAL   = 140         # BPM
ACCEL_FALL    = 3.0         # m/s² sudden spike = fall detected
HEALTH_ALERT  = 60          # Below this → alert

# ─── LOGGING ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("MineServer")

# ─── FLASK APP ───────────────────────────────────────────────
app = Flask(__name__, static_folder="dashboard", static_url_path="")
CORS(app)

# ─── MONGODB CONNECTION ──────────────────────────────────────
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db         = client[DB_NAME]
    collection = db[COLLECTION]
    collection.create_index([("minerID", 1), ("timestamp", DESCENDING)])
    log.info("✅ MongoDB connected successfully")
except ConnectionFailure as e:
    log.warning(f"⚠️  MongoDB not available: {e}")
    log.warning("    Running in in-memory mode (data will not persist)")
    client     = None
    collection = None

# ─── IN-MEMORY FALLBACK ──────────────────────────────────────
memory_store = {}   # {minerID: [records]}

# ================================================================
#  AI LOGIC MODULE
# ================================================================

def compute_health_score(heart_rate: int, gas: int, temperature: float) -> int:
    """
    Health Score (0–100):
      - Heart rate contributes 40 points
      - Gas level contributes 40 points
      - Temperature contributes 20 points
    """
    # Heart rate score (optimal = 60-100 BPM)
    if 60 <= heart_rate <= 100:
        hr_score = 40
    elif 50 <= heart_rate < 60 or 100 < heart_rate <= 120:
        hr_score = 25
    elif 40 <= heart_rate < 50 or 120 < heart_rate <= 140:
        hr_score = 10
    else:
        hr_score = 0  # Critical

    # Gas score (lower = better)
    if gas < GAS_SAFE:
        gas_score = 40
    elif gas < GAS_DANGER:
        # Linear interpolation between 300-600
        gas_score = int(40 * (1 - (gas - GAS_SAFE) / (GAS_DANGER - GAS_SAFE)))
    else:
        gas_score = 0  # Danger zone

    # Temperature score
    if temperature <= 35:
        temp_score = 20
    elif temperature <= TEMP_MAX:
        temp_score = 10
    else:
        temp_score = 0

    total = hr_score + gas_score + temp_score
    return max(0, min(100, total))


def classify_working_status(accel_x: float, heart_rate: int, health_score: int,
                            accel_y: float = 0.0, accel_z: float = 9.8) -> str:
    """
    Working Status using MPU6050 + heart rate:
      CRITICAL  → health_score < 40 OR extreme HR
      WORKING   → movement detected (deviation from gravity) + HR elevated
      IDLE      → low movement + normal/low HR

    Uses full 3D deviation from gravity vector (9.8 m/s²) to measure
    actual movement, not just the x-axis component.
    """
    if health_score < 40 or heart_rate > HR_CRITICAL or heart_rate < 40:
        return "CRITICAL"

    # Deviation of the total acceleration magnitude from resting gravity.
    # When still: magnitude ≈ 9.8. When moving: magnitude deviates.
    magnitude = math.sqrt(accel_x**2 + accel_y**2 + accel_z**2)
    movement = abs(magnitude - 9.8)

    if movement > 1.5 and heart_rate > 70:
        return "WORKING"
    elif movement < 0.5 or heart_rate < 65:
        return "IDLE"
    else:
        return "WORKING"


def detect_fall(accel_x: float, accel_y: float, accel_z: float) -> bool:
    """
    Fall detection: sudden large deviation from gravity vector.
    If total acceleration magnitude differs significantly from 9.8 m/s²
    a fall / sudden impact is suspected.
    accel_y and accel_z must be real sensor readings — never use 9.8 as
    a default for accel_z because that would make the magnitude always
    look like normal gravity even during a real fall.
    """
    magnitude = math.sqrt(accel_x**2 + accel_y**2 + accel_z**2)
    return magnitude > (9.8 + ACCEL_FALL) or magnitude < (9.8 - ACCEL_FALL)


def detect_anomalies(data: dict) -> list:
    """
    Rule-based anomaly detection.
    Returns list of alert strings.
    """
    alerts = []

    gas  = data.get("gas", 0)
    hr   = data.get("heartRate")   # None when sensor has no contact
    temp = data.get("temperature", 30)
    hs   = data.get("healthScore", 100)
    ax   = data.get("accel_x", 0)
    ay   = data.get("accel_y", 0)
    az   = data.get("accel_z", 0)  # 0 = unknown; real sensor should send actual value

    # Heart-rate sensor contact check
    if hr is None or hr == 0:
        alerts.append("🟡 WARNING: Heart rate sensor — no contact detected")
        hr = 0  # treat as 0 for threshold checks below (won't falsely trigger HR alerts)

    if gas > GAS_DANGER:
        alerts.append(f"🔴 DANGER: Gas level critical ({gas})")
    elif gas > GAS_SAFE:
        alerts.append(f"🟡 WARNING: Gas elevated ({gas})")

    if hr > HR_CRITICAL:
        alerts.append(f"🔴 DANGER: Heart rate very high ({hr} BPM)")
    elif hr > HR_MAX:
        alerts.append(f"🟡 WARNING: Heart rate elevated ({hr} BPM)")
    elif hr < HR_MIN:
        alerts.append(f"🟡 WARNING: Heart rate low ({hr} BPM)")

    if temp > TEMP_MAX:
        alerts.append(f"🔴 DANGER: Temperature critical ({temp}°C)")

    if hs < HEALTH_ALERT:
        alerts.append(f"🔴 DANGER: Health score low ({hs}/100)")

    if detect_fall(ax, ay, az):
        alerts.append(f"🔴 DANGER: Possible fall detected!")

    return alerts


def analyze(record: dict) -> dict:
    """Run all AI logic and enrich record."""
    hr   = record.get("heartRate") or 0   # 0 = no contact; don't default to 72
    gas  = record.get("gas", 0)
    temp = record.get("temperature", 30)
    ax   = record.get("accel_x", 0)
    ay   = record.get("accel_y", 0)
    az   = record.get("accel_z", 0)   # 0 = unknown; real sensor must send value

    hs     = compute_health_score(hr, gas, temp)
    status = classify_working_status(ax, hr, hs, ay, az)
    alerts = detect_anomalies({**record, "healthScore": hs})
    fall   = detect_fall(ax, ay, az)

    record["healthScore"]     = hs
    record["workingStatus"]   = status
    record["alerts"]          = alerts
    record["fallDetected"]    = fall
    record["dangerLevel"]     = "DANGER" if hs < 40 else "WARNING" if hs < 60 else "SAFE"

    return record


# ================================================================
#  ROUTES
# ================================================================

@app.route("/data", methods=["POST"])
def receive_data():
    """
    POST /data
    Receive sensor data from ESP32 helmet.
    """
    try:
        payload = request.get_json(force=True)
        if not payload:
            return jsonify({"error": "No JSON payload"}), 400

        required = ["minerID", "temperature", "humidity", "gas", "heartRate", "accel_x"]
        for field in required:
            if field not in payload:
                return jsonify({"error": f"Missing field: {field}"}), 400

        # Timestamp (UTC ISO8601)
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        payload["unix_ts"]   = int(time.time())

        # AI analysis
        payload = analyze(payload)

        # Console alerts
        miner_id = payload["minerID"]
        for alert in payload["alerts"]:
            log.warning(f"[ALERT] {miner_id}: {alert}")

        # Persist
        if collection is not None:
            collection.insert_one({**payload, "_id": None} if False else payload)
        else:
            # In-memory fallback
            if miner_id not in memory_store:
                memory_store[miner_id] = []
            memory_store[miner_id].append(payload)
            # Keep last 500 records per miner
            memory_store[miner_id] = memory_store[miner_id][-500:]

        log.info(f"[{miner_id}] HR={payload['heartRate']} Gas={payload['gas']} "
                 f"Temp={payload['temperature']} Score={payload['healthScore']} "
                 f"Status={payload['workingStatus']}")

        return jsonify({
            "status":        "ok",
            "healthScore":   payload["healthScore"],
            "workingStatus": payload["workingStatus"],
            "dangerLevel":   payload["dangerLevel"],
            "alerts":        payload["alerts"]
        }), 200

    except Exception as e:
        log.error(f"Error processing data: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/latest", methods=["GET"])
def latest_data():
    """
    GET /latest
    Return most recent record for each miner.
    Optional ?minerID=xxx to filter.
    """
    miner_filter = request.args.get("minerID")

    try:
        if collection is not None:
            # MongoDB: latest record per miner using aggregation
            pipeline = [
                {"$sort": {"unix_ts": -1}},
                {"$group": {
                    "_id": "$minerID",
                    "doc": {"$first": "$$ROOT"}
                }},
                {"$replaceRoot": {"newRoot": "$doc"}}
            ]
            if miner_filter:
                pipeline.insert(0, {"$match": {"minerID": miner_filter}})

            results = list(collection.aggregate(pipeline))
            for r in results:
                r.pop("_id", None)  # Remove MongoDB internal ID

        else:
            # In-memory fallback
            results = []
            miners = [miner_filter] if miner_filter else memory_store.keys()
            for mid in miners:
                records = memory_store.get(mid, [])
                if records:
                    results.append(records[-1])

        return jsonify({"miners": results, "count": len(results)}), 200

    except Exception as e:
        log.error(f"Error fetching latest: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/history/<miner_id>", methods=["GET"])
def history(miner_id):
    """
    GET /history/<miner_id>
    Return last N records for a specific miner. Default N=50.
    """
    limit = int(request.args.get("limit", 50))
    limit = min(limit, 200)  # Cap at 200

    try:
        if collection is not None:
            records = list(
                collection.find(
                    {"minerID": miner_id},
                    {"_id": 0}
                ).sort("unix_ts", DESCENDING).limit(limit)
            )
        else:
            records = memory_store.get(miner_id, [])[-limit:]
            records = list(reversed(records))  # Most recent first

        return jsonify({"minerID": miner_id, "records": records, "count": len(records)}), 200

    except Exception as e:
        log.error(f"Error fetching history: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/simulate", methods=["POST"])
def simulate():
    """
    POST /simulate
    Inject simulated data for testing (multiple miners).
    """
    import random

    miners = ["miner_101", "miner_102", "miner_103", "miner_104"]
    inserted = []

    for mid in miners:
        fake = {
            "minerID":     mid,
            "temperature": round(random.uniform(25, 45), 1),
            "humidity":    round(random.uniform(40, 90), 1),
            "gas":         random.randint(100, 800),
            "heartRate":   random.randint(55, 155),
            "accel_x":     round(random.uniform(-3, 3), 2),
            "accel_y":     round(random.uniform(-1, 1), 2),
            "accel_z":     round(random.uniform(8, 11), 2),
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "unix_ts":     int(time.time())
        }
        fake = analyze(fake)

        if collection is not None:
            collection.insert_one(fake)
            fake.pop("_id", None)
        else:
            if mid not in memory_store:
                memory_store[mid] = []
            memory_store[mid].append(fake)

        inserted.append(mid)

    return jsonify({"simulated": inserted}), 200


# Serve dashboard
@app.route("/")
def index():
    return send_from_directory("dashboard", "index.html")


@app.route("/health")
def health_check():
    return jsonify({"status": "running", "time": datetime.now().isoformat()}), 200


# ─── ENTRY POINT ─────────────────────────────────────────────
if __name__ == "__main__":
    log.info(f"🚀 Mine Safety Server starting on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
