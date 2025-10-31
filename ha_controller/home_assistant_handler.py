"""
Home Assistant Handler
Manages communication with Home Assistant for light and scene control.
"""

import os
import requests
from typing import Optional, Callable
from time import sleep
from dotenv import load_dotenv
from homeassistant_api import Client
from homeassistant_api.errors import EndpointNotFoundError, HomeassistantAPIError

load_dotenv()


class HomeAssistantHandler:
    """
    Handler for Home Assistant light and scene control.
    
    Provides methods for:
    - Health checking
    - Light control (on/off/brightness)
    - Scene activation
    - Flicker effects
    """
    
    def __init__(self, server: Optional[str] = None, token: Optional[str] = None):
        """
        Initialize the Home Assistant handler.
        
        Args:
            server: HA server URL (defaults to HA_SERVER env var)
            token: HA access token (defaults to HA_TOKEN env var)
        """
        self.server = server or os.getenv("HA_SERVER")
        self.token = token or os.getenv("HA_TOKEN")
        self.client: Optional[Client] = None
        self.available = False
        self._abort_callback: Optional[Callable[[], bool]] = None
        
        # Light entity for flicker effect
        self.flicker_light = "light.ytterbelysning_entre"
        
        # Initialize the client
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the Home Assistant API client."""
        try:
            self.client = Client(self.server, self.token)
            self.available = True
            print("✓ Home Assistant client initialized successfully")
        except Exception as e:
            print(f"⚠️  Home Assistant not available: {e}")
            print("   System will run in degraded mode")
            self.client = None
            self.available = False
    
    def set_abort_callback(self, callback: Callable[[], bool]):
        """
        Set a callback function to check if operations should abort.
        
        Args:
            callback: Function that returns True if abort is requested
        """
        self._abort_callback = callback
    
    def should_abort(self) -> bool:
        """Check if operations should abort."""
        if self._abort_callback:
            return self._abort_callback()
        return False
    
    def check_health(self) -> bool:
        """
        Check if Home Assistant API is responding.
        
        Returns:
            True if HA is healthy and responding, False otherwise
        """
        if not self.available or not self.server:
            return False
        
        try:
            health_url = self.server.rstrip('/') + '/'
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(health_url, headers=headers, timeout=3)
            if response.status_code == 200:
                data = response.json()
                return data.get("message") == "API running."
            return False
        except requests.exceptions.RequestException:
            return False
    
    def turn_off_light(self, entity_id: str) -> bool:
        """
        Turn off a Home Assistant light.
        
        Args:
            entity_id: Light entity ID (e.g., "light.living_room")
        
        Returns:
            True on success, False on failure
        """
        if not self.available:
            print(f"HA unavailable - skipping turn_off_light({entity_id})")
            return False
        
        try:
            with self.client:
                light = self.client.get_domain("light")
                light.toggle(entity_id=entity_id)
            return True
        except (EndpointNotFoundError, HomeassistantAPIError) as e:
            print(f"HA Error turning off light: {e}")
            return False
    
    def turn_on_light(self, entity_id: str) -> bool:
        """
        Turn on a Home Assistant light.
        
        Args:
            entity_id: Light entity ID (e.g., "light.living_room")
        
        Returns:
            True on success, False on failure
        """
        if not self.available:
            print(f"HA unavailable - skipping turn_on_light({entity_id})")
            return False
        
        try:
            with self.client:
                light = self.client.get_domain("light")
                light.toggle(entity_id=entity_id)
            return True
        except (EndpointNotFoundError, HomeassistantAPIError) as e:
            print(f"HA Error turning on light: {e}")
            return False
    
    def set_brightness(self, entity_id: str, brightness: int) -> bool:
        """
        Set brightness of a Home Assistant light.
        
        Args:
            entity_id: Light entity ID (e.g., "light.living_room")
            brightness: Brightness value (0-255)
        
        Returns:
            True on success, False on failure
        """
        if not self.available:
            print(f"HA unavailable - skipping set_brightness({entity_id}, {brightness})")
            return False
        
        try:
            with self.client:
                light = self.client.get_domain("light")
                light.turn_on(entity_id=entity_id, brightness=brightness)
            return True
        except (EndpointNotFoundError, HomeassistantAPIError) as e:
            print(f"HA Error setting brightness: {e}")
            return False
    
    def activate_scene(self, entity_id: str) -> bool:
        """
        Activate a Home Assistant scene.
        
        Args:
            entity_id: Scene entity ID (e.g., "scene.movie_time")
        
        Returns:
            True on success, False on failure
        """
        if not self.available:
            print(f"HA unavailable - skipping activate_scene({entity_id})")
            return False
        
        try:
            with self.client:
                scene = self.client.get_domain("scene")
                scene.turn_on(entity_id=entity_id)
            return True
        except (EndpointNotFoundError, HomeassistantAPIError) as e:
            print(f"HA Error activating scene: {e}")
            return False
    
    def _cycle_light(self, brightness: int, duration: float) -> bool:
        """
        Cycle light brightness with abort check.
        
        Args:
            brightness: Brightness value (0 for off, 1-255 for on)
            duration: Duration to hold this brightness in seconds
        
        Returns:
            True if aborted, False if completed normally
        """
        if brightness == 0:
            self.turn_off_light(self.flicker_light)
        else:
            self.set_brightness(self.flicker_light, brightness)
        
        # Sleep in small increments to allow abort checking
        elapsed = 0
        sleep_increment = 0.1
        while elapsed < duration:
            if self.should_abort():
                return True  # Signal abort
            sleep(sleep_increment)
            elapsed += sleep_increment
        return False  # No abort
    
    def flicker_effect(self, rounds: int = 3) -> bool:
        """
        Run flicker effect on the configured flicker light.
        
        Args:
            rounds: Number of flicker rounds to perform (default: 3)
        
        Returns:
            True if aborted, False if completed normally
        """
        if not self.available:
            print("HA unavailable - simulating flicker with sleep")
            # Sleep in increments to check for abort
            for i in range(300):  # 30 seconds in 0.1s increments
                if self.should_abort():
                    print("⚠️  Abort detected during simulated flicker")
                    return True
                sleep(0.1)
            return False
        
        for x in range(rounds):
            print(f"Starting flicker round {x+1}/{rounds}")
            if self._cycle_light(10, 0.3): return True
            if self._cycle_light(0, 3): return True
            if self._cycle_light(200, 0.3): return True
            if self._cycle_light(0, 2.5): return True

            if self._cycle_light(150, 0.3): return True
            if self._cycle_light(50, 0.3): return True
            if self._cycle_light(0, 3.5): return True

            if self._cycle_light(70, 0.3): return True
            if self._cycle_light(200, 0.4): return True
            if self._cycle_light(70, 0.3): return True
            if self._cycle_light(0, 1.5): return True

            if self._cycle_light(200, 0.4): return True
            if self._cycle_light(0, 3): return True

            if self._cycle_light(70, 0.3): return True
            if self._cycle_light(0, 3): return True

            if self._cycle_light(250, 0.2): return True
            if self._cycle_light(0, 1): return True
            
            if self._cycle_light(70, 1): return True
        
        return False  # Completed without abort
