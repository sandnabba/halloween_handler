#!/usr/bin/env python3
"""
Test script for Halloween Controller
Verifies all components are properly configured
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all required packages are installed"""
    print("Testing imports...")
    try:
        import paho.mqtt.client as mqtt
        print("  ✓ paho-mqtt")
        
        import flask
        print("  ✓ flask")
        
        import requests
        print("  ✓ requests")
        
        from homeassistant_api import Client
        print("  ✓ homeassistant-api")
        
        from dotenv import load_dotenv
        print("  ✓ python-dotenv")
        
        return True
    except ImportError as e:
        print(f"  ✗ Missing package: {e}")
        print("\nRun: pip install -r requirements.txt")
        return False

def test_env_file():
    """Test that .env file exists and has required variables"""
    print("\nTesting .env configuration...")
    
    if not os.path.exists('.env'):
        print("  ✗ .env file not found")
        print("  Copy .env.example to .env and configure it")
        return False
    
    print("  ✓ .env file exists")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = ['HA_SERVER', 'HA_TOKEN']
    optional_vars = ['PORTAL_IP']
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            print(f"  ✗ {var} not set")
            missing.append(var)
        else:
            print(f"  ✓ {var} is set")
    
    for var in optional_vars:
        if os.getenv(var):
            print(f"  ✓ {var} is set")
        else:
            print(f"  ! {var} not set (using default)")
    
    return len(missing) == 0

def test_portal_connection():
    """Test connection to RGB portal"""
    print("\nTesting portal connection...")
    
    from dotenv import load_dotenv
    import requests
    
    load_dotenv()
    portal_ip = os.getenv('PORTAL_IP', '192.168.1.100')
    
    try:
        response = requests.get(f"http://{portal_ip}/state", timeout=3)
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ Portal connected at {portal_ip}")
            print(f"  ✓ Portal state: {data.get('state', 'unknown')}")
            return True
        else:
            print(f"  ✗ Portal returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Cannot connect to portal at {portal_ip}")
        print(f"    Error: {e}")
        print("    Make sure:")
        print("    1. Portal is powered on")
        print("    2. Portal is on the same network")
        print("    3. PORTAL_IP in .env is correct")
        return False

def test_ha_connection():
    """Test connection to Home Assistant"""
    print("\nTesting Home Assistant connection...")
    
    from dotenv import load_dotenv
    from homeassistant_api import Client
    
    load_dotenv()
    ha_server = os.getenv('HA_SERVER')
    ha_token = os.getenv('HA_TOKEN')
    
    if not ha_server or not ha_token:
        print("  ✗ HA_SERVER or HA_TOKEN not configured")
        return False
    
    try:
        client = Client(ha_server, ha_token)
        with client:
            # Try to get config to verify connection
            print(f"  ✓ Connected to Home Assistant")
            
            # Check if scenes exist
            scene = client.get_domain("scene")
            print("  ✓ Scene domain accessible")
            
            # Note: Can't easily check if specific scenes exist without triggering them
            print("  ! Make sure these scenes exist:")
            print("    - scene.halloween_pa (lights on)")
            print("    - scene.halloween_av (lights off)")
            
            return True
    except Exception as e:
        print(f"  ✗ Cannot connect to Home Assistant")
        print(f"    Error: {e}")
        print("    Make sure:")
        print("    1. HA_SERVER URL is correct (include /api/)")
        print("    2. HA_TOKEN is valid (not expired)")
        print("    3. Home Assistant is accessible")
        return False

def test_module_loading():
    """Test that handler modules load correctly"""
    print("\nTesting handler modules...")
    
    try:
        from home_assistant_handler import HomeAssistantHandler
        print("  ✓ home_assistant_handler imported successfully")
        
        from portal_handler import PortalHandler
        print("  ✓ portal_handler imported successfully")
        
        from scenario_handler import ScenarioHandler
        print("  ✓ scenario_handler imported successfully")
        
        # Check that classes can be instantiated
        try:
            portal = PortalHandler()
            print("  ✓ PortalHandler instantiated")
            
            ha = HomeAssistantHandler()
            print("  ✓ HomeAssistantHandler instantiated")
            
            scenario = ScenarioHandler(portal, ha)
            print("  ✓ ScenarioHandler instantiated")
        except Exception as e:
            print(f"  ⚠️  Warning instantiating handlers: {e}")
            print("     (This is expected if HA/Portal are not available)")
        
        return True
    except Exception as e:
        print(f"  ✗ Error loading handler modules: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Halloween Controller - Configuration Test")
    print("=" * 60)
    
    results = {
        "Imports": test_imports(),
        "Environment": test_env_file(),
        "Module Loading": test_module_loading(),
        "Portal Connection": test_portal_connection(),
        "Home Assistant": test_ha_connection(),
    }
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:.<30} {status}")
    
    all_passed = all(results.values())
    
    print("=" * 60)
    if all_passed:
        print("✓ All tests passed! System is ready.")
        print("\nYou can now run: python main.py")
        return 0
    else:
        print("✗ Some tests failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
