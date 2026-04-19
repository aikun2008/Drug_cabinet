#ifndef MQTT_LISTENER_H
#define MQTT_LISTENER_H

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_log.h"
#include "mqtt_client.h"
#include "cJSON.h"
#include "mbedtls/aes.h"
#include "mbedtls/sha256.h"
#include "mbedtls/base64.h"

// 导入统一配置文件
#include "config.h"

// MQTT主题宏 - 使用统一配置
#define MQTT_PUBLIC_TOPIC      MQTT_PUB_ENV_DATA
#define MQTT_PUBLIC_TOPIC_2    MQTT_PUB_DOOR_LOCK_DATA
#define MQTT_PUBLIC_TOPIC_3    MQTT_PUB_ENV_DATA_NOW
#define MQTT_PUBLIC_TOPIC_4    MQTT_PUB_RFID_DATA
#define MQTT_PUBLIC_TOPIC_5    MQTT_PUB_DOOR_LOCK_DATA_NOW
#define MQTT_PUBLIC_TOPIC_6    MQTT_PUB_MED_OP_DATA

// 外部声明全局变量
extern esp_mqtt_client_handle_t s_mqtt_client;
extern bool s_is_mqtt_connected;
extern char *s_session_id; // 会话ID

// 函数声明
void mqtt_listener_init(void);
void mqtt_start(void);
void mqtt_publish_rfid_data(void);
void mqtt_publish_medicine_operation(const char *rfid, const char *medicine_code);
void mqtt_publish_door_lock_data(int door, int lock, int timeout);
void mqtt_send_network_status(char status);

#endif // MQTT_LISTENER_H
