#include "DOOR_LOCK_Task.h"
#include "LightSensor_HAL.h"
#include "SG90_HAL.h"
#include "Serial_HAL.h"
#include "cmsis_os.h"
#include "main.h"
#include <stdio.h>
#include <string.h>

// 锁状态定义
#define LOCK_UNLOCKED 0
#define LOCK_LOCKED   1

// 门状态定义
#define DOOR_CLOSED 0
#define DOOR_OPEN  1

// 360°舵机控制定义
#define SERVO_STOP     1   // 停止
#define SERVO_FORWARD  2   // 正转（解锁方向）
#define SERVO_BACKWARD 0   // 反转（锁定方向）
#define SERVO_ROTATE_TIME 450  // 旋转时间（毫秒）- 调整为更准确的值

// 状态变量
static uint8_t door_status = DOOR_CLOSED;
static uint8_t lock_status = LOCK_LOCKED;
static uint8_t prev_door_status = DOOR_CLOSED;
static uint8_t prev_lock_status = LOCK_LOCKED;

// 任务句柄和属性定义
osThreadId_t DoorLockTaskHandle;

// 函数声明
void DOOR_LOCK_Task(void *argument);

/**
  * 函    数：DOOR_LOCK_Task_Init
  * 参    数：无
  * 返 回 值：无
  * 描    述：门锁任务初始化函数
  */
void DOOR_LOCK_Task_Init(void)
{
    // 创建门锁任务
    const osThreadAttr_t DoorLockTask_attributes = {
      .name = "DOOR_LOCK_Task",
      .stack_size = 100 * 4,
      .priority = (osPriority_t) osPriorityNormal,
    };
    DoorLockTaskHandle = osThreadNew(DOOR_LOCK_Task, NULL, &DoorLockTask_attributes);
}
/**
  * 函    数：DOOR_LOCK_Task
  * 参    数：argument 任务参数
  * 返 回 值：无
  * 描    述：门锁状态监控任务
  */
void DOOR_LOCK_Task(void *argument)
{
    // 初始化组件
    LightSensor_Init();
    SG90_Init();

    // 读取初始状态
    // 光传感器返回1表示有光（门开），返回0表示无光（门关）
    door_status = LightSensor_Get() ? DOOR_OPEN : DOOR_CLOSED;
    // PB12初始状态，用于控制锁
    uint8_t pb12_status = HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_12);
    uint8_t prev_pb12_status = pb12_status;
    prev_door_status = door_status;
    prev_lock_status = lock_status;
    
    // 发送初始状态
    DOOR_LOCK_SendStatus();
    
    // 任务主循环
    for(;;)
    {
        // 读取当前状态
        door_status = LightSensor_Get() ? DOOR_OPEN : DOOR_CLOSED;
        pb12_status = HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_12);
        
        // 检查PB12状态变化，控制锁
        // 注意：ESP32发送高电平表示开锁，低电平表示关锁
        if(pb12_status != prev_pb12_status)
        {
            if(pb12_status == GPIO_PIN_SET)
            {
                // PB12高电平，解锁（与ESP32逻辑一致）
                DOOR_LOCK_SetLockStatus(LOCK_UNLOCKED);
            }
            else
            {
                // PB12低电平，锁定
                DOOR_LOCK_SetLockStatus(LOCK_LOCKED);
            }
            prev_pb12_status = pb12_status;
        }
        
        // 检查门状态或锁状态是否发生变化
        if(door_status != prev_door_status || lock_status != prev_lock_status)
        {
            // 发送状态变更信息
            DOOR_LOCK_SendStatus();
            prev_door_status = door_status;
            prev_lock_status = lock_status;
        }

        // 每100ms检查一次状态
        osDelay(100);
    }
}

/**
  * 函    数：设置锁状态
  * 参    数：status 锁状态 LOCK_UNLOCKED 或 LOCK_LOCKED
  * 返 回 值：无
  */
void DOOR_LOCK_SetLockStatus(uint8_t status)
{
    // 保存之前的锁状态
    uint8_t old_status = lock_status;
    
    if(status == LOCK_UNLOCKED)
    {
        // 360°舵机解锁：正转一定时间
        SG90_SetAngle(SERVO_FORWARD);  // 正转
        osDelay(SERVO_ROTATE_TIME);     // 旋转指定时间
        SG90_SetAngle(SERVO_STOP);      // 停止
        lock_status = LOCK_UNLOCKED;    // 0未锁
    }
    else
    {
        // 360°舵机锁定：反转一定时间
        SG90_SetAngle(SERVO_BACKWARD);  // 反转
        osDelay(SERVO_ROTATE_TIME);     // 旋转指定时间
        SG90_SetAngle(SERVO_STOP);      // 停止
        lock_status = LOCK_LOCKED;      // 1已锁
    }
    
    // 不需要在这里更新prev_lock_status，让主循环来检测状态变化
}

/**
  * 函    数：发送门锁状态到串口
  * 参    数：无
  * 返 回 值：无
  */
void DOOR_LOCK_SendStatus(void)
{
    char status_str[100];
    
    // 格式化状态字符串为JSON格式
    // 门状态：0关，1开
    // 锁状态：0未锁，1已锁
    snprintf(status_str, sizeof(status_str), 
             "{\"Door\":%d,\"Lock\":%d}\r\n",
             (door_status == DOOR_OPEN) ? 1 : 0,
             (lock_status == LOCK_UNLOCKED) ? 0 : 1);
    
    // 发送到串口
    Serial_SendString(status_str);
}

/**
  * 函    数：获取门状态
  * 参    数：无
  * 返 回 值：DOOR_OPEN 或 DOOR_CLOSED 1和0(分别表示开和关)
  */
uint8_t DOOR_LOCK_GetDoorStatus(void)
{
    return door_status;
}

/**
  * 函    数：获取锁状态
  * 参    数：无
  * 返 回 值：LOCK_UNLOCKED 或 LOCK_LOCKED
  */
uint8_t DOOR_LOCK_GetLockStatus(void)
{
    return lock_status;
}
