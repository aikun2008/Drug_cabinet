//系统模块文件
#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_wifi.h"
#include "esp_heap_caps.h"

// 自定义模块头文件
#include "wifi_manager.h"       //Wi-Fi 连接模块
#include "uart_manager.h"       //串口模块
#include "mqtt_listener.h"      //MQTT监听模块
#include "action_functions.h"   //动作函数模块
#include "mqtt_ota_handler.h"   //MQTT OTA升级模块

// 任务堆栈大小定义（根据实际需求调整）
#define UART_TASK_STACK_SIZE        4096    // UART任务堆栈
#define NETWORK_TASK_STACK_SIZE     3072    // 网络状态任务堆栈（增加以容纳更多功能）
#define DOOR_REPORT_TASK_STACK_SIZE 2048    // 门状态上报任务堆栈
#define THRESHOLD_RETRY_STACK_SIZE  2048    // 阈值重试任务堆栈

//定义一个事件组，用于通知main函数WIFI连接成功
#define WIFI_CONNECT_BIT     BIT0
static EventGroupHandle_t   s_wifi_ev = NULL;

// 网络状态定义
typedef enum {
    NET_STATUS_OFFLINE = 0,     // 无网络
    NET_STATUS_WIFI_OK,         // WiFi已连接但MQTT未连接
    NET_STATUS_MQTT_OK          // MQTT已连接
} net_status_t;

// 当前网络状态
static net_status_t s_current_net_status = NET_STATUS_OFFLINE;

/** wifi事件通知
 * @param 无
 * @return 无
*/
void wifi_event_handler(WIFI_EV_e ev)
{if(ev == WIFI_CONNECTED){xEventGroupSetBits(s_wifi_ev,WIFI_CONNECT_BIT);}}

/**
 * @brief 网络状态监控任务
 * @param pvParameters 任务参数
 * @return 无
 */
void network_status_task(void *pvParameters) {
    net_status_t last_status = NET_STATUS_OFFLINE;
    uint32_t loop_count = 0;
    
    // 等待一段时间让系统稳定，然后直接开始发送网络状态
    vTaskDelay(pdMS_TO_TICKS(3000));
    ESP_LOGI("main", "Network status task started, stack high water mark: %lu bytes",
              (unsigned long)uxTaskGetStackHighWaterMark(NULL));
    
    while (1) {
        // 检查WiFi连接状态
        wifi_ap_record_t ap_info;
        esp_err_t wifi_status = esp_wifi_sta_get_ap_info(&ap_info);
        
        // 确定当前网络状态
        if (wifi_status != ESP_OK) {
            s_current_net_status = NET_STATUS_OFFLINE;  // WiFi未连接
        } else if (!s_is_mqtt_connected) {
            s_current_net_status = NET_STATUS_WIFI_OK;  // WiFi已连接但MQTT未连接
        } else {
            s_current_net_status = NET_STATUS_MQTT_OK;  // MQTT已连接
        }
        
        // 状态变化时发送给STM32
        if (s_current_net_status != last_status) {
            char status_char;
            switch (s_current_net_status) {
                case NET_STATUS_MQTT_OK:
                    status_char = 'C';  // Connected
                    break;
                case NET_STATUS_WIFI_OK:
                    status_char = 'D';  // Disconnected (MQTT)
                    break;
                case NET_STATUS_OFFLINE:
                default:
                    status_char = 'O';  // Offline
                    break;
            }
            mqtt_send_network_status(status_char);
            last_status = s_current_net_status;
        }
        
        // 每30秒打印一次内存和堆栈使用情况
        loop_count++;
        if (loop_count % 30 == 0) {
            ESP_LOGI("main", "Memory - Free heap: %lu bytes, Min free heap: %lu bytes",
                     (unsigned long)esp_get_free_heap_size(), (unsigned long)esp_get_minimum_free_heap_size());
            ESP_LOGI("main", "Stack high water mark: %lu bytes",
                     (unsigned long)uxTaskGetStackHighWaterMark(NULL));
        }
        
        vTaskDelay(pdMS_TO_TICKS(1000));  // 每秒检查一次
    }
}

void app_main(void)
{
    // 初始化NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());//NVS出现错误，执行擦除
        ESP_ERROR_CHECK(nvs_flash_init());//重新尝试初始化
    }
    // 创建WiFi事件组
    s_wifi_ev = xEventGroupCreate();
    EventBits_t ev = 0;
    // 初始化WIFI，传入回调函数，用于通知连接成功事件
    wifi_sta_init(wifi_event_handler);
    // 循环监听WIFI连接事件，直到WiFi连接成功后，才启动MQTT连接
    ev = xEventGroupWaitBits(s_wifi_ev, WIFI_CONNECT_BIT, pdTRUE, pdFALSE, portMAX_DELAY);
    if(ev & WIFI_CONNECT_BIT)
    {
        mqtt_listener_init();   // 初始化MQTT监听模块
    }
    uart_manager_init();        // 初始化串口模块
    lock_gpio_init();           // 初始化锁控制GPIO
    mqtt_ota_init();            // 初始化MQTT OTA升级模块
    xTaskCreatePinnedToCore(uart_event_task, "uart", UART_TASK_STACK_SIZE, NULL, 5, NULL, 1);// 创建串口事件处理任务
    xTaskCreatePinnedToCore(network_status_task, "net_status", NETWORK_TASK_STACK_SIZE, NULL, 5, NULL, 1);// 创建网络状态监控任务
    
    // 打印初始内存状态
    ESP_LOGI("main", "System initialized. Free heap: %lu bytes, Min free heap: %lu bytes",
             (unsigned long)esp_get_free_heap_size(), (unsigned long)esp_get_minimum_free_heap_size());
}
