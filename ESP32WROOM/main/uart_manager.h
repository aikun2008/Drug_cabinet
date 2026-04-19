#ifndef UART_MANAGER_H
#define UART_MANAGER_H

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/uart.h"
#include "driver/gpio.h"
#include "cJSON.h"

// 串口配置宏
#define USER_UART_NUM   UART_NUM_2
#define UART_BUFFER_SIZE        1024
#define UART_FRAME_BUFFER_SIZE  2048   // 帧缓冲区大小
#define TAGD     "uart"

// 定义UART管理器结构体
typedef struct {
    QueueHandle_t uart_queue;
    uint8_t uart_buffer[UART_BUFFER_SIZE];
    
    // 帧缓冲区，用于处理分包数据
    uint8_t frame_buffer[UART_FRAME_BUFFER_SIZE];
    uint16_t frame_buffer_index;
    uint8_t brace_count;  // 大括号计数器，用于检测完整JSON
    
    cJSON *s_env_json;       // 环境信息缓存
    cJSON *s_door_lock_json; // 门锁状态信息缓存
    cJSON *s_rfid_json;      // RFID信息缓存
    bool is_door_open;       // 门是否打开
    uint32_t door_open_start_time; // 门打开的开始时间
    uint32_t door_open_duration;   // 门打开的持续时间（秒）
} uart_manager_t;

// 外部声明全局UART管理器实例
extern uart_manager_t g_uart_manager;

// UART处理使能标志（OTA期间禁用UART处理）
extern volatile bool g_uart_processing_enabled;

// 函数声明
void uart_manager_init(void);
void uart_event_task(void *pvParameters);

#endif // UART_MODULE_H
