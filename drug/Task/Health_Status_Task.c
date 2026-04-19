#include "Health_Status_Task.h"
#include "cmsis_os.h"
#include "Serial_HAL.h"
#include "gpio.h"

// 任务句柄
osThreadId_t healthStatusTaskHandle;

// 任务属性
const osThreadAttr_t healthStatusTask_attributes = {
  .name = "healthStatusTask",
  .stack_size = 128 * 4,
  .priority = (osPriority_t) osPriorityNormal,
};

// 当前健康状态
static uint8_t currentHealthStatus = 'N'; // N-正常, Y-异常(黄色), R-报警(红色)
// 当前网络状态
static uint8_t currentNetworkStatus = 'O'; // O-离线, D-有网无服务, C-正常连接

// LED引脚定义
#define BLUE_LED_PIN    GPIO_PIN_11  // PA11 - 蓝灯（网络状态）
#define YELLOW_LED_PIN  GPIO_PIN_12  // PA12 - 黄灯（健康状态-异常）
#define RED_LED_PIN     GPIO_PIN_15  // PA15 - 红灯（健康状态-报警）

// 蜂鸣器引脚定义
#define BUZZER_PIN      GPIO_PIN_1   // PB1 - 蜂鸣器（报警时响）

/**
  * 函    数：健康状态任务
  * 参    数：argument 任务参数
  * 返 回 值：无
  */
void Health_Status_Task(void *argument)
{
  uint8_t command;
  uint8_t healthLedState = 0; // 健康状态LED状态 0-灭, 1-亮
  uint8_t networkLedState = 0; // 网络状态LED状态 0-灭, 1-亮
  uint32_t networkBlinkCount = 0; // 网络状态闪烁计数器
  uint32_t healthBlinkCount = 0;  // 健康状态闪烁计数器
  uint32_t buzzerBlinkCount = 0;  // 蜂鸣器闪烁计数器
  
  // 发送就绪信号给ESP32
  Serial_SendByte('S');
  
  for(;;)
  {
    // 非阻塞方式检查是否有新命令
    if(Serial_ReceiveByteNonBlocking(&command))
    {
      // 处理健康状态命令
      if(command == 'Y' || command == 'R' || command == 'N')
      {
        currentHealthStatus = command;
        healthLedState = 0;
        healthBlinkCount = 0;
      }
      // 处理网络状态命令
      else if(command == 'C' || command == 'D' || command == 'O')
      {
        currentNetworkStatus = command;
        networkLedState = 0;
        networkBlinkCount = 0;
      }
    }
    
    // 处理健康状态LED（黄/红）- 互斥控制
    switch(currentHealthStatus)
    {
      case 'Y': // 黄色闪烁（异常）
        // 先关闭红灯（互斥）
        HAL_GPIO_WritePin(GPIOA, RED_LED_PIN, GPIO_PIN_RESET);
        
        // 黄灯闪烁（200ms周期）
        if(healthBlinkCount >= 2) // 100ms * 2 = 200ms
        {
          healthBlinkCount = 0;
          if(healthLedState)
          {
            HAL_GPIO_WritePin(GPIOA, YELLOW_LED_PIN, GPIO_PIN_RESET);
            healthLedState = 0;
          }
          else
          {
            HAL_GPIO_WritePin(GPIOA, YELLOW_LED_PIN, GPIO_PIN_SET);
            healthLedState = 1;
          }
        }
        break;
        
      case 'R': // 红色闪烁（报警）
        // 先关闭黄灯（互斥）
        HAL_GPIO_WritePin(GPIOA, YELLOW_LED_PIN, GPIO_PIN_RESET);
        
        // 红灯闪烁（200ms周期，快速闪烁）
        if(healthBlinkCount >= 2) // 100ms * 2 = 200ms
        {
          healthBlinkCount = 0;
          if(healthLedState)
          {
            HAL_GPIO_WritePin(GPIOA, RED_LED_PIN, GPIO_PIN_RESET);
            healthLedState = 0;
          }
          else
          {
            HAL_GPIO_WritePin(GPIOA, RED_LED_PIN, GPIO_PIN_SET);
            healthLedState = 1;
          }
        }
        
        // 蜂鸣器控制（每1秒响一次，每次响0.2秒）
        if(buzzerBlinkCount >= 10) // 100ms * 10 = 1秒
        {
          buzzerBlinkCount = 0;
        }
        
        // 当计数器为0-1时（0.2秒），蜂鸣器响
        if(buzzerBlinkCount < 2)
        {
          HAL_GPIO_WritePin(GPIOB, BUZZER_PIN, GPIO_PIN_RESET); // 蜂鸣器响
        }
        else
        {
          HAL_GPIO_WritePin(GPIOB, BUZZER_PIN, GPIO_PIN_SET); // 蜂鸣器关闭
        }
        break;
        
      case 'N': // 正常，关闭黄/红LED和蜂鸣器
      default:
        HAL_GPIO_WritePin(GPIOA, YELLOW_LED_PIN, GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOA, RED_LED_PIN, GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOB, BUZZER_PIN, GPIO_PIN_SET); // 确保蜂鸣器关闭
        healthLedState = 0;
        break;
    }
    
    // 处理网络状态LED（蓝色）- 独立控制
    switch(currentNetworkStatus)
    {
      case 'C': // MQTT已连接 - 蓝灯常亮
        HAL_GPIO_WritePin(GPIOA, BLUE_LED_PIN, GPIO_PIN_SET);
        networkLedState = 1;
        break;
        
      case 'D': // 有网络但MQTT未连接 - 蓝灯慢闪（1秒周期）
        if(networkBlinkCount >= 10) // 100ms * 10 = 1秒
        {
          networkBlinkCount = 0;
          if(networkLedState)
          {
            HAL_GPIO_WritePin(GPIOA, BLUE_LED_PIN, GPIO_PIN_RESET);
            networkLedState = 0;
          }
          else
          {
            HAL_GPIO_WritePin(GPIOA, BLUE_LED_PIN, GPIO_PIN_SET);
            networkLedState = 1;
          }
        }
        networkBlinkCount++;
        break;
        
      case 'O': // 无网络 - 蓝灯熄灭
      default:
        HAL_GPIO_WritePin(GPIOA, BLUE_LED_PIN, GPIO_PIN_RESET);
        networkLedState = 0;
        networkBlinkCount = 0;
        break;
    }
    
    healthBlinkCount++;
    buzzerBlinkCount++;
    osDelay(100);
  }
}

/**
  * 函    数：健康状态任务初始化
  * 参    数：无
  * 返 回 值：无
  */
void Health_Status_Task_Init(void)
{
  // 初始化LED引脚
  GPIO_InitTypeDef GPIO_InitStructure;
  
  // 开启GPIOA和GPIOB时钟
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();
  
  // 配置PA11（蓝色-网络状态）
  GPIO_InitStructure.Pin = BLUE_LED_PIN;
  GPIO_InitStructure.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStructure.Speed = GPIO_SPEED_FREQ_HIGH;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStructure);
  HAL_GPIO_WritePin(GPIOA, BLUE_LED_PIN, GPIO_PIN_RESET);
  
  // 配置PA12（黄色-健康状态异常）
  GPIO_InitStructure.Pin = YELLOW_LED_PIN;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStructure);
  HAL_GPIO_WritePin(GPIOA, YELLOW_LED_PIN, GPIO_PIN_RESET);
  
  // 配置PA15（红色-健康状态报警）
  GPIO_InitStructure.Pin = RED_LED_PIN;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStructure);
  HAL_GPIO_WritePin(GPIOA, RED_LED_PIN, GPIO_PIN_RESET);
  
  // 配置PB1（蜂鸣器）
  GPIO_InitStructure.Pin = BUZZER_PIN;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStructure);
  HAL_GPIO_WritePin(GPIOB, BUZZER_PIN, GPIO_PIN_SET);
  
  // 创建健康状态任务
  healthStatusTaskHandle = osThreadNew(Health_Status_Task, NULL, &healthStatusTask_attributes);
}
