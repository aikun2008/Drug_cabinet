/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    MQ135_Task.h
  * @brief   Header for MQ135_Task.c file.
  *          This file contains the common defines of the task.
  ******************************************************************************
  */
/* USER CODE END Header */
/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MQ135_TASK_H__
#define __MQ135_TASK_H__

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "cmsis_os.h"

/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Exported types ------------------------------------------------------------*/

/* USER CODE BEGIN ET */

/* USER CODE END ET */

/* Exported constants --------------------------------------------------------*/

/* USER CODE BEGIN EC */

/* USER CODE END EC */

/* Exported macro ------------------------------------------------------------*/

/* USER CODE BEGIN EM */

/* USER CODE END EM */

/* Exported functions prototypes ---------------------------------------------*/
void MQ135Task(void * argument);
void MQ135_Task_Init(void);

/* USER CODE BEGIN EFP */

/* USER CODE END EFP */

/* Exported variables --------------------------------------------------------*/
extern osThreadId_t MQ135TaskHandle;
extern const osThreadAttr_t MQ135Task_attributes;
extern float g_co2_value;

#ifdef __cplusplus
}
#endif

#endif /* __MQ135_TASK_H__ */

