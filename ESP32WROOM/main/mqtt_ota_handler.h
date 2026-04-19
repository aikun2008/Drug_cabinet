/**
 * ESP32 MQTT OTA升级模块头文件
 * 定义MQTT OTA相关的常量、枚举和函数声明
 */

#ifndef MQTT_OTA_HANDLER_H
#define MQTT_OTA_HANDLER_H

#include <stdint.h>
#include <stdbool.h>
#include "esp_err.h"

// ========================== OTA配置常量 ==========================
#define MQTT_OTA_MAX_PACKET_SIZE   1024        // 最大包大小 (1KB)
#define MQTT_OTA_TIMEOUT_MS        10000       // 超时时间（毫秒）
#define MQTT_OTA_MAX_RETRY         3           // 最大重试次数

// ========================== OTA状态枚举 ==========================
/**
 * @brief MQTT OTA升级状态枚举
 */
typedef enum {
    MQTT_OTA_STATE_IDLE = 0,        // 空闲状态
    MQTT_OTA_STATE_WAIT_START,      // 等待开始
    MQTT_OTA_STATE_DOWNLOADING,     // 固件下载中
    MQTT_OTA_STATE_VERIFYING,       // 固件验证中
    MQTT_OTA_STATE_COMPLETED,       // 升级完成
    MQTT_OTA_STATE_FAILED           // 升级失败
} mqtt_ota_state_t;

// ========================== 函数声明 ==========================
/**
 * @brief 初始化MQTT OTA模块
 * @return esp_err_t 初始化结果
 */
esp_err_t mqtt_ota_init(void);

/**
 * @brief 处理MQTT OTA命令
 * @param command 命令字符串 (如 "mqtt_ota_start", "mqtt_ota_cancel")
 * @param json_data JSON格式的命令数据
 */
void mqtt_ota_handle_command(const char *command, const char *json_data);

/**
 * @brief 处理MQTT OTA数据
 * @param json_data JSON格式的固件数据
 */
void mqtt_ota_handle_data(const char *json_data);

/**
 * @brief 获取当前OTA状态
 * @return mqtt_ota_state_t 当前OTA状态
 */
mqtt_ota_state_t mqtt_ota_get_state(void);

/**
 * @brief 检查OTA是否正在进行
 * @return true OTA正在进行
 * @return false OTA未进行
 */
bool mqtt_ota_is_in_progress(void);

/**
 * @brief 获取当前进度
 * @return int 当前升级进度（0-100）
 */
int mqtt_ota_get_progress(void);

/**
 * @brief 恢复OTA传输（MQTT断线重连后调用）
 */
void mqtt_ota_resume(void);

#endif // MQTT_OTA_HANDLER_H
