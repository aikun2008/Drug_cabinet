#ifndef STACKMONITOR_TASK_H
#define STACKMONITOR_TASK_H

#include "cmsis_os.h"

extern osThreadId_t stackMonitorTaskHandle;
extern const osThreadAttr_t stackMonitorTask_attributes;

void StackMonitor_Task_Init(void);

#endif
