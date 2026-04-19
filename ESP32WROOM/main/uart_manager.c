#include "uart_manager.h"
#include "esp_log.h"
#include "mqtt_listener.h"
#include "esp_timer.h"
#include "alarm_manager.h"
#include "mqtt_ota_handler.h"
#include <string.h>

// UART处理使能标志（OTA期间禁用UART处理）
volatile bool g_uart_processing_enabled = true;

// 全局UART管理器实例
uart_manager_t g_uart_manager = {
    .uart_queue = NULL,
    .s_env_json = NULL,
    .s_door_lock_json = NULL,
    .s_rfid_json = NULL,
    .is_door_open = false,
    .door_open_start_time = 0,
    .door_open_duration = 0,
    .frame_buffer_index = 0,
    .brace_count = 0
};

// 定时上报任务配置
#define DOOR_STATUS_REPORT_INTERVAL_MS  5000  // 门状态定时上报间隔（5秒）
static TaskHandle_t s_door_report_task_handle = NULL;  // 定时上报任务句柄
static int s_last_reported_door = 0;      // 上次上报的门状态
static int s_last_reported_lock = 0;      // 上次上报的锁状态

/**
 * @brief 处理完整的JSON帧
 * @param json_str JSON字符串
 * @return 无
 */
static void process_json_frame(const char *json_str) {
    cJSON *root = cJSON_Parse(json_str);
    if (root == NULL) {
        ESP_LOGW(TAGD, "Failed to parse JSON: %s", json_str);
        return;
    }
    
    // 检查是否包含cardid字段
    cJSON *cardid_item = cJSON_GetObjectItemCaseSensitive(root, "cardid");
    
    // 判断消息类型
    if (cJSON_GetObjectItemCaseSensitive(root, "temp") ||
        cJSON_GetObjectItemCaseSensitive(root, "humi") ||
        cJSON_GetObjectItemCaseSensitive(root, "AQI")) {
        // 1. 环境信息：{"temp":25.6,"humi":28.0,"AQI":0}
        cJSON *temp_item = cJSON_GetObjectItemCaseSensitive(root, "temp");
        cJSON *humi_item = cJSON_GetObjectItemCaseSensitive(root, "humi");
        cJSON *aqi_item = cJSON_GetObjectItemCaseSensitive(root, "AQI");
        
        float temp = 0.0f, humi = 0.0f;
        int aqi = 0;
        
        if (temp_item && cJSON_IsNumber(temp_item)) temp = temp_item->valuedouble;
        if (humi_item && cJSON_IsNumber(humi_item)) humi = humi_item->valuedouble;
        if (aqi_item && cJSON_IsNumber(aqi_item)) aqi = aqi_item->valueint;
        
        ESP_LOGI(TAGD, "Environment data - temp: %.1f, humi: %.1f, AQI: %d", temp, humi, aqi);
        
        // 保存到缓存供查询使用
        if (g_uart_manager.s_env_json) cJSON_Delete(g_uart_manager.s_env_json);
        g_uart_manager.s_env_json = root;
        ESP_LOGI(TAGD, "Cached environment data");
        
        // 添加环境数据（上报到服务器，服务器判断是否需要报警）
        add_env_data(temp, humi, aqi);
    } else if (cJSON_GetObjectItemCaseSensitive(root, "Door") ||
               cJSON_GetObjectItemCaseSensitive(root, "Lock")) {
        // 2. 门锁状态信息：{"Door":1,"Lock":1}
        if (g_uart_manager.s_door_lock_json) cJSON_Delete(g_uart_manager.s_door_lock_json);
        g_uart_manager.s_door_lock_json = root;
        //ESP_LOGI(TAGD, "Cached door lock data");
        
        // 解析门和锁的状态
        int door = 0;
        int lock = 0;
        
        cJSON *door_item = cJSON_GetObjectItemCaseSensitive(root, "Door");
        cJSON *lock_item = cJSON_GetObjectItemCaseSensitive(root, "Lock");
        
        if (door_item && cJSON_IsNumber(door_item)) {
            door = door_item->valueint;
        }
        if (lock_item && cJSON_IsNumber(lock_item)) {
            lock = lock_item->valueint;
        }
        
        // 获取当前时间（毫秒）
        uint64_t current_time_ms = esp_timer_get_time() / 1000;
        uint32_t current_time_s = current_time_ms / 1000;
        
        // 检查门状态变化并更新计时
        if (door == 1) {
            // 门打开
            if (!g_uart_manager.is_door_open) {
                // 门从关闭变为打开，记录开始时间
                g_uart_manager.is_door_open = true;
                g_uart_manager.door_open_start_time = current_time_s;
                g_uart_manager.door_open_duration = 0;
                //ESP_LOGI(TAGD, "Door opened, start timing");
            } else {
                // 门保持打开，更新持续时间
                g_uart_manager.door_open_duration = current_time_s - g_uart_manager.door_open_start_time;
                //ESP_LOGI(TAGD, "Door still open, duration: %lu seconds", g_uart_manager.door_open_duration);
            }
        } else {
            // 门关闭
            if (g_uart_manager.is_door_open) {
                // 门从打开变为关闭，计算总持续时间
                g_uart_manager.door_open_duration = current_time_s - g_uart_manager.door_open_start_time;
                //ESP_LOGI(TAGD, "Door closed, total duration: %lu seconds", g_uart_manager.door_open_duration);
                // 重置计时状态
                g_uart_manager.is_door_open = false;
                g_uart_manager.door_open_start_time = 0;
            } else {
                // 门保持关闭，持续时间为0
                g_uart_manager.door_open_duration = 0;
                //ESP_LOGI(TAGD, "Door closed, duration: 0 seconds");
            }
        }
        
        // 立即发布门锁数据到服务器，timeout为门打开的持续时间
        //ESP_LOGI(TAGD, "Publishing door lock data - door: %d, lock: %d, timeout: %lu", door, lock, g_uart_manager.door_open_duration);
        mqtt_publish_door_lock_data(door, lock, g_uart_manager.door_open_duration);
        
        // 更新上次上报的状态
        s_last_reported_door = door;
        s_last_reported_lock = lock;
    } else if (cardid_item) {
        // 3. RFID信息：{"cardid":"0446F605"}
        //ESP_LOGI(TAGD, "RFID data received: %s", cardid_item->valuestring);
        if (g_uart_manager.s_rfid_json) cJSON_Delete(g_uart_manager.s_rfid_json);
        g_uart_manager.s_rfid_json = root;

        // 立即发布RFID数据到服务器
        //ESP_LOGI(TAGD, "Publishing RFID data to server");
        mqtt_publish_rfid_data();
    } else {
        // 非预期数据，释放
        cJSON_Delete(root);
    }
}

/**
 * @brief 处理接收到的字节数据，进行帧缓冲
 * @param data 接收到的数据
 * @param len 数据长度
 * @return 无
 */
static void process_uart_data(const uint8_t *data, size_t len) {
    for (size_t i = 0; i < len; i++) {
        char ch = data[i];
        
        // 检查缓冲区溢出
        if (g_uart_manager.frame_buffer_index >= UART_FRAME_BUFFER_SIZE - 1) {
            //ESP_LOGW(TAGD, "Frame buffer overflow, resetting");
            g_uart_manager.frame_buffer_index = 0;
            g_uart_manager.brace_count = 0;
            continue;
        }
        
        // 如果当前没有在累积帧，等待找到 '{'
        if (g_uart_manager.frame_buffer_index == 0 && ch != '{') {
            // 跳过非JSON开头的字符
            continue;
        }
        
        // 累积字符到帧缓冲区
        g_uart_manager.frame_buffer[g_uart_manager.frame_buffer_index++] = ch;
        
        // 更新大括号计数
        if (ch == '{') {
            g_uart_manager.brace_count++;
        } else if (ch == '}') {
            g_uart_manager.brace_count--;
            
            // 如果大括号匹配完成，说明收到完整的JSON
            if (g_uart_manager.brace_count == 0 && g_uart_manager.frame_buffer_index > 0) {
                g_uart_manager.frame_buffer[g_uart_manager.frame_buffer_index] = '\0';
                //ESP_LOGI(TAGD, "Complete frame received: %s", g_uart_manager.frame_buffer);
                
                // 处理完整的JSON帧
                process_json_frame((const char *)g_uart_manager.frame_buffer);
                
                // 重置缓冲区
                g_uart_manager.frame_buffer_index = 0;
                g_uart_manager.brace_count = 0;
            }
        }
    }
}

/**
 * @brief 门状态定时上报任务
 * 当门打开时，定时上报门状态，使服务器能够检测长时间开门
 * @param pvParameters 任务参数
 */
static void door_status_report_task(void *pvParameters)
{
    while (1) {
        // 每5秒检查一次
        vTaskDelay(pdMS_TO_TICKS(DOOR_STATUS_REPORT_INTERVAL_MS));
        
        // 只有在门打开状态下才定时上报
        if (g_uart_manager.is_door_open) {
            // 更新持续时间
            uint64_t current_time_ms = esp_timer_get_time() / 1000;
            uint32_t current_time_s = current_time_ms / 1000;
            g_uart_manager.door_open_duration = current_time_s - g_uart_manager.door_open_start_time;
            
            // 上报当前门状态
            ESP_LOGI(TAGD, "Door status report - door: %d, lock: %d, timeout: %lu", 
                     s_last_reported_door, s_last_reported_lock, g_uart_manager.door_open_duration);
            mqtt_publish_door_lock_data(s_last_reported_door, s_last_reported_lock, g_uart_manager.door_open_duration);
        }
    }
    vTaskDelete(NULL);
}

/**
 * @brief 串口模块初始化
 * @return 无
 */
void uart_manager_init(void) {
    uart_config_t uart_cfg = {
        .baud_rate = 115200,
        .data_bits = UART_DATA_8_BITS,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1
    };
    uart_driver_install(USER_UART_NUM, 1024, 1024, 20, &g_uart_manager.uart_queue, 0);
    uart_param_config(USER_UART_NUM, &uart_cfg);
    uart_set_pin(USER_UART_NUM, GPIO_NUM_32, GPIO_NUM_33, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    
    // 初始化帧缓冲区
    g_uart_manager.frame_buffer_index = 0;
    g_uart_manager.brace_count = 0;
    memset(g_uart_manager.frame_buffer, 0, UART_FRAME_BUFFER_SIZE);
    
    // 创建门状态定时上报任务
    if (xTaskCreate(door_status_report_task, "door_report_task", 2048, NULL, 5, &s_door_report_task_handle) != pdPASS) {
        ESP_LOGE(TAGD, "Failed to create door status report task");
    } else {
        ESP_LOGI(TAGD, "Door status report task created successfully");
    }
}

/**
 * @brief 串口事件处理任务
 * @param pvParameters 任务参数
 * @return 无
 */
void uart_event_task(void *pvParameters) {
    uart_event_t event;
    while (1) {
        if (xQueueReceive(g_uart_manager.uart_queue, (void *)&event, (TickType_t)portMAX_DELAY)) {

            switch (event.type) {
                case UART_DATA:
                {
                    // 检查是否允许处理 UART 数据（OTA 期间禁用）
                    if (!g_uart_processing_enabled) {
                        // OTA 期间，丢弃 UART 数据
                        uint8_t discard_buffer[UART_BUFFER_SIZE];
                        uart_read_bytes(USER_UART_NUM, discard_buffer, event.size, portMAX_DELAY);
                        break;
                    }
                    
                    // 读取数据到临时缓冲区
                    uint8_t temp_buffer[UART_BUFFER_SIZE];
                    int len = uart_read_bytes(USER_UART_NUM, temp_buffer, event.size, portMAX_DELAY);
                    if (len > 0) {
                        ESP_LOGI(TAGD, "Received %d bytes from UART", len);
                        // 处理接收到的数据，进行帧缓冲
                        process_uart_data(temp_buffer, len);
                    }
                    break;
                }
                case UART_FIFO_OVF:
                    uart_flush_input(USER_UART_NUM);
                    xQueueReset(g_uart_manager.uart_queue);
                    // 重置帧缓冲区
                    g_uart_manager.frame_buffer_index = 0;
                    g_uart_manager.brace_count = 0;
                    break;
                case UART_BUFFER_FULL:
                    //ESP_LOGW(TAGD, "UART buffer full");
                    uart_flush_input(USER_UART_NUM);
                    xQueueReset(g_uart_manager.uart_queue);
                    // 重置帧缓冲区
                    g_uart_manager.frame_buffer_index = 0;
                    g_uart_manager.brace_count = 0;
                    break;
                case UART_BREAK:
                    //ESP_LOGW(TAGD, "UART break detected");
                    break;
                case UART_PARITY_ERR:
                    //ESP_LOGW(TAGD, "UART parity error");
                    break;
                case UART_FRAME_ERR:
                    //ESP_LOGW(TAGD, "UART frame error");
                    break;
                default:
                    break;
            }
        }
    }
    vTaskDelete(NULL);
}
