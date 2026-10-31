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
    - 1 (ROTATING): Rotating animation (normal/idle state)
    - 2 (BLINK_RED): Red blinking then solid red (triggered/alert state, until reset)
    - 3 (BLINK_GREEN): Solid green while someone is in the portal
    """

    STATE_ROTATING = 1
    STATE_BLINK_RED = 2
    STATE_BLINK_GREEN = 3

    def __init__(self, portal_ip: Optional[str] = None, timeout: int = 2):
        """
        Args:
            portal_ip: IP address of the ESP32 portal (defaults to env var PORTAL_IP or 10.1.5.32)
            timeout: HTTP request timeout in seconds for commands (default: 2)
        """
        self.portal_ip = portal_ip or os.getenv("PORTAL_IP", "10.1.5.32")
        self.timeout = timeout
        self.base_url = f"http://{self.portal_ip}"

    def check_online(self) -> bool:
        """Check if the portal responds (short timeout: called on every status update)."""
        try:
            return requests.get(f"{self.base_url}/state", timeout=1).ok
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
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"Failed to get portal state: {e}")
            return None

    def _command(self, path: str, description: str) -> bool:
        try:
            response = requests.get(f"{self.base_url}/{path}", timeout=self.timeout)
            response.raise_for_status()
            print(f"Portal: {description}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Portal: failed to {path}: {e}")
            return False

    def trigger_red_blink(self) -> bool:
        """Set state 2 (BLINK_RED); stays red until reset."""
        return self._command("red", "Red blink triggered")

    def trigger_green_blink(self) -> bool:
        """Set state 3 (BLINK_GREEN)."""
        return self._command("green", "Green blink triggered")

    def reset(self) -> bool:
        """Set state 1 (ROTATING)."""
        return self._command("reset", "Reset to rotating state")
