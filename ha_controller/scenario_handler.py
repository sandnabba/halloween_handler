"""
Scenario Handler
Orchestrates the complete Halloween scenario by coordinating
Home Assistant lighting effects and RGB portal states.
"""

from time import sleep
from portal_handler import PortalHandler
from home_assistant_handler import HomeAssistantHandler


class ScenarioHandler:
    """
    Orchestrates the Halloween scenario.
    
    Coordinates:
    - RGB portal state changes
    - Home Assistant lighting effects
    - Abort handling
    """
    
    # Scene entity IDs
    SCENE_LIGHTS_OFF = "scene.halloween_av"
    SCENE_LIGHTS_ON = "scene.halloween_pa"
    
    def __init__(self, portal: PortalHandler, ha: HomeAssistantHandler):
        """
        Initialize the scenario handler.
        
        Args:
            portal: PortalHandler instance for RGB portal control
            ha: HomeAssistantHandler instance for lighting control
        """
        self.portal = portal
        self.ha = ha
    
    def set_abort_callback(self, callback):
        """
        Set abort callback for both portal and HA handlers.
        
        Args:
            callback: Function that returns True if abort is requested
        """
        self.ha.set_abort_callback(callback)
    
    def should_abort(self) -> bool:
        """Check if scenario should abort."""
        return self.ha.should_abort()
    
    def run_scenario(self) -> bool:
        """
        Run the complete Halloween scenario.
        
        Sequence:
        1. Set portal to red (alert state)
        2. Turn off all lights
        3. Run flicker effect on entrance light
        4. Restore normal lighting
        5. Reset portal to rotating
        
        Works in degraded mode if Home Assistant is unavailable (portal effects only).
        
        Returns:
            True if aborted, False if completed normally
        """
        print("=" * 50)
        print("Starting Halloween scenario...")
        print(f"Home Assistant: {'Available' if self.ha.available else 'UNAVAILABLE (degraded mode)'}")
        print("=" * 50)
        
        # Step 1: Set portal to red (state 2 - triggered)
        print("→ Triggering red blink on portal...")
        self.portal.trigger_red_blink()
        
        if self.should_abort():
            print("⚠️  Abort detected after portal trigger")
            return True
        
        # Step 2-4: HA lighting effects (if available)
        if self.ha.available:
            # Turn off all lights
            print("→ Turning off all lights...")
            self.ha.activate_scene(self.SCENE_LIGHTS_OFF)
            
            if self.should_abort():
                print("⚠️  Abort detected after lights off")
                return True
            
            # Run flicker effect
            print("→ Starting flicker effect...")
            aborted = self.ha.flicker_effect(rounds=3)
            if aborted:
                print("⚠️  Flicker was aborted")
                return True
            
            if self.should_abort():
                print("⚠️  Abort detected after flicker")
                return True
            
            # Restore normal lighting
            print("→ Restoring normal lighting...")
            self.ha.activate_scene(self.SCENE_LIGHTS_ON)
        else:
            # Degraded mode: just wait
            print("→ HA unavailable - skipping light effects (waiting 30s)...")
            for i in range(300):  # 30 seconds in 0.1s increments
                if self.should_abort():
                    print("⚠️  Abort detected during degraded mode wait")
                    return True
                sleep(0.1)
        
        if self.should_abort():
            print("⚠️  Abort detected before portal reset")
            return True
        
        # Step 5: Reset portal to rotating (state 1 - normal)
        print("→ Resetting portal to rotating state...")
        self.portal.reset()
        
        print("=" * 50)
        print("Halloween scenario completed!")
        print("=" * 50)
        return False  # Completed without abort
