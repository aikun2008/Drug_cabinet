/**
 * ESP32 MQTT OTA升级模块实现文件
 * 实现基于MQTT的OTA升级，支持分包传输、确认机制和断点续传
 */

#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_partition.h"
#include "esp_system.h"
#include "cJSON.h"
#include "mqtt_listener.h"
#include "mqtt_ota_handler.h"
#include "uart_manager.h"
#include <mbedtls/base64.h>

// 日志标签
static const char *TAG = "MQTT_OTA";

// ========================== 全局变量 ==========================
static mqtt_ota_state_t g_ota_state = MQTT_OTA_STATE_IDLE;
static uint32_t g_firmware_size = 0;
static uint32_t g_total_packets = 0;
static uint32_t g_current_packet = 0;
static uint32_t g_packet_size = 1024;  // 默认1KB每包
static char g_md5_hash[33] = {0};
static esp_ota_handle_t g_ota_handle = 0;
static const esp_partition_t *g_update_partition = NULL;
static bool g_ota_in_progress = false;
static uint8_t g_decode_buffer[MQTT_OTA_MAX_PACKET_SIZE + 256];  // Base64解码缓冲区

// ========================== 辅助函数 ==========================

/**
 * @brief 更新 OTA 状态并上报
 */
static void update_ota_state(mqtt_ota_state_t state, int progress, const char *message)
{
    mqtt_ota_state_t old_state = g_ota_state;
    g_ota_state = state;
    
    // 状态变化时打印日志
    if (old_state != state) {
        ESP_LOGI(TAG, "OTA state: %d -> %d", old_state, state);
    }
    
    // 上报状态到服务器
    cJSON *root = cJSON_CreateObject();
    if (root) {
        cJSON_AddStringToObject(root, "equipment_id", MQTT_CLIENT);
        cJSON_AddStringToObject(root, "status", 
            (state == MQTT_OTA_STATE_IDLE) ? "idle" :
            (state == MQTT_OTA_STATE_WAIT_START) ? "wait_start" :
            (state == MQTT_OTA_STATE_DOWNLOADING) ? "downloading" :
            (state == MQTT_OTA_STATE_VERIFYING) ? "verifying" :
            (state == MQTT_OTA_STATE_COMPLETED) ? "completed" : "failed"
        );
        cJSON_AddNumberToObject(root, "progress", progress);
        if (message) {
            cJSON_AddStringToObject(root, "message", message);
        }
        
        char *json_str = cJSON_PrintUnformatted(root);
        if (json_str) {
            esp_mqtt_client_publish(s_mqtt_client, "/esp32/ota_status/server", json_str, strlen(json_str), 1, 0);
            free(json_str);
        }
        cJSON_Delete(root);
    }
    
    ESP_LOGI(TAG, "OTA progress: %d%%", progress);
}

/**
 * @brief 发送数据包请求到服务器
 * 支持断点续传：告诉后端当前需要哪个包
 */
static void request_packet(uint32_t packet_index)
{
    if (!s_is_mqtt_connected || s_mqtt_client == NULL) {
        ESP_LOGE(TAG, "MQTT not connected, cannot request packet");
        return;
    }
    
    cJSON *root = cJSON_CreateObject();
    if (!root) {
        ESP_LOGE(TAG, "Failed to create JSON for packet request");
        return;
    }
    
    cJSON_AddStringToObject(root, "equipment_id", MQTT_CLIENT);
    cJSON_AddNumberToObject(root, "packet_index", packet_index);
    cJSON_AddNumberToObject(root, "total_packets", g_total_packets);
    cJSON_AddNumberToObject(root, "current_progress", (packet_index * 100) / g_total_packets);
    
    char *json_str = cJSON_PrintUnformatted(root);
    if (json_str) {
        char topic[64];
        snprintf(topic, sizeof(topic), "/esp32/ota/request/%s", MQTT_CLIENT);
        esp_mqtt_client_publish(s_mqtt_client, topic, json_str, strlen(json_str), 1, 0);
        free(json_str);
    } else {
        ESP_LOGE(TAG, "Failed to print JSON for packet request");
    }
    cJSON_Delete(root);
}

/**
 * @brief 发送确认到服务器
 */
static void send_ack(uint32_t packet_index, const char *status)
{
    if (!s_is_mqtt_connected || s_mqtt_client == NULL) {
        return;
    }
    
    cJSON *root = cJSON_CreateObject();
    if (!root) return;
    
    cJSON_AddStringToObject(root, "equipment_id", MQTT_CLIENT);
    cJSON_AddNumberToObject(root, "packet_index", packet_index);
    cJSON_AddStringToObject(root, "status", status);
    
    char *json_str = cJSON_PrintUnformatted(root);
    if (json_str) {
        char topic[64];
        snprintf(topic, sizeof(topic), "/esp32/ota/ack/%s", MQTT_CLIENT);
        esp_mqtt_client_publish(s_mqtt_client, topic, json_str, strlen(json_str), 1, 0);
        free(json_str);
    }
    cJSON_Delete(root);
}

/**
 * @brief OTA关键段进入 - 禁用中断防止干扰
 */
static void ota_enter_critical(void)
{
    // 在OTA关键操作期间，短暂禁用非关键中断
    // 注意：这里不使用portENTER_CRITICAL，因为时间太长
    // 而是依靠合理的任务优先级设计
}

/**
 * @brief OTA关键段退出
 */
static void ota_exit_critical(void)
{
}

/**
 * @brief 处理接收到的固件数据包
 * 注意：此函数在中断或事件循环中调用，需要快速处理
 */
static void handle_ota_data(const char *json_data)
{
    static TickType_t last_packet_time = 0;
    TickType_t current_time = xTaskGetTickCount();
    
    // 检查状态
    if (g_ota_state != MQTT_OTA_STATE_DOWNLOADING) {
        ESP_LOGE(TAG, "OTA data received but not in downloading state");
        return;
    }
    
    // 检查是否超时（超过 5 秒没有收到包）
    if (last_packet_time != 0 && (current_time - last_packet_time) > pdMS_TO_TICKS(5000)) {
        ESP_LOGW(TAG, "OTA timeout, last packet was %lu ms ago", 
                 (current_time - last_packet_time) * portTICK_PERIOD_MS);
    }
    
    cJSON *root = cJSON_Parse(json_data);
    if (!root) {
        ESP_LOGE(TAG, "Failed to parse OTA data JSON");
        return;
    }
    
    cJSON *packet_index_item = cJSON_GetObjectItem(root, "packet_index");
    cJSON *data_item = cJSON_GetObjectItem(root, "data");
    cJSON *data_len_item = cJSON_GetObjectItem(root, "data_len");
    cJSON *encoded_len_item = cJSON_GetObjectItem(root, "encoded_len");
    
    if (!packet_index_item || !data_item || !data_len_item) {
        ESP_LOGE(TAG, "Missing required fields in OTA data");
        cJSON_Delete(root);
        return;
    }
    
    uint32_t packet_index = packet_index_item->valueint;
    const char *base64_data = data_item->valuestring;
    size_t data_len = data_len_item->valueint;  // 原始数据长度
    size_t encoded_len = encoded_len_item ? encoded_len_item->valueint : strlen(base64_data);  // Base64 编码长度
    
    // 验证包序号
    if (packet_index != g_current_packet) {
        ESP_LOGW(TAG, "Packet index mismatch: expected %lu, got %lu", g_current_packet, packet_index);
        cJSON_Delete(root);
        return;
    }
    
    // 检查 encoded_len 字段是否存在
    (void)encoded_len_item;  // 避免未使用警告
    
    // 验证 Base64 数据长度
    size_t base64_actual_len = strlen(base64_data);
    if (base64_actual_len != encoded_len) {
        ESP_LOGE(TAG, "Base64 length mismatch: %zu vs %zu", base64_actual_len, encoded_len);
        send_ack(packet_index, "error");
        cJSON_Delete(root);
        return;
    }
    
    // Base64 解码
    size_t decoded_len = 0;
    int ret = mbedtls_base64_decode(g_decode_buffer, sizeof(g_decode_buffer), &decoded_len,
                                     (const unsigned char *)base64_data, base64_actual_len);
    
    if (ret != 0) {
        ESP_LOGE(TAG, "Base64 decode failed: %d", ret);
        send_ack(packet_index, "error");
        cJSON_Delete(root);
        return;
    }
    
    // 验证解码后的长度是否与原始数据长度一致
    if (decoded_len != data_len) {
        ESP_LOGE(TAG, "Data length mismatch: %zu vs %zu", decoded_len, data_len);
        send_ack(packet_index, "error");
        cJSON_Delete(root);
        return;
    }
    
    // 进入关键段 - 写入Flash期间尽量减少干扰
    ota_enter_critical();
    
    // 写入OTA分区
    esp_err_t err = esp_ota_write(g_ota_handle, g_decode_buffer, decoded_len);
    
    ota_exit_critical();
    
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to write OTA data: %s", esp_err_to_name(err));
        send_ack(packet_index, "error");
        update_ota_state(MQTT_OTA_STATE_FAILED, 0, "Write firmware data failed");
        cJSON_Delete(root);
        return;
    }
    
    // 更新最后包时间
    last_packet_time = current_time;
    
    // 发送确认（尽快发送，让服务器准备下一包）
    send_ack(packet_index, "ok");
    
    // 延时，让系统处理其他任务，避免后端发送过快
    // Flash 写入需要较长时间，特别是大固件时
    vTaskDelay(pdMS_TO_TICKS(100));  // 100ms 延迟
    
    // 更新进度
    g_current_packet++;
    int progress = (int)((g_current_packet * 100) / g_total_packets);
    
    // 每 10 个包报告一次进度，减少 MQTT 流量
    if (g_current_packet % 10 == 0 || g_current_packet >= g_total_packets) {
        char progress_msg[64];
        snprintf(progress_msg, sizeof(progress_msg), "Downloading... (%lu/%lu)", g_current_packet, g_total_packets);
        update_ota_state(MQTT_OTA_STATE_DOWNLOADING, progress, progress_msg);
        ESP_LOGI(TAG, "OTA packet %lu/%lu, %d%%", g_current_packet, g_total_packets, progress);
    }
    
    // 检查是否所有包都已接收
    if (g_current_packet >= g_total_packets) {
        // 完成OTA写入
        ESP_LOGI(TAG, "OTA download complete, finalizing...");
        
        err = esp_ota_end(g_ota_handle);
        if (err != ESP_OK) {
            if (err == ESP_ERR_OTA_VALIDATE_FAILED) {
                ESP_LOGE(TAG, "Firmware validation failed");
                update_ota_state(MQTT_OTA_STATE_FAILED, 0, "Validation failed");
            } else {
                ESP_LOGE(TAG, "Failed to end OTA: %s", esp_err_to_name(err));
                update_ota_state(MQTT_OTA_STATE_FAILED, 0, "End OTA failed");
            }
            cJSON_Delete(root);
            return;
        }
        
        // 设置新的启动分区
        err = esp_ota_set_boot_partition(g_update_partition);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "Failed to set boot partition: %s", esp_err_to_name(err));
            update_ota_state(MQTT_OTA_STATE_FAILED, 0, "Set boot partition failed");
            cJSON_Delete(root);
            return;
        }
        
        update_ota_state(MQTT_OTA_STATE_COMPLETED, 100, "OTA complete, rebooting");
        g_ota_in_progress = false;
        
        // OTA完成，恢复UART处理
        g_uart_processing_enabled = true;
        ESP_LOGI(TAG, "UART processing re-enabled after OTA");
        
        // 延迟一段时间后重启
        vTaskDelay(pdMS_TO_TICKS(3000));
        esp_restart();
    }
    
    cJSON_Delete(root);
}

/**
 * @brief 处理OTA开始命令
 */
static void handle_ota_start(const char *json_data)
{
    if (g_ota_in_progress) {
        ESP_LOGW(TAG, "OTA already in progress");
        return;
    }
    
    cJSON *root = cJSON_Parse(json_data);
    if (!root) {
        ESP_LOGE(TAG, "Failed to parse OTA start JSON");
        return;
    }
    
    cJSON *firmware_size_item = cJSON_GetObjectItem(root, "firmware_size");
    cJSON *total_packets_item = cJSON_GetObjectItem(root, "total_packets");
    cJSON *packet_size_item = cJSON_GetObjectItem(root, "packet_size");
    cJSON *md5_item = cJSON_GetObjectItem(root, "md5");
    
    if (!firmware_size_item || !total_packets_item || !md5_item) {
        ESP_LOGE(TAG, "Missing required fields in OTA start command");
        cJSON_Delete(root);
        return;
    }
    
    g_firmware_size = firmware_size_item->valueint;
    g_total_packets = total_packets_item->valueint;
    g_packet_size = packet_size_item ? packet_size_item->valueint : 1024;
    strncpy(g_md5_hash, md5_item->valuestring, sizeof(g_md5_hash) - 1);
    g_md5_hash[sizeof(g_md5_hash) - 1] = '\0';
    
    ESP_LOGI(TAG, "OTA start: size=%lu, packets=%lu, packet_size=%lu",
             g_firmware_size, g_total_packets, g_packet_size);
    
    // 获取更新分区
    g_update_partition = esp_ota_get_next_update_partition(NULL);
    if (g_update_partition == NULL) {
        ESP_LOGE(TAG, "Failed to get update partition");
        update_ota_state(MQTT_OTA_STATE_FAILED, 0, "获取更新分区失败");
        cJSON_Delete(root);
        return;
    }
    
    // 检查固件大小是否超过分区大小
    if (g_firmware_size > g_update_partition->size) {
        ESP_LOGE(TAG, "Firmware size exceeds partition size");
        update_ota_state(MQTT_OTA_STATE_FAILED, 0, "Size exceeds partition");
        cJSON_Delete(root);
        return;
    }
    
    // 开始 OTA
    esp_err_t err = esp_ota_begin(g_update_partition, g_firmware_size, &g_ota_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to begin OTA: %s", esp_err_to_name(err));
        update_ota_state(MQTT_OTA_STATE_FAILED, 0, "Init OTA failed");
        cJSON_Delete(root);
        return;
    }
    
    // 初始化状态
    g_current_packet = 0;
    g_ota_in_progress = true;
    g_ota_state = MQTT_OTA_STATE_DOWNLOADING;
    
    // OTA 期间禁用 UART 数据处理，避免干扰
    g_uart_processing_enabled = false;
    ESP_LOGI(TAG, "UART processing disabled during OTA");
    
    update_ota_state(MQTT_OTA_STATE_DOWNLOADING, 0, "Starting download");
    
    // 请求第一包数据
    request_packet(0);
    
    cJSON_Delete(root);
}

/**
 * @brief 处理OTA取消命令
 */
static void handle_ota_cancel(void)
{
    ESP_LOGI(TAG, "OTA cancelled");
    
    if (g_ota_handle != 0) {
        esp_ota_abort(g_ota_handle);
        g_ota_handle = 0;
    }
    
    g_ota_in_progress = false;
    g_ota_state = MQTT_OTA_STATE_IDLE;
    g_current_packet = 0;
    
    // OTA取消，恢复UART处理
    g_uart_processing_enabled = true;
    ESP_LOGI(TAG, "UART processing re-enabled after OTA cancel");
    
    update_ota_state(MQTT_OTA_STATE_IDLE, 0, "OTA cancelled");
}

// ========================== 公共函数实现 ==========================

/**
 * @brief 初始化MQTT OTA模块
 */
esp_err_t mqtt_ota_init(void)
{
    ESP_LOGI(TAG, "Initializing MQTT OTA module");
    
    g_ota_state = MQTT_OTA_STATE_IDLE;
    g_ota_in_progress = false;
    g_current_packet = 0;
    g_firmware_size = 0;
    g_total_packets = 0;
    memset(g_md5_hash, 0, sizeof(g_md5_hash));
    
    return ESP_OK;
}

/**
 * @brief 处理MQTT OTA命令
 */
void mqtt_ota_handle_command(const char *command, const char *json_data)
{
    if (!command || !json_data) {
        return;
    }
    
    ESP_LOGI(TAG, "Received OTA command: %s", command);
    
    if (strcmp(command, "mqtt_ota_start") == 0) {
        handle_ota_start(json_data);
    } else if (strcmp(command, "mqtt_ota_cancel") == 0) {
        handle_ota_cancel();
    } else {
        ESP_LOGW(TAG, "Unknown OTA command: %s", command);
    }
}

/**
 * @brief 处理 MQTT OTA 数据
 */
void mqtt_ota_handle_data(const char *json_data)
{
    if (!json_data) {
        ESP_LOGE(TAG, "Received NULL json_data");
        return;
    }
    
    size_t json_len = strlen(json_data);
    
    // 清理 JSON 数据（移除首尾的空白字符、换行符等）
    const char *start = json_data;
    const char *end = json_data + json_len - 1;
    
    // 跳过开头的空白字符
    while (*start && (*start == ' ' || *start == '\t' || *start == '\n' || *start == '\r')) {
        start++;
    }
    
    // 跳过结尾的空白字符
    while (end > start && (*end == ' ' || *end == '\t' || *end == '\n' || *end == '\r')) {
        end--;
    }
    
    // 检查清理后的数据是否有效
    size_t clean_len = end - start + 1;
    if (clean_len < 2 || *start != '{' || *end != '}') {
        ESP_LOGE(TAG, "Invalid JSON format after cleaning");
        return;
    }
    
    // 如果数据被清理过，需要复制一份
    if (start != json_data || end != json_data + json_len - 1) {
        char *clean_json = malloc(clean_len + 1);
        if (clean_json) {
            memcpy(clean_json, start, clean_len);
            clean_json[clean_len] = '\0';
            handle_ota_data(clean_json);
            free(clean_json);
        } else {
            ESP_LOGE(TAG, "Failed to allocate memory for cleaned JSON");
            return;
        }
    } else {
        // 数据不需要清理，直接处理
        handle_ota_data(json_data);
    }
}

/**
 * @brief 获取当前OTA状态
 */
mqtt_ota_state_t mqtt_ota_get_state(void)
{
    return g_ota_state;
}

/**
 * @brief 检查OTA是否正在进行
 */
bool mqtt_ota_is_in_progress(void)
{
    return g_ota_in_progress;
}

/**
 * @brief 获取当前进度
 */
int mqtt_ota_get_progress(void)
{
    if (g_total_packets == 0) {
        return 0;
    }
    return (int)((g_current_packet * 100) / g_total_packets);
}

/**
 * @brief 恢复 OTA 传输（MQTT 断线重连后调用）
 */
void mqtt_ota_resume(void)
{
    if (!g_ota_in_progress || g_ota_state != MQTT_OTA_STATE_DOWNLOADING) {
        ESP_LOGI(TAG, "OTA not in progress, no need to resume");
        return;
    }
    
    ESP_LOGI(TAG, "Resuming OTA from packet %lu/%lu", g_current_packet, g_total_packets);
    
    // 重新请求当前包
    request_packet(g_current_packet);
    
    // 上报状态
    char progress_msg[64];
    snprintf(progress_msg, sizeof(progress_msg), "Resuming... (%lu/%lu)", g_current_packet, g_total_packets);
    update_ota_state(MQTT_OTA_STATE_DOWNLOADING, mqtt_ota_get_progress(), progress_msg);
}
