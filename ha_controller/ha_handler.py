# Used as a Python module in main.
# Todo:
# * convert to real class
# * Fix proper logging

from homeassistant_api import Client
from homeassistant_api.errors import EndpointNotFoundError, HomeassistantAPIError
from dotenv import load_dotenv
import os
from time import sleep
import requests
from portal_handler import PortalHandler

load_dotenv()
HA_SERVER = os.getenv("HA_SERVER")
HA_TOKEN = os.getenv("HA_TOKEN")

# Initialize portal handler
portal = PortalHandler()

# Initialize the Home Assistant Client (may be unavailable)
try:
    client = Client(HA_SERVER, HA_TOKEN)
    HA_AVAILABLE = True
    print("Home Assistant client initialized successfully")
except Exception as e:
    print(f"Warning: Home Assistant not available: {e}")
    print("System will run in degraded mode (portal and MQTT only)")
    client = None
    HA_AVAILABLE = False

def check_ha_health():
    """
    Check if Home Assistant API is actually responding.
    Returns: True if HA is healthy and responding, False otherwise
    """
    if not HA_AVAILABLE or not HA_SERVER:
        print(f"   HA health check: HA_AVAILABLE={HA_AVAILABLE}, HA_SERVER={HA_SERVER}")
        return False
    
    try:
        # Home Assistant /api/ endpoint returns {"message": "API running."} when healthy
        # HA_SERVER already includes /api/ in the URL, so just check the root
        health_url = HA_SERVER.rstrip('/') + '/'
        print(f"   Checking HA health at: {health_url}")
        
        # Need to send auth token in header
        headers = {
            "Authorization": f"Bearer {HA_TOKEN}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(health_url, headers=headers, timeout=3)
        print(f"   Response status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response data: {data}")
            result = data.get("message") == "API running."
            print(f"   Health check result: {result}")
            return result
        print(f"   Unexpected status code: {response.status_code}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"   HA health check failed: {type(e).__name__}: {e}")
        return False

flicker_light = "light.ytterbelysning_entre"
#flicker_light = "light.kontoret_taklampa"

# Abort callback - will be set by main.py
_abort_check_callback = None

def set_abort_check_callback(callback):
    """Set a callback function that returns True if scenario should abort"""
    global _abort_check_callback
    _abort_check_callback = callback

def should_abort():
    """Check if scenario should abort"""
    if _abort_check_callback:
        return _abort_check_callback()
    return False

def light_off(name):
    """Turn off a Home Assistant light"""
    if not HA_AVAILABLE:
        print(f"HA unavailable - skipping light_off({name})")
        return False
    try:
        with client:
            light = client.get_domain("light")
            light.toggle(entity_id=name)
        return True
    except (EndpointNotFoundError, HomeassistantAPIError) as e:
        print(f"HA Error in light_off: {e}")
        return False

def light_on(name):
    """Turn on a Home Assistant light"""
    if not HA_AVAILABLE:
        print(f"HA unavailable - skipping light_on({name})")
        return False
    try:
        with client:
            light = client.get_domain("light")
            light.toggle(entity_id=name)
        return True
    except (EndpointNotFoundError, HomeassistantAPIError) as e:
        print(f"HA Error in light_on: {e}")
        return False

def light_brightness(name, brightness):
    """Set brightness of a Home Assistant light"""
    if not HA_AVAILABLE:
        print(f"HA unavailable - skipping light_brightness({name}, {brightness})")
        return False
    try:
        with client:
            light = client.get_domain("light")
            light.turn_on(entity_id=name, brightness=brightness)
        return True
    except (EndpointNotFoundError, HomeassistantAPIError) as e:
        print(f"HA Error in light_brightness: {e}")
        return False

def activate_scene(name):
    """Activate a Home Assistant scene"""
    if not HA_AVAILABLE:
        print(f"HA unavailable - skipping activate_scene({name})")
        return False
    try:
        with client:
            scene = client.get_domain("scene")
            status = scene.turn_on(entity_id=name)
            print(status)
        return True
    except (EndpointNotFoundError, HomeassistantAPIError) as e:
        print(f"HA Error in activate_scene: {e}")
        return False

def cycle(value, time_sec):
    """Light cycle with abort check"""
    if value == 0:
        light_off(flicker_light)
    else:
        light_brightness(flicker_light, value)
    
    # Sleep in small increments to allow abort checking
    elapsed = 0
    sleep_increment = 0.1
    while elapsed < time_sec:
        if should_abort():
            print("  ⚠️  Abort detected during cycle sleep")
            return True  # Signal abort
        sleep(sleep_increment)
        elapsed += sleep_increment
    return False  # No abort

def flicker():
    """Run flicker effect on entrance light with abort support"""
    if not HA_AVAILABLE:
        print("HA unavailable - simulating flicker with sleep")
        # Sleep in increments to check for abort
        for i in range(300):  # 30 seconds in 0.1s increments
            if should_abort():
                print("⚠️  Abort detected during simulated flicker")
                return True
            sleep(0.1)
        return False
    
    for x in range(3):
        print(f"Starting flicker round {x+1}/3")
        if cycle(10, 0.3): return True
        if cycle(0, 3): return True
        if cycle(200, 0.3): return True
        if cycle(0, 2.5): return True

        if cycle(150, 0.3): return True
        if cycle(50, 0.3): return True
        if cycle(0, 3.5): return True

        if cycle(70, 0.3): return True
        if cycle(200, 0.4): return True
        if cycle(70, 0.3): return True
        if cycle(0, 1.5): return True

        if cycle(200, 0.4): return True
        if cycle(0, 3): return True

        if cycle(70, 0.3): return True
        if cycle(0, 3): return True

        if cycle(250, 0.2): return True
        if cycle(0, 1): return True
        
        if cycle(70, 1): return True
    
    return False  # Completed without abort

def run_scenario():
    """
    Run the complete Halloween scenario.
    Works in degraded mode if Home Assistant is unavailable (portal effects only).
    Returns True if aborted, False if completed normally.
    """
    print("=" * 50)
    print("Starting Halloween scenario...")
    print(f"Home Assistant: {'Available' if HA_AVAILABLE else 'UNAVAILABLE (degraded mode)'}")
    print("=" * 50)
    
    # Set portal to red (state 2 - triggered)
    print("→ Triggering red blink on portal...")
    portal.trigger_red_blink()
    
    if should_abort():
        print("⚠️  Abort detected after trigger_red_blink")
        return True
    
    if HA_AVAILABLE:
        # Turn off all lights
        print("→ Turning off all lights...")
        activate_scene("scene.halloween_av")
        
        if should_abort():
            print("⚠️  Abort detected after lights off")
            return True
        
        # Run flicker effect
        print("→ Starting flicker effect...")
        aborted = flicker()
        if aborted:
            print("⚠️  Flicker was aborted")
            return True
        
        if should_abort():
            print("⚠️  Abort detected after flicker")
            return True
        
        # Restore normal lighting
        print("→ Restoring normal lighting...")
        activate_scene("scene.halloween_pa")
    else:
        print("→ HA unavailable - skipping light effects (waiting 30s)...")
        # Sleep in increments to check for abort
        for i in range(300):  # 30 seconds in 0.1s increments
            if should_abort():
                print("⚠️  Abort detected during degraded mode wait")
                return True
            sleep(0.1)
    
    if should_abort():
        print("⚠️  Abort detected before portal reset")
        return True
    
    # Reset portal to rotating (state 1 - normal)
    print("→ Resetting portal to rotating state...")
    portal.reset()
    
    print("=" * 50)
    print("Halloween scenario completed!")
    print("=" * 50)
    return False  # Completed without abort

if __name__ == "__main__":
    run_scenario()
