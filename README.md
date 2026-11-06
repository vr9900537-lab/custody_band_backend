# CUSTODY WATCH PLATFORM

An enterprise monitoring backend and real-time telemetry receiver for the **Huaten C05 4G GPS Custody Watch** (Inmate & Parolee Tracking Band).

---

## Architecture Overview

```text
CUSTODY_WATCH/
│
├── backend/
│   ├── venv/                       # Python Virtual Environment
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI Application & Background Receiver Lifespan
│   │   ├── config.py               # Environment & App Configuration
│   │   │
│   │   ├── core/                   # Firebase, Security & Auth Dependencies
│   │   ├── authentication/         # /api/v1/auth
│   │   ├── dashboard/              # /api/v1/dashboard
│   │   ├── devices/                # /api/v1/devices
│   │   ├── gps/                    # /api/v1/gps
│   │   │
│   │   ├── accounts/               # /api/v1/accounts (Officer Profiles & Settings)
│   │   ├── monitoring/             # /api/v1/monitoring (Real-time Live Grid Feed)
│   │   ├── playback/               # /api/v1/playback (Historical Route Playback & Stops)
│   │   ├── geofences/              # /api/v1/geofences (Perimeter Boundary Management)
│   │   ├── commands/               # /api/v1/commands (Watch Command Dispatch & Audit)
│   │   ├── alerts/                 # /api/v1/alerts (Incident Lifecycle & Acknowledgment)
│   │   ├── statistics/             # /api/v1/statistics (Compliance & Fleet Analytics)
│   │   ├── health_data/            # /api/v1/health-data (Heart Rate & Steps Telemetry)
│   │   ├── roles/                  # /api/v1/roles (RBAC Permissions & Role Assignments)
│   │   ├── exports/                # /api/v1/exports (CSV & Court Evidence Packages)
│   │   └── integrations/           # /api/v1/integrations (CAD Webhooks & Cloud Connectors)
│   │   │
│   │   ├── receiver/               # Dual TCP + UDP Listener (0.0.0.0:9001)
│   │   ├── services/               # Firestore, GPS, Device & Alert Services
│   │   ├── schemas/                # Pydantic Schemas
│   │   └── utils/                  # Rotating Loggers & Timestamp Utilities
│   │
│   ├── logs/
│   │   ├── tcp_logs/               # Low-level TCP socket logs
│   │   └── gps_logs/               # Parsed GPS telemetry logs
│   │
│   ├── secrets/
│   │   └── firebase_service_account.json
│   │
│   ├── .env                        # Active Environment Variables
│   ├── .env.example
│   ├── .gitignore
│   ├── requirements.txt            # Python Dependencies
│   └── simulate_watch.py           # Watch Simulator Client
│
└── README.md                       # Documentation
```

---

## Quick Start Guide

### Option A: Run with Docker Compose (Recommended)

Docker isolates all execution and bypasses Windows Application Control / AppLocker policies entirely:

```powershell
# Build and start all services in background
docker-compose up --build -d

# View live container logs (HTTP requests & incoming watch TCP/UDP packets)
docker-compose logs -f

# Check container health and status
docker-compose ps

# Stop the platform
docker-compose down
```

---

### Option B: Run Locally with Python

> [!IMPORTANT]
> If Windows Application Control blocks `uvicorn.exe` (`Program 'uvicorn.exe' failed to run: An Application Control policy has blocked this file`), run through `python` directly:

From either the root folder or `backend/`:

```powershell
# Option 1: Using the pre-configured server launcher script
python run_server.py

# Option 2: Running module via Python
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

### 2. Configure Environment (`.env`)

Verify your settings in `backend/.env`:

```ini
# FastAPI HTTP Server
API_HOST=0.0.0.0
API_PORT=8000

# Watch TCP & UDP Receiver
TCP_HOST=0.0.0.0
TCP_PORT=9001
PUBLIC_SERVER_IP=103.44.0.5

# Firebase Project & Credentials
FIREBASE_PROJECT_ID=update-custody-band-back-1c169
FIREBASE_CREDENTIALS_PATH=secrets/firebase_service_account.json

# Admin Account
ADMIN_EMAIL=awsdevopskumar2026@gmail.com
ADMIN_NAME=aditya
ADMIN_ROLE=admin

# Watch Config
DEFAULT_MANUFACTURER=MNYD
DEFAULT_WATCH_IMEI=863758061830955
AUTO_POLL_GPS_ON_PING=true
```

---

### 3. Run the Backend Platform

From the `backend/` folder:

```powershell
..\venv\Scripts\python run_server.py
```
*(or `python run_server.py` with virtual environment activated)*

When started, FastAPI automatically launches:
1. **HTTP REST API** on `http://localhost:8000` (Interactive docs at `/docs`)
2. **TCP & UDP Watch Receiver** on `0.0.0.0:9001` (Accepting cellular packets forwarded from `103.44.0.5:9001`)
3. **Database Layer** (Google Cloud Firestore or SQLite fallback `custody_watch.db`)

---

### 4. Configure Your Huaten C05 Watch

Point your custody watch to your public server endpoint via SMS or BLE UART command:

```text
[MNYD*863758061830955*001C*SETIP,103.44.0.5,9001]
```

---

### 5. Test with Watch Simulator

To verify packet reception and live GPS parsing without waiting for watch sleep cycles:

Open a second terminal window in `backend/`:
```bash
python simulate_watch.py
```

The simulator will replay real `PING`, `KA`, `UD` (GPS: `17.446317, 78.368395`), and `heart` (96 BPM) frames.

---

## API Documentation & Endpoint Structure

Once running, view the complete Swagger documentation at:
**[http://localhost:8000/docs](http://localhost:8000/docs)**

The API is structured into 4 distinct modules:

### 1. 🔐 Authentication (`/api/v1/auth`)
* `POST /api/v1/auth/register` - Create an officer / monitoring account
* `POST /api/v1/auth/login` - Officer login (returns JWT Bearer token)
* `GET  /api/v1/auth/me` - Authenticated user profile

### 2. 📊 Dashboard (`/api/v1/dashboard`)
* `GET /api/v1/dashboard/stats` - High-level KPIs (total bands, online, offline, low battery, active alerts)
* `GET /api/v1/dashboard/overview` - Complete dashboard summary with recent devices and alarms
* `GET /api/v1/dashboard/alerts` - Live security alarms (SOS, strap cut / tamper, low battery)

### 3. ⌚ Devices (`/api/v1/devices`)
* `GET  /api/v1/devices` - List all registered custody bands (IMEI, battery, steps, heart rate, wearer)
* `POST /api/v1/devices` - Register a new tracking band IMEI
* `GET  /api/v1/devices/{device_id}` - Detailed status and telemetry for a specific band
* `PUT  /api/v1/devices/{device_id}` - Update wearer assignment, case number, or active status
* `POST /api/v1/devices/{device_id}/command` - Transmit protocol commands to the watch (`CR` to poll, `RESET` to reboot)

### 4. 📍 GPS & Locations (`/api/v1/gps`)
* `GET  /api/v1/gps/live` - Latest coordinates of all active wearers (for rendering on live map)
* `GET  /api/v1/gps/{device_id}/latest` - Most recent GPS fix, speed, battery, and Google Maps pin
* `GET  /api/v1/gps/{device_id}/history` - Historical GPS coordinate breadcrumb trail for route replay
* `POST /api/v1/gps/{device_id}/poll` - Force watch to wake GPS chip and return instant location (`CR` command)
* `POST /api/v1/gps/geofence/check` - Test if a coordinate falls inside an allowed zone radius
* `GET  /api/v1/dashboard/devices` - List all monitored watches with last positions and battery
* `GET  /api/v1/dashboard/devices/{device_id}` - Detailed status + recent coordinates
* `GET  /api/v1/dashboard/devices/{device_id}/history` - Historical GPS trail
* `POST /api/v1/dashboard/devices/{device_id}/command` - Send instant command to watch (`CR` for live location)
* `GET  /api/v1/dashboard/alerts` - Recent security alarms (SOS, strap cut, low battery)

