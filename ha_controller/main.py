from home_assistant_handler import HomeAssistantHandler
from portal_handler import PortalHandler
from scenario_handler import ScenarioHandler
import api_routes
import websocket_handlers
import paho.mqtt.client as mqtt
import time
from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS
from threading import Thread, Lock
from datetime import datetime
import json
import os
from dotenv import load_dotenv

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

# Initialize handlers
portal = PortalHandler()
ha = HomeAssistantHandler()
scenario = ScenarioHandler(portal, ha)

# Global state variables
status_lock = Lock()
system_status = {
    "last_trigger_time": None,
    "cooldown_remaining": 0,
    "scenario_running": False,
    "scenario_state": "Waiting",  # "Active", "Waiting", "Cooldown"
    "abort_requested": False,  # Set to True to abort running scenario
    "auto_trigger_enabled": True,  # Enable/disable automatic triggering from MQTT
    "total_triggers": 0,
    "last_person_count": 0,
    "portal_state": 1,  # 1=ROTATING, 2=BLINK_RED, 3=BLINK_GREEN
    "portal_last_update": None,
    "portal_online": False,  # True if ESP32 portal is reachable
    "uptime_start": datetime.now().isoformat(),
    "last_mqtt_message": None,
    "ha_available": False,  # Will be updated periodically by health check
    "mqtt_connected": False,  # True if MQTT broker is connected
    "visitor_count": 0  # Total visitors tracked
}

def load_visitor_count():
    """Load visitor count from disk"""
    try:
        if os.path.exists(VISITORS_FILE):
            with open(VISITORS_FILE, 'r') as f:
                data = json.load(f)
                return data.get('visitor_count', 0)
    except Exception as e:
        print(f"Error loading visitor count: {e}")
    return 0

def save_visitor_count(count):
    """Save visitor count to disk"""
    try:
        with open(VISITORS_FILE, 'w') as f:
            json.dump({
                'visitor_count': count,
                'last_updated': datetime.now().isoformat()
            }, f)
    except Exception as e:
        print(f"Error saving visitor count: {e}")

# MQTT client reference (will be set in main)
mqtt_client_ref = None

# Flask app for web interface and API
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Register API routes Blueprint
app.register_blueprint(api_routes.api)

def broadcast_status():
    """Broadcast status update to all connected WebSocket clients"""
    update_status()
    with status_lock:
        status_copy = system_status.copy()
    
    # Only log significant state changes
    if status_copy.get("scenario_running") or status_copy.get("cooldown_remaining", 0) > 0:
        print(f"📡 Broadcasting status: scenario_state={status_copy['scenario_state']}, " +
              f"scenario_running={status_copy['scenario_running']}, " +
              f"cooldown={status_copy['cooldown_remaining']:.1f}s")
    
    socketio.emit('status_update', status_copy)

def get_cooldown_remaining():
    """Calculate remaining cooldown time in seconds"""
    if system_status["last_trigger_time"] is None:
        return 0
    elapsed = time.time() - system_status["last_trigger_time"]
    remaining = max(0, COOLDOWN_SECONDS - elapsed)
    return round(remaining, 1)

def update_status():
    """Update dynamic status fields"""
    with status_lock:
        system_status["cooldown_remaining"] = get_cooldown_remaining()
        
        # Update scenario state
        if system_status["scenario_running"]:
            system_status["scenario_state"] = "Active"
        elif system_status["cooldown_remaining"] > 0:
            system_status["scenario_state"] = "Cooldown"
        else:
            system_status["scenario_state"] = "Waiting"
        
        # Update health checks
        system_status["ha_available"] = ha.check_health()
        system_status["portal_online"] = portal.check_online()

# Initialize API dependencies (must be after utility functions are defined)
api_routes.init_api_dependencies(
    portal, ha, scenario,
    system_status, status_lock,
    broadcast_status,
    get_cooldown_remaining,
    save_visitor_count
)

# Initialize WebSocket dependencies
websocket_handlers.init_websocket_dependencies(
    portal, ha,
    broadcast_status
)

# Register WebSocket handlers
websocket_handlers.register_handlers(socketio)

# MQTT event callbacks
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")
    with status_lock:
        system_status["mqtt_connected"] = (rc == 0)
    client.subscribe(PERSON_TOPIC)
    client.subscribe(PORTAL_STATE_TOPIC)
    print(f"Subscribed to topics: {PERSON_TOPIC}, {PORTAL_STATE_TOPIC}")
    broadcast_status()

def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode()
    print(f"Message received from {topic}: {payload}")
    
    # Store last MQTT message for debug
    with status_lock:
        system_status["last_mqtt_message"] = {
            "topic": topic,
            "payload": payload,
            "timestamp": datetime.now().isoformat()
        }
    
    # Handle portal state updates
    if topic == PORTAL_STATE_TOPIC:
        try:
            state = int(payload)
            with status_lock:
                old_state = system_status["portal_state"]
                system_status["portal_state"] = state
                system_status["portal_last_update"] = datetime.now().isoformat()
            broadcast_status()
            print(f"Portal state updated: {old_state} → {state}")
            
            # Portal state 2 (red) triggers scenario automatically if auto-trigger enabled
            if state == 2 and old_state != 2:
                with status_lock:
                    if not system_status["auto_trigger_enabled"]:
                        print("⚠️  Auto-trigger disabled - ignoring portal state 2")
                        return
                    
                    if system_status["scenario_running"]:
                        print("⚠️  Scenario already running - ignoring portal trigger")
                        return
                    
                    cooldown_remaining = get_cooldown_remaining()
                    if cooldown_remaining > 0:
                        print(f"⚠️  Cooldown active ({cooldown_remaining:.1f}s) - ignoring portal trigger")
                        return
                
                print("🚨 Portal state 2 detected - triggering scenario!")
                scenario.trigger_from_source("portal_red")
                
        except ValueError as e:
            print(f"Error parsing portal state: {e}")
        return
    
    # Handle person detection from camera
    if topic == PERSON_TOPIC:
        try:
            persons = int(payload)
            
            with status_lock:
                system_status["last_person_count"] = persons
            broadcast_status()
            
            if persons >= 1:
                print("👤 Person detected by camera!")
                
                with status_lock:
                    if not system_status["auto_trigger_enabled"]:
                        print("⚠️  Auto-trigger disabled - ignoring camera detection")
                        return
                    
                    if system_status["scenario_running"]:
                        print("⚠️  Scenario already running - ignoring camera trigger")
                        return
                    
                    cooldown_remaining = get_cooldown_remaining()
                    if cooldown_remaining > 0:
                        print(f"⚠️  Cooldown active ({cooldown_remaining:.1f}s) - ignoring camera trigger")
                        return
                
                print("🎥 Camera detection - setting portal to red and triggering scenario!")
                # First set portal to red
                portal.trigger_red_blink()
                # Then trigger scenario
                scenario.trigger_from_source("camera")
        
        except ValueError as e:
            print(f"Error parsing message payload: {e}")

def on_disconnect(client, userdata, rc):
    print("Disconnected from MQTT broker")
    with status_lock:
        system_status["mqtt_connected"] = False
    broadcast_status()

def run_flask():
    """Run Flask-SocketIO web server in a separate thread"""
    socketio.run(app, host='0.0.0.0', port=WEB_PORT, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)

def main():
    print("=" * 50)
    print("Halloween Controller Starting...")
    print("=" * 50)
    
    # Load visitor count from disk
    with status_lock:
        system_status["visitor_count"] = load_visitor_count()
    print(f"✓ Visitor count loaded: {system_status['visitor_count']}")
    
    # Set up abort callback for scenario control
    scenario.set_abort_callback(lambda: system_status.get("abort_requested", False))
    print("✓ Abort callback initialized")
    
    # Set up dependencies for scenario triggering
    scenario.set_dependencies(system_status, status_lock, broadcast_status)
    print("✓ Scenario dependencies initialized")
    
    # Check Home Assistant availability and update status
    with status_lock:
        system_status["ha_available"] = ha.available
    
    if ha.available:
        print("✓ Home Assistant: Connected")
    else:
        print("✗ Home Assistant: UNAVAILABLE")
        print("  System will run in degraded mode (portal and MQTT only)")
    
    # Initialize MQTT client
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.on_disconnect = on_disconnect
    
    # Start Flask-SocketIO web server in background thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print(f"✓ Web interface started at http://0.0.0.0:{WEB_PORT}")
    print(f"✓ WebSocket server running on ws://0.0.0.0:{WEB_PORT}")
    
    # Set initial state (lights on, portal reset to rotating)
    print("\nSetting initial state...")
    if ha.available:
        ha.activate_scene("scene.halloween_pa")
    else:
        print("  Skipping HA scene activation (HA unavailable)")
    portal.reset()
    print("✓ Initial state configured")
    
    # Connect to MQTT broker
    print(f"\nConnecting to MQTT broker at {BROKER_HOSTNAME}:{BROKER_PORT}...")
    try:
        mqtt_client.connect(BROKER_HOSTNAME, BROKER_PORT, 60)
        print("✓ MQTT broker connected")
    except Exception as e:
        print(f"✗ Failed to connect to MQTT broker: {e}")
        print("  System will run without person detection")
    
    print("\n" + "=" * 50)
    print("System ready!")
    if not ha.available:
        print("⚠️  Running in DEGRADED MODE (no HA lighting)")
    print(f"Web interface: http://localhost:{WEB_PORT}")
    print("Waiting for person detection or manual triggers...")
    print("=" * 50)
    
    # Start MQTT loop (blocking)
    mqtt_client.loop_forever()

if __name__ == "__main__":
    main()

