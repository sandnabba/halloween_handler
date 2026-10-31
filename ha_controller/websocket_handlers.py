"""
WebSocket Handlers
WebSocket event handlers for real-time communication with web clients.
"""

from datetime import datetime
from typing import Callable
from flask_socketio import SocketIO, emit
from home_assistant_handler import HomeAssistantHandler
from portal_handler import PortalHandler


def ping_response(success: bool, error: str, **extra) -> dict:
    response = {"success": success, "timestamp": datetime.now().isoformat(), **extra}
    if not success:
        response["error"] = error
    return response


def register_handlers(socketio: SocketIO, portal: PortalHandler, ha: HomeAssistantHandler,
                      broadcast_status: Callable[[], None]):

    @socketio.on('connect')
    def handle_connect():
        print('Client connected')
        broadcast_status()

    @socketio.on('disconnect')
    def handle_disconnect():
        print('Client disconnected')

    @socketio.on('ping_portal')
    def handle_ping_portal():
        """Ping the ESP32 portal to check connectivity"""
        state_info = portal.get_state()
        emit('portal_ping_response', ping_response(
            bool(state_info), "Failed to connect to portal",
            state=(state_info or {}).get('state', 0),
        ))

    @socketio.on('ping_ha')
    def handle_ping_ha():
        """Ping Home Assistant to check connectivity"""
        emit('ha_ping_response', ping_response(ha.check_health(), "Home Assistant not responding"))
