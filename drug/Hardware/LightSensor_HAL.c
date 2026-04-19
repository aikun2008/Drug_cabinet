#include "LightSensor_HAL.h"

/**
  * 函    数：光敏传感器初始化
  * 参    数：无
  * 返 回 值：无
  * 描    述：由于已在CubeMX中配置好PC13为上拉输入，
  *           此函数可以为空或执行额外的初始化操作
  */
void LightSensor_Init(void)
{
    // 已在MX_GPIO_Init()中完成PC13的初始化配置
    // 这里可以留空或者进行其他特殊设置
}

/**
  * 函    数：获取当前光敏传感器输出的高低电平
  * 参    数：无
  * 返 回 值：光敏传感器输出的高低电平，范围：0/1
  */
uint8_t LightSensor_Get(void)
{
    return HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_13);  // 读取PC13引脚的电平状态
}
