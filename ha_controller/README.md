# Halloween Controller

Python backend service that orchestrates the entire Halloween experience. Listens to MQTT events from Frigate camera and RGB Portal, controls Home Assistant scenes and lights, and provides a real-time WebSocket dashboard.

## Features

- **MQTT Integration**: Subscribes to Frigate camera person detection and portal state events
- **Home Assistant Control**: Triggers scenes and controls lights via REST API
- **Portal Integration**: Controls RGB portal LED states via HTTP
- **WebSocket Dashboard**: Real-time status updates and manual controls (port 5000)
- **REST API**: Programmatic access to trigger scenarios and manage state
- **Cooldown Management**: 30-second cooldown between triggers
- **Thread-Safe**: Concurrent handling of MQTT events and HTTP requests

## Configuration

Create a `.env` file in this directory:

```env
# Required
HA_SERVER="https://your-homeassistant-url/api/"
HA_TOKEN="your_long_lived_access_token"
PORTAL_IP="192.168.0.100"
BROKER_HOSTNAME="192.168.0.1"

# Optional (defaults shown)
BROKER_PORT=1883
PERSON_TOPIC=frigate/uppfarten/person
PORTAL_STATE_TOPIC=portal/state
COOLDOWN_SECONDS=30
WEB_PORT=5000
VISITORS_FILE=visitors.json
```

See [../QUICKSTART.md](../QUICKSTART.md) for detailed setup instructions.

## Installation and Running

```bash
pip install -r requirements.txt
python main.py
```

The service will start on port 5000 and automatically:
1. Set initial state (lights on, portal green)
2. Connect to MQTT broker
3. Listen for person detection and portal state events

## Web Dashboard

Access at `http://localhost:5000`

**Displays:**
- System state (Ready/Running/Cooldown)
- Cooldown remaining time
- Last trigger timestamp and person count
- Total triggers count
- System uptime

**Controls:**
- Trigger Scenario (manual activation)
- Reset Cooldown
- Portal controls (red/green/reset)

## API Endpoints

### Backend REST API

**System Control:**
- `GET /api/status` - Get current system status (state, cooldown, triggers, uptime)
- `POST /api/trigger-scenario` - Manually trigger Halloween scenario
- `POST /api/reset-cooldown` - Reset cooldown timer

**Portal Control:**
- `GET /api/portal/state` - Get current portal state (1/2/3)
- `POST /api/portal/red` - Trigger red blink (persists until reset)
- `POST /api/portal/green` - Trigger green blink (auto-returns)
- `POST /api/portal/reset` - Reset portal to rotating state

### WebSocket Events

**Client → Server:**
- `ping_portal` - Ping ESP32 to check connectivity

**Server → Client:**
- `status_update` - Broadcast when system status changes
- `portal_ping_response` - Response to portal ping

### MQTT Topics (Subscribed)

- `frigate/uppfarten/person` - Person detection count (triggers scenario when ≥ 1)
- `portal/state` - Portal state updates (1=ROTATING, 2=RED, 3=GREEN)

## Scenario Flow

When triggered (by MQTT person detection or manual API call):

1. **Portal → Red**: Set portal to State 2 (red blinking, then solid)
2. **Lights Off**: Activate `scene.halloween_av`
3. **Flicker Effect**: Run spooky entrance light sequence (~30s)
4. **Lights On**: Activate `scene.halloween_pa`
5. **Portal → Green**: Return portal to State 1 (green rotating)
6. **Cooldown**: Start 30-second cooldown timer

## Requirements

**Home Assistant Scenes:**
- `scene.halloween_pa` - Normal state (lights on)
- `scene.halloween_av` - Dark state (lights off)

**MQTT Broker:**
- Address: Configured in `.env`
- Topics: Configurable via `PERSON_TOPIC` and `PORTAL_STATE_TOPIC`

**RGB Portal:**
- ESP32 with HTTP endpoints enabled
- IP address configured in `.env`

## Architecture

```
main.py (main thread) ─┬─ Flask web server (background thread)
                       │   ├─ WebSocket dashboard
                       │   ├─ REST API (/api/*)
                       │   └─ Static web UI
                       │
                       └─ MQTT client (blocking)
                           └─ Subscribes to person detection & portal state

ha_handler.py ─────────┬─ Home Assistant API client
                       ├─ Portal HTTP client
                       ├─ Scene activation
                       ├─ Light control
                       └─ Flicker effects
```

**Thread Safety:** Global `status_lock` ensures safe access to shared state between MQTT handler (main thread) and Flask API handlers (Flask thread).

## Troubleshooting

**Portal not responding:**
- Verify `PORTAL_IP` matches ESP32's IP address
- Test with: `curl http://{PORTAL_IP}/state`

**Home Assistant errors:**
- Verify `HA_TOKEN` is valid and `HA_SERVER` URL ends with `/api/`
- Ensure scenes exist: `scene.halloween_pa` and `scene.halloween_av`

**MQTT not connecting:**
- Check broker address in `.env` (BROKER_HOSTNAME and BROKER_PORT)
- Verify broker is running and reachable
- Verify Frigate is publishing to configured PERSON_TOPIC

**Web interface not loading:**
- Check configured WEB_PORT is available (default: 5000)
- Check firewall settings