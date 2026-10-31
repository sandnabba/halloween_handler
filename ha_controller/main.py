from datetime import datetime
import os
from threading import Thread
from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
from api_routes import create_api
from home_assistant_handler import HomeAssistantHandler
from portal_handler import PortalHandler
from scenario_handler import ScenarioHandler
from system_state import SystemState
import websocket_handlers

# Load environment variables
load_dotenv()

# Configuration variables with defaults
BROKER_HOSTNAME = os.getenv("BROKER_HOSTNAME")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))
PERSON_TOPIC = os.getenv("PERSON_TOPIC", "frigate/insidan/person")
PORTAL_STATE_TOPIC = os.getenv("PORTAL_STATE_TOPIC", "portal/state")
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "30"))
WEB_PORT = int(os.getenv("WEB_PORT", "5000"))
VISITORS_FILE = os.getenv("VISITORS_FILE", "visitors.json")

# Validate required configuration
if not BROKER_HOSTNAME:
    raise ValueError("BROKER_HOSTNAME must be set in .env file")

state = SystemState(COOLDOWN_SECONDS, VISITORS_FILE)
portal = PortalHandler()
ha = HomeAssistantHandler()

# Flask app for the REST API and WebSocket used by the web frontend
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")


def refresh_status() -> dict:
    """Run the health checks and return a status snapshot"""
    # Outside the lock: these are network requests, and an offline portal
    # would otherwise block every other thread until the timeout
    state.update(
        ha_available=ha.check_health(),
        portal_online=portal.check_online(),
        debug_mode=ha.debug_mode,
    )
    return state.snapshot()


def broadcast_status():
    """Send the current status to all connected WebSocket clients"""
    socketio.emit('status_update', refresh_status())


scenario = ScenarioHandler(portal, ha, state, broadcast_status)
app.register_blueprint(create_api(state, portal, ha, scenario, refresh_status, broadcast_status))
websocket_handlers.register_handlers(socketio, portal, ha, broadcast_status)


# MQTT event callbacks (paho-mqtt callback API version 2)
def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected to MQTT broker: {reason_code}")
    state.update(mqtt_connected=not reason_code.is_failure)
    client.subscribe(PERSON_TOPIC)
    client.subscribe(PORTAL_STATE_TOPIC)
    print(f"Subscribed to topics: {PERSON_TOPIC}, {PORTAL_STATE_TOPIC}")
    broadcast_status()


def on_disconnect(client, userdata, flags, reason_code, properties):
    print(f"Disconnected from MQTT broker: {reason_code}")
    state.update(mqtt_connected=False)
    broadcast_status()


def auto_trigger(source: str):
    reason = scenario.try_trigger(source, automatic=True)
    if reason:
        print(f"⚠️  {reason} - ignoring {source} trigger")


def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    print(f"Message received from {msg.topic}: {payload}")
    state.update(last_mqtt_message={
        "topic": msg.topic,
        "payload": payload,
        "timestamp": datetime.now().isoformat(),
    })

    try:
        value = int(payload)
    except ValueError:
        print(f"Error parsing payload on {msg.topic}: {payload!r}")
        return

    if msg.topic == PORTAL_STATE_TOPIC:
        with state.lock:
            old_state = state.data["portal_state"]
            state.data["portal_state"] = value
            state.data["portal_last_update"] = datetime.now().isoformat()
        print(f"Portal state updated: {old_state} → {value}")
        # The portal turning red on its own (its sensor) triggers the scenario
        if value == 2 and old_state != 2:
            auto_trigger("portal_red")

    elif msg.topic == PERSON_TOPIC:
        state.update(last_person_count=value)
        if value >= 1:
            print("👤 Person detected by camera!")
            auto_trigger("camera")

    broadcast_status()


def run_flask():
    """Run Flask-SocketIO web server in a separate thread"""
    socketio.run(app, host='0.0.0.0', port=WEB_PORT, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)


def main():
    print("=" * 50)
    print("Halloween Controller Starting...")
    print("=" * 50)
    print(f"✓ Visitor count loaded: {state.data['visitor_count']}")

    if ha.check_health():
        print("✓ Home Assistant: Connected")
    else:
        print("✗ Home Assistant: UNAVAILABLE (light effects will fail)")
    if ha.debug_mode:
        print("🐞 Debug mode ON: no calls are sent to Home Assistant")

    Thread(target=run_flask, daemon=True).start()
    print(f"✓ API and WebSocket started on port {WEB_PORT}")

    # Initial state: lights on, portal rotating
    print("\nSetting initial state...")
    ha.lights_on()
    portal.reset()

    # Connect to the MQTT broker; the client keeps retrying until it succeeds
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.on_disconnect = on_disconnect
    print(f"Connecting to MQTT broker at {BROKER_HOSTNAME}:{BROKER_PORT}...")
    mqtt_client.connect_async(BROKER_HOSTNAME, BROKER_PORT, 60)

    print("\n" + "=" * 50)
    print("System ready!")
    print(f"API: http://localhost:{WEB_PORT}/api/status (web frontend: web_frontend/)")
    print("Waiting for person detection or manual triggers...")
    print("=" * 50)

    # MQTT loop (blocking)
    mqtt_client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
