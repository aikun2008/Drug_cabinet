#ifndef __HEALTH_STATUS_TASK_H
#define __HEALTH_STATUS_TASK_H

#include "cmsis_os.h"

// 任务句柄
extern osThreadId_t healthStatusTaskHandle;

// 任务属性
extern const osThreadAttr_t healthStatusTask_attributes;

// 任务函数
void Health_Status_Task(void *argument);

// 任务初始化函数
void Health_Status_Task_Init(void);

#endif /* __HEALTH_STATUS_TASK_H */
