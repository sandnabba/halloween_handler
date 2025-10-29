# RGB Portal - ESP32 LED Controller

Source code for ESP32 microcontroller controlling a WS2815 LED strip shaped as a portal (circle or "door" with 100+ LEDs).

## Features

- **State 1 (ROTATING - Default):** Color-transitioning circle (blue → purple → pink) with four bright rotating light points evenly spaced (90° apart, 21 LEDs wide each with fade)
- **State 2 (BLINK_RED):** 5 fast red blinks, then solid red (persists until manual reset via API)
- **State 3 (BLINK_GREEN):** Solid green while person is in portal, returns to ROTATING when clear
- **Motion Detection:** HC-SR04 ultrasonic sensor automatically triggers random state when motion detected (60% chance green, 40% chance red)
- **MQTT Integration:** Publishes state changes to MQTT broker
- **REST API:** HTTP endpoints to control the portal via WiFi (including distance sensor readout)

## Hardware

- **Microcontroller:** ESP32-WROOM-32D
- **LED Strip:** WS2815 (12V, dual signal variant)
- **LED Data GPIO:** GPIO 5
- **Ultrasonic Sensor:** HC-SR04
  - **Trigger GPIO:** GPIO 18
  - **Echo GPIO:** GPIO 19

### WS2815 Pin Configuration

| Pin | Function | Comment |
|-----|----------|---------|
| +12V | Power supply | Connect to +12V from power supply |
| GND | Ground | Connect to GND from both power supply and microcontroller |
| DI | Data in | Data input from ESP32 (GPIO 5) |
| BI | Backup data in | Often internally connected, can be left unconnected |
| DO / BO | Outputs | For chaining additional segments |

### HC-SR04 Ultrasonic Sensor Wiring

| Pin | Connection | Comment |
|-----|-----------|---------|
| VCC | 5V | HC-SR04 requires 5V |
| GND | GND | Common ground |
| TRIG | GPIO 18 | Trigger pin |
| ECHO | GPIO 19 | Echo pin (may need voltage divider for 3.3V ESP32) |

## Getting Started

### Prerequisites

- [VS Code](https://code.visualstudio.com/) installed
- [PlatformIO IDE](https://platformio.org/install/ide?install=vscode) extension installed in VS Code

### Installation

1. Clone or open this project in VS Code
2. Create a `src/secrets.h` file based on template:
   ```cpp
   #ifndef SECRETS_H
   #define SECRETS_H
   
   #define WIFI_SSID "Your WiFi SSID"
   #define WIFI_PASSWORD "Your WiFi password"
   
   // MQTT Configuration
   #define MQTT_SERVER "192.168.1.100"  // Your MQTT broker IP
   #define MQTT_PORT 1883
   #define MQTT_USER ""                 // Leave empty if no auth
   #define MQTT_PASSWORD ""             // Leave empty if no auth
   
   #endif
   ```
3. Connect ESP32 via USB
4. In VS Code, open command palette (`Ctrl+Shift+P`) and select **PlatformIO: Build**
5. After build, select **PlatformIO: Upload** to upload to ESP32

### Development

The project is structured according to PlatformIO standards:
- `src/main.cpp` - Main code
- `src/secrets.h` - WiFi and MQTT settings (NOT committed to Git)
- `platformio.ini` - Project configuration

### MQTT Integration

The portal publishes state changes to MQTT topic `portal/state`:
- `1` = ROTATING (blue/purple/pink)
- `2` = BLINK_RED
- `3` = BLINK_GREEN

Messages are published whenever:
- Motion is detected and triggers a state
- Manual toggle via REST API
- State automatically returns to ROTATING

### REST API

After upload, you can control the portal via HTTP:

```bash
# Toggle between ROTATING and BLINK_RED
curl http://<ESP32-IP>/toggle

# Trigger red blink (persists until manual reset)
curl http://<ESP32-IP>/red

# Trigger green blink
curl http://<ESP32-IP>/green

# Reset to ROTATING state
curl http://<ESP32-IP>/reset

# Get current state (1=ROTATING, 2=BLINK_RED, 3=BLINK_GREEN)
curl http://<ESP32-IP>/state

# Get ultrasonic sensor distance reading
curl http://<ESP32-IP>/distance

# Web page for testing
curl http://<ESP32-IP>/
```

### Configurable Variables

In `src/main.cpp`:

**LED Configuration:**
- `NUM_LEDS` - Number of LEDs on strip (currently 140)
- `LED_PIN` - GPIO pin for data input (currently GPIO 5)
- `ANIMATION_SPEED` - Update speed in ms (currently 75)

**Color Configuration:**
- `colorBlue`, `colorPurple`, `colorPink` - Color transition sequence for ROTATING mode
- `COLOR_TRANSITION_SPEED` - Speed of color transitions (currently 0.025)

**Blink Configuration:**
- `redBlinkConfig` - Red blink: 5 blinks, 200ms each, solid red after (persists until reset)
- `greenBlinkConfig` - Green blink: Solid green while person in portal

**Motion Detection:**
- `TRIG_PIN` - Ultrasonic sensor trigger pin (currently GPIO 18)
- `ECHO_PIN` - Ultrasonic sensor echo pin (currently GPIO 19)
- `DETECTION_RANGE` - Distance threshold for person detection in cm (currently 60)
- `MIN_DETECTION_DISTANCE` - Minimum valid reading in cm (currently 1)
- `MAX_DETECTION_DISTANCE` - Maximum valid reading in cm (currently 70)
- `SENSOR_READ_INTERVAL` - Time between sensor reads in ms (currently 50)
- `MIN_PASSAGE_DURATION` - Minimum time to stay green during passage in ms (currently 1500)
- `PASSAGE_COOLDOWN` - Cooldown after passage before next trigger in ms (currently 1000)