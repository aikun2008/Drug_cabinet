#include "cmsis_os.h"
#include "MQ135_Task.h"
#include "MQ135_HAL.h"
#include "Serial_HAL.h"
#include <stdio.h>
#include <string.h>

// 全局变量定义
float g_co2_value = 0.0f;    // 共享的CO2浓度变量

// 任务句柄和属性
osThreadId_t MQ135TaskHandle;
const osThreadAttr_t MQ135Task_attributes = {
  .name = "MQ135Task",
  .stack_size = 128 * 4,
  .priority = (osPriority_t) osPriorityBelowNormal,
};

// 引用互斥锁
extern osMutexId_t co2MutexHandle;

// 标志位
static uint8_t mq135_needs_calibration = 1;  // 是否需要校准

/**
  * @brief  初始化MQ135任务
  * @param  None
  * @retval None
  */
void MQ135_Task_Init(void)
{
  /* 初始化MQ135传感器 */
  //Serial_Printf("Initializing MQ135 Sensor...\r\n");
  MQ135_Init();  // 不再包含预热过程
  //Serial_Printf("MQ135 Sensor Ready!\r\n");
  
  // 标记需要校准，但不在这里执行
  mq135_needs_calibration = 1;
}

/**
  * @brief  MQ135任务函数
  * @param  argument: Not used
  * @retval None
  */
void MQ135Task(void * argument)
{
  float co2_value = 0.0f;
  uint32_t loop_count = 0;

  /* Infinite loop */
  for(;;)
  {
    loop_count++;

    // 直接读取ADC值，不检查连接状态
    uint32_t adc_raw = MQ135_ReadRaw();

    // 如果ADC值为0，可能传感器未连接
    if (adc_raw == 0) {
      g_co2_value = -1.0f;
    } else {
      // 第一次运行时进行校准
      if (mq135_needs_calibration) {
        MQ135_Calibrate();
        mq135_needs_calibration = 0;
      }

      // 读取MQ135传感器数据
      co2_value = MQ135_GetPPM_CO2();

      // 更新共享变量
      g_co2_value = co2_value;
    }

    osDelay(3000);  // 3秒间隔
  }
}
