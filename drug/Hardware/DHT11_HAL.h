#ifndef _DHT11_HAL_H
#define _DHT11_HAL_H

#include "main.h"

// 确保Bit_SET和Bit_RESET宏定义
#ifndef Bit_SET
#define Bit_SET      1
#endif

#ifndef Bit_RESET
#define Bit_RESET    0
#endif

// 定义DHT11连接的GPIO引脚
#define DHT11_PORT       GPIOA
#define DHT11_PIN        GPIO_PIN_1

// 定义输出高电平
#define DHT11_HIGH       HAL_GPIO_WritePin(DHT11_PORT, DHT11_PIN, GPIO_PIN_SET)
// 定义输出低电平
#define DHT11_LOW        HAL_GPIO_WritePin(DHT11_PORT, DHT11_PIN, GPIO_PIN_RESET)
// 读取输入电平
#define DHT11_DATA_IN()  HAL_GPIO_ReadPin(DHT11_PORT, DHT11_PIN)
// 设置为输出模式
#define DHT11_MODE_OUT() DHT11_Mode_Out_PP()
// 设置为输入模式
#define DHT11_MODE_IN()  DHT11_Mode_IPU()

// 定义返回状态（使用标准的SUCCESS/ERROR宏）
#ifndef SUCCESS
#define SUCCESS      0
#endif

#ifndef ERROR
#define ERROR        1
#endif

// DHT11数据结构体
typedef struct {
    uint8_t humi_int;    // 湿度整数部分
    uint8_t humi_deci;   // 湿度小数部分
    uint8_t temp_int;    // 温度整数部分
    uint8_t temp_deci;   // 温度小数部分
    uint8_t check_sum;   // 校验和
} DHT11_Data_TypeDef;

// 函数声明
void DHT11_Init(void);
void Delay_us(uint32_t us);
void Delay_ms(uint32_t ms);
uint8_t Read_DHT11(DHT11_Data_TypeDef *DHT11_Data);
static void DHT11_Mode_IPU(void);
static void DHT11_Mode_Out_PP(void);
static uint8_t Read_Byte(void);

#endif
