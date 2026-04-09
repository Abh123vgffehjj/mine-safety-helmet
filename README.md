# ⛏ Mine Safety Smart Helmet System
## Complete Deployment Guide & Architecture Reference

---

## 📁 Project Structure

```
SmartHelmet_ESP32/
└── SmartHelmet.ino          ← Upload to each ESP32 helmet

MineServer/
├── app.py                   ← Flask backend (AI + APIs)
├── requirements.txt         ← Python dependencies
├── render.yaml              ← Render deployment config
└── dashboard/
    └── index.html           ← Control room web dashboard
```

---

## ⚙️ STEP 1 — MongoDB Atlas Setup

MongoDB Atlas is the cloud database where all helmet sensor readings are stored. The free tier (M0) is sufficient for this project.

### 1.1 — Create Your Atlas Account

1. Open your browser and go to: **https://cloud.mongodb.com**
2. Click **"Try Free"** in the top-right corner
3. Sign up using your email address, or click **"Sign in with Google"** for faster registration
4. Verify your email if prompted — check your inbox for a confirmation link
5. Once logged in, you will land on the **Atlas Dashboard**

### 1.2 — Create a Free Cluster

1. Click the green **"Create"** button (or **"Build a Database"** if shown)
2. On the plan selection screen, choose **M0 — Free Forever**
3. Select a **Cloud Provider**: choose **AWS** (recommended) or Google Cloud / Azure
4. Select the **Region** closest to your deployment location (e.g., `Asia Pacific (Mumbai)` for India)
5. Leave the **Cluster Name** as `Cluster0` or rename it to `MineHelmetCluster`
6. Click **"Create Deployment"** — Atlas will provision your cluster in about 1–3 minutes
7. While it provisions, a popup may appear asking you to create a database user — proceed to the next section

### 1.3 — Create a Database User

> This is a **database-level** user (not your Atlas login). The Flask backend uses these credentials to connect.

1. In the left sidebar, click **"Database Access"** under the *Security* section
2. Click **"Add New Database User"**
3. Select **Authentication Method: Password**
4. Fill in:
   - **Username:** `mineAdmin`
   - **Password:** Create a strong password (e.g., `Mine@Safety2025`) — **save this, you'll need it**
   - Avoid special characters like `@`, `/`, `:` in the password as they break the URI
5. Under **Database User Privileges**, select **"Atlas admin"** (or at minimum **"Read and write to any database"**)
6. Click **"Add User"** — the user appears in the list with a green checkmark

### 1.4 — Whitelist All IP Addresses

> Render's servers use dynamic IPs, so we must allow connections from anywhere.

1. In the left sidebar, click **"Network Access"** under the *Security* section
2. Click **"Add IP Address"**
3. In the popup, click **"Allow Access from Anywhere"** — this auto-fills `0.0.0.0/0`
4. Add a comment: `Render Cloud Server`
5. Click **"Confirm"**
6. The entry will show as **Active** within a few seconds

### 1.5 — Get Your Connection String (URI)

1. In the left sidebar, click **"Database"** under the *Deployment* section
2. Click **"Connect"** next to your cluster
3. In the popup, select **"Drivers"** (Connect your application)
4. Choose:
   - **Driver:** Python
   - **Version:** 3.12 or later
5. Copy the connection string shown — it looks like:
   ```
   mongodb+srv://mineAdmin:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
6. **Edit the URI** — replace `<password>` with your actual password from Step 1.3, and append the database name before the `?`:
   ```
   mongodb+srv://mineAdmin:Mine@Safety2025@cluster0.xxxxx.mongodb.net/mineDB?retryWrites=true&w=majority
   ```
7. **Save this full URI** in a text file — you will paste it into Render in the next step

> ✅ **Checkpoint:** You should now have a URI that starts with `mongodb+srv://mineAdmin:...` and ends with `.../mineDB?...`

---

## 🚀 STEP 2 — Deploy Backend to Render

Render is a cloud platform that will host the Flask server. It runs your Python code 24/7 and gives you a public HTTPS URL that the ESP32 helmets send data to.

### 2.1 — Prepare Your GitHub Repository (No Git Required)

> Render deploys directly from GitHub. You will upload your files manually through the GitHub website — no Git installation needed.

#### A — Create a GitHub Account (skip if you already have one)

1. Go to **https://github.com**
2. Click **"Sign up"** → enter your email, create a password, choose a username
3. Verify your email address via the confirmation link sent to your inbox
4. Complete the onboarding (you can skip all optional steps)

#### B — Create a New Repository

1. Once logged in, click the **"+"** icon in the top-right corner of GitHub
2. Select **"New repository"** from the dropdown
3. Fill in the details:
   - **Repository name:** `mine-safety-helmet`
   - **Description:** *(optional)* Mine Safety IoT System
   - **Visibility:** Select **Public** — Render's free tier requires public repos
   - ✅ Check **"Add a README file"** — this is important, it initializes the repo so you can upload files immediately
4. Click **"Create repository"**
5. You will land on the new repo page showing just the README file

#### C — Upload the Root-Level Files

You need to upload these 3 files that sit directly inside `MineServer/`:
- `app.py`
- `requirements.txt`
- `render.yaml`

Steps:
1. On the repo page, click **"Add file"** → select **"Upload files"**
2. On your computer, open the `MineServer/` folder
3. Drag and drop these 3 files into the GitHub upload area:
   - `app.py`
   - `requirements.txt`
   - `render.yaml`
4. Scroll down to the **"Commit changes"** section
5. Leave the commit message as default or type: `Add backend server files`
6. Make sure **"Commit directly to the main branch"** is selected
7. Click **"Commit changes"**
8. You will return to the repo — you should now see all 3 files listed alongside the README

#### D — Create the `dashboard` Folder and Upload `index.html`

GitHub does not let you create empty folders — you must upload a file into it at the same time.

1. On the repo page, click **"Add file"** → **"Upload files"**
2. In the upload area, you will see a text field at the top that shows the current path (e.g., `mine-safety-helmet /`)
3. Click inside that path field and type `dashboard/` — this tells GitHub to create a folder called `dashboard`
4. Now drag and drop `index.html` from the `MineServer/dashboard/` folder on your computer into the upload area
5. Scroll down → commit message: `Add dashboard`
6. Click **"Commit changes"**

#### E — Verify the Final Repository Structure

After both uploads, click the repo name at the top to go back to the home page. You should see:

```
mine-safety-helmet/
├── README.md
├── app.py
├── requirements.txt
├── render.yaml
└── dashboard/
    └── index.html
```

If all 5 items are visible, your repository is ready. Copy the repo URL from your browser — it will look like:
```
https://github.com/YOUR_USERNAME/mine-safety-helmet
```
You will need this in Step 2.3.

### 2.2 — Create a Render Account

1. Go to **https://render.com**
2. Click **"Get Started for Free"**
3. Sign up using your **GitHub account** (strongly recommended — it allows direct repo access)
4. Authorize Render to access your GitHub when prompted
5. You will land on the **Render Dashboard**

### 2.3 — Create a New Web Service

1. On the Render Dashboard, click the **"New +"** button in the top-right
2. From the dropdown, select **"Web Service"**
3. Under *"Connect a repository"*, you will see your GitHub repos listed
4. Find and click **`mine-safety-helmet`** → click **"Connect"**

### 2.4 — Configure the Web Service

Fill in the service settings exactly as follows:

| Field | Value |
|---|---|
| **Name** | `mine-safety-helmet` |
| **Region** | Choose closest to you (e.g., Singapore for India) |
| **Branch** | `main` |
| **Root Directory** | *(leave blank)* |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2` |
| **Instance Type** | `Free` |

> Make sure the **Start Command** is exactly as shown — Render uses this to launch Flask via Gunicorn (a production web server).

### 2.5 — Add the MongoDB Environment Variable

This is the most critical step — it securely passes your database credentials to the server without hardcoding them in code.

1. Scroll down on the same configuration page to the **"Environment Variables"** section
2. Click **"Add Environment Variable"**
3. Enter:
   - **Key:** `MONGO_URI`
   - **Value:** *(paste the full connection URI you saved in Step 1.5)*
4. Double-check the URI — ensure `<password>` has been replaced with the real password and `mineDB` is present before the `?`

### 2.6 — Deploy the Service

1. Scroll to the bottom and click **"Create Web Service"**
2. Render will now:
   - Clone your GitHub repository
   - Run `pip install -r requirements.txt` (installs Flask, PyMongo, etc.)
   - Start the server with Gunicorn
3. Watch the **Deploy Log** in real time — it streams all output
4. After 1–3 minutes, you will see:
   ```
   ==> Your service is live 🎉
   ```
5. At the top of the page, your public URL is shown:
   ```
   https://mine-safety-helmet.onrender.com
   ```
6. **Test it** — open this URL in your browser. You should see the control room dashboard load.
7. Also test the health endpoint: `https://mine-safety-helmet.onrender.com/health` — it should return:
   ```json
   {"status": "running", "time": "2025-..."}
   ```

### 2.7 — Verify MongoDB Connection

1. In the Render deploy log, look for this line near the top:
   ```
   ✅ MongoDB connected successfully
   ```
2. If you instead see `⚠️ MongoDB not available`, go back and check:
   - The `MONGO_URI` environment variable has no typos
   - The password doesn't contain special characters that need URL encoding
   - Network Access in Atlas has `0.0.0.0/0` whitelisted
3. To update the environment variable: go to your Render service → **Environment** tab → edit `MONGO_URI` → click **"Save Changes"** → Render will automatically redeploy

> **⚠️ Free Tier Note:** Render's free tier spins down after 15 minutes of inactivity. The first request after sleep takes ~30 seconds to wake up. For a production mine safety system, upgrade to the **Starter plan ($7/month)** to keep it always-on.

---

## 📡 STEP 3 — Configure ESP32 Helmets

Edit `SmartHelmet.ino` and update:

```cpp
#define MINER_ID      "miner_101"          // Unique per helmet!
#define WIFI_SSID     "Your_WiFi_Name"
#define WIFI_PASSWORD "Your_WiFi_Pass"
#define SERVER_URL    "https://mine-safety-helmet.onrender.com/data"
```

### Arduino Libraries to Install (Library Manager):
- `DHT sensor library` by Adafruit
- `Adafruit MPU6050`
- `Adafruit Unified Sensor`
- `ArduinoJson` by Benoit Blanchon

### Wiring Guide:

| Sensor     | ESP32 Pin | Notes                              |
|------------|-----------|------------------------------------|
| DHT11 Data | GPIO 4    | 10kΩ pull-up to 3.3V              |
| MQ2 Signal | GPIO 34   | ADC1 (analog, 3.3V max!)          |
| HW-827 Sig | GPIO 35   | ADC1 (analog) — place on wrist    |
| MPU6050 SDA| GPIO 21   | I2C Data                          |
| MPU6050 SCL| GPIO 22   | I2C Clock                         |
| All VCC    | 3.3V      | MQ2 needs 5V separately via VIN   |
| All GND    | GND       | Common ground                     |

> ⚠️ **IMPORTANT:** ESP32 ADC pins only support 0–3.3V.  
> MQ2 heater uses 5V but signal output is 0–5V — use a voltage divider (2:1) on the analog pin.

### Upload:
1. Install Arduino IDE or PlatformIO
2. Select board: **ESP32 Dev Module**
3. Set Flash size: 4MB, Partition Scheme: Default
4. Upload at 115200 baud

---

## 🌐 STEP 4 — Access the Dashboard

Open your browser:
```
https://mine-safety-helmet.onrender.com
```

The dashboard auto-refreshes every 3 seconds. No login required.

**To test without hardware:** Click the **⚡ SIMULATE DATA** button in the header.

---

## 🔌 API Reference

| Method | Endpoint            | Description                        |
|--------|--------------------|------------------------------------|
| POST   | `/data`            | Receive sensor data from ESP32     |
| GET    | `/latest`          | Get latest reading per miner       |
| GET    | `/history/<id>`    | Get historical records for a miner |
| POST   | `/simulate`        | Inject test data for 4 miners      |
| GET    | `/health`          | Server health check                |

### POST /data — Payload Format:
```json
{
  "minerID":     "miner_101",
  "temperature": 30.5,
  "humidity":    68.0,
  "gas":         340,
  "heartRate":   88,
  "accel_x":     1.2,
  "accel_y":     0.1,
  "accel_z":     9.7
}
```

### GET /latest — Response:
```json
{
  "miners": [
    {
      "minerID":       "miner_101",
      "temperature":   30.5,
      "gas":           340,
      "heartRate":     88,
      "healthScore":   78,
      "workingStatus": "WORKING",
      "dangerLevel":   "SAFE",
      "alerts":        [],
      "fallDetected":  false,
      "timestamp":     "2025-01-15T10:30:00Z"
    }
  ],
  "count": 1
}
```

---

## 🧠 AI Logic Reference

### Health Score Algorithm (0–100)

| Component    | Weight | Safe Range        | Points |
|--------------|--------|-------------------|--------|
| Heart Rate   | 40%    | 60–100 BPM        | 40     |
| Gas Level    | 40%    | < 300 ppm         | 40     |
| Temperature  | 20%    | ≤ 35°C            | 20     |

Score < 60 → Alert triggered  
Score < 40 → CRITICAL status

### Working Status Classification

| Condition                              | Status   |
|----------------------------------------|----------|
| healthScore < 40 OR heartRate > 140    | CRITICAL |
| Movement > 1.5 m/s² AND heartRate > 70 | WORKING  |
| Low movement OR heartRate < 65         | IDLE     |

### Alert Thresholds

| Parameter   | Warning     | Danger      |
|-------------|-------------|-------------|
| Gas         | > 300 ppm   | > 600 ppm   |
| Heart Rate  | > 120 BPM   | > 140 BPM   |
| Temperature | > 35°C      | > 40°C      |
| Health Score| < 60        | < 40        |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     MINE ENVIRONMENT                         │
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ ESP32 #1 │    │ ESP32 #2 │    │ ESP32 #N │              │
│  │ Helmet   │    │ Helmet   │    │ Helmet   │              │
│  │ miner_101│    │ miner_102│    │ miner_xxx│              │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘              │
│       │               │               │                      │
│       └───────────────┴───────────────┘                      │
│                    WiFi / 4G                                  │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP POST /data (JSON)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  RENDER CLOUD SERVER                          │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Flask Backend (app.py)                  │    │
│  │                                                      │    │
│  │  POST /data ──→ AI Analysis ──→ MongoDB Store        │    │
│  │  GET  /latest ─────────────────────────────────────→ │    │
│  │                                                      │    │
│  │  ┌─────────────────────────────────────────────┐    │    │
│  │  │           AI Logic Engine                    │    │    │
│  │  │  • compute_health_score()                   │    │    │
│  │  │  • classify_working_status()                │    │    │
│  │  │  • detect_fall()                            │    │    │
│  │  │  • detect_anomalies()                       │    │    │
│  │  └─────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
│                         │                                     │
│                         ▼                                     │
│  ┌─────────────────────────────────────────────────────┐    │
│  │          MongoDB Atlas (Cloud Database)               │    │
│  │  Collection: helmetData                              │    │
│  │  Indexed: minerID + timestamp                        │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                         │ GET /latest (JSON)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                 CONTROL ROOM DASHBOARD                        │
│              (Browser → dashboard/index.html)                 │
│                                                              │
│  • Auto-refresh every 3 seconds                             │
│  • Miner cards grid (color-coded)                           │
│  • Real-time Gas + Heart Rate charts                        │
│  • Alert log + audio alarm                                  │
│  • Health score bars                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Local Development

```bash
# 1. Install Python deps
pip install -r requirements.txt

# 2. Set environment variable (without MongoDB, uses in-memory)
export MONGO_URI="mongodb+srv://..."

# 3. Run server
python app.py

# 4. Open dashboard
open http://localhost:5000

# 5. Click "SIMULATE DATA" or send test POST:
curl -X POST http://localhost:5000/data \
  -H "Content-Type: application/json" \
  -d '{"minerID":"miner_101","temperature":32,"humidity":70,"gas":450,"heartRate":95,"accel_x":1.5}'
```

---

## 🛡️ Safety Alert Escalation

```
Level 1 (WARNING)  → Yellow card + console log
Level 2 (DANGER)   → Red blinking card + audio alarm + alert tag
Level 3 (CRITICAL) → Status = CRITICAL + all above + fall detection
```

---

## 📊 Scaling

To add more miners, simply:
1. Flash another ESP32 with a different `MINER_ID`
2. Configure same WiFi and server URL
3. It will automatically appear in the dashboard
4. No backend changes needed — fully multi-miner out of the box
