#include "alarm_manager.h"
#include "mqtt_listener.h"
#include "uart_manager.h"
#include "mqtt_ota_handler.h"
#include "esp_log.h"
#include "cJSON.h"
#include "esp_timer.h"
#include <string.h>

// 日志标签
#define TAG_ALARM "alarm_mgr"

// 全局阈值配置（只保留NOR范围，用于触发上报）
// 注意：必须使用服务器配置的阈值，is_valid 默认为 false
// 在获取到服务器阈值前，不进行异常检测和上报
threshold_config_t g_threshold_config = {
    .temp_min = 0.0f,   // 初始值无效
    .temp_max = 0.0f,
    .humi_min = 0.0f,
    .humi_max = 0.0f,
    .aqi_max = 0.0f,
    .is_valid = false   // 必须等待服务器配置
};

// 环境数据缓存（滑动窗口，用于计算平均值）
env_data_cache_t g_env_cache = {
    .index = 0,
    .count = 0
};

// 是否处于异常上报状态
volatile bool g_alarm_reporting_active = false;

// 互斥锁
static SemaphoreHandle_t s_alarm_mutex = NULL;

// 定时器句柄
static TimerHandle_t s_reporting_timer = NULL;

/**
 * @brief 定时器回调函数 - 停止异常上报
 */
static void reporting_timer_callback(TimerHandle_t xTimer) {
    stop_alarm_reporting();
    ESP_LOGI(TAG_ALARM, "Alarm reporting period ended, back to normal mode");
}

/**
 * @brief 初始化报警管理器
 */
void alarm_manager_init(void) {
    s_alarm_mutex = xSemaphoreCreateMutex();
    if (s_alarm_mutex == NULL) {
        ESP_LOGE(TAG_ALARM, "Failed to create alarm mutex");
    }

    // 创建定时器（单次定时，30秒后停止上报）
    s_reporting_timer = xTimerCreate(
        "reporting_timer",
        pdMS_TO_TICKS(ALARM_REPORT_DURATION_MS),
        pdFALSE,  // 单次定时
        NULL,
        reporting_timer_callback
    );

    if (s_reporting_timer == NULL) {
        ESP_LOGE(TAG_ALARM, "Failed to create reporting timer");
    }

    ESP_LOGI(TAG_ALARM, "Alarm manager initialized");
}

/**
 * @brief 阈值请求重试任务
 * 如果阈值获取失败，每隔10秒重试一次，最多重试10次
 */
static void threshold_retry_task(void *pvParameters) {
    int retry_count = 0;
    const int max_retries = 10;
    const int retry_interval_ms = 10000;  // 10秒

    while (retry_count < max_retries) {
        vTaskDelay(pdMS_TO_TICKS(retry_interval_ms));

        if (g_threshold_config.is_valid) {
            ESP_LOGI(TAG_ALARM, "Threshold config received");
            break;
        }

        if (s_is_mqtt_connected && s_mqtt_client != NULL) {
            retry_count++;
            ESP_LOGW(TAG_ALARM, "Threshold not received, retrying (%d/%d)...", retry_count, max_retries);

            char json_str[128];
            snprintf(json_str, sizeof(json_str),
                     "{\"equipment_id\":\"%s\",\"query\":\"threshold_config\"}",
                     MQTT_CLIENT);

            esp_mqtt_client_publish(s_mqtt_client, MQTT_PUB_DEVICE_REQUEST,
                                   json_str, strlen(json_str), 1, 0);
        }
    }

    if (retry_count >= max_retries && !g_threshold_config.is_valid) {
        ESP_LOGE(TAG_ALARM, "Failed to get threshold config after %d retries", max_retries);
    }

    vTaskDelete(NULL);
}

/**
 * @brief 请求阈值配置（MQTT连接后调用）
 * 启动后会创建一个重试任务，确保能获取到阈值
 */
void request_threshold_config(void) {
    if (!s_is_mqtt_connected || s_mqtt_client == NULL) {
        ESP_LOGW(TAG_ALARM, "MQTT not connected, cannot request threshold");
        return;
    }

    char json_str[128];
    snprintf(json_str, sizeof(json_str),
             "{\"equipment_id\":\"%s\",\"query\":\"threshold_config\"}",
             MQTT_CLIENT);

    esp_mqtt_client_publish(s_mqtt_client, MQTT_PUB_DEVICE_REQUEST,
                           json_str, strlen(json_str), 1, 0);

    // 创建重试任务
    xTaskCreate(threshold_retry_task, "threshold_retry", 2048, NULL, 5, NULL);
}

/**
 * @brief 解析并保存阈值配置（只解析NOR范围）
 * @param payload JSON格式的阈值配置
 */
void parse_threshold_config(const char *payload) {
    cJSON *root = cJSON_Parse(payload);
    if (root == NULL) {
        ESP_LOGE(TAG_ALARM, "Failed to parse threshold config");
        return;
    }

    // 检查互斥锁是否已初始化
    if (s_alarm_mutex == NULL) {
        ESP_LOGW(TAG_ALARM, "Alarm mutex not initialized, skipping threshold config");
        cJSON_Delete(root);
        return;
    }

    if (xSemaphoreTake(s_alarm_mutex, portMAX_DELAY) == pdTRUE) {
        // 解析NOR范围（服务器可能返回 temp_NOR_min 或 temp_min）
        cJSON *temp_min = cJSON_GetObjectItemCaseSensitive(root, "temp_min");
        cJSON *temp_max = cJSON_GetObjectItemCaseSensitive(root, "temp_max");
        cJSON *humi_min = cJSON_GetObjectItemCaseSensitive(root, "humi_min");
        cJSON *humi_max = cJSON_GetObjectItemCaseSensitive(root, "humi_max");
        cJSON *aqi_max = cJSON_GetObjectItemCaseSensitive(root, "aqi_max");

        // 如果找不到，尝试带NOR后缀的字段名
        if (!temp_min) temp_min = cJSON_GetObjectItemCaseSensitive(root, "temp_NOR_min");
        if (!temp_max) temp_max = cJSON_GetObjectItemCaseSensitive(root, "temp_NOR_max");
        if (!humi_min) humi_min = cJSON_GetObjectItemCaseSensitive(root, "humi_NOR_min");
        if (!humi_max) humi_max = cJSON_GetObjectItemCaseSensitive(root, "humi_NOR_max");
        if (!aqi_max) aqi_max = cJSON_GetObjectItemCaseSensitive(root, "aqi_NOR_max");

        if (temp_min && cJSON_IsNumber(temp_min)) g_threshold_config.temp_min = temp_min->valuedouble;
        if (temp_max && cJSON_IsNumber(temp_max)) g_threshold_config.temp_max = temp_max->valuedouble;
        if (humi_min && cJSON_IsNumber(humi_min)) g_threshold_config.humi_min = humi_min->valuedouble;
        if (humi_max && cJSON_IsNumber(humi_max)) g_threshold_config.humi_max = humi_max->valuedouble;
        if (aqi_max && cJSON_IsNumber(aqi_max)) g_threshold_config.aqi_max = aqi_max->valuedouble;

        g_threshold_config.is_valid = true;
        xSemaphoreGive(s_alarm_mutex);
    }

    cJSON_Delete(root);
    ESP_LOGI(TAG_ALARM, "Threshold config updated: Temp[%.1f, %.1f], Humi[%.1f, %.1f], AQI<%.1f",
             g_threshold_config.temp_min, g_threshold_config.temp_max,
             g_threshold_config.humi_min, g_threshold_config.humi_max,
             g_threshold_config.aqi_max);
}

/**
 * @brief 检查数据是否在正常范围内
 * @param temp 温度
 * @param humi 湿度
 * @param aqi 空气质量
 * @return true-正常, false-不正常
 */
bool check_data_normal(float temp, float humi, int aqi) {
    if (!g_threshold_config.is_valid) {
        return true;  // 阈值无效，默认正常
    }

    // 检查温度
    if (temp < g_threshold_config.temp_min || temp > g_threshold_config.temp_max) {
        return false;
    }

    // 检查湿度
    if (humi < g_threshold_config.humi_min || humi > g_threshold_config.humi_max) {
        return false;
    }

    // 检查AQI
    if (aqi > g_threshold_config.aqi_max) {
        return false;
    }

    return true;
}

/**
 * @brief 启动异常上报任务
 */
void start_alarm_reporting(void) {
    if (!g_alarm_reporting_active) {
        g_alarm_reporting_active = true;
        ESP_LOGW(TAG_ALARM, "Alarm mode activated");
    }

    // 每次检测到异常都重置定时器（延长上报时间）
    if (s_reporting_timer != NULL) {
        xTimerReset(s_reporting_timer, 0);
    }
}

/**
 * @brief 停止异常上报任务
 */
void stop_alarm_reporting(void) {
    g_alarm_reporting_active = false;
    ESP_LOGI(TAG_ALARM, "Alarm mode deactivated");
}

/**
 * @brief 上报环境数据到服务器（常规数据，用于历史记录）
 * @param temp 温度
 * @param humi 湿度
 * @param aqi 空气质量
 */
void report_env_data(float temp, float humi, int aqi) {
    if (!s_is_mqtt_connected || s_mqtt_client == NULL) {
        ESP_LOGW(TAG_ALARM, "MQTT not connected, cannot report data");
        return;
    }

    char json_str[256];

    // 计算滑动平均值
    float avg_temp = temp;
    float avg_humi = humi;
    int avg_aqi = aqi;

    if (g_env_cache.count > 0) {
        float sum_temp = temp;
        float sum_humi = humi;
        int sum_aqi = aqi;

        for (int i = 0; i < g_env_cache.count; i++) {
            sum_temp += g_env_cache.data[i].temp;
            sum_humi += g_env_cache.data[i].humi;
            sum_aqi += g_env_cache.data[i].aqi;
        }

        int total = g_env_cache.count + 1;
        avg_temp = sum_temp / total;
        avg_humi = sum_humi / total;
        avg_aqi = sum_aqi / total;
    }

    // 上报到常规环境数据主题
    snprintf(json_str, sizeof(json_str),
             "{\"equipment_id\":\"%s\",\"temp\":%.1f,\"humi\":%.1f,\"aqi\":%d,\"avg_temp\":%.1f,\"avg_humi\":%.1f,\"avg_aqi\":%d}",
             MQTT_CLIENT, temp, humi, aqi, avg_temp, avg_humi, avg_aqi);

    esp_mqtt_client_publish(s_mqtt_client, MQTT_PUB_ENV_DATA,
                           json_str, strlen(json_str), 1, 0);

    ESP_LOGI(TAG_ALARM, "Env data reported: temp=%.1f, humi=%.1f, aqi=%d", temp, humi, aqi);
}

/**
 * @brief 上报报警数据到服务器（异常/报警专用主题）
 * @param temp 温度
 * @param humi 湿度
 * @param aqi 空气质量
 */
void report_alarm_data(float temp, float humi, int aqi) {
    if (!s_is_mqtt_connected || s_mqtt_client == NULL) {
        ESP_LOGW(TAG_ALARM, "MQTT not connected, cannot report alarm");
        return;
    }

    char json_str[256];

    // 计算滑动平均值
    float avg_temp = temp;
    float avg_humi = humi;
    int avg_aqi = aqi;

    if (g_env_cache.count > 0) {
        float sum_temp = temp;
        float sum_humi = humi;
        int sum_aqi = aqi;

        for (int i = 0; i < g_env_cache.count; i++) {
            sum_temp += g_env_cache.data[i].temp;
            sum_humi += g_env_cache.data[i].humi;
            sum_aqi += g_env_cache.data[i].aqi;
        }

        int total = g_env_cache.count + 1;
        avg_temp = sum_temp / total;
        avg_humi = sum_humi / total;
        avg_aqi = sum_aqi / total;
    }

    // 上报到专门的报警数据主题
    snprintf(json_str, sizeof(json_str),
             "{\"equipment_id\":\"%s\",\"temp\":%.1f,\"humi\":%.1f,\"aqi\":%d,\"avg_temp\":%.1f,\"avg_humi\":%.1f,\"avg_aqi\":%d}",
             MQTT_CLIENT, temp, humi, aqi, avg_temp, avg_humi, avg_aqi);

    esp_mqtt_client_publish(s_mqtt_client, MQTT_PUB_ALARM_DATA,
                           json_str, strlen(json_str), 1, 0);

    ESP_LOGW(TAG_ALARM, "Alarm reported: temp=%.1f, humi=%.1f, aqi=%d", temp, humi, aqi);
}

/**
 * @brief 添加环境数据（智能上报：平时静默，异常时启动定时上报）
 * 注意：必须使用服务器配置的阈值，阈值无效时不进行异常检测
 * @param temp 温度
 * @param humi 湿度
 * @param aqi 空气质量指数
 */
void add_env_data(float temp, float humi, int aqi) {
    // 检查互斥锁是否已初始化（alarm_manager_init 可能还未调用）
    if (s_alarm_mutex == NULL) {
        // 报警管理器未初始化，直接返回，不进行缓存和检测
        return;
    }
    
    // OTA 期间禁用报警处理，避免干扰 OTA
    if (mqtt_ota_is_in_progress()) {
        return;
    }

    // 添加到缓存（用于滑动平均）
    if (xSemaphoreTake(s_alarm_mutex, portMAX_DELAY) == pdTRUE) {
        g_env_cache.data[g_env_cache.index].temp = temp;
        g_env_cache.data[g_env_cache.index].humi = humi;
        g_env_cache.data[g_env_cache.index].aqi = aqi;
        g_env_cache.data[g_env_cache.index].timestamp = esp_timer_get_time() / 1000000;

        g_env_cache.index = (g_env_cache.index + 1) % ENV_CACHE_SIZE;
        if (g_env_cache.count < ENV_CACHE_SIZE) {
            g_env_cache.count++;
        }

        xSemaphoreGive(s_alarm_mutex);
    }

    // 检查阈值是否有效（必须使用服务器配置的阈值）
    if (!g_threshold_config.is_valid) {
        return;  // 阈值无效，不进行任何检测和上报
    }

    // 检查数据是否正常
    bool is_normal = check_data_normal(temp, humi, aqi);

    if (!is_normal) {
        // 数据异常，启动上报（如果还没启动）
        ESP_LOGW(TAG_ALARM, "Abnormal data: temp=%.1f, humi=%.1f, aqi=%d", temp, humi, aqi);
        start_alarm_reporting();
    }

    // 如果处于异常上报状态，则使用专门的报警主题上报数据
    if (g_alarm_reporting_active) {
        report_alarm_data(temp, humi, aqi);  // 使用 /esp32/alarm_data/server 主题
    }
}

/**
 * @brief 重置报警计数（服务器通知报警已处理后调用）
 * 管理员处理报警后，ESP32停止当前的上报，等待下次异常再触发
 */
void reset_alarm_count(void) {
    ESP_LOGI(TAG_ALARM, "Alarm handled, stopping reporting");
    
    // 停止当前的上报（管理员已处理，不需要继续上报）
    stop_alarm_reporting();
    
    // 重置异常计数器
    g_env_cache.count = 0;
    g_env_cache.index = 0;
}
