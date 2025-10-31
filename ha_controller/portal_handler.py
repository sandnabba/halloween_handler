"""
RGB Portal Handler
Manages communication with the ESP32 RGB portal device over HTTP.
"""

import os
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()


class PortalHandler:
    """
    Handler for RGB Portal communication via HTTP.
    
    Portal States:
    - 1 (ROTATING): Green rotating animation (normal/idle state)
    - 2 (BLINK_RED): Red blinking then solid red (triggered/alert state)
    - 3 (BLINK_GREEN): Green blinking (success/acknowledgment state)
    """
    
    STATE_ROTATING = 1
    STATE_BLINK_RED = 2
    STATE_BLINK_GREEN = 3
    
    def __init__(self, portal_ip: Optional[str] = None, timeout: int = 5):
        """
        Initialize the PortalHandler.
        
        Args:
            portal_ip: IP address of the ESP32 portal (defaults to env var PORTAL_IP or 10.1.5.32)
            timeout: HTTP request timeout in seconds (default: 5)
        """
        self.portal_ip = portal_ip or os.getenv("PORTAL_IP", "10.1.5.32")
        self.timeout = timeout
        self.base_url = f"http://{self.portal_ip}"
    
    def check_online(self) -> bool:
        """
        Check if ESP32 portal is online and responding.
        
        Returns:
            True if portal is reachable, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/state", timeout=3)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def get_state(self) -> Optional[Dict[str, Any]]:
        """
        Get the current portal state via HTTP.
        
        Returns:
            Dictionary with state info (e.g., {'state': 1}) or None on error
        """
        try:
            response = requests.get(f"{self.base_url}/state", timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to get portal state: HTTP {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"Error communicating with portal: {e}")
            return None
    
    def trigger_red_blink(self) -> bool:
        """
        Trigger red blink state (persists until reset).
        Sets portal to state 2 (BLINK_RED).
        
        Returns:
            True on success, False on failure
        """
        try:
            response = requests.get(f"{self.base_url}/red", timeout=self.timeout)
            if response.status_code == 200:
                print("Portal: Red blink triggered")
                return True
            else:
                print(f"Failed to trigger red blink: HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"Error communicating with portal: {e}")
            return False
    
    def trigger_green_blink(self) -> bool:
        """
        Trigger green blink state (auto-returns to rotating).
        Sets portal to state 3 (BLINK_GREEN).
        
        Returns:
            True on success, False on failure
        """
        try:
            response = requests.get(f"{self.base_url}/green", timeout=self.timeout)
            if response.status_code == 200:
                print("Portal: Green blink triggered")
                return True
            else:
                print(f"Failed to trigger green blink: HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"Error communicating with portal: {e}")
            return False
    
    def reset(self) -> bool:
        """
        Reset portal to rotating state.
        Sets portal to state 1 (ROTATING).
        
        Returns:
            True on success, False on failure
        """
        try:
            response = requests.get(f"{self.base_url}/reset", timeout=self.timeout)
            if response.status_code == 200:
                print("Portal: Reset to rotating state")
                return True
            else:
                print(f"Failed to reset portal: HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"Error communicating with portal: {e}")
            return False
    

