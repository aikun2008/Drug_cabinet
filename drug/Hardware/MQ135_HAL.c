/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    MQ135_HAL.c
  * @brief   This file provides code for the MQ135 gas sensor driver
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "MQ135_HAL.h"
#include <math.h>

/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/* Exported variables --------------------------------------------------------*/
float MQ135_Ro = MQ135_DEFAULT_RO;  // 初始化Ro值为默认值
static uint8_t mq135_connected = 1; // 默认认为传感器已连接

/* USER CODE BEGIN 1 */
#define MQ135_READ_TIMES 10  // MQ-135传感器ADC循环读取次数
/* USER CODE END 1 */

/**
  * @brief  初始化MQ135传感器
  * @retval None
  */
void MQ135_Init(void)
{
  /* ADC已在adc.c中由MX_ADC1_Init()初始化，这里不需要重复配置 */
  /* 预热传感器 - 已移除以加快启动速度 */
  // HAL_Delay(60000);  // 传感器需要预热至少1分钟以获得稳定读数
}


/**
  * @brief  检查MQ135传感器是否连接
  * @retval 1: 连接, 0: 未连接
  */
uint8_t MQ135_IsConnected(void)
{
  uint32_t adcValue = MQ135_ReadRaw();
  
  // 如果读取到的ADC值为0，可能表示传感器未连接
  if (adcValue == 0) {
    mq135_connected = 0;
  } else {
    mq135_connected = 1;
  }
  
  return mq135_connected;
}
/**
  * @brief  读取MQ135传感器的原始ADC值（单次读取）
  * @retval 原始ADC值 (0-4095)
  */
static uint32_t MQ135_ADC_Read(void)
{
  uint32_t adcValue = 0;
  
  /* 开始ADC转换 */
  if (HAL_ADC_Start(MQ135_ADC_INSTANCE) != HAL_OK)
  {
    return 0;  // 转换启动失败
  }
  
  /* 等待转换完成 */
  if (HAL_ADC_PollForConversion(MQ135_ADC_INSTANCE, 100) != HAL_OK)
  {
    HAL_ADC_Stop(MQ135_ADC_INSTANCE);
    return 0;  // 转换超时
  }
  
  /* 读取ADC值 */
  adcValue = HAL_ADC_GetValue(MQ135_ADC_INSTANCE);
  
  /* 停止ADC转换 */
  HAL_ADC_Stop(MQ135_ADC_INSTANCE);
  
  return adcValue;
}

/**
  * @brief  读取MQ135传感器的原始ADC值（多次采样求平均值）
  * @retval 原始ADC值 (0-4095)
  */
uint32_t MQ135_ReadRaw(void)
{
  uint32_t tempData = 0;
  for (uint8_t i = 0; i < MQ135_READ_TIMES; i++)
  {
    tempData += MQ135_ADC_Read();
    // 使用简单延时替代 HAL_Delay
    for(volatile int j = 0; j < 5000; j++);
  }

  tempData /= MQ135_READ_TIMES;
  return tempData;
}

/**
  * @brief  读取MQ135传感器的电压值
  * @retval 电压值
  */
float MQ135_ReadVoltage(void)
{
  uint32_t tempData = 0;
  for (uint8_t i = 0; i < MQ135_READ_TIMES; i++)
  {
    tempData += MQ135_ADC_Read();
    // 使用简单延时替代 HAL_Delay
    for(volatile int j = 0; j < 5000; j++);
  }
  tempData /= MQ135_READ_TIMES;

  float voltage = (float)tempData * MQ135_REF_VOLTAGE / MQ135_ADC_RESOLUTION;
  return voltage;
}

/**
  * @brief  计算MQ135传感器的电阻值
  * @retval 传感器电阻值 (Ω)
  */
float MQ135_GetResistance(void)
{
  uint32_t adcValue = MQ135_ReadRaw();
  
  /* 避免除以零 */
  if (adcValue == 0)
  {
    return 0.0f;
  }
  
  /* 电阻计算公式：Rs = RL * (Vcc - Vout) / Vout */
  float voltage = (float)adcValue * MQ135_REF_VOLTAGE / MQ135_ADC_RESOLUTION;
  float resistance = ((MQ135_REF_VOLTAGE - voltage) / voltage) * MQ135_DEFAULT_RLOAD;  // 使用实际负载电阻
  return resistance;
}

/**
  * @brief  获取Ro值（传感器在标准大气条件下的电阻值）
  * @retval Ro值 (Ω)
  */
float MQ135_GetRo(void)
{
  return MQ135_Ro;
}

/**
  * @brief  计算CO2浓度 (PPM) - 使用参考代码的计算方法
  * @retval CO2浓度值 (PPM)
  */
float MQ135_GetPPM_CO2(void)
{
  uint32_t tempData = 0;

  for (uint8_t i = 0; i < MQ135_READ_TIMES; i++)
  {
    tempData += MQ135_ADC_Read();
    // 使用简单延时替代 HAL_Delay
    for(volatile int j = 0; j < 5000; j++);
  }
  tempData /= MQ135_READ_TIMES;
  
  float Vol = (float)tempData * MQ135_REF_VOLTAGE / MQ135_ADC_RESOLUTION;
  float RS = ((MQ135_REF_VOLTAGE - Vol) / Vol) * MQ135_DEFAULT_RLOAD;  // 使用实际负载电阻
  
  /* CO2浓度计算公式 - 根据实际硬件调整参数
     实测清洁空气中 Rs/Ro ≈ 2.5，期望输出约400PPM
     公式: ppm = a * (Rs/Ro)^b
     通过实测数据拟合: 当 ratio=2.5 时 ppm=400; ratio=0.1 时 ppm=5000
     取 b = -1.5, 则 a = 400 / (2.5)^(-1.5) = 400 * 3.95 = 1580 */
  float ratio = RS / MQ135_Ro;
  float ppm = 1580.0f * pow(ratio, -1.5f);
  
  /* 限制PPM范围在合理区间 */
  if (ppm > 5000.0f) ppm = 5000.0f;
  if (ppm < 300.0f) ppm = 300.0f;  /* 清洁空气最低约300PPM */
  
  return ppm;
}

/**
  * @brief  计算氨气浓度 (PPM)
  * @retval 氨气浓度值 (PPM)
  */
float MQ135_GetPPM_Ammonia(void)
{
  float Rs_Ro_Ratio = MQ135_GetResistance() / MQ135_Ro;
  
  /* 氨气浓度计算公式 */
  float ppm = 574.25f * pow(Rs_Ro_Ratio, -3.819f);
  
  return ppm;
}

/**
  * @brief  计算甲苯浓度 (PPM)
  * @retval 甲苯浓度值 (PPM)
  */
float MQ135_GetPPM_Toluene(void)
{
  float Rs_Ro_Ratio = MQ135_GetResistance() / MQ135_Ro;
  
  /* 甲苯浓度计算公式 */
  float ppm = 44.947f * pow(Rs_Ro_Ratio, -3.245f);
  
  return ppm;
}

/**
  * @brief  计算丙酮浓度 (PPM)
  * @retval 丙酮浓度值 (PPM)
  */
float MQ135_GetPPM_Acetone(void)
{
  float Rs_Ro_Ratio = MQ135_GetResistance() / MQ135_Ro;
  
  /* 丙酮浓度计算公式 */
  float ppm = 33.953f * pow(Rs_Ro_Ratio, -3.117f);
  
  return ppm;
}

/**
  * @brief  校准MQ135传感器
  * @retval None
  * @note   校准时需将传感器置于标准清新空气中（CO2浓度约为400PPM）
  */
void MQ135_Calibrate(void)
{
  uint8_t sampleCount = 10;  // 增加采样次数以提高精度
  float rsSum = 0.0f;
  float rsAvg = 0.0f;
  float resistance;
  uint8_t validCount = 0;

  /* 读取多个样本并计算平均值 */
  for (uint8_t i = 0; i < sampleCount; i++)
  {
    resistance = MQ135_GetResistance();
    // 放宽过滤条件，适应1kΩ负载电阻的情况
    if (resistance > 1000.0f && resistance < 1000000.0f) {
      rsSum += resistance;
      validCount++;
    }
    HAL_Delay(100);  // 增加间隔时间确保稳定读数
  }

  if (validCount > 0) {
    rsAvg = rsSum / validCount;
  } else {
    rsAvg = MQ135_DEFAULT_RO;  // 使用默认值
  }

  /* 根据实际测量数据调整：清洁空气中 Rs ≈ 70kΩ
     期望 Rs/Ro ≈ 2.5（使CO2读数约400PPM）
     因此 Ro ≈ 70kΩ / 2.5 ≈ 28kΩ */
  float ratio = 2.5f;  // 调整比值使清洁空气CO2读数约400PPM
  MQ135_Ro = rsAvg / ratio;

  /* 确保Ro值在合理范围内（MQ135典型R0为10kΩ~100kΩ） */
  if (MQ135_Ro < 1000.0f) {
    MQ135_Ro = 1000.0f;
  } else if (MQ135_Ro > 1000000.0f) {
    MQ135_Ro = 1000000.0f;
  }
}

/* USER CODE BEGIN 2 */

/* USER CODE END 2 */
