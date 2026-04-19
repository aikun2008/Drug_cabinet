/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * File Name          : freertos.c
  * Description        : Code for freertos applications
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2025 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Includes ------------------------------------------------------------------*/
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "cmsis_os.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "DHT11_HAL.h"
#include "OLED_HAL.h"
#include "MFRC522_HAL.h"
#include "Serial_HAL.h"

#include "RFID_Task.h"
#include "DHT11_Task.h"
#include "MQ135_Task.h"
#include "StackMonitor_Task.h"
#include "DOOR_LOCK_Task.h"
#include "Health_Status_Task.h"

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
/* USER CODE BEGIN Variables */
osMutexId_t oledMutexHandle;  // OLED互斥量句柄
osMutexId_t co2MutexHandle;   // CO2值互斥量句柄

/* USER CODE END Variables */
/* Definitions for defaultTask */
osThreadId_t defaultTaskHandle;
const osThreadAttr_t defaultTask_attributes = {
  .name = "defaultTask",
  .stack_size = 128 * 4,
  .priority = (osPriority_t) osPriorityNormal,
};

/* Private function prototypes -----------------------------------------------*/
/* USER CODE BEGIN FunctionPrototypes */

/* USER CODE END FunctionPrototypes */

void StartDefaultTask(void *argument);

void MX_FREERTOS_Init(void); /* (MISRA C 2004 rule 8.1) */

/**
  * @brief  FreeRTOS initialization
  * @param  None
  * @retval None
  */
void MX_FREERTOS_Init(void) {
  /* USER CODE BEGIN Init */
  //1.硬件初始化
  Serial_Init();
  DHT11_Init(); 
  OLED_Init();
  OLED_Clear();
  
 //3.任务初始化
  RFID_Task_Init(); // 初始化RFID任务
  DHT11_Task_Init(); // 初始化DHT11任务
  MQ135_Task_Init(); // 初始化MQ135任务
  StackMonitor_Task_Init(); // 初始化堆栈监控任务
  DOOR_LOCK_Task_Init(); // 初始化门锁任务
  Health_Status_Task_Init(); // 初始化健康状态任务
  /* USER CODE END Init */

  /* USER CODE BEGIN RTOS_MUTEX */
  /* add mutexes, ... */
  //系统资源初始化
  // 创建OLED互斥锁
  oledMutexHandle = osMutexNew(NULL);
  // 创建CO2值互斥锁
  co2MutexHandle = osMutexNew(NULL);
  /* USER CODE END RTOS_MUTEX */

  /* USER CODE BEGIN RTOS_SEMAPHORES */
  /* add semaphores, ... */
  /* USER CODE END RTOS_SEMAPHORES */

  /* USER CODE BEGIN RTOS_TIMERS */
  /* start timers, add new ones, ... */
  /* USER CODE END RTOS_TIMERS */

  /* USER CODE BEGIN RTOS_QUEUES */
  /* add queues, ... */
  /* USER CODE END RTOS_QUEUES */

  /* Create the thread(s) */
  /* creation of defaultTask */
  defaultTaskHandle = osThreadNew(StartDefaultTask, NULL, &defaultTask_attributes);

  /* USER CODE BEGIN RTOS_THREADS */
  /* add threads, ... */
 
  rfidTaskHandle = osThreadNew(StartRFIDTask, NULL, &rfidTask_attributes); // 创建RFID任务


  MQ135TaskHandle = osThreadNew(MQ135Task, NULL, &MQ135Task_attributes); // 创建MQ135任务
  // DoorLockTaskHandle = osThreadNew(DOOR_LOCK_Task, NULL, &DoorLockTask_attributes); // 创建门锁任务（已移至DOOR_LOCK_Task_Init函数中）
  /* USER CODE END RTOS_THREADS */

  /* USER CODE BEGIN RTOS_EVENTS */
  /* add events, ... */
  /* USER CODE END RTOS_EVENTS */

}

/* USER CODE BEGIN Header_StartDefaultTask */
/**
  * @brief  Function implementing the defaultTask thread.
  * @param  argument: Not used
  * @retval None
  */
/* USER CODE END Header_StartDefaultTask */
void StartDefaultTask(void *argument)
{
  /* USER CODE BEGIN StartDefaultTask */
  /* Infinite loop */
  for(;;)
  {
    osDelay(5000);
  }
  /* USER CODE END StartDefaultTask */
}

/* Private application code --------------------------------------------------*/
/* USER CODE BEGIN Application */

/* USER CODE END Application */

