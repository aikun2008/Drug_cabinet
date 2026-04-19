#include "SG90_HAL.h"
#include "tim.h"

/**
  * 函    数：SG90舵机初始化
  * 参    数：无
  * 返 回 值：无
  * 描    述：初始化SG90舵机，启动PWM输出
  */
void SG90_Init(void)
{
    // 启动TIM2的PWM输出通道3
    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_3);
}

/**
  * 函    数：设置360°舵机转动
  * 参    数：direction 转动方向和速度，0=反转，1=停止，2=正转
  * 返 回 值：无
  * 描    述：控制360°舵机的转动方向和速度
  *           360°舵机是速度/方向控制型，而非角度控制型
  *           脉冲宽度对应关系：
  *           - 1.0ms (1000): 快速反转
  *           - 1.5ms (1500): 停止
  *           - 2.0ms (2000): 快速正转
  */
void SG90_SetAngle(uint16_t direction)
{
    uint16_t compare_value;
    
    // 根据方向设置PWM脉冲宽度
    switch(direction)
    {
        case 0:  // 反转
            compare_value = 1000;  // 1.0ms 脉冲宽度，快速反转
            break;
        case 1:  // 停止
            compare_value = 1500;  // 1.5ms 脉冲宽度，停止
            break;
        case 2:  // 正转
            compare_value = 2000;  // 2.0ms 脉冲宽度，快速正转
            break;
        default:
            compare_value = 1500;  // 默认停止
            break;
    }
    
    // 设置PWM比较值
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_3, compare_value);
}
