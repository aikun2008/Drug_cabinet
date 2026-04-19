#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include "esp_err.h"

// WiFi事件类型
typedef enum {
    WIFI_CONNECTED,
    WIFI_DISCONNECTED
} WIFI_EV_e;

// WiFi事件回调函数类型
typedef void (*wifi_event_cb)(WIFI_EV_e ev);

/**
 * @brief 初始化WiFi STA模式
 * @param f WiFi事件回调函数
 * @return esp_err_t 初始化结果
 */
esp_err_t wifi_sta_init(wifi_event_cb f);

#endif // WIFI_MANAGER_H