import { useState, useEffect } from 'react'
import { io, Socket } from 'socket.io-client'
import './App.css'

interface SystemStatus {
  last_trigger_time: number | null
  cooldown_remaining: number
  scenario_running: boolean
  scenario_state: string  // "Active", "Waiting", "Cooldown"
  auto_trigger_enabled: boolean
  total_triggers: number
  last_person_count: number
  portal_state: number
  portal_last_update: string | null
  portal_online: boolean
  uptime_start: string
  ha_available: boolean
  mqtt_connected: boolean
  visitor_count: number  // Added visitor count
  last_mqtt_message: {
    topic: string
    payload: string
    timestamp: string
  } | null
}

interface PingResponse {
  success: boolean
  state?: number
  timestamp: string
  error?: string
}

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://10.1.1.1:5000'

function App() {
  const [socket, setSocket] = useState<Socket | null>(null)
  const [connected, setConnected] = useState(false)
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [showDebug, setShowDebug] = useState(false)
  const [portalPingResponse, setPortalPingResponse] = useState<PingResponse | null>(null)
  const [haPingResponse, setHaPingResponse] = useState<PingResponse | null>(null)
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [localCooldown, setLocalCooldown] = useState(0)
  const [scenarioProgress, setScenarioProgress] = useState(0) // 0-60 seconds
  const [scenarioStartTime, setScenarioStartTime] = useState<number | null>(null)
  const [addingVisitorCount, setAddingVisitorCount] = useState<number | null>(null) // Track which button is loading

  // Scenario progress tracker (60 second duration)
  useEffect(() => {
    if (!status?.scenario_running) {
      setScenarioProgress(0)
      setScenarioStartTime(null)
      return
    }

    // Scenario just started
    if (scenarioStartTime === null) {
      setScenarioStartTime(Date.now())
    }

    // Update progress every 100ms
    const interval = setInterval(() => {
      if (scenarioStartTime) {
        const elapsed = (Date.now() - scenarioStartTime) / 1000 // seconds
        setScenarioProgress(Math.min(elapsed, 60))
      }
    }, 100)

    return () => clearInterval(interval)
  }, [status?.scenario_running, scenarioStartTime])

  // Realtime cooldown countdown
  useEffect(() => {
    if (!status) return

    // Initialize local cooldown from status
    setLocalCooldown(status.cooldown_remaining)

    // Set up interval to count down every second
    const interval = setInterval(() => {
      setLocalCooldown((prev) => {
        if (prev <= 0) return 0
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [status?.cooldown_remaining, status?.last_trigger_time])

  useEffect(() => {
    // Connect to WebSocket
    const newSocket = io(BACKEND_URL)

    newSocket.on('connect', () => {
      console.log('Connected to WebSocket')
      setConnected(true)
    })

    newSocket.on('disconnect', () => {
      console.log('Disconnected from WebSocket')
      setConnected(false)
    })

    newSocket.on('status_update', (data: SystemStatus) => {
      console.log('Status update received:', data)
      setStatus(data)
    })

    newSocket.on('portal_ping_response', (data: PingResponse) => {
      console.log('Portal ping response:', data)
      setPortalPingResponse(data)
    })

    newSocket.on('ha_ping_response', (data: PingResponse) => {
      console.log('HA ping response:', data)
      setHaPingResponse(data)
    })

    setSocket(newSocket)

    // Cleanup on unmount
    return () => {
      newSocket.close()
    }
  }, [])

  const showMessage = (text: string, type: 'success' | 'error' = 'success') => {
    setMessage({ text, type })
    setTimeout(() => setMessage(null), 5000)
  }

  const handleTriggerScenario = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/trigger-scenario`, {
        method: 'POST',
      })
      const data = await response.json()
      if (data.status === 'ok') {
        showMessage('✓ Scenario triggered successfully!')
      } else {
        showMessage(`✗ ${data.message}`, 'error')
      }
    } catch (error) {
      showMessage('✗ Error triggering scenario', 'error')
      console.error('Error:', error)
    }
  }

  const handleScenarioToggle = async () => {
    // If scenario is running, stop it. Otherwise trigger it.
    if (status?.scenario_running) {
      // Stop scenario
      handleScenarioReset()
    } else {
      // Trigger scenario
      handleTriggerScenario()
    }
  }

  const handleScenarioReset = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/scenario/reset`, {
        method: 'POST',
      })
      const data = await response.json()
      if (data.status === 'ok') {
        showMessage(`🔄 ${data.message}`)
      } else {
        showMessage(`✗ ${data.message}`, 'error')
      }
    } catch (error) {
      showMessage('✗ Error resetting scenario', 'error')
      console.error('Error:', error)
    }
  }

  const handleResetCooldown = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/reset-cooldown`, {
        method: 'POST',
      })
      const data = await response.json()
      if (data.status === 'ok') {
        showMessage('⏱️ Cooldown reset!')
        setLocalCooldown(0)
      } else {
        showMessage(`✗ ${data.message}`, 'error')
      }
    } catch (error) {
      showMessage('✗ Error resetting cooldown', 'error')
      console.error('Error:', error)
    }
  }

  const handleAutoTriggerToggle = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/auto-trigger/toggle`, {
        method: 'POST',
      })
      const data = await response.json()
      if (data.status === 'ok') {
        const statusIcon = data.auto_trigger_enabled ? '✅' : '⏸️'
        showMessage(`${statusIcon} ${data.message}`)
      } else {
        showMessage(`✗ ${data.message}`, 'error')
      }
    } catch (error) {
      showMessage('✗ Error toggling auto-trigger', 'error')
      console.error('Error:', error)
    }
  }

  const handlePortalRed = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/portal/red`, {
        method: 'POST',
      })
      const data = await response.json()
      if (data.status === 'ok') {
        showMessage('🔴 Red blink triggered!')
      } else {
        showMessage(`✗ ${data.message}`, 'error')
      }
    } catch (error) {
      showMessage('✗ Error triggering red blink', 'error')
      console.error('Error:', error)
    }
  }

  const handlePortalGreen = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/portal/green`, {
        method: 'POST',
      })
      const data = await response.json()
      if (data.status === 'ok') {
        showMessage('🟢 Green blink triggered!')
      } else {
        showMessage(`✗ ${data.message}`, 'error')
      }
    } catch (error) {
      showMessage('✗ Error triggering green blink', 'error')
      console.error('Error:', error)
    }
  }

  const handlePortalReset = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/portal/reset`, {
        method: 'POST',
      })
      const data = await response.json()
      if (data.status === 'ok') {
        showMessage('🔵 Portal reset to rotating!')
      } else {
        showMessage(`✗ ${data.message}`, 'error')
      }
    } catch (error) {
      showMessage('✗ Error resetting portal', 'error')
      console.error('Error:', error)
    }
  }

  const handlePingPortal = () => {
    if (socket) {
      setPortalPingResponse(null)
      socket.emit('ping_portal')
    }
  }

  const handlePingHA = () => {
    if (socket) {
      setHaPingResponse(null)
      socket.emit('ping_ha')
    }
  }

  const handleHALightsOff = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/ha/lights-off`, {
        method: 'POST',
      })
      const data = await response.json()
      if (data.status === 'ok') {
        showMessage('💡 All lights turned off!')
      } else {
        showMessage(`✗ ${data.message}`, 'error')
      }
    } catch (error) {
      showMessage('✗ Error turning lights off', 'error')
      console.error('Error:', error)
    }
  }

  const handleHALightsOn = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/ha/lights-on`, {
        method: 'POST',
      })
      const data = await response.json()
      if (data.status === 'ok') {
        showMessage('💡 All lights turned on!')
      } else {
        showMessage(`✗ ${data.message}`, 'error')
      }
    } catch (error) {
      showMessage('✗ Error turning lights on', 'error')
      console.error('Error:', error)
    }
  }

  const handleHAFlicker = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/ha/flicker`, {
        method: 'POST',
      })
      const data = await response.json()
      if (data.status === 'ok') {
        showMessage('⚡ Flicker effect started!')
      } else {
        showMessage(`✗ ${data.message}`, 'error')
      }
    } catch (error) {
      showMessage('✗ Error starting flicker', 'error')
      console.error('Error:', error)
    }
  }

  const handleAddVisitors = async (count: number) => {
    // Mark button as loading
    setAddingVisitorCount(count)
    
    // Update local state immediately for instant feedback
    setStatus(prev => prev ? { ...prev, visitor_count: prev.visitor_count + count } : prev)
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/visitors/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ count }),
      })
      const data = await response.json()
      if (data.status !== 'ok') {
        showMessage(`✗ ${data.message}`, 'error')
        // Revert on error
        setStatus(prev => prev ? { ...prev, visitor_count: prev.visitor_count - count } : prev)
      }
    } catch (error) {
      showMessage('✗ Error adding visitors', 'error')
      console.error('Error:', error)
      // Revert on error
      setStatus(prev => prev ? { ...prev, visitor_count: prev.visitor_count - count } : prev)
    } finally {
      // Clear loading state
      setAddingVisitorCount(null)
    }
  }

  const getPortalStateName = (state: number): string => {
    switch (state) {
      case 1:
        return 'ROTATING (Blue→Purple→Pink)'
      case 2:
        return 'BLINK RED (Alarm)'
      case 3:
        return 'BLINK GREEN (Success)'
      default:
        return 'UNKNOWN'
    }
  }

  const getPortalStateColor = (state: number): string => {
    switch (state) {
      case 1:
        return '#6b5b95' // Purple
      case 2:
        return '#ff0000' // Red
      case 3:
        return '#00ff00' // Green
      default:
        return '#666666' // Gray
    }
  }

  const getScenarioStateColor = (state: string): string => {
    switch (state) {
      case 'Active':
        return '#ffaa00'  // Yellow/Orange
      case 'Cooldown':
        return '#ff0000'  // Red
      case 'Waiting':
        return '#00ff00'  // Green
      default:
        return '#666666'  // Gray
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>🎃 Halloween Controller 🎃</h1>
        <div className="connection-status">
          <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`}></span>
          {connected ? 'Connected' : 'Disconnected'}
        </div>
      </header>

      {message && (
        <div className={`message message-${message.type}`}>
          {message.text}
        </div>
      )}

      <div className="main-content">
        {/* Top row: Scenario Control and Ghost Tracker */}
        <div className="top-row">
          {/* Scenario Control Card */}
          <div className="card portal-state-card">
          <h2>Scenario Control</h2>
          {!status?.ha_available && (
            <div className="warning-banner">
              ⚠️ Home Assistant Offline - Running in degraded mode (portal only)
            </div>
          )}
          {!status?.portal_online && (
            <div className="warning-banner">
              ⚠️ Portal Offline - ESP32 not responding
            </div>
          )}
          <div className="portal-state-display">
            <div 
              className="portal-state-indicator"
              style={{ backgroundColor: getScenarioStateColor(status?.scenario_state || 'Waiting') }}
            >
              {status?.scenario_state === 'Active' && '▶'}
              {status?.scenario_state === 'Waiting' && '⏸'}
              {status?.scenario_state === 'Cooldown' && '⏱'}
            </div>
            <div className="portal-state-name">
              {status?.scenario_state || 'Waiting'}
            </div>
          </div>
          {status?.scenario_state === 'Cooldown' && (
            <div className="portal-last-update">
              Cooldown: {Math.ceil(localCooldown)}s remaining
            </div>
          )}
          <div className="button-grid" style={{ marginTop: '20px' }}>
            <button 
              className={`btn scenario-btn ${status?.scenario_running ? 'btn-red running' : 'btn-primary'}`}
              onClick={handleScenarioToggle}
              disabled={!status?.scenario_running && localCooldown > 0}
              style={status?.scenario_running ? { 
                fontWeight: 'bold'
              } : {}}
            >
              <span className="btn-content">
                {status?.scenario_running ? (
                  <>
                    <span className="icon-with-spinner">
                      <span className="play-icon">⏹️</span>
                      <svg className="spinner-ring" viewBox="0 0 50 50">
                        <circle
                          cx="25"
                          cy="25"
                          r="20"
                          fill="none"
                          stroke="rgba(255, 255, 255, 0.3)"
                          strokeWidth="3"
                        />
                        <circle
                          cx="25"
                          cy="25"
                          r="20"
                          fill="none"
                          stroke="white"
                          strokeWidth="3"
                          strokeDasharray={`${(scenarioProgress / 60) * 125.6} 125.6`}
                          strokeLinecap="round"
                          transform="rotate(-90 25 25)"
                        />
                      </svg>
                    </span>
                    {' Stop Scenario'}
                  </>
                ) : (
                  '🎭 Trigger Scenario'
                )}
              </span>
              {status?.scenario_running && (
                <div className="scenario-timer">
                  {Math.floor(scenarioProgress)}s / 60s
                </div>
              )}
            </button>
            {localCooldown > 0 && !status?.scenario_running && (
              <button 
                className="btn btn-secondary"
                onClick={handleResetCooldown}
              >
                ⏱️ Reset Cooldown ({Math.ceil(localCooldown)}s)
              </button>
            )}
          </div>
          
          {/* Auto-Trigger Toggle */}
          <div className="auto-trigger-section">
            <button 
              className={`btn btn-toggle ${status?.auto_trigger_enabled ? 'btn-toggle-on' : 'btn-toggle-off'}`}
              onClick={handleAutoTriggerToggle}
            >
              {status?.auto_trigger_enabled ? '✅ Auto-Trigger ON' : '⏸️ Auto-Trigger OFF'}
            </button>
            <div className="auto-trigger-info">
              {status?.auto_trigger_enabled ? (
                <span>Camera & portal detection active</span>
              ) : (
                <span>Manual trigger only</span>
              )}
            </div>
          </div>
        </div>

        {/* Ghost Tracker Card */}
        <div className="card ghost-tracker-card">
          <h2>👻 Ghost Tracker</h2>
          <div className="visitor-count-display">
            <div className="visitor-count-number">
              {status?.visitor_count || 0}
            </div>
            <div className="visitor-count-label">
              Total Visitors
            </div>
          </div>
          <div className="button-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px' }}>
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((count) => (
              <button 
                key={count}
                className={`btn btn-visitor ${addingVisitorCount === count ? 'btn-visitor-loading' : ''}`}
                onClick={() => handleAddVisitors(count)}
                disabled={addingVisitorCount !== null}
              >
                {addingVisitorCount === count ? '...' : `+${count}`}
              </button>
            ))}
          </div>
        </div>
      </div>

        {/* Secondary Controls - Portal and Home Assistant */}
        <div className="secondary-controls">
          {/* Portal Controls Card */}
          <div className="card secondary-card">
            <h3>🚪 Portal Controls</h3>
            {!status?.portal_online && (
              <div className="warning-banner-small">
                ⚠️ Portal Offline
              </div>
            )}
            <div className="portal-state-display-compact">
              <div 
                className="portal-state-indicator-small"
                style={{ 
                  backgroundColor: getPortalStateColor(status?.portal_state || 1)
                }}
              >
                {status?.portal_state || 1}
              </div>
              <div className="portal-state-name-compact">
                {getPortalStateName(status?.portal_state || 1)}
              </div>
            </div>
            <div className="button-grid-compact">
              <button 
                className="btn btn-small btn-red"
                onClick={handlePortalRed}
                disabled={!status?.portal_online}
              >
                🔴 Red
              </button>
              <button 
                className="btn btn-small btn-green"
                onClick={handlePortalGreen}
                disabled={!status?.portal_online}
              >
                🟢 Green
              </button>
              <button 
                className="btn btn-small btn-reset"
                onClick={handlePortalReset}
                disabled={!status?.portal_online}
              >
                🔵 Reset
              </button>
            </div>
          </div>

          {/* Home Assistant Controls Card */}
          <div className="card secondary-card">
            <h3>🏠 Home Assistant Controls</h3>
            {!status?.ha_available && (
              <div className="warning-banner-small">
                ⚠️ HA Offline
              </div>
            )}
            <div className="button-grid-compact">
              <button 
                className="btn btn-small btn-secondary"
                onClick={handleHALightsOff}
                disabled={!status?.ha_available}
              >
                � Lights Off
              </button>
              <button 
                className="btn btn-small btn-secondary"
                onClick={handleHALightsOn}
                disabled={!status?.ha_available}
              >
                � Lights On
              </button>
              <button 
                className="btn btn-small btn-secondary"
                onClick={handleHAFlicker}
                disabled={!status?.ha_available}
              >
                ⚡ Flicker
              </button>
            </div>
          </div>
        </div>

        {/* Debug Section */}
        <div className="card debug-card">
          <div className="debug-header" onClick={() => setShowDebug(!showDebug)}>
            <h2>🔧 Debug Panel</h2>
            <span className="debug-toggle">{showDebug ? '▼' : '▶'}</span>
          </div>
          
          {showDebug && (
            <div className="debug-content">
              <div className="debug-section">
                <h3>System Status</h3>
                <div className="system-info">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <strong>Home Assistant:</strong>{' '}
                      <span className="status-indicator" style={{ 
                        backgroundColor: status?.ha_available ? '#00ff00' : '#ff0000',
                        display: 'inline-block',
                        marginLeft: '8px'
                      }}></span>
                      {status?.ha_available ? ' Online' : ' Offline'}
                    </div>
                    <button 
                      className="btn btn-debug" 
                      onClick={handlePingHA}
                      style={{ 
                        padding: '4px 12px', 
                        fontSize: '0.8rem',
                        width: 'auto'
                      }}
                    >
                      📡 Ping
                    </button>
                  </div>
                  {haPingResponse && (
                    <div className={`ping-response ${haPingResponse.success ? 'success' : 'error'}`} style={{ marginTop: '8px', fontSize: '0.85rem' }}>
                      {haPingResponse.success ? (
                        <>✓ HA responded at {new Date(haPingResponse.timestamp).toLocaleTimeString()}</>
                      ) : (
                        <>✗ {haPingResponse.error} at {new Date(haPingResponse.timestamp).toLocaleTimeString()}</>
                      )}
                    </div>
                  )}
                  
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <strong>Portal (ESP32):</strong>{' '}
                      <span className="status-indicator" style={{ 
                        backgroundColor: status?.portal_online ? '#00ff00' : '#ff0000',
                        display: 'inline-block',
                        marginLeft: '8px'
                      }}></span>
                      {status?.portal_online ? ' Online' : ' Offline'}
                    </div>
                    <button 
                      className="btn btn-debug" 
                      onClick={handlePingPortal}
                      style={{ 
                        padding: '4px 12px', 
                        fontSize: '0.8rem',
                        width: 'auto'
                      }}
                    >
                      📡 Ping
                    </button>
                  </div>
                  {portalPingResponse && (
                    <div className={`ping-response ${portalPingResponse.success ? 'success' : 'error'}`} style={{ marginTop: '8px', fontSize: '0.85rem' }}>
                      {portalPingResponse.success ? (
                        <>✓ Portal responded (State: {portalPingResponse.state}) at {new Date(portalPingResponse.timestamp).toLocaleTimeString()}</>
                      ) : (
                        <>✗ {portalPingResponse.error} at {new Date(portalPingResponse.timestamp).toLocaleTimeString()}</>
                      )}
                    </div>
                  )}
                  
                  <div>
                    <strong>MQTT Broker:</strong>{' '}
                    <span className="status-indicator" style={{ 
                      backgroundColor: status?.mqtt_connected ? '#00ff00' : '#ff0000',
                      display: 'inline-block',
                      marginLeft: '8px'
                    }}></span>
                    {status?.mqtt_connected ? ' Connected' : ' Disconnected'}
                  </div>
                  
                  <div><strong>Total Triggers:</strong> {status?.total_triggers || 0}</div>
                  <div><strong>Last Person Count:</strong> {status?.last_person_count || 0}</div>
                  <div><strong>Scenario Running:</strong> {status?.scenario_running ? 'Yes' : 'No'}</div>
                  <div><strong>Cooldown:</strong> {Math.ceil(localCooldown)}s</div>
                </div>
              </div>

              <div className="debug-section">
                <h3>Last MQTT Message</h3>
                {status?.last_mqtt_message ? (
                  <div className="mqtt-message">
                    <div><strong>Topic:</strong> {status.last_mqtt_message.topic}</div>
                    <div><strong>Payload:</strong> {status.last_mqtt_message.payload}</div>
                    <div><strong>Time:</strong> {new Date(status.last_mqtt_message.timestamp).toLocaleString()}</div>
                  </div>
                ) : (
                  <div className="no-data">No MQTT messages received yet</div>
                )}
              </div>

              <div className="debug-section">
                <h3>System Info</h3>
                <div className="system-info">
                  <div><strong>WebSocket:</strong> {connected ? '✓ Connected' : '✗ Disconnected'}</div>
                  <div><strong>Backend:</strong> {BACKEND_URL}</div>
                  <div><strong>Uptime Start:</strong> {status?.uptime_start ? new Date(status.uptime_start).toLocaleString() : 'N/A'}</div>
                </div>
              </div>

              <div className="debug-section">
                <h3>Raw Status Data</h3>
                <pre className="raw-data">
                  {JSON.stringify(status, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default App
