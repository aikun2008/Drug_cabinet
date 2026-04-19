/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    MQ135_HAL.h
  * @brief   This file contains all the function prototypes and definitions for
  *          the MQ135 gas sensor driver
  ******************************************************************************
  */
/* USER CODE END Header */
/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MQ135_HAL_H__
#define __MQ135_HAL_H__

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "adc.h"

/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Exported defines ----------------------------------------------------------*/
#define MQ135_ADC_CHANNEL     ADC_CHANNEL_2  // PA2 对应 ADC1_IN2
#define MQ135_ADC_INSTANCE    &hadc1         // ADC1 句柄
#define MQ135_ADC_RESOLUTION  4096          // 12位ADC分辨率
#define MQ135_REF_VOLTAGE     4.2f          // 参考电压（实际供电4.2V）
#define MQ135_DEFAULT_RLOAD   1000.0f       // 负载电阻 1kΩ（实测0.99kΩ）
#define MQ135_DEFAULT_RO      10000.0f      // 默认R0值 10kΩ（将根据校准调整）

/* USER CODE BEGIN Private defines */

/* USER CODE END Private defines */

/* Exported types ------------------------------------------------------------*/

/* USER CODE BEGIN ET */

/* USER CODE END ET */

/* Exported variables --------------------------------------------------------*/

extern float MQ135_Ro;  // 传感器在标准大气条件下的电阻值

/* USER CODE BEGIN EV */

/* USER CODE END EV */

/* Exported functions prototypes ---------------------------------------------*/
void MQ135_Init(void);
uint32_t MQ135_ReadRaw(void);
float MQ135_ReadVoltage(void);
float MQ135_GetResistance(void);
float MQ135_GetRo(void);
float MQ135_GetPPM_CO2(void);
float MQ135_GetPPM_Ammonia(void);
float MQ135_GetPPM_Toluene(void);
float MQ135_GetPPM_Acetone(void);
void MQ135_Calibrate(void);
uint8_t MQ135_IsConnected(void);  // 新增函数声明

/* USER CODE BEGIN Prototypes */

/* USER CODE END Prototypes */

#ifdef __cplusplus
}
#endif

#endif /* __MQ135_HAL_H__ */
