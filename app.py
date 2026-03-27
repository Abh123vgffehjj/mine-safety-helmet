"""
================================================================
 MINE SAFETY SMART HELMET - Flask Backend  (FIXED v3)
================================================================
"""
import os, time, math, logging
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure

MONGO_URI    = os.getenv("MONGO_URI", "mongodb+srv://son17july2006_db_user:m8KVGi6MLaQG7vwc@cluster0.ww44vj4.mongodb.net/mineDB?retryWrites=true&w=majority&appName=Cluster0")
DB_NAME      = "mineDB"
COLLECTION   = "helmetData"
PORT         = int(os.getenv("PORT", 5000))
GAS_SAFE     = 300
GAS_DANGER   = 600
TEMP_MAX     = 40.0
HR_MIN       = 50
HR_MAX       = 120
HR_CRITICAL  = 140
HEALTH_ALERT = 60
OFFLINE_TIMEOUT = 15   # seconds before miner shown as offline

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("MineServer")

app = Flask(__name__, static_folder="dashboard", static_url_path="")
CORS(app)

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[DB_NAME]
    collection = db[COLLECTION]
    collection.create_index([("minerID", 1), ("unix_ts", DESCENDING)])
    log.info("MongoDB connected")
except ConnectionFailure as e:
    log.warning(f"MongoDB unavailable: {e}")
    client = None; collection = None

memory_store = {}
last_seen    = {}
ack_store    = {}

def compute_health_score(heart_rate, finger_on, gas, temperature):
    if not finger_on:
        hr_score = 20
    elif 60 <= heart_rate <= 100:
        hr_score = 40
    elif 50 <= heart_rate < 60 or 100 < heart_rate <= 120:
        hr_score = 25
    elif 40 <= heart_rate < 50 or 120 < heart_rate <= 140:
        hr_score = 10
    else:
        hr_score = 0
    if gas < GAS_SAFE:
        gas_score = 40
    elif gas < GAS_DANGER:
        gas_score = int(40 * (1 - (gas - GAS_SAFE) / (GAS_DANGER - GAS_SAFE)))
    else:
        gas_score = 0
    if temperature <= 35:
        temp_score = 20
    elif temperature <= TEMP_MAX:
        temp_score = 10
    else:
        temp_score = 0
    return max(0, min(100, hr_score + gas_score + temp_score))

def classify_status(movement_mag, heart_rate, finger_on, health_score, fall):
    if fall:
        return "CRITICAL"
    if health_score < 40:
        return "CRITICAL"
    if finger_on and heart_rate > HR_CRITICAL:
        return "CRITICAL"
    if movement_mag > 0.3:
        return "WORKING"
    return "IDLE"

def detect_anomalies(data):
    alerts = []
    gas       = data.get("gas", 0)
    hr        = data.get("heartRate", 0)
    finger_on = data.get("fingerOn", True)
    temp      = data.get("temperature", 30)
    hs        = data.get("healthScore", 100)
    fall      = data.get("fallDetected", False)
    if gas > GAS_DANGER:
        alerts.append(f"DANGER: Gas level critical ({gas} ppm)")
    elif gas > GAS_SAFE:
        alerts.append(f"WARNING: Gas elevated ({gas} ppm)")
    if finger_on:
        if hr > HR_CRITICAL:
            alerts.append(f"DANGER: Heart rate very high ({hr} BPM)")
        elif hr > HR_MAX:
            alerts.append(f"WARNING: Heart rate elevated ({hr} BPM)")
        elif 0 < hr < HR_MIN:
            alerts.append(f"WARNING: Heart rate low ({hr} BPM)")
    if temp > TEMP_MAX:
        alerts.append(f"DANGER: Temperature critical ({temp}C)")
    if hs < HEALTH_ALERT:
        alerts.append(f"DANGER: Health score low ({hs}/100)")
    if fall:
        alerts.append("DANGER: Fall detected!")
    return alerts

def analyze(record):
    hr        = record.get("heartRate", 0)
    finger_on = record.get("fingerOn", True)
    gas       = record.get("gas", 0)
    temp      = record.get("temperature", 30)
    mov       = record.get("movementMag", 0.0)
    fall      = record.get("fallDetected", False)
    hs        = compute_health_score(hr, finger_on, gas, temp)
    status    = classify_status(mov, hr, finger_on, hs, fall)
    alerts    = detect_anomalies({**record, "healthScore": hs, "fallDetected": fall})
    record["healthScore"]   = hs
    record["workingStatus"] = status
    record["alerts"]        = alerts
    record["fallDetected"]  = fall
    record["dangerLevel"]   = "DANGER" if hs < 40 else "WARNING" if hs < 60 else "SAFE"
    record["hrStatus"]      = "OK" if finger_on else "NO_CONTACT"
    return record

@app.route("/data", methods=["POST"])
def receive_data():
    try:
        payload = request.get_json(force=True)
        if not payload:
            return jsonify({"error": "Empty payload"}), 400
        for field in ["minerID","temperature","humidity","gas","heartRate","accel_x"]:
            if field not in payload:
                return jsonify({"error": f"Missing: {field}"}), 400
        miner_id = payload["minerID"]
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        payload["unix_ts"]   = int(time.time())
        payload = analyze(payload)
        last_seen[miner_id] = payload["unix_ts"]
        if len(payload["alerts"]) > 0:
            ack_store[miner_id] = False
        for alert in payload["alerts"]:
            log.warning(f"[ALERT] {miner_id}: {alert}")
        if collection is not None:
            collection.insert_one(payload)
            payload.pop("_id", None)
        else:
            memory_store.setdefault(miner_id, []).append(payload)
            memory_store[miner_id] = memory_store[miner_id][-500:]
        log.info(f"[{miner_id}] HR={payload['heartRate']} fingerOn={payload.get('fingerOn')} Gas={payload['gas']} Mov={payload.get('movementMag',0):.2f} Status={payload['workingStatus']}")
        return jsonify({"status":"ok","healthScore":payload["healthScore"],"workingStatus":payload["workingStatus"],"dangerLevel":payload["dangerLevel"],"alerts":payload["alerts"]}), 200
    except Exception as e:
        log.error(f"Error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/latest", methods=["GET"])
def latest_data():
    now = int(time.time())
    try:
        if collection is not None:
            pipeline = [
                {"$sort": {"unix_ts": -1}},
                {"$group": {"_id": "$minerID", "doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$doc"}}
            ]
            results = list(collection.aggregate(pipeline))
            for r in results:
                r.pop("_id", None)
        else:
            results = [records[-1] for records in memory_store.values() if records]
        for r in results:
            mid = r["minerID"]
            seen = last_seen.get(mid, r.get("unix_ts", 0))
            r["isOnline"]   = (now - seen) < OFFLINE_TIMEOUT
            r["alertAcked"] = ack_store.get(mid, False)
            r["secondsAgo"] = now - seen
        return jsonify({"miners": results, "count": len(results)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/acknowledge/<miner_id>", methods=["POST"])
def acknowledge(miner_id):
    ack_store[miner_id] = True
    if collection is not None:
        collection.update_many({"minerID": miner_id}, {"$set": {"alerts": [], "alertAcked": True}})
    else:
        if miner_id in memory_store and memory_store[miner_id]:
            memory_store[miner_id][-1]["alerts"]     = []
            memory_store[miner_id][-1]["alertAcked"] = True
    log.info(f"[ACK] Alerts dismissed for {miner_id}")
    return jsonify({"status": "ok", "minerID": miner_id}), 200

@app.route("/history/<miner_id>", methods=["GET"])
def history(miner_id):
    limit = min(int(request.args.get("limit", 50)), 200)
    try:
        if collection is not None:
            records = list(collection.find({"minerID": miner_id}, {"_id": 0}).sort("unix_ts", DESCENDING).limit(limit))
        else:
            records = list(reversed(memory_store.get(miner_id, [])[-limit:]))
        return jsonify({"minerID": miner_id, "records": records}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/simulate", methods=["POST"])
def simulate():
    import random
    miners = ["miner_101", "miner_102", "miner_103", "miner_104"]
    for mid in miners:
        fake = {
            "minerID": mid,
            "temperature": round(random.uniform(25, 45), 1),
            "humidity":    round(random.uniform(40, 90), 1),
            "gas":         random.randint(100, 800),
            "heartRate":   random.randint(55, 155),
            "fingerOn":    random.choice([True, True, True, False]),
            "accel_x":     round(random.uniform(-3, 3), 2),
            "accel_y":     round(random.uniform(-1, 1), 2),
            "accel_z":     round(random.uniform(8, 11), 2),
            "movementMag": round(random.uniform(0, 3), 2),
            "fallDetected": random.random() < 0.15,
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "unix_ts":     int(time.time())
        }
        fake = analyze(fake)
        last_seen[mid] = fake["unix_ts"]
        if collection is not None:
            collection.insert_one(fake)
            fake.pop("_id", None)
        else:
            memory_store.setdefault(mid, []).append(fake)
    return jsonify({"simulated": miners}), 200

@app.route("/")
def index():
    return send_from_directory("dashboard", "index.html")

@app.route("/health")
def health_check():
    return jsonify({"status": "running", "time": datetime.now().isoformat()}), 200

if __name__ == "__main__":
    log.info(f"Mine Safety Server on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
