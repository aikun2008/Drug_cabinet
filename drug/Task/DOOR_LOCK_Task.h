#ifndef __DOOR_LOCK_TASK_H
#define __DOOR_LOCK_TASK_H

#include "main.h"
#include "cmsis_os.h"

// 门锁任务句柄
extern osThreadId_t DoorLockTaskHandle;

// 门锁任务属性
extern const osThreadAttr_t DoorLockTask_attributes;

// 锁状态定义
#define LOCK_UNLOCKED 0
#define LOCK_LOCKED   1

// 门状态定义
#define DOOR_OPEN  0
#define DOOR_CLOSED 1

void DOOR_LOCK_Task(void *argument);
void DOOR_LOCK_Task_Init(void);  // 添加初始化函数声明
void DOOR_LOCK_SetLockStatus(uint8_t status);
void DOOR_LOCK_SendStatus(void);
uint8_t DOOR_LOCK_GetDoorStatus(void);
uint8_t DOOR_LOCK_GetLockStatus(void);

#endif
