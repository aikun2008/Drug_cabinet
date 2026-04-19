#ifndef __DHT11_TASK_H
#define __DHT11_TASK_H

#include "cmsis_os.h"
#include "DHT11_HAL.h"

// 声明DHT11任务函数
void DHT11Task(void * argument);
void DHT11_Task_Init(void);
void SendEnvDataAsJson(DHT11_Data_TypeDef *dht11_data, float co2_value, uint8_t dht11_result);

#endif /* __DHT11_TASK_H */
