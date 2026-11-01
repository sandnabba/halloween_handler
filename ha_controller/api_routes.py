"""
API Routes
RESTful API endpoints for the Halloween controller.
"""

from threading import Thread
from typing import Callable
from flask import Blueprint, jsonify, request
from home_assistant_handler import HomeAssistantHandler
from portal_handler import PortalHandler
from scenario_handler import ScenarioHandler
from system_state import SystemState


def ok(message: str, **extra):
    return jsonify({"status": "ok", "message": message, **extra})


def error(message: str, code: int):
    return jsonify({"status": "error", "message": message}), code


def create_api(state: SystemState, portal: PortalHandler, ha: HomeAssistantHandler,
               scenario: ScenarioHandler, get_status: Callable[[], dict],
               broadcast_status: Callable[[], None]) -> Blueprint:
    api = Blueprint('api', __name__)

    # ==================== System Status ====================

    @api.get('/api/status')
    def api_status():
        """Get current system status"""
        return jsonify({"status": "ok", "data": get_status()})

    @api.post('/api/debug-mode/toggle')
    def api_debug_mode_toggle():
        """Toggle debug mode: everything runs, but no calls are sent to Home Assistant"""
        ha.debug_mode = not ha.debug_mode
        broadcast_status()
        status_text = "enabled" if ha.debug_mode else "disabled"
        print(f"🐞 Debug mode {status_text}")
        return ok(f"Debug mode {status_text}", debug_mode=ha.debug_mode)

    # ==================== Portal Control ====================

    @api.get('/api/portal/state')
    def api_portal_state():
        """Get current portal state from ESP32"""
        state_info = portal.get_state()
        if not state_info:
            return error("Failed to get portal state", 503)
        return jsonify({"status": "ok", "data": state_info})

    def portal_action(action: Callable[[], bool], message: str):
        if not action():
            return error("Portal not responding", 503)
        broadcast_status()
        return ok(message)

    @api.post('/api/portal/red')
    def api_portal_red():
        """Trigger red blink on portal (persists until reset)"""
        return portal_action(portal.trigger_red_blink, "Red blink triggered")

    @api.post('/api/portal/green')
    def api_portal_green():
        """Trigger green on portal"""
        return portal_action(portal.trigger_green_blink, "Green blink triggered")

    @api.post('/api/portal/reset')
    def api_portal_reset():
        """Reset portal to rotating state"""
        return portal_action(portal.reset, "Portal reset to rotating state")

    # ==================== Scenario Control ====================

    @api.post('/api/trigger-scenario')
    def api_trigger_scenario():
        """Manually trigger the Halloween scenario (ignores the auto-trigger setting)"""
        reason = scenario.try_trigger("manual")
        if reason:
            print(f"✗ Manual trigger rejected: {reason}")
            return error(reason, 409)
        return ok("Scenario triggered manually")

    @api.post('/api/scenario/reset')
    def api_scenario_reset():
        """Stop a running scenario, clear the cooldown, reset portal and lights"""
        was_running = scenario.abort()
        portal.reset()
        ha.lights_on()
        broadcast_status()
        message = "Scenario stopped and reset" if was_running else "Scenario reset"
        print(f"🔄 {message}")
        return ok(message)

    @api.post('/api/reset-cooldown')
    def api_reset_cooldown():
        """Reset the cooldown timer"""
        state.update(last_trigger_time=None)
        broadcast_status()
        return ok("Cooldown timer reset")

    @api.post('/api/auto-trigger/toggle')
    def api_auto_trigger_toggle():
        """Toggle auto-trigger on/off"""
        with state.lock:
            enabled = state.data["auto_trigger_enabled"] = not state.data["auto_trigger_enabled"]
        broadcast_status()
        status_text = "enabled" if enabled else "disabled"
        print(f"🔄 Auto-trigger {status_text}")
        return ok(f"Auto-trigger {status_text}", auto_trigger_enabled=enabled)

    # ==================== Home Assistant Control ====================

    def ha_action(action: Callable[[], bool], message: str):
        if not action():
            return error("Home Assistant call failed", 502)
        return ok(message)

    @api.post('/api/ha/lights-off')
    def api_ha_lights_off():
        """Turn off all lights (scene.halloween_av)"""
        return ha_action(ha.lights_off, "Lights turned off")

    @api.post('/api/ha/lights-on')
    def api_ha_lights_on():
        """Turn on all lights (scene.halloween_pa)"""
        return ha_action(ha.lights_on, "Lights turned on")

    @api.post('/api/ha/flicker')
    def api_ha_flicker():
        """Run the flicker effect on the entrance light (in the background, ~65 s)"""
        Thread(target=ha.flicker_effect, daemon=True).start()
        return ok("Flicker effect started")

    # ==================== Visitor Tracking ====================

    @api.get('/api/visitors/get')
    def api_visitors_get():
        """Get current visitor count"""
        return jsonify({"status": "ok", "visitor_count": state.snapshot()["visitor_count"]})

    @api.post('/api/visitors/add')
    def api_visitors_add():
        """Add visitors to the count"""
        count = (request.get_json(silent=True) or {}).get('count', 1)
        if not isinstance(count, int) or not 1 <= count <= 100:
            return error("Count must be an integer between 1 and 100", 400)
        total = state.add_visitors(count)
        broadcast_status()
        print(f"👻 Added {count} visitor(s). Total: {total}")
        return ok(f"Added {count} visitor(s)", visitor_count=total, added=count)

    @api.post('/api/visitors/reset')
    def api_visitors_reset():
        """Reset visitor count to zero"""
        state.reset_visitors()
        broadcast_status()
        print("👻 Visitor count reset to 0")
        return ok("Visitor count reset", visitor_count=0)

    return api
