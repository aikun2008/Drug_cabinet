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

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      User Interaction Layer                  │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │   WeChat Mini App   │    │   Web Admin (HTML+Jinja2)   │ │
│  │  Student/Teacher    │    │        Admin Only           │ │
│  └─────────┬───────────┘    └──────────────┬──────────────┘ │
└────────────┼───────────────────────────────┼────────────────┘
             │ HTTP (REST API)               │ HTTP (Session)
             ▼                               ▼
┌────────────────────────────────────────────────────────────┐
│                    Flask Web Service Layer                  │
│  login.py · permission_manager.py · redis_manager.py       │
│  emqx_manager.py · alarm_handler.py · db_cache_sync.py    │
│  admin_*.py · teacher_*.py · student_*.py                  │
└────────┬───────────────────────────────┬──────────────────┘
         │                               │
         ▼                               ▼
┌─────────────────┐              ┌────────────────────────────┐
│   MySQL 8.0+    │              │  Redis (Cache)             │
│  (web + history)│              │  drug_cabinet:* keys       │
└─────────────────┘              └────────────────────────────┘
         │                               │
         └───────────────┬───────────────┘
                         │ MQTT (paho-mqtt)
                         ▼
┌────────────────────────────────────────────────────────────┐
│              EMQX Broker (8.134.109.28:1883)               │
│  /server/command/esp32   ← Server commands                │
│  /esp32/*/server         ← Device data                    │
└─────────────────────────────┬──────────────────────────────┘
                              │ MQTT
                              ▼
┌────────────────────────────────────────────────────────────┐
│                   ESP32-WROOM-32 (Gateway)                 │
│  WiFi + MQTT Client  ←→  UART (115200)  ←→  STM32F103     │
│  OTA Updates                                               │
└─────────────────────────────┬──────────────────────────────┘
                              │ UART TTL
                              ▼
┌────────────────────────────────────────────────────────────┐
│                 STM32F103C8T6 (Controller)                 │
│  FreeRTOS: DHT11_task / MQ135_task / RFID_task /          │
│            OLED_task / door_lock_task / buzzer_task        │
│  Hardware: DHT11 / MQ135 / Light Sensor / RFID-RC522 /    │
│            SG90 Servo / OLED 128x64 / LED / Buzzer        │
└────────────────────────────────────────────────────────────┘
```

## Role-Based Access Control

| Role | role Value | Permissions |
|------|------------|-------------|
| Admin | `0` | Device monitoring, drug management, user management, alarm handling, OTA upgrades |
| Teacher | `1` | Drug query, reservation/approval, borrow/return, student binding/unbinding |
| Student | `2` | Drug query, drug reservation, usage records |

Permission configurations are stored in the `permission_settings` table, supporting login time range restrictions (`login_time_range` format: `HH:MM-HH:MM`).

## Database Design

The system uses two MySQL databases:

- **`web`**: Business data (users, devices, drugs, operation logs)
- **`history`**: Environmental time-series data (one table per device)

### Core Tables

#### `web_user` — Users

| Field | Type | Description |
|-------|------|-------------|
| `id` | INT | Primary key |
| `username` | VARCHAR | Username |
| `password` | VARCHAR | Password (bcrypt) |
| `role` | TINYINT | 0=Admin, 1=Teacher, 2=Student |
| `real_name` | VARCHAR | Real name |
| `rfid_card_id` | VARCHAR | Bound RFID card number |
| `status` | TINYINT | Account status |
| `created_at` | DATETIME | Creation time |

#### `web_equipment` — Devices

| Field | Type | Description |
|-------|------|-------------|
| `id` | INT | Primary key |
| `equipment_id` | VARCHAR | Device ID (e.g., `cabinet_002`) |
| `equipment_name` | VARCHAR | Device name |
| `location` | VARCHAR | Installation location |
| `connection_status` | TINYINT | 0=Online, 1=Offline |
| `last_heartbeat` | DATETIME | Last heartbeat time |
| `firmware_version` | VARCHAR | Current firmware version |

#### `web_medicine_list` — Drug Catalog

| Field | Type | Description |
|-------|------|-------------|
| `id` | INT | Primary key |
| `medicine_code` | VARCHAR | Drug code (unique) |
| `name` | VARCHAR | Drug name |
| `type` | TINYINT | 0=Normal, 1=Controlled, 2=Hazardous |
| `specification` | VARCHAR | Specification |
| `status` | VARCHAR | `in_stock`/`lent_out`/`reserved`/`discarded` |
| `current_holder_id` | VARCHAR | Current holder (RFID) |
| `location` | VARCHAR | Storage location |
| `expiry_date` | DATE | Expiration date |

#### `medicine_trace` — Drug Operation Trace

| Field | Type | Description |
|-------|------|-------------|
| `id` | INT | Primary key |
| `equipment_id` | VARCHAR | Device ID |
| `rfid_card_id` | VARCHAR | Operator RFID |
| `medicine_code` | VARCHAR | Drug code |
| `operation_type` | VARCHAR | `borrow`/`return` |
| `operation_time` | DATETIME | Operation time |

## Backend Service (Drug_cabinet_server)

### Module Overview

```
Drug_cabinet_server/
├── main.py                       # Flask app entry, route initialization
├── config.py                     # Global config (MySQL/Redis/MQTT/JWT)
├── login.py                      # Authentication (session + JWT Bearer)
├── permission_manager.py         # Permission management decorators
├── emqx_manager.py               # MQTT client manager (~1590 lines)
├── redis_manager.py              # Redis cache manager
├── alarm_handler.py              # Alarm detection and handling
├── db_cache_sync.py              # Database-cache sync layer
├── requirements.txt              # Python dependencies
├── admin_*.py                    # Admin modules (10 files)
├── teacher_*.py                  # Teacher modules
├── student_*.py                  # Student modules
├── templates/                    # Jinja2 HTML templates
└── static/                       # CSS / JS / Image assets
```

### Core Modules

#### `login.py` — Authentication

| Function/Decorator | Description |
|-------------------|-------------|
| `generate_jwt_token(user_id, username, role)` | Generate HS256 JWT, valid for 24h |
| `verify_jwt_token(token)` | Verify and decode JWT, return payload or None |
| `login_required` | Decorator: Web session check, API/Mini Program Bearer token check |
| `init_login_routes(app)` | Register `/login` (Web), `/api/login` (JSON), `/logout` |

- **Account Lock**: 5 consecutive failed logins → lock for 30 minutes
- **Web Login**: Only role=0 (Admin)
- **Mini Program/API Login**: All roles allowed
- **Login Time Range**: Validated via `permission_manager.check_login_time()`

#### `emqx_manager.py` — MQTT Manager (~1590 lines)

`EMQXManager` class is the core of device communication:

| Method | Description |
|--------|-------------|
| `connect()` | Initialize paho-mqtt client, connect to EMQX |
| `publish(topic, payload)` | Publish message to topic |
| `subscribe(topic, qos)` | Subscribe to topic |
| `save_environment_data(data)` | Save environmental data to `history` DB |

**Message Processing Routes** (`_process_message_async`):

| Topic Suffix | Processing Logic |
|-------------|-----------------|
| `environment_data` | Check thresholds via `alarm_handler`, store in history DB |
| `rfid_data` | Validate RFID card, check user permissions, control door |
| `door_lock_data` | Update `web_equipment` lock status, handle timeout alarms |
| `medicine_operation` | Auto-determine borrow/return, write to `medicine_trace` |
| `ota_status` | Update device firmware version |
| `alarm_data` | Receive active alarms from ESP32 |

#### `alarm_handler.py` — Alarm Handling

| Constant/Function | Description |
|------------------|-------------|
| `CONSECUTIVE_ABNORMAL_THRESHOLD = 3` | 3 consecutive abnormalities trigger alarm |
| `ALARM_COOLDOWN_SECONDS = 300` | 5-minute alarm cooldown |
| `check_data_level(temp, humi, aqi, config)` | Three-level judgment: `normal`/`abnormal`/`critical` |

## WeChat Mini Program (Drug_cabinet_MP)

### Page Structure

```
Drug_cabinet_MP/
├── app.js / app.json / app.wxss    # Global entry
└── pages/
    ├── login/                       # Login page
    ├── index/                       # Home page (role-based features)
    ├── drugInfo/                    # Drug information query
    ├── drugRecords/                 # Usage records
    ├── profile/                     # Personal center
    ├── pendingDrugs/                # Pending drugs (Teacher)
    ├── applicationQuery/            # Application query (Student)
    └── approveApplication/          # Application approval (Teacher)
```

### Global Configuration (app.js)

```javascript
globalData: {
  isLoggedIn: false,
  userInfo: null,
  baseUrl: 'http://192.168.0.104:5000/api',
  roleConfig: {
    0: { name: 'Admin', color: '#ff6b6b', icon: 'admin' },
    1: { name: 'Teacher', color: '#4ecdc4', icon: 'teacher' },
    2: { name: 'Student', color: '#45b7d1', icon: 'student' }
  }
}
```

## ESP32 Firmware (ESP32WROOM)

### Module Structure

```
ESP32WROOM/main/
├── main.c                   # App entry, FreeRTOS tasks
├── config.h                 # Unified config (MQTT topics, GPIO, system params)
├── wifi_manager.c/h         # WiFi connection and reconnection
├── uart_manager.c/h         # UART DMA TX/RX
├── mqtt_listener.c/h        # MQTT event handling and message dispatch
├── action_functions.c/h     # Business actions (publish data, door lock)
├── mqtt_ota_handler.c/h     # OTA firmware upgrade
└── alarm_manager.c/h        # Alarm state machine
```

### Key Configuration (config.h)

| Config Item | Value | Description |
|------------|-------|-------------|
| `FIRMWARE_VERSION` | `"2.1.6"` | Firmware version |
| `MQTT_ADDRESS` | `mqtt://8.134.109.28` | EMQX server address |
| `MQTT_PORT` | `1883` | MQTT port |
| `MQTT_CLIENT` | `cabinet_002` | MQTT Client ID |
| `UART_BAUD_RATE` | `115200` | UART baud rate |
| `HEARTBEAT_INTERVAL_SECONDS` | `20` | Heartbeat interval |
| `DOOR_LOCK_TIMEOUT` | `30` seconds | Door lock timeout |

## STM32 Firmware (drug)

### Project Structure

```
drug/
├── Core/
│   ├── Src/
│   │   ├── main.c              # Entry, HAL init, FreeRTOS start
│   │   ├── freertos.c          # FreeRTOS task definitions
│   │   ├── gpio.c              # GPIO init (LED/buzzer/SG90)
│   │   ├── usart.c             # UART1 (ESP32 communication)
│   │   ├── adc.c               # ADC1 init (MQ135/Light Sensor)
│   │   └── tim.c               # Timer init (DHT11 software delay)
│   └── Inc/                    # HAL headers
├── Hardware/                   # Hardware driver layer
│   ├── dht11.c/h               # DHT11 driver
│   ├── mq135.c/h               # MQ135 air quality sensor
│   ├── rfid.c/h                # RFID-RC522 driver
│   ├── oled.c/h                # OLED 128x64 driver
│   ├── servo.c/h               # SG90 servo control
│   └── buzzer.c/h              # Buzzer control
└── Task/                       # FreeRTOS task layer
    ├── dht11_task.c/h          # Temperature/humidity acquisition
    ├── mq135_task.c/h          # MQ135 acquisition
    ├── rfid_task.c/h           # RFID detection
    ├── oled_task.c/h           # OLED display update
    └── buzzer_task.c/h         # Buzzer task
```

### GPIO Pin Assignment

| GPIO | Function | Description |
|------|----------|-------------|
| PA0 | ADC (MQ135) | Air quality sensor analog input |
| PA1 | ADC (Light) | Light sensor analog input |
| PA9 / PA10 | USART1 TX/RX | Communication with ESP32 (115200) |
| PB0 | DHT11 DATA | Temperature/humidity sensor data line |
| PB12-PB15 | SPI2 | RFID SPI interface |
| PA8 | Servo (SG90) | Servo PWM control |
| PB5-PB7 | LED (RGB) | Status indicator LEDs |

### FreeRTOS Task Configuration

| Task | Priority | Stack Size | Period/Trigger |
|------|----------|-----------|----------------|
| DHT11 Acquisition | Normal | 256 | 2s polling |
| MQ135 Acquisition | Normal | 256 | 5s polling |
| RFID Detection | High | 512 | Polling detection |
| OLED Display | Normal | 256 | 1s update |
| Door Lock Control | High | 256 | Event-driven |
| Buzzer | Normal | 128 | Event-driven |
| UART Communication | High | 512 | Interrupt/DMA driven |

## Dependencies and Configuration

### Python Dependencies (requirements.txt)

| Package | Version | Purpose |
|---------|---------|---------|
| flask | * | Web framework |
| pymysql | * | MySQL driver |
| paho-mqtt | 1.6.1 | MQTT client |
| bcrypt | * | Password hashing |
| redis | * | Redis client |
| PyJWT | * | JWT authentication |
| requests | * | HTTP requests |
| pandas | * | Data processing |
| openpyxl | * | Excel import/export |

### Frontend Dependencies (HTML Templates)

- **Bootstrap 5**: Responsive UI framework
- **Chart.js**: Environmental data trend charts
- **AdminLTE**: Admin dashboard template

### Middleware Version Requirements

| Component | Minimum Version | Recommended Version |
|-----------|----------------|---------------------|
| MySQL | 5.7+ | 8.0+ |
| Redis | 3.0+ | 6.x |
| EMQX | 5.0 | 5.x |
| Python | 3.7+ | 3.9/3.10 |

## Deployment

### Backend Service Startup

```bash
# Enter backend directory
cd Drug_cabinet_server

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # Linux/macOS

# Install dependencies (Tsinghua mirror)
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Start service
python main.py
```

Service listens on `http://0.0.0.0:5000`.

### WeChat Mini Program Development

1. Import `Drug_cabinet_MP` project using WeChat Developer Tools
2. Modify `baseUrl` in `app.js` to your backend service address
3. Check "Do not verify valid domain names" in "Details" → "Local Settings"
4. Compile and run

### ESP32 Firmware Flashing

```bash
cd ESP32WROOM
idf.py set-target esp32
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

### STM32 Firmware Flashing

Use STM32CubeProgrammer or Keil MDK to flash `drug.hex` via ST-Link.

### EMQX Configuration

1. Login to EMQX Dashboard (`http://8.134.109.28:18083`)
2. Go to "Integration" → "Webhook", create Webhook:
   - URL: `http://8.134.109.28:5000/api/emqx/webhook`
   - Events: `client.connected`, `client.disconnected`
3. Configure MQTT authentication (username/password)
4. Ensure firewall opens ports: 1883 (MQTT), 18083 (Dashboard)

### Database Initialization

1. Create `web` and `history` databases
2. Refer to DDL comments in `config.py` to create tables
3. Or execute `create_batch_import_record.sql` and `create_remote_operation_monitor.sql`

## API Endpoints

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/login` | None | Web login |
| POST | `/api/login` | None | API/Mini Program login |
| POST | `/logout` | Session | Logout |
| GET | `/api/check_token` | Bearer | Verify JWT |

### Admin APIs

| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/api/dashboard/stats` | admin | Dashboard statistics |
| GET | `/api/drugs` | admin | Drug list |
| POST | `/api/drugs` | admin | Add drug |
| GET | `/api/drugs/<id>` | admin | Drug details |
| PUT | `/api/drugs/<id>` | admin | Update drug |
| DELETE | `/api/drugs/<id>` | admin | Delete drug |
| GET | `/api/equipment` | admin | Equipment list |
| POST | `/api/equipment/<id>/ota` | admin | Initiate OTA upgrade |
| GET | `/api/alarm-log` | admin | Alarm logs |

### Teacher APIs

| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| POST | `/api/teacher/drugs/reserve` | teacher | Reserve drug |
| POST | `/api/teacher/drugs/cancel-reserve` | teacher | Cancel reservation |
| POST | `/api/teacher/drugs/borrow` | teacher | Borrow drug |
| POST | `/api/teacher/drugs/return` | teacher | Return drug |
| GET | `/api/teacher/drugs/pending` | teacher | Pending drugs |
| GET | `/api/teacher/drugs/borrow-return-records` | teacher | Borrow/return records |
| POST | `/api/teacher/drugs/approve-reserve` | teacher | Approve student reservation |

### Student APIs

| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/api/mini/student/drugs` | student | Drug list |
| POST | `/api/student/drugs/reserve` | student | Reserve drug |
| GET | `/api/student/drugs/records` | student | Usage records |

## Key Constants

| Constant | Value | File | Description |
|----------|-------|------|-------------|
| `HEARTBEAT_INTERVAL_SECONDS` | 20 | config.h | ESP32 heartbeat interval |
| `DOOR_LOCK_TIMEOUT` | 30 | config.h | Door lock timeout (seconds) |
| `CONSECUTIVE_ABNORMAL_THRESHOLD` | 3 | alarm_handler.py | Consecutive abnormalities to trigger alarm |
| `ALARM_COOLDOWN_SECONDS` | 300 | alarm_handler.py | Alarm cooldown period |
| `UART_BAUD_RATE` | 115200 | config.h | ESP32-STM32 communication rate |
| `JWT_EXPIRY_HOURS` | 24 | config.py | JWT validity period |
| `MAX_LOGIN_ATTEMPTS` | 5 | config.py | Maximum login attempts |
| `LOGIN_LOCKOUT_MINUTES` | 30 | config.py | Login lockout duration |
| `MQTT_PORT` | 1883 | config.h | MQTT port |

## Troubleshooting

| Issue | Possible Cause | Solution |
|-------|---------------|----------|
| Device offline | WiFi not connected / MQTT config error | Check `MQTT_ADDRESS` and credentials in config.h |
| Drug borrow/return failed | RFID card not bound / insufficient permissions | Check `web_user.rfid_card_id` and `permission_settings` |
| Environmental data not updating | ESP32 not receiving UART data | Check UART connection and baud rate (115200) |
| Redis connection failed | Redis service not running | Start Redis service, code auto-fallback to MockCacheManager |
| OTA upgrade failed | Firmware URL inaccessible / missing otadata partition | Check URL accessibility, configure