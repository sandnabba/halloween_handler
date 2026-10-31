"""
Home Assistant Handler
Controls lights and scenes through the Home Assistant REST API.
"""

import os
from time import monotonic, sleep
from typing import Callable
import requests
from dotenv import load_dotenv

load_dotenv()

# Spooky flicker pattern for one round: (brightness 0-255, seconds to hold), 0 = off
FLICKER_PATTERN = [
    (10, 0.3), (0, 3), (200, 0.3), (0, 2.5),
    (150, 0.3), (50, 0.3), (0, 3.5),
    (70, 0.3), (200, 0.4), (70, 0.3), (0, 1.5),
    (200, 0.4), (0, 3),
    (70, 0.3), (0, 3),
    (250, 0.2), (0, 1),
    (70, 1),
]


class HomeAssistantHandler:
    """
    Handler for Home Assistant light and scene control.

    In debug mode every service call is logged instead of sent, so the
    scenario runs as usual (timing, portal, MQTT) without touching the lights.
    """

    SCENE_LIGHTS_OFF = "scene.halloween_av"
    SCENE_LIGHTS_ON = "scene.halloween_pa"

    def __init__(self, timeout: int = 3):
        self.base_url = os.getenv("HA_SERVER", "").rstrip("/")
        token = os.getenv("HA_TOKEN")
        if not self.base_url or not token:
            raise ValueError("HA_SERVER and HA_TOKEN must be set in .env file")
        self.headers = {"Authorization": f"Bearer {token}"}
        self.timeout = timeout
        self.flicker_light = os.getenv("FLICKER_LIGHT", "light.fasadbelysning_ytterbelysning_entre")
        self.debug_mode = os.getenv("DEBUG_MODE", "false").lower() in ("1", "true", "yes")

    def check_health(self) -> bool:
        """Check if the Home Assistant API is responding."""
        try:
            response = requests.get(f"{self.base_url}/", headers=self.headers, timeout=self.timeout)
            return response.ok and response.json().get("message") == "API running."
        except (requests.RequestException, ValueError):
            return False

    def call_service(self, domain: str, service: str, **data) -> bool:
        """
        Call a Home Assistant service, e.g. call_service("light", "turn_off", entity_id=...).

        Returns:
            True on success (always in debug mode), False on failure
        """
        if self.debug_mode:
            print(f"🐞 Debug mode: skipping {domain}.{service} {data}")
            return True
        try:
            response = requests.post(
                f"{self.base_url}/services/{domain}/{service}",
                headers=self.headers, json=data, timeout=self.timeout,
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"HA error calling {domain}.{service} {data}: {e}")
            return False

    def activate_scene(self, entity_id: str) -> bool:
        return self.call_service("scene", "turn_on", entity_id=entity_id)

    def lights_off(self) -> bool:
        return self.activate_scene(self.SCENE_LIGHTS_OFF)

    def lights_on(self) -> bool:
        return self.activate_scene(self.SCENE_LIGHTS_ON)

    def set_light(self, entity_id: str, brightness: int) -> bool:
        """Set a light's brightness (1-255), or turn it off with 0."""
        if brightness == 0:
            return self.call_service("light", "turn_off", entity_id=entity_id)
        return self.call_service("light", "turn_on", entity_id=entity_id, brightness=brightness)

    def flicker_effect(self, rounds: int = 3, should_abort: Callable[[], bool] = lambda: False) -> bool:
        """
        Run the flicker pattern on the flicker light (~22 s per round).

        Returns:
            True if aborted, False if completed normally
        """
        for round_no in range(1, rounds + 1):
            print(f"Starting flicker round {round_no}/{rounds}")
            for brightness, duration in FLICKER_PATTERN:
                self.set_light(self.flicker_light, brightness)
                deadline = monotonic() + duration
                while monotonic() < deadline:
                    if should_abort():
                        return True
                    sleep(0.05)
        return False
