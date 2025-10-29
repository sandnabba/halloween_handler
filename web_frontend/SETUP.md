# Halloween Controller - Web Frontend

Modern React + TypeScript web application with real-time WebSocket communication for controlling the Halloween automation system.

## Features

- 🎃 **Real-time Updates**: WebSocket connection for instant status synchronization
- 🎭 **Scenario Control**: Trigger Halloween scenarios manually
- 🔴 **Portal Control**: Direct control over ESP32 RGB portal (red/green/reset)
- ⏱️ **Cooldown Management**: Visual cooldown timer with reset capability
- 🔧 **Debug Panel**: ESP32 ping, MQTT message viewer, raw status data
- 📱 **Responsive Design**: Works on desktop, tablet, and mobile
- 🌙 **Dark Theme**: Halloween-themed dark UI

## Tech Stack

- React 19
- TypeScript
- Socket.IO Client
- Vite
- CSS3 (Grid/Flexbox)

## Setup

1. Install dependencies:
```bash
npm install
```

2. Configure backend URL:
```bash
cp .env.example .env
```

Edit `.env`:
```
VITE_BACKEND_URL=http://your-backend-ip:5000
```

3. Run development server:
```bash
npm run dev
```

4. Build for production:
```bash
npm run build
```

## Features Overview

### Main Controls
- **Trigger Scenario**: Manually start the Halloween light show
- **Reset Cooldown**: Clear the cooldown timer to allow immediate re-trigger

### Portal Controls
- **Red Blink**: Trigger alarm state (persists until manual reset)
- **Green Blink**: Trigger success state (auto-returns to rotating after 1.5s)
- **Reset Portal**: Return to normal rotating animation (blue→purple→pink)

### System Status Display
- Current system state (Ready/Running/Cooldown)
- Scenario running indicator
- Cooldown timer countdown
- Total trigger count
- Last person detection count

### Portal State Display
- Real-time portal state visualization
- Color-coded state indicator:
  - Purple: ROTATING (normal)
  - Red: BLINK_RED (alarm)
  - Green: BLINK_GREEN (success)
- Last state update timestamp

### Debug Panel
Expandable debug section with:
- **ESP32 Ping**: Test connectivity to the portal
- **Last MQTT Message**: View most recent MQTT data (topic, payload, timestamp)
- **System Info**: WebSocket status, backend URL, uptime
- **Raw Status**: Complete JSON dump of system status

## WebSocket Events

The app automatically connects to the backend WebSocket server and receives:

- `status_update`: Real-time system status updates
- `portal_ping_response`: ESP32 connectivity test results

## Environment Variables

- `VITE_BACKEND_URL`: Backend server URL (default: `http://localhost:5000`)

## Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Type checking
npm run build

# Lint code
npm run lint
```

## Responsive Breakpoints

- Desktop: > 768px
- Tablet: 481px - 768px
- Mobile: ≤ 480px

## Color Scheme

```css
--bg-dark: #1a1a1a           /* Main background */
--bg-card: #2a2a2a           /* Card background */
--accent-orange: #ff6600     /* Primary accent */
--accent-red: #ff0000        /* Red state */
--accent-green: #00ff00      /* Green state */
--accent-blue: #6b5b95       /* Rotating state */
```

## Browser Support

- Chrome/Edge: Last 2 versions
- Firefox: Last 2 versions
- Safari: Last 2 versions
