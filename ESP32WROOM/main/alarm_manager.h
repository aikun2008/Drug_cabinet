#ifndef ALARM_MANAGER_H
#define ALARM_MANAGER_H

#include <stdbool.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "freertos/timers.h"

// ========================== 常量定义 ==========================
#define ENV_CACHE_SIZE 3            // 环境数据缓存大小
#define ALARM_REPORT_DURATION_MS 30000  // 异常时上报持续时间（30秒）

// ========================== 数据类型 ==========================

/**
 * @brief 阈值配置结构体（只保留NOR范围，用于触发上报）
 */
typedef struct {
    float temp_min;          // 温度正常最小值
    float temp_max;          // 温度正常最大值
    float humi_min;          // 湿度正常最小值
    float humi_max;          // 湿度正常最大值
    float aqi_max;           // AQI正常最大值
    bool is_valid;           // 配置是否有效
} threshold_config_t;

/**
 * @brief 环境数据点
 */
typedef struct {
    float temp;              // 温度
    float humi;              // 湿度
    int aqi;                 // 空气质量
    uint64_t timestamp;      // 时间戳（秒）
} env_data_point_t;

/**
 * @brief 环境数据缓存
 */
typedef struct {
    env_data_point_t data[ENV_CACHE_SIZE];  // 数据缓存
    int index;                              // 当前索引
    int count;                              // 有效数据数量
} env_data_cache_t;

// ========================== 全局变量声明 ==========================
extern threshold_config_t g_threshold_config;
extern env_data_cache_t g_env_cache;
extern volatile bool g_alarm_reporting_active;  // 是否处于异常上报状态

// ========================== 函数声明 ==========================

/**
 * @brief 初始化报警管理器
 */
void alarm_manager_init(void);

/**
 * @brief 请求阈值配置（MQTT连接后调用）
 */
void request_threshold_config(void);

/**
 * @brief 解析并保存阈值配置
 * @param payload JSON格式的阈值配置
 */
void parse_threshold_config(const char *payload);

/**
 * @brief 添加环境数据（平时不上报，异常时启动定时上报）
 * @param temp 温度
 * @param humi 湿度
 * @param aqi 空气质量指数
 */
void add_env_data(float temp, float humi, int aqi);

/**
 * @brief 上报环境数据到服务器（常规数据，用于历史记录）
 * @param temp 温度
 * @param humi 湿度
 * @param aqi 空气质量
 */
void report_env_data(float temp, float humi, int aqi);

/**
 * @brief 上报报警数据到服务器（异常/报警专用主题）
 * @param temp 温度
 * @param humi 湿度
 * @param aqi 空气质量
 */
void report_alarm_data(float temp, float humi, int aqi);

/**
 * @brief 检查数据是否在正常范围内
 * @param temp 温度
 * @param humi 湿度
 * @param aqi 空气质量
 * @return true-正常, false-不正常
 */
bool check_data_normal(float temp, float humi, int aqi);

/**
 * @brief 启动异常上报任务
 */
void start_alarm_reporting(void);

/**
 * @brief 停止异常上报任务
 */
void stop_alarm_reporting(void);

/**
 * @brief 重置报警计数（服务器通知报警已处理后调用）
 */
void reset_alarm_count(void);

#endif // ALARM_MANAGER_H
