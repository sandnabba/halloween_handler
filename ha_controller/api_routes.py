"""
API Routes
RESTful API endpoints for the Halloween controller.
"""

from flask import Blueprint, jsonify, request, render_template
from threading import Thread

# Create Blueprint
api = Blueprint('api', __name__)

# These will be injected by main.py
portal = None
ha = None
scenario = None
system_status = None
status_lock = None
broadcast_status = None
get_cooldown_remaining = None
save_visitor_count = None


def init_api_dependencies(portal_inst, ha_inst, scenario_inst, status, lock, broadcast_fn, cooldown_fn, save_fn):
    """
    Initialize API dependencies.
    Called from main.py to inject required objects.
    """
    global portal, ha, scenario, system_status, status_lock, broadcast_status, get_cooldown_remaining, save_visitor_count
    portal = portal_inst
    ha = ha_inst
    scenario = scenario_inst
    system_status = status
    status_lock = lock
    broadcast_status = broadcast_fn
    get_cooldown_remaining = cooldown_fn
    save_visitor_count = save_fn


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


# ==================== System Status ====================

@api.route('/api/status', methods=['GET'])
def api_status():
    """Get current system status"""
    update_status()
    with status_lock:
        return jsonify({
            "status": "ok",
            "data": system_status.copy()
        })


# ==================== Portal Control ====================

@api.route('/api/portal/state', methods=['GET'])
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


@api.route('/api/portal/red', methods=['POST'])
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


@api.route('/api/portal/green', methods=['POST'])
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


@api.route('/api/portal/reset', methods=['POST'])
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


# ==================== Scenario Control ====================

@api.route('/api/reset-cooldown', methods=['POST'])
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


@api.route('/api/auto-trigger/toggle', methods=['POST'])
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


@api.route('/api/trigger-scenario', methods=['POST'])
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
    
    # Trigger scenario via scenario handler
    scenario.trigger_from_source("manual")
    
    print("✓ Scenario triggered successfully")
    print("="*50 + "\n")
    
    return jsonify({
        "status": "ok",
        "message": "Scenario triggered manually"
    })


@api.route('/api/scenario/reset', methods=['POST'])
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


# ==================== Home Assistant Control ====================

@api.route('/api/ha/lights-off', methods=['POST'])
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


@api.route('/api/ha/lights-on', methods=['POST'])
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


@api.route('/api/ha/flicker', methods=['POST'])
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


# ==================== Visitor Tracking ====================

@api.route('/api/visitors/get', methods=['GET'])
def api_visitors_get():
    """Get current visitor count"""
    with status_lock:
        return jsonify({
            "status": "ok",
            "visitor_count": system_status["visitor_count"]
        })


@api.route('/api/visitors/add', methods=['POST'])
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


@api.route('/api/visitors/reset', methods=['POST'])
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


# ==================== Frontend ====================

@api.route('/')
def index():
    """Serve the web frontend"""
    return render_template('index.html')
