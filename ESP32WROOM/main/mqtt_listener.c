#include "mqtt_listener.h"
#include "esp_log.h"
#include "action_functions.h"
#include "uart_manager.h"
#include "alarm_manager.h"
#include "mqtt_ota_handler.h"
#include <time.h>

// 全局变量定义
esp_mqtt_client_handle_t s_mqtt_client = NULL;
bool s_is_mqtt_connected = false;
char *s_session_id = NULL; // 会话ID，初始化为NULL
static bool s_alarm_manager_initialized = false;  // 报警管理器是否已初始化
static TaskHandle_t s_heartbeat_task_handle = NULL;  // 心跳任务句柄

// 函数前向声明
static void heartbeat_task(void *pvParameters);

// 外部声明
extern uart_manager_t g_uart_manager;
/**
 * @brief MQTT事件处理函数
 * @param event_handler_arg 事件处理参数
 * @param event_base 事件基础
 * @param event_id 事件ID
 * @param event_data 事件数据
 * @return 无
 */
static void aliot_mqtt_event_handler(void* event_handler_arg,
                                        esp_event_base_t event_base,
                                        int32_t event_id,
                                        void* event_data) {
    esp_mqtt_event_handle_t event = event_data;

    switch ((esp_mqtt_event_id_t)event_id) {
        case MQTT_EVENT_CONNECTED:  //连接成功
            s_is_mqtt_connected = true;
            esp_mqtt_client_subscribe_single(s_mqtt_client, MQTT_SUBSCRIBE_TOPIC, 1);
            
            // 订阅 MQTT OTA 相关主题
            char ota_command_topic[64];
            char ota_data_topic[64];
            snprintf(ota_command_topic, sizeof(ota_command_topic), "/server/ota/command/%s", MQTT_CLIENT);
            snprintf(ota_data_topic, sizeof(ota_data_topic), "/server/ota/data/%s", MQTT_CLIENT);
            esp_mqtt_client_subscribe_single(s_mqtt_client, ota_command_topic, 1);
            esp_mqtt_client_subscribe_single(s_mqtt_client, ota_data_topic, 1);
            ESP_LOGI("mqtt", "Subscribed to OTA topics: %s, %s", ota_command_topic, ota_data_topic);
            
            // 如果 OTA 正在进行，重新请求当前包（断线重连恢复）
            if (mqtt_ota_is_in_progress()) {
                ESP_LOGI("mqtt", "MQTT reconnected during OTA, resuming...");
                mqtt_ota_resume();
            }
            
            // 只在首次连接时初始化报警管理器
            if (!s_alarm_manager_initialized) {
                alarm_manager_init();
                s_alarm_manager_initialized = true;
            }
            
            // 启动心跳任务（如果还没有启动）
            if (s_heartbeat_task_handle == NULL) {
                xTaskCreate(heartbeat_task, "heartbeat", 2048, NULL, 5, &s_heartbeat_task_handle);
            }
            
            // 延迟一下确保订阅完成
            vTaskDelay(pdMS_TO_TICKS(500));
            request_threshold_config();
            break;
        case MQTT_EVENT_DISCONNECTED:   //连接断开
            s_is_mqtt_connected = false;
            break;
        case MQTT_EVENT_SUBSCRIBED:     //收到订阅消息ACK
            break;
        case MQTT_EVENT_UNSUBSCRIBED:   //收到解订阅消息ACK
            break;
        case MQTT_EVENT_PUBLISHED:      //收到发布消息ACK
            break;
        case MQTT_EVENT_DATA: {
            // 处理合并后的主题命令
            size_t subscribe_topic_len = strlen(MQTT_SUBSCRIBE_TOPIC);
            if (event->topic_len == subscribe_topic_len && strncmp(event->topic, MQTT_SUBSCRIBE_TOPIC, subscribe_topic_len) == 0) {
                // 调用统一的消息处理函数
                handle_mqtt_command(event->data, event->data_len);
            }
            
            // 处理 MQTT OTA 命令主题
            char ota_command_topic[64];
            snprintf(ota_command_topic, sizeof(ota_command_topic), "/server/ota/command/%s", MQTT_CLIENT);
            size_t ota_command_topic_len = strlen(ota_command_topic);
            if (event->topic_len == ota_command_topic_len && strncmp(event->topic, ota_command_topic, ota_command_topic_len) == 0) {
                // 限制最大数据长度，防止内存溢出（命令通常很小）
                if (event->data_len > 2048) {
                    ESP_LOGE("mqtt", "OTA command data too large: %d bytes", event->data_len);
                } else {
                    // 确保数据以 null 结尾
                    char *data_copy = malloc(event->data_len + 1);
                    if (data_copy) {
                        memcpy(data_copy, event->data, event->data_len);
                        data_copy[event->data_len] = '\0';
                        ESP_LOGI("mqtt", ">>> Received OTA command on topic %s: %s", ota_command_topic, data_copy);
                        
                        // 解析 JSON 命令
                        cJSON *root = cJSON_Parse(data_copy);
                        if (root) {
                            cJSON *command_item = cJSON_GetObjectItem(root, "command");
                            if (command_item && cJSON_IsString(command_item)) {
                                ESP_LOGI("mqtt", ">>> Executing OTA command: %s", command_item->valuestring);
                                mqtt_ota_handle_command(command_item->valuestring, data_copy);
                            } else {
                                ESP_LOGE("mqtt", "Missing or invalid command field in JSON");
                            }
                            cJSON_Delete(root);
                        } else {
                            ESP_LOGE("mqtt", "Failed to parse OTA command JSON");
                        }
                        free(data_copy);
                    } else {
                        ESP_LOGE("mqtt", "Failed to allocate memory for OTA command");
                    }
                }
            }
            
            // 处理 MQTT OTA 数据主题
            char ota_data_topic[64];
            snprintf(ota_data_topic, sizeof(ota_data_topic), "/server/ota/data/%s", MQTT_CLIENT);
            size_t ota_data_topic_len = strlen(ota_data_topic);
            if (event->topic_len == ota_data_topic_len && strncmp(event->topic, ota_data_topic, ota_data_topic_len) == 0) {
                ESP_LOGI("mqtt", ">>> OTA data event: data_len=%d", event->data_len);
                
                // 限制最大数据长度，防止内存溢出（数据包通常小于 2KB）
                if (event->data_len > 4096) {
                    ESP_LOGE("mqtt", "OTA data too large: %d bytes", event->data_len);
                } else {
                    // 确保数据以 null 结尾
                    char *data_copy = malloc(event->data_len + 1);
                    if (data_copy) {
                        memcpy(data_copy, event->data, event->data_len);
                        data_copy[event->data_len] = '\0';
                        mqtt_ota_handle_data(data_copy);
                        free(data_copy);
                    } else {
                        ESP_LOGE("mqtt", "Failed to allocate memory for OTA data");
                    }
                }
            }
            break;
        }
        case MQTT_EVENT_ERROR:
            break;
        default:
            break;
    }
}

/**
 * @brief 启动MQTT连接
 * @return 无
 */
void mqtt_start(void) {
    esp_mqtt_client_config_t mqtt_cfg = {0};
    mqtt_cfg.broker.address.uri = MQTT_ADDRESS;
    mqtt_cfg.broker.address.port = MQTT_PORT;
    mqtt_cfg.credentials.client_id = MQTT_CLIENT;
    mqtt_cfg.credentials.username = MQTT_USERNAME;
    mqtt_cfg.credentials.authentication.password = MQTT_PASSWORD;
    mqtt_cfg.session.keepalive = HEARTBEAT_INTERVAL_SECONDS;  // 设置MQTT心跳间隔为20秒
    
    s_mqtt_client = esp_mqtt_client_init(&mqtt_cfg);
    esp_mqtt_client_register_event(s_mqtt_client, ESP_EVENT_ANY_ID, aliot_mqtt_event_handler, s_mqtt_client);
    esp_mqtt_client_start(s_mqtt_client);
}

/**
 * @brief 发布RFID数据
 * @return 无
 */
void mqtt_publish_rfid_data(void) {
    if (!s_is_mqtt_connected) {
        return;
    }
    
    if (s_mqtt_client == NULL) {
        return;
    }
    
    if (g_uart_manager.s_rfid_json == NULL) {
        return;
    }
    
    // 从缓存中获取RFID数据
    cJSON *cardid = cJSON_GetObjectItemCaseSensitive(g_uart_manager.s_rfid_json, "cardid");
    if (!cardid || !cJSON_IsString(cardid)) {
        return;
    }
    
    char json_str[256];
    int len;
    
    // 使用静态字符串格式化，避免动态内存分配
    if (s_session_id) {
        len = snprintf(json_str, sizeof(json_str), "{\"session_id\":\"%s\",\"equipment_id\":\"%s\",\"rfid\":\"%s\"}", 
                      s_session_id, MQTT_CLIENT, cardid->valuestring);
    } else {
        len = snprintf(json_str, sizeof(json_str), "{\"equipment_id\":\"%s\",\"rfid\":\"%s\"}", 
                      MQTT_CLIENT, cardid->valuestring);
    }
    
    if (len > 0 && len < sizeof(json_str)) {
        esp_mqtt_client_publish(s_mqtt_client, MQTT_PUBLIC_TOPIC_4, json_str, len, 1, 0);
    }
}

/**
 * @brief 发布药品操作数据
 * @param rfid RFID卡号
 * @param medicine_code 药品代码
 * @return 无
 */
void mqtt_publish_medicine_operation(const char *rfid, const char *medicine_code) {
    if (s_is_mqtt_connected && s_mqtt_client != NULL) {
        char json_str[256];
        int len;
        
        // 使用静态字符串格式化，避免动态内存分配
        if (s_session_id) {
            len = snprintf(json_str, sizeof(json_str), "{\"session_id\":\"%s\",\"equipment_id\":\"%s\",\"rfid\":\"%s\",\"medicine_code\":\"%s\"}", 
                          s_session_id, MQTT_CLIENT, rfid, medicine_code);
        } else {
            len = snprintf(json_str, sizeof(json_str), "{\"equipment_id\":\"%s\",\"rfid\":\"%s\",\"medicine_code\":\"%s\"}", 
                          MQTT_CLIENT, rfid, medicine_code);
        }
        
        if (len > 0 && len < sizeof(json_str)) {
            esp_mqtt_client_publish(s_mqtt_client, MQTT_PUBLIC_TOPIC_6, json_str, len, 1, 0);
        }
    }
}

/**
 * @brief 发布门锁数据
 * @param door 门状态（0-关闭，1-开启）
 * @param lock 锁状态（0-锁定，1-解锁）
 * @param timeout 超时时间
 * @return 无
 */
void mqtt_publish_door_lock_data(int door, int lock, int timeout) {
    if (s_is_mqtt_connected && s_mqtt_client != NULL) {
        char json_str[256];
        int len;
        
        // 使用静态字符串格式化，避免动态内存分配
        if (s_session_id) {
            len = snprintf(json_str, sizeof(json_str), "{\"session_id\":\"%s\",\"equipment_id\":\"%s\",\"door\":%d,\"lock\":%d,\"timeout\":%d}", 
                          s_session_id, MQTT_CLIENT, door, lock, timeout);
        } else {
            len = snprintf(json_str, sizeof(json_str), "{\"equipment_id\":\"%s\",\"door\":%d,\"lock\":%d,\"timeout\":%d}", 
                          MQTT_CLIENT, door, lock, timeout);
        }
        
        if (len > 0 && len < sizeof(json_str)) {
            esp_mqtt_client_publish(s_mqtt_client, MQTT_PUBLIC_TOPIC_2, json_str, len, 1, 0);
        }
    }
}

/**
 * @brief 发送心跳数据到服务器
 * @return 无
 */
void mqtt_publish_heartbeat(void) {
    if (s_is_mqtt_connected && s_mqtt_client != NULL) {
        char json_str[128];
        int len;
        
        len = snprintf(json_str, sizeof(json_str), 
                      "{\"equipment_id\":\"%s\",\"timestamp\":%lld}", 
                      MQTT_CLIENT, (long long)time(NULL));
        
        if (len > 0 && len < sizeof(json_str)) {
            esp_mqtt_client_publish(s_mqtt_client, MQTT_PUB_HEARTBEAT, json_str, len, 1, 0);
        }
    }
}

/**
 * @brief 心跳发送任务
 * @param pvParameters 任务参数
 * @return 无
 */
static void heartbeat_task(void *pvParameters) {
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(HEARTBEAT_INTERVAL_SECONDS * 1000));
        mqtt_publish_heartbeat();
    }
    vTaskDelete(NULL);
}

/**
 * @brief 发送网络状态到STM32
 * @param status 网络状态: 'C'-MQTT已连接, 'D'-有网络但MQTT未连接, 'O'-无网络
 * @return 无
 */
void mqtt_send_network_status(char status) {
    uart_write_bytes(USER_UART_NUM, &status, 1);
    //ESP_LOGI("mqtt", "Sent network status to STM32: %c", status);
}

/**
 * @brief MQTT监听模块初始化
 * @return 无
 */
void mqtt_listener_init(void) {
    // 初始化MQTT客户端
    mqtt_start();
}
