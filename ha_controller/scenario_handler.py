"""
Scenario Handler
Runs the Halloween scenario by coordinating the RGB portal and the
Home Assistant lighting effects.
"""

import time
from threading import Event, Thread
from typing import Callable, Optional
from portal_handler import PortalHandler
from home_assistant_handler import HomeAssistantHandler
from system_state import SystemState


class ScenarioHandler:
    """
    Sequence:
    1. Portal red (alert state)
    2. All lights off
    3. Flicker effect on the entrance light
    4. Normal lighting restored
    5. Portal back to rotating

    Each run gets its own abort event, so an aborted run that is still
    winding down can't touch the status of a newer run.
    """

    def __init__(self, portal: PortalHandler, ha: HomeAssistantHandler,
                 state: SystemState, broadcast_status: Callable[[], None]):
        self.portal = portal
        self.ha = ha
        self.state = state
        self.broadcast_status = broadcast_status
        self._abort = Event()  # Abort event of the current (or last) run

    def try_trigger(self, source: str, automatic: bool = False) -> Optional[str]:
        """
        Start the scenario in a background thread unless something blocks it.

        Args:
            source: Trigger source for the log ("manual", "camera", "portal_red")
            automatic: True for MQTT triggers, which respect the auto-trigger setting

        Returns:
            None if started, otherwise the reason it was not
        """
        with self.state.lock:
            if automatic and not self.state.data["auto_trigger_enabled"]:
                return "Auto-trigger disabled"
            if self.state.data["scenario_running"]:
                return "Scenario is already running"
            remaining = self.state.cooldown_remaining()
            if remaining > 0:
                return f"Cooldown active. Wait {remaining}s"
            self.state.data["scenario_running"] = True
            self.state.data["total_triggers"] += 1
            abort = self._abort = Event()

        print(f"\n🎭 Scenario triggered (source: {source})")
        Thread(target=self._run, args=(abort,), daemon=True).start()
        return None

    def abort(self) -> bool:
        """
        Stop the running scenario, if any, and clear the cooldown.

        Returns:
            True if a scenario was running
        """
        with self.state.lock:
            was_running = self.state.data["scenario_running"]
            self._abort.set()
            self.state.data["scenario_running"] = False
            self.state.data["last_trigger_time"] = None
        return was_running

    def _run(self, abort: Event):
        self.broadcast_status()
        try:
            self._run_steps(abort)
        except Exception as e:
            print(f"✗ Error in scenario: {e}")
        finally:
            with self.state.lock:
                if self._abort is abort:  # Not replaced by a newer run
                    self.state.data["scenario_running"] = False
                    if not abort.is_set():
                        self.state.data["last_trigger_time"] = time.time()
            print("⚠️  Scenario aborted" if abort.is_set() else "✓ Scenario completed, cooldown started")
            self.broadcast_status()

    def _run_steps(self, abort: Event):
        if self.ha.debug_mode:
            print("🐞 Debug mode: Home Assistant calls are skipped")

        print("→ Portal red")
        self.portal.trigger_red_blink()
        if abort.is_set():
            return

        print("→ Lights off")
        self.ha.lights_off()
        if abort.is_set():
            return

        print("→ Flicker")
        if self.ha.flicker_effect(rounds=3, should_abort=abort.is_set):
            return

        print("→ Lights on")
        self.ha.lights_on()

        print("→ Portal back to rotating")
        self.portal.reset()
