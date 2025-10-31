"""
WebSocket Handlers
WebSocket event handlers for real-time communication with web clients.
"""

from flask_socketio import emit
from datetime import datetime

# These will be injected by main.py
portal = None
ha = None
broadcast_status = None


def init_websocket_dependencies(portal_inst, ha_inst, broadcast_fn):
    """
    Initialize WebSocket dependencies.
    Called from main.py to inject required objects.
    """
    global portal, ha, broadcast_status
    portal = portal_inst
    ha = ha_inst
    broadcast_status = broadcast_fn


def register_handlers(socketio_inst):
    """
    Register WebSocket event handlers with the SocketIO instance.
    
    Args:
        socketio_inst: Flask-SocketIO instance
    """
    
    @socketio_inst.on('connect')
    def handle_connect():
        """Handle client connection"""
        print('Client connected')
        broadcast_status()
    
    @socketio_inst.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        print('Client disconnected')
    
    @socketio_inst.on('ping_portal')
    def handle_ping_portal():
        """Ping the ESP32 portal to check connectivity"""
        state_info = portal.get_state()
        if state_info:
            emit('portal_ping_response', {
                'success': True,
                'state': state_info.get('state', 0),
                'timestamp': datetime.now().isoformat()
            })
        else:
            emit('portal_ping_response', {
                'success': False,
                'error': 'Failed to connect to portal',
                'timestamp': datetime.now().isoformat()
            })
    
    @socketio_inst.on('ping_ha')
    def handle_ping_ha():
        """Ping Home Assistant to check connectivity"""
        print("🏥 HA ping requested via WebSocket")
        is_healthy = ha.check_health()
        print(f"   HA health check result: {is_healthy}")
        if is_healthy:
            emit('ha_ping_response', {
                'success': True,
                'timestamp': datetime.now().isoformat()
            })
            print("   ✓ Sent success response to client")
        else:
            emit('ha_ping_response', {
                'success': False,
                'error': 'Home Assistant not responding',
                'timestamp': datetime.now().isoformat()
            })
            print("   ✗ Sent error response to client")
