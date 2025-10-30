#include <Arduino.h>
#include <FastLED.h>
#include <WiFi.h>
#include <WebServer.h>
#include <PubSubClient.h>
#include <ArduinoOTA.h>
#include "secrets.h"

// WiFi configuration from secrets.h
const char* ssid = WIFI_SSID;
const char* password = WIFI_PASSWORD;

// MQTT configuration from secrets.h
const char* mqtt_server = MQTT_SERVER;
const int mqtt_port = MQTT_PORT;
const char* mqtt_user = MQTT_USER;
const char* mqtt_password = MQTT_PASSWORD;
const char* mqtt_topic_state = "portal/state";  // Topic to publish state changes

WiFiClient espClient;
PubSubClient mqttClient(espClient);

// WS2815 LED strip configuration
#define LED_PIN     5       // GPIO pin where the LED strip is connected
#define NUM_LEDS    140     // Number of LEDs to control
#define LED_TYPE    WS2812B // WS2815 works with WS2812B protocol
#define COLOR_ORDER RGB     // Color order for WS2815

// HC-SR04 Ultrasonic Sensor configuration
#define TRIG_PIN    18      // GPIO pin for trigger
#define ECHO_PIN    19      // GPIO pin for echo
#define DETECTION_RANGE 56  // cm - someone is in portal if distance < this
#define MIN_DETECTION_DISTANCE 1  // cm - ignore readings closer than this (noise)
#define MAX_DETECTION_DISTANCE 70  // cm - ignore readings farther than this (for sensor validity)

CRGB leds[NUM_LEDS];
WebServer server(80);

// Portal states
enum PortalState {
  ROTATING,      // Rotating light points
  BLINK_RED,     // Blink red, then solid red
  BLINK_GREEN    // Blink green once, then return to ROTATING
};

PortalState currentState = ROTATING;
unsigned long lastUpdate = 0;
int rotatingPosition = 0;

// Animation speed (ms between updates)
#define ANIMATION_SPEED 75

// Rotating effect configuration
CRGB rotatingSpotColor = CRGB(0, 255, 0); // Spot color (default: bright green)

// Color transition configuration for base color (Blue -> Purple -> Pink)
CRGB colorBlue = CRGB(0, 0, 255);     // Blue
CRGB colorPurple = CRGB(128, 0, 255); // Purple
CRGB colorPink = CRGB(255, 0, 128);   // Pink
float colorPhase = 0.0;               // Current position in transition (0.0 to 2.0)
float colorDirection = 1.0;           // 1.0 = forward, -1.0 = backward
#define COLOR_TRANSITION_SPEED 0.025  // How fast color transitions

// Blink configuration
struct BlinkConfig {
  CRGB color;
  int numBlinks;
  int blinkDuration;  // ms per blink (on or off)
  bool solidAfterBlink; // true = solid color after blink, false = return to ROTATING
};

// State-specific configurations
BlinkConfig redBlinkConfig = {CRGB::Red, 5, 200, true};
BlinkConfig greenBlinkConfig = {CRGB::Green, 0, 0, true};  // Solid green, stays until manually cleared

// Variables for blink animation
unsigned long blinkStartTime = 0;
bool blinkingDone = false;
BlinkConfig activeBlinkConfig;

// Variables for auto-trigger and timeout
unsigned long stateEndTime = ULONG_MAX; // Initialize to max value to prevent false timeout at startup
bool autoTriggered = false;
#define RED_STATE_DURATION 10000 // ms - how long red mode should be active (10 seconds)

// Calculate opposite position (across the circle)
int getOppositePosition(int pos) {
  return (pos + NUM_LEDS / 2) % NUM_LEDS;
}

// Variables for ultrasonic sensor
float lastDistance = DETECTION_RANGE;  // Initialize to "no one there"
unsigned long lastSensorRead = 0;
unsigned long sensorStartTime = 0; // Track when sensor started
bool sensorWarmedUp = false; // Flag to indicate sensor warmup complete
#define SENSOR_READ_INTERVAL 50 // ms between readings
#define SENSOR_WARMUP_TIME 3000 // ms - ignore detections for first 3 seconds

// Variables for passage detection
bool inPassage = false; // True when someone is passing through
unsigned long passageStartTime = 0; // When passage started
unsigned long lastPassageEndTime = 0; // When last passage ended
#define MIN_PASSAGE_DURATION 1500 // ms - minimum time to stay green during passage
#define PASSAGE_COOLDOWN 1000 // ms - cooldown after passage before next trigger

// Variables for WiFi reconnection
unsigned long lastWiFiReconnectAttempt = 0;
#define WIFI_RECONNECT_INTERVAL 5000 // ms - try reconnecting every 5 seconds

// Forward declarations
void triggerRedBlink();
void triggerGreenBlink();
void triggerRandomBlink();
void updateLEDs();
void publishStateToMQTT();
void reconnectMQTT();

// Function to draw rotating effect
void drawRotatingEffect() {
  // 4 punkter jämnt fördelade på 140 LEDs: 0, 35, 70, 105
  int secondPos = (rotatingPosition + 35) % NUM_LEDS;  // 90 degrees (140/4 = 35)
  int thirdPos = (rotatingPosition + 70) % NUM_LEDS;   // 180 degrees
  int fourthPos = (rotatingPosition + 105) % NUM_LEDS; // 270 degrees
  
  // Calculate current base color by blending between blue -> purple -> pink
  CRGB rotatingBaseColor;
  if (colorPhase < 1.0) {
    // Blend from blue to purple (phase 0.0 to 1.0)
    rotatingBaseColor = blend(colorBlue, colorPurple, (uint8_t)(colorPhase * 255));
  } else {
    // Blend from purple to pink (phase 1.0 to 2.0)
    rotatingBaseColor = blend(colorPurple, colorPink, (uint8_t)((colorPhase - 1.0) * 255));
  }
  
  for(int i = 0; i < NUM_LEDS; i++) {
    // Set base color (dim version of the blended color)
    leds[i] = rotatingBaseColor;
    leds[i].nscale8(50); // Dim to 20% brightness for base
    
    // First rotating light point (21 LEDs wide with fade: center + 10 on each side)
    int dist1 = abs(i - rotatingPosition);
    if (dist1 > NUM_LEDS / 2) dist1 = NUM_LEDS - dist1; // Wrapping
    
    if (dist1 == 0) {
      leds[i] = rotatingBaseColor; // Center - max brightness
    } else if (dist1 <= 2) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(240); // 94% brightness
    } else if (dist1 <= 4) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(210); // 82% brightness
    } else if (dist1 <= 6) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(180); // 71% brightness
    } else if (dist1 <= 8) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(140); // 55% brightness
    } else if (dist1 <= 10) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(90); // 35% brightness
    }
    
    // Second rotating light point (90 degrees, 21 LEDs wide with fade)
    int dist2 = abs(i - secondPos);
    if (dist2 > NUM_LEDS / 2) dist2 = NUM_LEDS - dist2; // Wrapping
    
    if (dist2 == 0) {
      leds[i] = rotatingBaseColor; // Center - max brightness
    } else if (dist2 <= 2) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(240); // 94% brightness
    } else if (dist2 <= 4) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(210); // 82% brightness
    } else if (dist2 <= 6) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(180); // 71% brightness
    } else if (dist2 <= 8) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(140); // 55% brightness
    } else if (dist2 <= 10) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(90); // 35% brightness
    }
    
    // Third rotating light point (180 degrees, 21 LEDs wide with fade)
    int dist3 = abs(i - thirdPos);
    if (dist3 > NUM_LEDS / 2) dist3 = NUM_LEDS - dist3; // Wrapping
    
    if (dist3 == 0) {
      leds[i] = rotatingBaseColor; // Center - max brightness
    } else if (dist3 <= 2) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(240); // 94% brightness
    } else if (dist3 <= 4) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(210); // 82% brightness
    } else if (dist3 <= 6) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(180); // 71% brightness
    } else if (dist3 <= 8) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(140); // 55% brightness
    } else if (dist3 <= 10) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(90); // 35% brightness
    }
    
    // Fourth rotating light point (270 degrees, 21 LEDs wide with fade)
    int dist4 = abs(i - fourthPos);
    if (dist4 > NUM_LEDS / 2) dist4 = NUM_LEDS - dist4; // Wrapping
    
    if (dist4 == 0) {
      leds[i] = rotatingBaseColor; // Center - max brightness
    } else if (dist4 <= 2) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(240); // 94% brightness
    } else if (dist4 <= 4) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(210); // 82% brightness
    } else if (dist4 <= 6) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(180); // 71% brightness
    } else if (dist4 <= 8) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(140); // 55% brightness
    } else if (dist4 <= 10) {
      leds[i] = rotatingBaseColor;
      leds[i].nscale8(90); // 35% brightness
    }
  }
  FastLED.show();
}

// Function to draw blink effect
void drawBlinkEffect() {
  unsigned long elapsed = millis() - blinkStartTime;
  
  // Calculate total duration based on numBlinks
  unsigned long totalBlinkDuration;
  if (activeBlinkConfig.numBlinks == 0) {
    // Special case: solid color indefinitely (blinkDuration = 0) or for specific time
    if (activeBlinkConfig.blinkDuration == 0) {
      // Duration 0 means stay solid forever (until manually changed)
      totalBlinkDuration = ULONG_MAX;
    } else {
      totalBlinkDuration = activeBlinkConfig.blinkDuration;
    }
  } else {
    // Normal blinking: numBlinks * (on + off time)
    totalBlinkDuration = activeBlinkConfig.numBlinks * activeBlinkConfig.blinkDuration * 2;
  }
  
  if (!blinkingDone) {
    if (elapsed > totalBlinkDuration) {
      // Blinking is complete
      blinkingDone = true;
      
      if (activeBlinkConfig.solidAfterBlink) {
        // Solid color with blink color
        for(int i = 0; i < NUM_LEDS; i++) {
          leds[i] = activeBlinkConfig.color;
        }
      } else {
        // Return to ROTATING
        currentState = ROTATING;
        autoTriggered = false;
        publishStateToMQTT();
        drawRotatingEffect();
        return;
      }
    } else {
      // Special case: if numBlinks is 0, just show solid color
      if (activeBlinkConfig.numBlinks == 0) {
        for(int i = 0; i < NUM_LEDS; i++) {
          leds[i] = activeBlinkConfig.color;
        }
      } else {
        // Blink phase: toggle between color and black
        int cycle = elapsed / activeBlinkConfig.blinkDuration;
        bool shouldLight = (cycle % 2 == 0);
        
        for(int i = 0; i < NUM_LEDS; i++) {
          leds[i] = shouldLight ? activeBlinkConfig.color : CRGB::Black;
        }
      }
    }
  } else {
    // After blinking - solid color
    if (activeBlinkConfig.solidAfterBlink) {
      for(int i = 0; i < NUM_LEDS; i++) {
        leds[i] = activeBlinkConfig.color;
      }
    }
  }
  FastLED.show();
}

// Function to set LED colors based on state
void updateLEDs() {
  switch (currentState) {
    case ROTATING:
      drawRotatingEffect();
      break;
    case BLINK_RED:
    case BLINK_GREEN:
      drawBlinkEffect();
      break;
  }
}

// Update animations
void updateAnimations() {
  unsigned long now = millis();
  if (now - lastUpdate > ANIMATION_SPEED) {
    rotatingPosition = (rotatingPosition + 1) % NUM_LEDS;
    
    // Update color transition for ROTATING state (Blue -> Purple -> Pink -> Purple -> Blue)
    if (currentState == ROTATING) {
      colorPhase += colorDirection * COLOR_TRANSITION_SPEED;
      
      // Reverse direction at endpoints (0.0 = blue, 1.0 = purple, 2.0 = pink)
      if (colorPhase >= 2.0) {
        colorPhase = 2.0;
        colorDirection = -1.0;
      } else if (colorPhase <= 0.0) {
        colorPhase = 0.0;
        colorDirection = 1.0;
      }
    }
    
    updateLEDs();
    lastUpdate = now;
  }
}

void handleToggle() {
  autoTriggered = false; // Manual toggle, not automatic
  
  // Toggle between ROTATING and BLINK_RED
  if (currentState == ROTATING) {
    currentState = BLINK_RED;
    activeBlinkConfig = redBlinkConfig;
    blinkStartTime = millis();
    blinkingDone = false;
    stateEndTime = millis() + RED_STATE_DURATION;
  } else {
    currentState = ROTATING;
  }
  
  updateLEDs();
  publishStateToMQTT();
  
  String response = "{\"status\":\"ok\",\"state\":";
  response += (currentState == ROTATING) ? "1" : "2";
  response += "}";

  Serial.println("Toggle state (manual)");
  
  server.send(200, "application/json", response);
}

void handleState() {
  String response = "{\"state\":";
  response += (currentState == ROTATING) ? "1" : ((currentState == BLINK_RED) ? "2" : "3");
  response += "}";
  
  server.send(200, "application/json", response);
}

void handleGreenBlink() {
  triggerGreenBlink();
  
  String response = "{\"status\":\"ok\",\"state\":3}";
  Serial.println("Green blink triggered (manual)");
  
  server.send(200, "application/json", response);
}

void handleRedBlink() {
  triggerRedBlink();
  
  String response = "{\"status\":\"ok\",\"state\":2}";
  Serial.println("Red blink triggered (manual)");
  
  server.send(200, "application/json", response);
}

void handleReset() {
  currentState = ROTATING;
  publishStateToMQTT();
  
  String response = "{\"status\":\"ok\",\"state\":1}";
  Serial.println("Reset to ROTATING state (manual)");
  
  server.send(200, "application/json", response);
}

void handleRoot() {
  String html = "<html><body>";
  html += "<h1>ESP32 LED Controller</h1>";
  html += "<p>Available endpoints:</p>";
  html += "<ul>";
  html += "<li>GET /toggle - Toggle between ROTATING and BLINK_RED</li>";
  html += "<li>GET /red - Trigger red blink (persists until reset)</li>";
  html += "<li>GET /green - Trigger green blink (returns to ROTATING)</li>";
  html += "<li>GET /reset - Reset to ROTATING state</li>";
  html += "<li>GET /state - Get current state (1=ROTATING, 2=BLINK_RED, 3=BLINK_GREEN)</li>";
  html += "<li>GET /distance - Get current ultrasonic sensor distance</li>";
  html += "</ul>";
  html += "<button onclick=\"fetch('/toggle')\">Toggle Red</button> ";
  html += "<button onclick=\"fetch('/red')\">Red Blink</button> ";
  html += "<button onclick=\"fetch('/green')\">Green Blink</button> ";
  html += "<button onclick=\"fetch('/reset')\">Reset</button> ";
  html += "<button onclick=\"fetch('/distance').then(r=>r.json()).then(d=>alert('Distance: '+d.distance+' cm'))\">Check Distance</button>";
  html += "</body></html>";
  
  server.send(200, "text/html", html);
}

// Function to measure distance with HC-SR04
float measureDistance() {
  // Send out a pulse
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  // Read the echo (timeout after 30ms = approx 5m)
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  
  // Calculate distance in cm (speed of sound: 343 m/s)
  // Distance = (time * speed) / 2 (because sound travels there and back)
  float distance = duration * 0.034 / 2;
  
  return distance;
}

void handleDistance() {
  float distance = measureDistance();
  
  String response = "{\"distance\":";
  response += String(distance, 2); // 2 decimaler
  response += ",\"unit\":\"cm\",\"inRange\":";
  response += (distance >= MIN_DETECTION_DISTANCE && distance <= MAX_DETECTION_DISTANCE) ? "true" : "false";
  response += ",\"personDetected\":";
  response += (distance < DETECTION_RANGE && distance >= MIN_DETECTION_DISTANCE) ? "true" : "false";
  response += "}";
  
  server.send(200, "application/json", response);
}

// Function to trigger red blink (state 2)
void triggerRedBlink() {
  if (currentState == ROTATING) { // Only trigger if we're in ROTATING mode
    currentState = BLINK_RED;
    autoTriggered = true;
    activeBlinkConfig = redBlinkConfig;
    blinkStartTime = millis();
    blinkingDone = false;
    // No timeout - stays red until manual reset
    updateLEDs();
    publishStateToMQTT();
    Serial.println("Red state triggered! Will stay red until manual reset via API...");
  }
}

// Function to trigger green blink (state 3)
void triggerGreenBlink() {
  if (currentState == ROTATING || currentState == BLINK_RED) { // Trigger from ROTATING or RED mode
    currentState = BLINK_GREEN;
    autoTriggered = true;
    activeBlinkConfig = greenBlinkConfig;
    blinkStartTime = millis();
    blinkingDone = false;
    updateLEDs();
    publishStateToMQTT();
    Serial.println("Green blink triggered! Will stay green while person in portal...");
  }
}

// Function to trigger random blink (60% green, 40% red)
void triggerRandomBlink() {
  if (currentState == ROTATING) {
    // Generate random number between 0-99
    int randomValue = random(100);
    
    if (randomValue < 60) {
      // 60% chance for green blink
      Serial.println("Random trigger: GREEN (60% chance)");
      triggerGreenBlink();
    } else {
      // 40% chance for red blink
      Serial.println("Random trigger: RED (40% chance)");
      triggerRedBlink();
    }
  }
}

// Publish current state to MQTT
void publishStateToMQTT() {
  if (!mqttClient.connected()) {
    return; // Don't try to publish if not connected
  }
  
  String stateStr;
  switch (currentState) {
    case ROTATING:
      stateStr = "1";
      break;
    case BLINK_RED:
      stateStr = "2";
      break;
    case BLINK_GREEN:
      stateStr = "3";
      break;
  }
  
  mqttClient.publish(mqtt_topic_state, stateStr.c_str());
  Serial.print("MQTT: Published state ");
  Serial.print(stateStr);
  Serial.print(" to ");
  Serial.println(mqtt_topic_state);
}

// Reconnect to MQTT broker
void reconnectMQTT() {
  // Don't block if MQTT is down
  if (!mqttClient.connected()) {
    Serial.print("Attempting MQTT connection...");
    
    // Create a random client ID
    String clientId = "ESP32Portal-";
    clientId += String(random(0xffff), HEX);
    
    // Attempt to connect
    if (mqttClient.connect(clientId.c_str(), mqtt_user, mqtt_password)) {
      Serial.println("connected");
      publishStateToMQTT(); // Publish initial state
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" (will retry later)");
    }
  }
}

// Function to check if red blink should end (removed - now manual reset only)
// State 2 (red) now stays until manually reset via API

// Function to check if someone is moving through the portal
void checkMotionDetection() {
  unsigned long now = millis();
  
  // Check if sensor warmup period has passed
  if (!sensorWarmedUp) {
    if (now - sensorStartTime > SENSOR_WARMUP_TIME) {
      sensorWarmedUp = true;
      Serial.println("Motion sensor warmup complete, detection active");
      Serial.print("Initial distance: ");
      Serial.print(lastDistance);
      Serial.println(" cm");
    } else {
      // During warmup, just read without triggering
      if (now - lastSensorRead > SENSOR_READ_INTERVAL) {
        float distance = measureDistance();
        if (distance >= MIN_DETECTION_DISTANCE && distance <= MAX_DETECTION_DISTANCE) {
          lastDistance = distance;
        }
        lastSensorRead = now;
      }
      return;
    }
  }
  
  if (now - lastSensorRead > SENSOR_READ_INTERVAL) {
    float distance = measureDistance();
    
    // Check if reading is valid
    bool validReading = (distance >= MIN_DETECTION_DISTANCE && distance <= MAX_DETECTION_DISTANCE);
    
    if (validReading) {
      bool someoneInPortal = (distance < DETECTION_RANGE);
      bool inCooldown = (now - lastPassageEndTime) < PASSAGE_COOLDOWN;
      
      if (!inPassage && !inCooldown && someoneInPortal) {
        // Someone just entered the portal - start passage
        Serial.print("PASSAGE STARTED! Distance: ");
        Serial.print(distance);
        Serial.println(" cm (someone in portal)");
        
        inPassage = true;
        passageStartTime = now;
        triggerRandomBlink(); // Use random selection (60% green, 40% red)
        
      } else if (inPassage) {
        unsigned long passageDuration = now - passageStartTime;
        
        if (!someoneInPortal) {
          // No one in portal anymore - check if we can end passage
          if (passageDuration >= MIN_PASSAGE_DURATION) {
            Serial.print("PASSAGE ENDED after ");
            Serial.print(passageDuration);
            Serial.print(" ms. Distance: ");
            Serial.print(distance);
            Serial.println(" cm (portal clear)");
            
            inPassage = false;
            lastPassageEndTime = now;
            
            // Return to ROTATING state - but ONLY if we're in GREEN state
            // RED state (2) must stay until manual API reset
            if (currentState == BLINK_GREEN) {
              currentState = ROTATING;
              autoTriggered = false;
              publishStateToMQTT();
              Serial.println("Returning to ROTATING state");
            } else if (currentState == BLINK_RED) {
              Serial.println("Staying in RED state (requires manual reset)");
            }
          } else {
            // Minimum duration not reached yet
            Serial.print("Maintaining state (min duration not reached: ");
            Serial.print(passageDuration);
            Serial.print("/");
            Serial.print(MIN_PASSAGE_DURATION);
            Serial.print(" ms, distance: ");
            Serial.print(distance);
            Serial.println(" cm)");
          }
        } else {
          // Someone still in portal - keep state active
          if ((passageDuration % 500) == 0) {  // Log every 500ms to avoid spam
            Serial.print("Person in portal (distance: ");
            Serial.print(distance);
            Serial.print(" cm, duration: ");
            Serial.print(passageDuration);
            Serial.println(" ms)");
          }
        }
      }
      
      lastDistance = distance;
      
    } else {
      // Invalid reading (out of range)
      if (inPassage) {
        unsigned long passageDuration = now - passageStartTime;
        
        if (passageDuration >= MIN_PASSAGE_DURATION) {
          Serial.print("PASSAGE ENDED (out of range) after ");
          Serial.print(passageDuration);
          Serial.print(" ms. Distance: ");
          Serial.print(distance);
          Serial.println(" cm");
          
          inPassage = false;
          lastPassageEndTime = now;
          
          // Return to ROTATING state - but ONLY if we're in GREEN state
          if (currentState == BLINK_GREEN) {
            currentState = ROTATING;
            autoTriggered = false;
            publishStateToMQTT();
            Serial.println("Returning to ROTATING state");
          } else if (currentState == BLINK_RED) {
            Serial.println("Staying in RED state (requires manual reset)");
          }
        }
      }
    }
    
    lastSensorRead = now;
  }
}

void setup() {
  Serial.begin(115200);
  delay(500); // Give serial port time to initialize
  
  Serial.println("\n\n=== RGB Portal Starting ===");
  
  // Initialize ultrasonic sensor pins
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  Serial.println("Ultrasonic sensor initialized");
  
  // Initialize FastLED
  FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setBrightness(50); // Set brightness (0-255)
  Serial.println("FastLED initialized");
  
  // Set initial state to ROTATING before any updates
  currentState = ROTATING;
  autoTriggered = false;
  blinkingDone = false;
  Serial.println("Initial state set to ROTATING");
  
  // Draw initial rotating effect
  drawRotatingEffect();
  Serial.println("Initial portal effect displayed");
  
  // Initialize motion sensor warmup
  sensorStartTime = millis();
  sensorWarmedUp = false;
  Serial.println("Motion sensor warmup started (3 seconds)...");
  
  // Connect to WiFi
  Serial.println("Connecting to WiFi...");
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\nWiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
  
  // Initialize random seed for random blink selection
  randomSeed(micros());
  
  // Setup OTA updates
  ArduinoOTA.setHostname("rgb_portal");
  
  ArduinoOTA.onStart([]() {
    String type;
    if (ArduinoOTA.getCommand() == U_FLASH) {
      type = "sketch";
    } else { // U_SPIFFS
      type = "filesystem";
    }
    Serial.println("Start updating " + type);
  });
  
  ArduinoOTA.onEnd([]() {
    Serial.println("\nEnd");
  });
  
  ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
    Serial.printf("Progress: %u%%\r", (progress / (total / 100)));
  });
  
  ArduinoOTA.onError([](ota_error_t error) {
    Serial.printf("Error[%u]: ", error);
    if (error == OTA_AUTH_ERROR) {
      Serial.println("Auth Failed");
    } else if (error == OTA_BEGIN_ERROR) {
      Serial.println("Begin Failed");
    } else if (error == OTA_CONNECT_ERROR) {
      Serial.println("Connect Failed");
    } else if (error == OTA_RECEIVE_ERROR) {
      Serial.println("Receive Failed");
    } else if (error == OTA_END_ERROR) {
      Serial.println("End Failed");
    }
  });
  
  ArduinoOTA.begin();
  Serial.println("OTA ready");
  
  // Setup MQTT
  mqttClient.setServer(mqtt_server, mqtt_port);
  Serial.print("MQTT server set to: ");
  Serial.print(mqtt_server);
  Serial.print(":");
  Serial.println(mqtt_port);
  reconnectMQTT();
  
  // REST API endpoints
  
  // GET /toggle - Toggle between ROTATING and BLINK_RED
  server.on("/toggle", handleToggle);
  
  // GET /red - Trigger red blink
  server.on("/red", handleRedBlink);
  
  // GET /green - Trigger green blink
  server.on("/green", handleGreenBlink);
  
  // GET /reset - Reset to ROTATING state
  server.on("/reset", handleReset);
  
  // GET /state - Get current state
  server.on("/state", handleState);
  
  // GET /distance - Get current ultrasonic sensor distance
  server.on("/distance", handleDistance);
  
  // GET / - Welcome page
  server.on("/", handleRoot);
  
  // Start server
  server.begin();
  Serial.println("HTTP server started!");
  
  // Extra status message (in case serial monitor started late)
  delay(1000);
  Serial.println("\n=== SYSTEM READY ===");
  Serial.print("Portal state: ROTATING (green)\n");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
  Serial.println("====================\n");
}

void loop() {
  // Handle OTA updates
  ArduinoOTA.handle();
  
  // Maintain WiFi connection
  if (WiFi.status() != WL_CONNECTED) {
    unsigned long now = millis();
    if (now - lastWiFiReconnectAttempt > WIFI_RECONNECT_INTERVAL) {
      lastWiFiReconnectAttempt = now;
      Serial.println("WiFi disconnected! Attempting to reconnect...");
      WiFi.reconnect();
    }
  }
  
  // Maintain MQTT connection (non-blocking)
  if (!mqttClient.connected()) {
    static unsigned long lastReconnectAttempt = 0;
    unsigned long now = millis();
    if (now - lastReconnectAttempt > 5000) { // Try reconnecting every 5 seconds
      lastReconnectAttempt = now;
      reconnectMQTT();
    }
  } else {
    mqttClient.loop();
  }
  
  server.handleClient();
  updateAnimations();
  checkMotionDetection();
}