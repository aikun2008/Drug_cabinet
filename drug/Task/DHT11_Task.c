#include "cmsis_os.h"
#include "DHT11_HAL.h"
#include "OLED_HAL.h"
#include "MQ135_Task.h"
#include "Serial_HAL.h"
#include <stdio.h>
#include <string.h>

// DHT11任务句柄
osThreadId_t DHT11TaskHandle;

// 函数声明
void DHT11Task(void * argument);
void SendEnvDataAsJson(DHT11_Data_TypeDef *dht11_data, float co2_value, uint8_t dht11_result);

// 引用RFID任务中的卡片检测标志
extern uint8_t cardDetected;

// 引用互斥锁
extern osMutexId_t oledMutexHandle;
extern osMutexId_t co2MutexHandle;
// 初始化DHT11任务
void DHT11_Task_Init(void)
{
    // 创建DHT11任务
    const osThreadAttr_t DHT11Task_attributes = {
        .name = "DHT11Task",
        .stack_size = 150 * 4,
        .priority = (osPriority_t) osPriorityNormal,
    };
    DHT11TaskHandle = osThreadNew(DHT11Task, NULL, &DHT11Task_attributes);
}

// DHT11任务主体
void DHT11Task(void * argument)
{
    DHT11_Data_TypeDef DHT11_Data;
    char displayStr[32];
    uint8_t result;
    uint8_t retry_count = 0;
    const uint8_t MAX_RETRY = 3;  // 优化为3次重试
    
    // 显示初始信息
    if (osMutexAcquire(oledMutexHandle, 1000) == osOK) { // 等待最多1秒
        OLED_ShowString(1, 1, "   ENV MON   ");
        OLED_ShowString(2, 1, "Initializing...");
        osMutexRelease(oledMutexHandle);
    }
    
    // 给DHT11足够的初始化时间
    osDelay(1500);
    
    // 第一次尝试读取并显示传感器数据
    if (osMutexAcquire(oledMutexHandle, 1000) == osOK) { // 等待最多1秒
        
        // 清除"Initializing..."行
        OLED_ClearRow(1);  // 清除第2行
        
        // 记录当前时间，用于检测阻塞
        uint32_t start_time = HAL_GetTick();
        
        // 尝试读取DHT11数据
        retry_count = 0;
        result = ERROR;
        
        while(retry_count < MAX_RETRY)
        {
            uint32_t read_start = HAL_GetTick();
            result = Read_DHT11(&DHT11_Data);
            uint32_t read_time = HAL_GetTick() - read_start;
            
            if(result == SUCCESS)
            {
                // 成功读取，跳出循环
                break;
            }
            
            // 读取失败，增加重试计数
            retry_count++;
            osDelay(500);
        }
        
        if(result == SUCCESS)
        {
            OLED_ShowString(1, 1, "   ENV MON   ");
            // 显示温度
            sprintf(displayStr, "Temp: %2d.%1d C", DHT11_Data.temp_int, DHT11_Data.temp_deci);
            OLED_ShowString(2, 1, displayStr);
            
            // 显示湿度
            sprintf(displayStr, "Humi: %2d.%1d %%", DHT11_Data.humi_int, DHT11_Data.humi_deci);
            OLED_ShowString(3, 1, displayStr);
        }
        else
        {
            // 读取失败，显示错误信息
            OLED_ShowString(2, 1, "Temp: --.- C");
            OLED_ShowString(3, 1, "Humi: --.- %");
        }
        
        // 显示CO2浓度
        float local_co2_value = 0.0f;
        uint32_t co2_mutex_start = HAL_GetTick();
        if (osMutexAcquire(co2MutexHandle, 100) == osOK) {
            local_co2_value = g_co2_value;
            osMutexRelease(co2MutexHandle);
        }
        
        if (local_co2_value >= 0) {
            sprintf(displayStr, "AQI:  %4.0f PPM", local_co2_value);
        } else {
            sprintf(displayStr, "AQI:  ---- PPM");
        }
        OLED_ShowString(4, 1, displayStr);
        
        osMutexRelease(oledMutexHandle);
    }
    

    for(;;)
    {
        // 只有在没有检测到卡片时才更新温湿度显示
        if (!cardDetected) {
            // 尝试多次读取DHT11数据
            retry_count = 0;
            result = ERROR;
            
            // 优化重试逻辑
            while(retry_count < MAX_RETRY)
            {
                uint32_t read_start = HAL_GetTick();
                result = Read_DHT11(&DHT11_Data);
                uint32_t read_time = HAL_GetTick() - read_start;
                
                if(result == SUCCESS)
                {
                    // 成功读取，跳出循环
                    break;
                }
                
                // 读取失败，增加重试计数
                retry_count++;
                osDelay(500);  // 优化重试间隔
            }
            
            // 获取OLED互斥锁并更新显示
            uint32_t oled_mutex_start = HAL_GetTick();
            if (osMutexAcquire(oledMutexHandle, 1000) == osOK) { // 等待最多1秒
                // 安全地读取CO2值
                float local_co2_value = 0.0f;
                
                if(result == SUCCESS)
                {
                    // 显示温度
                    sprintf(displayStr, "Temp: %2d.%1d C", DHT11_Data.temp_int, DHT11_Data.temp_deci);
                    OLED_ShowString(2, 1, displayStr);
                    
                    // 显示湿度
                    sprintf(displayStr, "Humi: %2d.%1d %%", DHT11_Data.humi_int, DHT11_Data.humi_deci);
                    OLED_ShowString(3, 1, displayStr);
                } else {
                    // 读取失败，显示错误信息
                    OLED_ShowString(2, 1, "Temp: --.- C");
                    OLED_ShowString(3, 1, "Humi: --.- %");
                }
                
                // 安全地读取AQI值
                uint32_t co2_mutex_start = HAL_GetTick();
                if (osMutexAcquire(co2MutexHandle, 100) == osOK) { // 等待最多100ms
                    local_co2_value = g_co2_value;
                    osMutexRelease(co2MutexHandle);
                }
                
                // 显示AQI浓度
                if (local_co2_value >= 0) {
                    sprintf(displayStr, "AQI:  %4.0f PPM", local_co2_value);
                } else {
                    sprintf(displayStr, "AQI:  ---- PPM");
                }
                OLED_ShowString(4, 1, displayStr);
                
                // 发送JSON格式的环境数据
                SendEnvDataAsJson(&DHT11_Data, local_co2_value, result);
                
                osMutexRelease(oledMutexHandle);
            }
        }
        
        // 记录延迟开始时间
        osDelay(5000);  // 每5秒发送一次环境数据
    }
}





// 发送JSON格式的环境数据
void SendEnvDataAsJson(DHT11_Data_TypeDef *dht11_data, float co2_value, uint8_t dht11_result) {
    char json_buffer[128];
    
    if (dht11_result == SUCCESS && co2_value >= 0) {
        // 温湿度和CO2数据都有效
        float temperature = dht11_data->temp_int + (dht11_data->temp_deci / 10.0);
        float humidity = dht11_data->humi_int + (dht11_data->humi_deci / 10.0);
        sprintf(json_buffer, 
                "{\"temp\":%.1f,\"humi\":%.1f,\"AQI\":%.0f}\r\n",
                temperature, humidity, co2_value);
    } else if (dht11_result == SUCCESS) {
        // 只有温湿度数据有效
        float temperature = dht11_data->temp_int + (dht11_data->temp_deci / 10.0);
        float humidity = dht11_data->humi_int + (dht11_data->humi_deci / 10.0);
        sprintf(json_buffer, 
                "{\"temp\":%.1f,\"humi\":%.1f,\"AQI\":null}\r\n",
                temperature, humidity);
    } else if (co2_value >= 0) {
        // 只有CO2数据有效
        sprintf(json_buffer, 
                "{\"temp\":null,\"humi\":null,\"AQI\":%.0f}\r\n",
                co2_value);
    } else {
        // 数据都无效
        sprintf(json_buffer, "{\"temp\":null,\"humi\":null,\"AQI\":null}\r\n");
    }
    
    Serial_SendString(json_buffer);
}
