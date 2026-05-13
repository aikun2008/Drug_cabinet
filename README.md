# Smart Drug Cabinet Management System

A comprehensive drug cabinet management system with IoT capabilities, featuring ESP32 + STM32 dual-controller architecture.

## Overview

This system provides intelligent drug management for laboratories and pharmacies, including remote monitoring, access control, and environmental monitoring.

## System Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| Web Backend | Flask + MySQL + Redis | Management platform |
| Mini Program | WeChat Mini Program | Mobile client for students/teachers |
| Gateway | ESP32-WROOM-32 | Network connectivity, MQTT, OTA |
| Controller | STM32F103C8T6 | Sensor data acquisition, actuator control |

## Key Features

- **Access Control**: RFID card authentication
- **Remote Monitoring**: Real-time temperature, humidity, and air quality
- **Drug Traceability**: Complete usage history and audit trail
- **OTA Updates**: Remote firmware updates for ESP32
- **Alarm System**: Environmental threshold alerts and unauthorized access detection

## Project Structure

```
Drug_cabinet/
├── Drug_cabinet_server/     # Flask backend
├── Drug_cabinet_MP/         # WeChat Mini Program
├── ESP32WROOM/              # ESP32 firmware (ESP-IDF)
└── drug/                    # STM32 firmware (HAL Library)
```

## Hardware Architecture

```
┌─────────────┐      UART       ┌─────────────┐
│   ESP32     │◄───────────────►│   STM32     │
│  (Network)  │    115200 baud  │  (Sensors)  │
└──────┬──────┘                 └──────┬──────┘
       │                               │
       ▼                               ▼
  ┌─────────┐                    ┌──────────┐
  │  MQTT   │                    │  RFID    │
  │  Broker │                    │  DHT11   │
  └─────────┘                    │  MQ135   │
                                 └──────────┘
```

## Communication Protocol

### MQTT Topics

| Topic | Direction | Description |
|-------|-----------|-------------|
| `/server/command/esp32` | Server → Device | Control commands |
| `/esp32/environment_data/server` | Device → Server | Environmental data |
| `/esp32/heartbeat/server` | Device → Server | Heartbeat (20s interval) |
| `/esp32/alarm_data/server` | Device → Server | Alarm notifications |

### UART Commands (ESP32 ↔ STM32)

| Command | Description |
|---------|-------------|
| `N` | Normal status |
| `Y` | Warning (yellow LED) |
| `R` | Alarm (red LED + buzzer) |
| `C` | MQTT connected |
| `D` | WiFi connected, MQTT disconnected |
| `O` | Offline |

## License

MIT License
