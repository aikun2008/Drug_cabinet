#ifndef CONFIG_H
#define CONFIG_H
/**
 * ESP32设备统一配置文件
 */
// ========================== 版本配置 ==========================
// 固件版本号
#define FIRMWARE_VERSION "2.1.6"
// ========================== MQTT配置 ==========================
// MQTT连接配置（请在编译前配置以下环境变量或使用menuconfig设置）
// #define MQTT_ADDRESS    "mqtt://YOUR_MQTT_SERVER"
#define MQTT_ADDRESS    "mqtt://8.134.109.28"
#define MQTT_PORT       1883              // MQTT端口
#define MQTT_CLIENT     "cabinet_002"     // MQTT客户端ID
#define MQTT_USERNAME   "YOUR_MQTT_USERNAME"  // MQTT用户名
#define MQTT_PASSWORD   "YOUR_MQTT_PASSWORD"  // MQTT密码

// ========================== MQTT主题配置 ==========================
// 订阅主题 - 接收来自服务器的命令
#define MQTT_SUBSCRIBE_TOPIC        "/server/command/esp32"
// 发布主题 - 环境数据
#define MQTT_PUB_ENV_DATA           "/esp32/environment_data/server"
// 发布主题 - 实时环境数据
#define MQTT_PUB_ENV_DATA_NOW       "/esp32/environment_data_now/server"
// 发布主题 - 门锁数据
#define MQTT_PUB_DOOR_LOCK_DATA     "/esp32/door_lock_data/server"
// 发布主题 - 实时门锁数据
#define MQTT_PUB_DOOR_LOCK_DATA_NOW "/esp32/door_lock_data_now/server"
// 发布主题 - RFID数据
#define MQTT_PUB_RFID_DATA          "/esp32/rfid_data/server"
// 发布主题 - 药品操作数据
#define MQTT_PUB_MED_OP_DATA        "/esp32/medicine_operation/server"
// 发布主题 - 报警数据（主动上报异常）
#define MQTT_PUB_ALARM_DATA         "/esp32/alarm_data/server"
// 发布主题 - 设备请求（阈值配置等）
#define MQTT_PUB_DEVICE_REQUEST     "/esp32/device_request/server"
// 发布主题 - 心跳数据
#define MQTT_PUB_HEARTBEAT          "/esp32/heartbeat/server"
// 心跳间隔（秒）
#define HEARTBEAT_INTERVAL_SECONDS  20
// ========================== GPIO配置 ==========================
// 锁控制GPIO（0为锁闭，1为解锁）
#define LOCK_GPIO       GPIO_NUM_2

// ========================== 系统配置 ==========================
// 默认控制模式：AT(自动)/MT(手动)
#define DEFAULT_CONTROL_MODE   AT

// 门锁超时时间（秒）
#define DOOR_LOCK_TIMEOUT      30

// ========================== 通信配置 ==========================
// UART波特率
#define UART_BAUD_RATE         115200

// ========================== 常量定义 ==========================
// 控制模式枚举
typedef enum {
    AT,  // 自动模式
    MT   // 手动模式
} ControlMode;

#endif // CONFIG_H
