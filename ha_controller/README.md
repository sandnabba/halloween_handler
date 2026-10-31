# Halloween Controller

Python backend service that orchestrates the entire Halloween experience. Listens to MQTT events from Frigate camera and RGB Portal, controls Home Assistant scenes and lights, and provides the REST API and WebSocket used by the web frontend (`../web_frontend`).

## Features

- **MQTT Integration**: Subscribes to Frigate camera person detection and portal state events
- **Home Assistant Control**: Triggers scenes and controls lights via REST API
- **Portal Integration**: Controls RGB portal LED states via HTTP
- **WebSocket**: Real-time status updates for the web frontend (port 5000)
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
PERSON_TOPIC=frigate/insidan/person
PORTAL_STATE_TOPIC=portal/state
COOLDOWN_SECONDS=30
WEB_PORT=5000
VISITORS_FILE=visitors.json
FLICKER_LIGHT=light.fasadbelysning_ytterbelysning_entre
DEBUG_MODE=false
```

`DEBUG_MODE=true` starts the controller in debug mode (also toggled from the web frontend's debug panel): everything runs as usual (MQTT triggers, portal, timing, cooldown), but no service calls are sent to Home Assistant, so the lights are left alone. The calls are logged instead.

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

## API Endpoints

### Backend REST API

**System Control:**
- `GET /api/status` - Get current system status (state, cooldown, triggers, uptime)
- `POST /api/trigger-scenario` - Manually trigger Halloween scenario
- `POST /api/reset-cooldown` - Reset cooldown timer
- `POST /api/scenario/reset` - Stop a running scenario, clear cooldown, reset portal and lights
- `POST /api/auto-trigger/toggle` - Toggle triggering from MQTT (camera and portal)
- `POST /api/debug-mode/toggle` - Toggle debug mode (no calls to Home Assistant)

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

- `frigate/insidan/person` - Person detection count (triggers scenario when ≥ 1)
- `portal/state` - Portal state updates (1=ROTATING, 2=RED, 3=GREEN)

## Scenario Flow

When triggered (by MQTT person detection or manual API call):

1. **Portal → Red**: Set portal to State 2 (red blinking, then solid)
2. **Lights Off**: Activate `scene.halloween_av`
3. **Flicker Effect**: Run spooky entrance light sequence (3 rounds, ~65s)
4. **Lights On**: Activate `scene.halloween_pa`
5. **Portal → Rotating**: Return portal to State 1
6. **Cooldown**: Start 30-second cooldown timer (not after an abort)

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
main.py (main thread) ──────┬─ Flask web server (background thread)
                            │   ├─ websocket_handlers.py (status updates, pings)
                            │   └─ api_routes.py (REST API, /api/*)
                            │
                            └─ MQTT client (blocking)
                                └─ Subscribes to person detection & portal state

scenario_handler.py ─────── Runs the scenario in a background thread
home_assistant_handler.py ─ Home Assistant REST API: scenes, lights, flicker, debug mode
portal_handler.py ───────── ESP32 portal over HTTP
system_state.py ─────────── Shared status and visitor count
```

**Thread Safety:** `SystemState` holds the status behind one lock, shared by the MQTT client (main thread), the Flask handlers and the scenario thread. `ScenarioHandler.try_trigger` checks and claims the scenario under that lock, so two triggers can't both start it.

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

**Web frontend can't reach the backend:**
- Check configured WEB_PORT is available (default: 5000)
- Check firewall settings

## Todo

* Refactor LED_Portal management into a proper class