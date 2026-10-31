"""
System State
Status shared by the MQTT client, the REST API, the WebSocket handlers and
the scenario thread. Every access goes through the lock.
"""

import json
import os
import time
from datetime import datetime
from threading import Lock


class SystemState:
    def __init__(self, cooldown_seconds: int, visitors_file: str):
        self.lock = Lock()
        self.cooldown_seconds = cooldown_seconds
        self.visitors_file = visitors_file
        self.data = {
            "last_trigger_time": None,
            "scenario_running": False,
            "auto_trigger_enabled": True,  # Trigger automatically from MQTT (camera and portal)
            "debug_mode": False,  # Mirrors HomeAssistantHandler.debug_mode
            "total_triggers": 0,
            "last_person_count": 0,
            "portal_state": 1,  # 1=ROTATING, 2=BLINK_RED, 3=BLINK_GREEN
            "portal_last_update": None,
            "portal_online": False,
            "ha_available": False,
            "mqtt_connected": False,
            "last_mqtt_message": None,
            "uptime_start": datetime.now().isoformat(),
            "visitor_count": self._load_visitor_count(),
        }

    def update(self, **fields):
        with self.lock:
            self.data.update(fields)

    def cooldown_remaining(self) -> float:
        """Seconds left of the cooldown. Call with the lock held."""
        last = self.data["last_trigger_time"]
        if last is None:
            return 0
        return round(max(0, self.cooldown_seconds - (time.time() - last)), 1)

    def snapshot(self) -> dict:
        """A copy of the status, with the derived fields the frontend uses."""
        with self.lock:
            snap = dict(self.data)
            snap["cooldown_remaining"] = self.cooldown_remaining()
        if snap["scenario_running"]:
            snap["scenario_state"] = "Active"
        elif snap["cooldown_remaining"] > 0:
            snap["scenario_state"] = "Cooldown"
        else:
            snap["scenario_state"] = "Waiting"
        return snap

    # ==================== Visitor count (persisted to disk) ====================

    def add_visitors(self, count: int) -> int:
        with self.lock:
            self.data["visitor_count"] += count
            total = self.data["visitor_count"]
        self._save_visitor_count(total)
        return total

    def reset_visitors(self):
        self.update(visitor_count=0)
        self._save_visitor_count(0)

    def _load_visitor_count(self) -> int:
        try:
            if os.path.exists(self.visitors_file):
                with open(self.visitors_file) as f:
                    return json.load(f).get("visitor_count", 0)
        except (OSError, ValueError) as e:
            print(f"Error loading visitor count: {e}")
        return 0

    def _save_visitor_count(self, count: int):
        try:
            with open(self.visitors_file, "w") as f:
                json.dump({"visitor_count": count, "last_updated": datetime.now().isoformat()}, f)
        except OSError as e:
            print(f"Error saving visitor count: {e}")
