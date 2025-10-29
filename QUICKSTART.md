# Quick Start Guide

Get the Halloween Handler system up and running in three simple steps.

## Prerequisites

- **ESP32 board** with PlatformIO installed
- **Python 3.x** with pip
- **Node.js** and npm
- **Home Assistant** instance with API access
- **MQTT Broker** running (e.g., Mosquitto)
- **Frigate Camera** setup (optional for automatic triggering)

## Setup Steps

### 1. ESP32 Portal

```bash
cd rgb_portal
# Configure secrets.h with WiFi and MQTT credentials
# Upload via PlatformIO
pio run --target upload # (Or upload from VScode)
```

**Configuration needed:**
- WiFi SSID and password
- MQTT broker IP and credentials
- See [rgb_portal/README.md](rgb_portal/README.md) for detailed hardware setup

### 2. Python Backend

```bash
cd ha_controller
cp .env.example .env
# Edit .env with your credentials
pip install -r requirements.txt
python main.py
```

**Configuration needed in `.env`:**
- `HA_SERVER` - Your Home Assistant URL
- `HA_TOKEN` - Long-lived access token
- `PORTAL_IP` - ESP32's IP address

The backend will start on port 5000.

### 3. Web Frontend

```bash
cd web_frontend
cp .env.example .env
# Edit .env with backend URL
npm install
npm run dev  # Development mode
npm run build  # Production build (Not really used)
```

In practise, we never really build the production build. We just use the dev server as we only use this once a year.

**Configuration needed in `.env`:**
- `VITE_BACKEND_URL` - Backend server URL (default: http://localhost:5000)

The development server will start on port 5173.

## Verification

1. **Portal**: Access `http://<PORTAL_IP>/` to see the portal control page
2. **Backend**: Access `http://localhost:5000` to see the web dashboard
3. **Frontend**: Access `http://localhost:5173` (dev mode) to see the React app

## Next Steps

For detailed configuration and troubleshooting:
- [ha_controller/README.md](ha_controller/README.md) - Backend API and configuration
- [rgb_portal/README.md](rgb_portal/README.md) - Hardware setup and firmware
- [web_frontend/SETUP.md](web_frontend/SETUP.md) - Frontend development guide
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture and flow
