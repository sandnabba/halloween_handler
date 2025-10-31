from home_assistant_handler import HomeAssistantHandler
from portal_handler import PortalHandler
from scenario_handler import ScenarioHandler
import paho.mqtt.client as mqtt
import time
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
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

# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    broadcast_status()

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('ping_portal')
def handle_ping_portal():
    """Ping the ESP32 portal to check connectivity"""
    state_info = portal.get_state()
    if state_info:
        emit('portal_ping_response', {
            'success': True,
            'state': state_info.get('state', 0),
            'timestamp': datetime.now().isoformat()
        })
    else:
        emit('portal_ping_response', {
            'success': False,
            'error': 'Failed to connect to portal',
            'timestamp': datetime.now().isoformat()
        })

@socketio.on('ping_ha')
def handle_ping_ha():
    """Ping Home Assistant to check connectivity"""
    print("🏥 HA ping requested via WebSocket")
    is_healthy = ha.check_health()
    print(f"   HA health check result: {is_healthy}")
    if is_healthy:
        emit('ha_ping_response', {
            'success': True,
            'timestamp': datetime.now().isoformat()
        })
        print("   ✓ Sent success response to client")
    else:
        emit('ha_ping_response', {
            'success': False,
            'error': 'Home Assistant not responding',
            'timestamp': datetime.now().isoformat()
        })
        print("   ✗ Sent error response to client")

# API Endpoints
@app.route('/api/status', methods=['GET'])
def api_status():
    """Get current system status"""
    update_status()
    with status_lock:
        return jsonify({
            "status": "ok",
            "data": system_status.copy()
        })

@app.route('/api/portal/state', methods=['GET'])
def api_portal_state():
    """Get current portal state from ESP32"""
    state_info = portal.get_state()
    if state_info:
        return jsonify({
            "status": "ok",
            "data": state_info
        })
    else:
        return jsonify({
            "status": "error",
            "message": "Failed to get portal state"
        }), 503

@app.route('/api/portal/red', methods=['POST'])
def api_portal_red():
    """Trigger red blink on portal"""
    if portal.trigger_red_blink():
        broadcast_status()
        return jsonify({
            "status": "ok",
            "message": "Red blink triggered"
        })
    else:
        return jsonify({
            "status": "error",
            "message": "Failed to trigger red blink"
        }), 503

@app.route('/api/portal/green', methods=['POST'])
def api_portal_green():
    """Trigger green blink on portal"""
    if portal.trigger_green_blink():
        broadcast_status()
        return jsonify({
            "status": "ok",
            "message": "Green blink triggered"
        })
    else:
        return jsonify({
            "status": "error",
            "message": "Failed to trigger green blink"
        }), 503

@app.route('/api/portal/reset', methods=['POST'])
def api_portal_reset():
    """Reset portal to rotating state"""
    if portal.reset():
        broadcast_status()
        return jsonify({
            "status": "ok",
            "message": "Portal reset to rotating state"
        })
    else:
        return jsonify({
            "status": "error",
            "message": "Failed to reset portal"
        }), 503

@app.route('/api/reset-cooldown', methods=['POST'])
def api_reset_cooldown():
    """Reset the cooldown timer"""
    with status_lock:
        system_status["last_trigger_time"] = None
        system_status["cooldown_remaining"] = 0
    
    broadcast_status()
    return jsonify({
        "status": "ok",
        "message": "Cooldown timer reset"
    })

@app.route('/api/auto-trigger/toggle', methods=['POST'])
def api_auto_trigger_toggle():
    """Toggle auto-trigger on/off"""
    with status_lock:
        system_status["auto_trigger_enabled"] = not system_status["auto_trigger_enabled"]
        new_state = system_status["auto_trigger_enabled"]
    
    broadcast_status()
    status_text = "enabled" if new_state else "disabled"
    print(f"🔄 Auto-trigger {status_text}")
    
    return jsonify({
        "status": "ok",
        "auto_trigger_enabled": new_state,
        "message": f"Auto-trigger {status_text}"
    })

def trigger_scenario_from_source(source):
    """
    Trigger scenario in background thread.
    Source can be: "manual", "camera", "portal_red"
    """
    def run_async():
        print(f"\n→ Scenario thread started (source: {source})")
        with status_lock:
            system_status["scenario_running"] = True
            system_status["abort_requested"] = False
            system_status["total_triggers"] += 1
            print(f"  scenario_running = True")
            print(f"  abort_requested = False (cleared)")
            print(f"  total_triggers = {system_status['total_triggers']}")
        broadcast_status()
        
        try:
            # Check abort before running scenario
            with status_lock:
                if system_status["abort_requested"]:
                    print("⚠️  Abort requested before scenario - stopping")
                    return
            
            # Run the scenario (will check abort flag internally)
            print("→ Running scenario (lights, flicker, etc)...")
            aborted = scenario.run_scenario()
            
            if aborted:
                print("⚠️  Scenario was aborted during execution")
                with status_lock:
                    system_status["abort_requested"] = True  # Ensure flag reflects actual state
            else:
                print("✓ Scenario completed successfully")
        except Exception as e:
            print(f"✗ Error in scenario: {e}")
        finally:
            with status_lock:
                was_aborted = system_status["abort_requested"]
                system_status["scenario_running"] = False
                # Only set cooldown if scenario wasn't aborted
                if not was_aborted:
                    system_status["last_trigger_time"] = time.time()
                    print(f"→ scenario_running = False")
                    print(f"→ Starting cooldown timer")
                else:
                    print(f"→ scenario_running = False")
                    print(f"→ Cooldown NOT set (scenario was aborted)")
                system_status["abort_requested"] = False  # Clear flag
            broadcast_status()
            print("→ Scenario thread finished\n")
    
    thread = Thread(target=run_async)
    thread.daemon = True
    thread.start()

@app.route('/api/trigger-scenario', methods=['POST'])
def api_trigger_scenario():
    """Manually trigger the Halloween scenario"""
    print("\n" + "="*50)
    print("🎭 TRIGGER SCENARIO REQUEST RECEIVED (manual)")
    print("="*50)
    
    with status_lock:
        if system_status["scenario_running"]:
            print("✗ Scenario already running - rejecting request")
            print("="*50 + "\n")
            return jsonify({
                "status": "error",
                "message": "Scenario is already running"
            }), 409
        
        cooldown_remaining = get_cooldown_remaining()
        if cooldown_remaining > 0:
            print(f"✗ Cooldown active ({cooldown_remaining}s) - rejecting request")
            print("="*50 + "\n")
            return jsonify({
                "status": "error",
                "message": f"Cooldown active. Wait {cooldown_remaining}s"
            }), 429
    
    print("✓ Starting scenario in background thread...")
    
    # Set portal to red before triggering
    print("→ Setting portal to red...")
    portal.trigger_red_blink()
    
    # Trigger scenario
    trigger_scenario_from_source("manual")
    
    print("✓ Scenario triggered successfully")
    print("="*50 + "\n")
    
    return jsonify({
        "status": "ok",
        "message": "Scenario triggered manually"
    })

@app.route('/api/scenario/reset', methods=['POST'])
def api_scenario_reset():
    """Reset the scenario (clear cooldown, stop running scenario, and reset portal)"""
    print("\n" + "="*50)
    print("🔄 SCENARIO RESET REQUEST RECEIVED")
    print("="*50)
    
    with status_lock:
        was_running = system_status["scenario_running"]
        print(f"Current state - scenario_running: {was_running}")
        print(f"Current state - cooldown_remaining: {system_status['cooldown_remaining']}")
        print(f"Current state - scenario_state: {system_status['scenario_state']}")
        
        if was_running:
            print("⚠️  Setting abort_requested = True to stop running scenario")
            system_status["abort_requested"] = True
        
        system_status["scenario_running"] = False  # Force stop scenario
        system_status["last_trigger_time"] = None
        system_status["cooldown_remaining"] = 0
        system_status["scenario_state"] = "Waiting"
        
        print("NEW state - scenario_running: False")
        print("NEW state - cooldown_remaining: 0")
        print("NEW state - scenario_state: Waiting")
        print(f"NEW state - abort_requested: {system_status['abort_requested']}")
    
    # Reset portal to rotating state
    print("Resetting portal to rotating state...")
    portal.reset()

    print("→ Restoring normal lighting...")
    ha.activate_scene("scene.halloween_pa")
    
    print("Broadcasting status update to all clients...")
    broadcast_status()
    
    message = "Scenario reset"
    if was_running:
        message = "Scenario stopped and reset"
        print(f"✓ {message} (abort flag set)")
    else:
        print(f"✓ {message}")
    
    print("="*50 + "\n")
    
    return jsonify({
        "status": "ok",
        "message": message
    })

@app.route('/api/ha/lights-off', methods=['POST'])
def api_ha_lights_off():
    """Turn off all lights (activate scene.halloween_av)"""
    if not ha.available:
        return jsonify({
            "status": "error",
            "message": "Home Assistant not available"
        }), 503
    
    try:
        ha.activate_scene("scene.halloween_av")
        return jsonify({
            "status": "ok",
            "message": "Lights turned off"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error: {str(e)}"
        }), 500

@app.route('/api/ha/lights-on', methods=['POST'])
def api_ha_lights_on():
    """Turn on all lights (activate scene.halloween_pa)"""
    if not ha.available:
        return jsonify({
            "status": "error",
            "message": "Home Assistant not available"
        }), 503
    
    try:
        ha.activate_scene("scene.halloween_pa")
        return jsonify({
            "status": "ok",
            "message": "Lights turned on"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error: {str(e)}"
        }), 500

@app.route('/api/ha/flicker', methods=['POST'])
def api_ha_flicker():
    """Trigger the flicker effect on entrance light"""
    if not ha.available:
        return jsonify({
            "status": "error",
            "message": "Home Assistant not available"
        }), 503
    
    try:
        # Run flicker in a background thread since it takes ~60 seconds
        def run_flicker():
            ha.flicker_effect()
        
        thread = Thread(target=run_flicker)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "status": "ok",
            "message": "Flicker effect started"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error: {str(e)}"
        }), 500

@app.route('/api/visitors/get', methods=['GET'])
def api_visitors_get():
    """Get current visitor count"""
    with status_lock:
        return jsonify({
            "status": "ok",
            "visitor_count": system_status["visitor_count"]
        })

@app.route('/api/visitors/add', methods=['POST'])
def api_visitors_add():
    """Add visitors to the count"""
    data = request.get_json()
    count = data.get('count', 1)
    
    if not isinstance(count, int) or count < 1 or count > 100:
        return jsonify({
            "status": "error",
            "message": "Count must be an integer between 1 and 100"
        }), 400
    
    with status_lock:
        system_status["visitor_count"] += count
        new_count = system_status["visitor_count"]
    
    save_visitor_count(new_count)
    broadcast_status()
    
    print(f"👻 Added {count} visitor(s). Total: {new_count}")
    
    return jsonify({
        "status": "ok",
        "visitor_count": new_count,
        "added": count
    })

@app.route('/api/visitors/reset', methods=['POST'])
def api_visitors_reset():
    """Reset visitor count to zero"""
    with status_lock:
        system_status["visitor_count"] = 0
    
    save_visitor_count(0)
    broadcast_status()
    
    print("👻 Visitor count reset to 0")
    
    return jsonify({
        "status": "ok",
        "visitor_count": 0,
        "message": "Visitor count reset"
    })

# WebSocket event handlers

from flask import render_template

@app.route('/')
def index():
    """Serve the web frontend"""
    return render_template('index.html')

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
                trigger_scenario_from_source("portal_red")
                
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
                trigger_scenario_from_source("camera")
        
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

