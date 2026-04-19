#include "action_functions.h"
#include "mqtt_listener.h"
#include "uart_manager.h"
#include "esp_log.h"
#include "cJSON.h"
#include "time.h"
#include "driver/gpio.h"
#include "mqtt_ota_handler.h"
#include "esp_timer.h"
#include "alarm_manager.h"
#include <string.h>

// 日志标签定义
#define TAG     "action"

// 定义并初始化全局变量
ControlMode control_model = DEFAULT_CONTROL_MODE;  // 默认自动模式

// 远程操作状态管理
static bool g_remote_operation_active = false;      // 远程操作是否激活（远程开锁后一直禁用RFID，直到远程上锁）
static char g_remote_operation_type[16] = {0};      // 远程操作类型

// 外部声明
extern uart_manager_t g_uart_manager;
extern char *s_session_id; // 会话ID

// GPIO初始化函数
void lock_gpio_init(void) {
    // 配置GPIO为输出模式
    gpio_config_t io_conf = {
        .mode = GPIO_MODE_OUTPUT,
        .pin_bit_mask = (1ULL << LOCK_GPIO),
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    gpio_config(&io_conf);
    
    // 初始状态：锁闭（高电平或低电平，根据实际硬件连接调整）
    gpio_set_level(LOCK_GPIO, 0); // 正确初始状态：0为锁闭，1为解锁
}

/**
 * @brief 处理MQTT命令消息
 * @param payload 消息负载
 * @param payload_len 消息长度
 * @return 无
 */
void handle_mqtt_command(const char *payload, int payload_len) {
    cJSON *root = cJSON_ParseWithLength(payload, payload_len);
    if (root != NULL) {
        // 1. 检查设备ID是否匹配
        cJSON *equipment_id = cJSON_GetObjectItemCaseSensitive(root, "equipment_id");
        if (!equipment_id || !cJSON_IsString(equipment_id)) {
                cJSON_Delete(root);
                return;
            }
            
            // 检查设备ID是否与本机ID匹配（MQTT_CLIENT宏定义）
            if (strcmp(equipment_id->valuestring, MQTT_CLIENT) != 0) {
                cJSON_Delete(root);
                return;
            }
            
            // 2. 处理查询命令
            cJSON *query = cJSON_GetObjectItemCaseSensitive(root, "query");
            if (query && cJSON_IsString(query)) {
            
            // 查询环境数据
            if (strcmp(query->valuestring, "environment_data") == 0) {
                publish_environment_data();
            }
            // 查询门锁数据
            else if (strcmp(query->valuestring, "door_lock_data") == 0) {
                publish_door_lock_data();
            }
            // 查询实时环境数据
            else if (strcmp(query->valuestring, "environment_data_now") == 0) {
                // 先发送环境数据到 /esp32/environment_data_now/server
                publish_environment_data_now();
            }
            // 查询实时门锁数据
            else if (strcmp(query->valuestring, "door_lock_data_now") == 0) {
                publish_door_lock_data_realtime();
            }
            // 查询版本号
            else if (strcmp(query->valuestring, "version") == 0) {
                publish_version_info();
            }
            // 阈值配置响应（支持两种格式：直接包含阈值字段或嵌套在config中）
            else if (strcmp(query->valuestring, "threshold_config") == 0) {
                // 服务器返回阈值配置，直接解析整个JSON
                char *config_str = cJSON_PrintUnformatted(root);
                if (config_str) {
                    parse_threshold_config(config_str);
                    free(config_str);
                }
            }
        }
        
        // 3. 处理控制命令
        cJSON *command = cJSON_GetObjectItemCaseSensitive(root, "command");
        if (command && cJSON_IsString(command)) {
            // 提取会话ID
            cJSON *session_id = cJSON_GetObjectItemCaseSensitive(root, "session_id");
            if (session_id && cJSON_IsString(session_id)) {
                // 保存会话ID到全局变量
                if (s_session_id) {
                    free(s_session_id);
                }
                s_session_id = strdup(session_id->valuestring);
            }
            
            // 提取控制模式
            cJSON *enum_field = cJSON_GetObjectItemCaseSensitive(root, "enum");
            if (enum_field && cJSON_IsString(enum_field)) {
                if (strcmp(enum_field->valuestring, "AT") == 0) {
                    control_model = AT;
                } else if (strcmp(enum_field->valuestring, "MT") == 0) {
                    control_model = MT;
                }
            }
            
            // 处理开锁指令
            if (strcmp(command->valuestring, "open_door") == 0) {
                // 开锁逻辑：控制GPIO输出高电平（0为锁闭，1为解锁）
                gpio_set_level(LOCK_GPIO, 1);
                // 不需要立即发布状态，等待传感器实际状态报告，避免重复消息
            }
            // 处理关锁指令
            else if (strcmp(command->valuestring, "close_door_lock") == 0) {
                // 关锁逻辑：控制GPIO输出低电平（0为锁闭，1为解锁）
                gpio_set_level(LOCK_GPIO, 0);
                // 不需要立即发布状态，等待传感器实际状态报告，避免重复消息
            }
            // 处理远程开锁指令
            else if (strcmp(command->valuestring, "remote_unlock") == 0) {
                // 激活远程操作状态（禁用本地刷卡，直到远程上锁）
                g_remote_operation_active = true;
                strncpy(g_remote_operation_type, "unlock", sizeof(g_remote_operation_type) - 1);

                // 远程开锁：控制GPIO输出高电平（1为解锁）
                gpio_set_level(LOCK_GPIO, 1);
                ESP_LOGI(TAG, "========================================");
                ESP_LOGI(TAG, "Remote unlock command received!");
                ESP_LOGI(TAG, "Equipment: %s", equipment_id->valuestring);
                ESP_LOGI(TAG, "Local RFID DISABLED until remote lock");
                ESP_LOGI(TAG, "========================================");

                // 发送确认消息到服务器（包含远程操作标记）
                publish_remote_operation_ack("remote_unlock", equipment_id->valuestring);
            }
            // 处理远程上锁指令
            else if (strcmp(command->valuestring, "remote_lock") == 0) {
                // 远程上锁：控制GPIO输出低电平（0为锁闭）
                gpio_set_level(LOCK_GPIO, 0);

                // 清除远程操作状态，恢复本地RFID
                g_remote_operation_active = false;
                memset(g_remote_operation_type, 0, sizeof(g_remote_operation_type));

                ESP_LOGI(TAG, "========================================");
                ESP_LOGI(TAG, "Remote lock command received!");
                ESP_LOGI(TAG, "Equipment: %s", equipment_id->valuestring);
                ESP_LOGI(TAG, "Local RFID ENABLED");
                ESP_LOGI(TAG, "========================================");

                // 发送确认消息到服务器
                publish_remote_operation_ack("remote_lock", equipment_id->valuestring);
            }
            // 处理报警已处理通知
            else if (strcmp(command->valuestring, "alarm_handled") == 0) {
                // 服务器通知报警已处理，重置报警计数
                extern void reset_alarm_count(void);
                reset_alarm_count();
                ESP_LOGI(TAG, "========================================");
                ESP_LOGI(TAG, "Alarm handled notification received!");
                ESP_LOGI(TAG, "Equipment: %s", equipment_id->valuestring);
                ESP_LOGI(TAG, "========================================");
            }
            // 处理MQTT OTA升级指令
            else if (strcmp(command->valuestring, "mqtt_ota_start") == 0) {
                // 处理MQTT OTA开始命令
                char *json_str = cJSON_PrintUnformatted(root);
                if (json_str) {
                    mqtt_ota_handle_command("mqtt_ota_start", json_str);
                    free(json_str);
                }
            }
            // 处理MQTT OTA取消指令
            else if (strcmp(command->valuestring, "mqtt_ota_cancel") == 0) {
                mqtt_ota_handle_command("mqtt_ota_cancel", "{}");
            }
        }
        
        // 4. 处理健康状态消息
        cJSON *health_status = cJSON_GetObjectItemCaseSensitive(root, "health_status");
        if (health_status && cJSON_IsNumber(health_status)) {
            int status = health_status->valueint;
            char command = 'N'; // 默认正常
            
            switch (status) {
                case 1: // 异常
                    command = 'Y'; // 黄色闪烁
                    break;
                case 2: // 报警
                    command = 'R'; // 红色闪烁
                    break;
                default: // 正常
                    command = 'N'; // 无操作
                    break;
            }
            
            // 发送单字符命令到STM32
            uart_write_bytes(USER_UART_NUM, &command, 1);
            //ESP_LOGI(TAG, "Sent health status command to STM32: %c", command);
        }
        
        cJSON_Delete(root);
    }
}

/**
 * @brief 发布环境数据到MQTT主题
 * @return 无
 */
void publish_environment_data(void) {
    char json_str[128];
    float temp = 0.0f;
    float humi = 0.0f;
    int aqi = 0;
    
    // 从缓存中获取环境数据
    if (g_uart_manager.s_env_json != NULL) {
        cJSON *temp_item = cJSON_GetObjectItemCaseSensitive(g_uart_manager.s_env_json, "temp");
        cJSON *humi_item = cJSON_GetObjectItemCaseSensitive(g_uart_manager.s_env_json, "humi");
        cJSON *aqi_item = cJSON_GetObjectItemCaseSensitive(g_uart_manager.s_env_json, "AQI");
        
        if (temp_item && cJSON_IsNumber(temp_item)) {
            temp = temp_item->valuedouble;
        }
        if (humi_item && cJSON_IsNumber(humi_item)) {
            humi = humi_item->valuedouble;
        }
        if (aqi_item && cJSON_IsNumber(aqi_item)) {
            aqi = aqi_item->valueint;
        }
    }
    
    // 使用静态字符串格式化，避免动态内存分配
    snprintf(json_str, sizeof(json_str), "{\"equipment_id\":\"%s\",\"temp\":%.1f,\"humi\":%.1f,\"AQI\":%d}", 
             MQTT_CLIENT, temp, humi, aqi);
    
    esp_mqtt_client_publish(s_mqtt_client, MQTT_PUBLIC_TOPIC, json_str, strlen(json_str), 1, 0);
}

/**
 * @brief 发布实时环境数据到MQTT主题
 * @return 无
 */
void publish_environment_data_now(void) {
    char json_str[150];
    char time_str[20];
    float temp = 0.0f;
    float humi = 0.0f;
    int aqi = 0;
    
    // 获取当前时间
    time_t now;
    struct tm timeinfo;
    time(&now);
    localtime_r(&now, &timeinfo);
    strftime(time_str, sizeof(time_str), "%Y/%m/%d %H:%M:%S", &timeinfo);
    
    // 从缓存中获取环境数据
    if (g_uart_manager.s_env_json != NULL) {
        cJSON *temp_item = cJSON_GetObjectItemCaseSensitive(g_uart_manager.s_env_json, "temp");
        cJSON *humi_item = cJSON_GetObjectItemCaseSensitive(g_uart_manager.s_env_json, "humi");
        cJSON *aqi_item = cJSON_GetObjectItemCaseSensitive(g_uart_manager.s_env_json, "AQI");
        
        if (temp_item && cJSON_IsNumber(temp_item)) {
            temp = temp_item->valuedouble;
        }
        if (humi_item && cJSON_IsNumber(humi_item)) {
            humi = humi_item->valuedouble;
        }
        if (aqi_item && cJSON_IsNumber(aqi_item)) {
            aqi = aqi_item->valueint;
        }
    }
    
    // 使用静态字符串格式化，避免动态内存分配
    snprintf(json_str, sizeof(json_str), "{\"time\":\"%s\",\"equipment_id\":\"%s\",\"temp\":%.1f,\"humi\":%.1f,\"AQI\":%d}", 
             time_str, MQTT_CLIENT, temp, humi, aqi);
    
    esp_mqtt_client_publish(s_mqtt_client, MQTT_PUBLIC_TOPIC_3, json_str, strlen(json_str), 1, 0);
}

/**
 * @brief 发布门锁数据
 * @return 无
 */
void publish_door_lock_data(void) {
    char json_str[128];
    int door = 0;
    int lock = 0;
    
    // 从缓存中获取门锁状态数据
    if (g_uart_manager.s_door_lock_json != NULL) {
        cJSON *door_item = cJSON_GetObjectItemCaseSensitive(g_uart_manager.s_door_lock_json, "Door");
        cJSON *lock_item = cJSON_GetObjectItemCaseSensitive(g_uart_manager.s_door_lock_json, "Lock");
        
        if (door_item && cJSON_IsNumber(door_item)) {
            door = door_item->valueint;
        }
        if (lock_item && cJSON_IsNumber(lock_item)) {
            lock = lock_item->valueint;
        }
    }
    
    // 实时计算门打开的持续时间
    extern uart_manager_t g_uart_manager;
    int real_timeout = g_uart_manager.door_open_duration;
    
    // 如果门是打开状态，重新计算持续时间
    if (door == 1 && g_uart_manager.is_door_open) {
        uint64_t current_time_ms = esp_timer_get_time() / 1000;
        uint32_t current_time_s = current_time_ms / 1000;
        real_timeout = current_time_s - g_uart_manager.door_open_start_time;
    }
    
    // 使用静态字符串格式化，避免动态内存分配
    snprintf(json_str, sizeof(json_str), "{\"equipment_id\":\"%s\",\"door\":%d,\"lock\":%d,\"timeout\":%d}", 
             MQTT_CLIENT, door, lock, real_timeout);
    
    esp_mqtt_client_publish(s_mqtt_client, MQTT_PUBLIC_TOPIC_2, json_str, strlen(json_str), 1, 0);
}

/**
 * @brief 发布实时门锁数据到MQTT主题
 * @return 无
 */
void publish_door_lock_data_realtime(void) {
    char json_str[150];
    char time_str[20];
    int door = 0;
    int lock = 0;
    
    // 获取当前时间
    time_t now;
    struct tm timeinfo;
    time(&now);
    localtime_r(&now, &timeinfo);
    strftime(time_str, sizeof(time_str), "%Y/%m/%d %H:%M:%S", &timeinfo);
    
    // 从缓存中获取门锁状态数据
    if (g_uart_manager.s_door_lock_json != NULL) {
        cJSON *door_item = cJSON_GetObjectItemCaseSensitive(g_uart_manager.s_door_lock_json, "Door");
        cJSON *lock_item = cJSON_GetObjectItemCaseSensitive(g_uart_manager.s_door_lock_json, "Lock");
        
        if (door_item && cJSON_IsNumber(door_item)) {
            door = door_item->valueint;
        }
        if (lock_item && cJSON_IsNumber(lock_item)) {
            lock = lock_item->valueint;
        }
    }
    
    // 使用静态字符串格式化，避免动态内存分配
    snprintf(json_str, sizeof(json_str), "{\"time\":\"%s\",\"equipment_id\":\"%s\",\"door\":%d,\"lock\":%d,\"buzzer\":0}", 
             time_str, MQTT_CLIENT, door, lock);
    
    esp_mqtt_client_publish(s_mqtt_client, MQTT_PUBLIC_TOPIC_5, json_str, strlen(json_str), 1, 0);
}

/**
 * @brief 发布药品操作数据
 * @param rfid RFID卡号
 * @param medicine_code 药品代码
 * @return 无
 */
void publish_medicine_operation(const char *rfid, const char *medicine_code) {
    // 使用新的MQTT发布函数，该函数支持会话ID
    mqtt_publish_medicine_operation(rfid, medicine_code);
}

/**
 * @brief 发布设备版本信息
 * @return 无
 */
void publish_version_info(void) {
    char json_str[128];
    
    // 使用静态字符串格式化，避免动态内存分配
    snprintf(json_str, sizeof(json_str), "{\"equipment_id\":\"%s\",\"version\":\"%s\"}", 
             MQTT_CLIENT, FIRMWARE_VERSION);
    
    // 发布到环境数据主题
    if (s_mqtt_client != NULL) {
        esp_mqtt_client_publish(s_mqtt_client, MQTT_PUB_ENV_DATA, json_str, strlen(json_str), 1, 0);
    }
}

/**
 * @brief 发布远程操作确认消息到MQTT
 * @param operation_type 操作类型：remote_unlock 或 remote_lock
 * @param equipment_id 设备ID
 * @return 无
 */
void publish_remote_operation_ack(const char *operation_type, const char *equipment_id) {
    if (s_mqtt_client == NULL) return;
    
    char json_str[256];
    char time_str[20];
    
    // 获取当前时间
    time_t now;
    struct tm timeinfo;
    time(&now);
    localtime_r(&now, &timeinfo);
    strftime(time_str, sizeof(time_str), "%Y/%m/%d %H:%M:%S", &timeinfo);
    
    // 获取当前门锁状态
    int door = 0;
    int lock = 0;
    if (g_uart_manager.s_door_lock_json != NULL) {
        cJSON *door_item = cJSON_GetObjectItemCaseSensitive(g_uart_manager.s_door_lock_json, "Door");
        cJSON *lock_item = cJSON_GetObjectItemCaseSensitive(g_uart_manager.s_door_lock_json, "Lock");
        if (door_item && cJSON_IsNumber(door_item)) door = door_item->valueint;
        if (lock_item && cJSON_IsNumber(lock_item)) lock = lock_item->valueint;
    }
    
    // 构建确认消息
    snprintf(json_str, sizeof(json_str), 
             "{\"time\":\"%s\",\"equipment_id\":\"%s\",\"command\":\"%s\",\"door\":%d,\"lock\":%d,\"remote_operation\":true}",
             time_str, equipment_id, operation_type, door, lock);
    
    esp_mqtt_client_publish(s_mqtt_client, MQTT_PUBLIC_TOPIC_2, json_str, strlen(json_str), 1, 0);
    ESP_LOGI(TAG, "Remote operation ACK published: %s", operation_type);
}

/**
 * @brief 检查是否允许本地RFID操作
 * @return true - 允许；false - 禁止（远程操作激活中）
 */
bool is_local_rfid_allowed(void) {
    if (!g_remote_operation_active) {
        return true;  // 没有激活的远程操作，允许本地RFID
    }

    // 远程操作激活中（远程开锁后未上锁），禁止本地RFID
    ESP_LOGW(TAG, "Local RFID blocked: remote unlock active, waiting for remote lock");
    return false;
}

/**
 * @brief 检查远程操作是否激活
 * @return true - 远程操作激活中；false - 未激活
 */
bool is_remote_operation_active(void) {
    return g_remote_operation_active;
}
