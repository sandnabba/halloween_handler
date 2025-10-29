# Architecture and Flow

## System Architecture

```mermaid
flowchart TB
    subgraph Camera
        Frigate["Frigate Camera
        (Person Detection)"]
    end

    subgraph MQTT_Broker
        MQTTBroker["MQTT Broker"]
    end

    subgraph BackendService
        Backend["Halloween Backend
        (Python + Flask + SocketIO)"]
    end

    subgraph PortalDevice
        ESP32["ESP32 RGB Portal
        (WS2815 + HC-SR04)"]
    end

    subgraph HomeAssistantService
        HA["Home Assistant
        (Plejd Lights)"]
    end

    subgraph WebInterface
        WebUI["Web Frontend
        (React + TypeScript)"]
    end

    Frigate -->|"MQTT: frigate/uppfarten/person"| MQTTBroker
    ESP32 -->|"MQTT: portal/state"| MQTTBroker
    MQTTBroker -->|"Subscribe: person & portal/state"| Backend

    Backend -->|"HTTP: /toggle, /red, /green, /reset"| ESP32
    Backend -->|"REST API: scenes/lights"| HA
    Backend <-->|"WebSocket: real-time updates"| WebUI
```

## System Flow

```mermaid
sequenceDiagram
    participant User as User/Web UI
    participant Camera as Frigate Camera<br/>(uppfarten)
    participant MQTT as MQTT Broker
    participant Controller as HA Controller<br/>(Python + Flask)
    participant Portal as RGB Portal<br/>(ESP32)
    participant HA as Home Assistant<br/>(Plejd Lights)
    
    Note over Controller: Initial state:<br/>Lights ON (scene.halloween_pa)<br/>Portal GREEN (State 1)
    Note over Controller: Web dashboard available<br/>at :5000
    
    alt Automatic Trigger (MQTT)
        Camera->>MQTT: Publish person count<br/>Topic: frigate/uppfarten/person
        MQTT->>Controller: Deliver message (persons ≥ 1)
    else Manual Trigger (Web UI)
        User->>Controller: POST /api/trigger-scenario
    end
    
    Controller->>Controller: Check cooldown timer<br/>(30 seconds minimum)
    
    alt Cooldown active (< 30s)
        Controller->>Controller: Ignore trigger
        Note over Controller: Wait for cooldown
        Controller->>User: Return 429 status<br/>(if manual trigger)
    else Cooldown expired (≥ 30s)
        Controller->>Controller: Set scenario_running = true
        Controller->>User: Update web dashboard
        
        Controller->>Portal: HTTP GET /state
        Portal->>Controller: Current state = 1
        Controller->>Portal: HTTP GET /toggle
        Note over Portal: State 1 → State 2<br/>5 rapid RED blinks<br/>Then permanent RED
        
        Controller->>HA: Activate scene.halloween_av
        Note over HA: Turn OFF all lights
        
        Controller->>HA: Flicker entrance light<br/>(light.ytterbelysning_entre)
        Note over HA: 3 cycles of spooky<br/>flicker patterns (~30s)
        
        Controller->>HA: Activate scene.halloween_pa
        Note over HA: Turn ON all lights
        
        Controller->>Portal: HTTP GET /state
        Portal->>Controller: Current state = 2
        Controller->>Portal: HTTP GET /toggle
        Note over Portal: State 2 → State 1<br/>Resume GREEN rotating<br/>animation
        
        Controller->>Controller: Set scenario_running = false<br/>Reset cooldown timer
        Controller->>User: Update web dashboard
    end
    
    Note over User: Can check status anytime:<br/>GET /api/status<br/>POST /api/reset-cooldown
```

## Detailed Flow

### 1. Detection Phase
- **Trigger**: Person detected in driveway by Frigate camera
- **MQTT Message**: Camera publishes person count to `frigate/uppfarten/person`
- **Cooldown Check**: Controller verifies at least 30 seconds have passed since last trigger

### 2. Activation Phase (if cooldown satisfied)
The following actions occur in parallel:

#### 2a. Portal Animation
- ESP32 receives HTTP GET request to `/toggle`
- Portal changes from **State 1** (green rotating) to **State 2**:
  - 5 rapid RED blinks (200ms on/off cycles)
  - Transitions to permanent RED light

#### 2b. Lights Out
- Home Assistant scene `scene.halloween_av` is activated
- All Plejd-controlled lights in the home turn OFF

#### 2c. Entrance Flicker
- Entrance light (`light.ytterbelysning_entre`) performs spooky flicker sequence
- 3 cycles of varying brightness and timing patterns (~30 seconds total)
- Creates atmospheric horror effect

### 3. Reset Phase
After the flicker sequence completes (~30 seconds):
- **Lights ON**: Home Assistant scene `scene.halloween_pa` restores normal lighting
- **Portal GREEN**: Portal receives HTTP GET `/toggle` to return to State 1 (green rotating animation)
- **Cooldown Reset**: Timer resets to prevent immediate re-triggering
