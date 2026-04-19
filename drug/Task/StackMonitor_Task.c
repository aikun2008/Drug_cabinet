#include "StackMonitor_Task.h"
#include "Serial_HAL.h"
#include "cmsis_os.h"
#include "FreeRTOS.h"
#include "task.h"
#include <stdio.h>
#include <string.h>

osThreadId_t stackMonitorTaskHandle;
// 优化堆栈监控任务的堆栈大小
const osThreadAttr_t stackMonitorTask_attributes = {
  .name = "stackMonitorTask",
  .stack_size = 120 * 4,  // 从128减小到100，因为我们只需要打印少量数据
  .priority = (osPriority_t) osPriorityNormal,
};

// 定义一个较小的任务状态数组
#define MAX_TASKS_COUNT 10
static TaskStatus_t xTaskStatusArray[MAX_TASKS_COUNT];

// 任务堆栈监控函数
void StartStackMonitorTask(void *argument);

void StackMonitor_Task_Init(void)
{
    stackMonitorTaskHandle = osThreadNew(StartStackMonitorTask, NULL, &stackMonitorTask_attributes);
}

void StartStackMonitorTask(void *argument)
{
    volatile UBaseType_t uxArraySize, x;
    char printBuffer[80];

    for(;;)
    {
        // 获取系统中所有任务的状态
        uxArraySize = uxTaskGetSystemState(xTaskStatusArray, MAX_TASKS_COUNT, NULL);

        if (uxArraySize > 0)
        {
            // 发送标题到串口
            Serial_SendString("\r\n== Task Stack ==\r\n");
            snprintf(printBuffer, sizeof(printBuffer), "%-10s %-3s %-5s\r\n", 
                     "Task", "Pri", "Free");
            Serial_SendString(printBuffer);
            Serial_SendString("------------------\r\n");

            // 遍历所有任务并打印其堆栈信息
            for (x = 0; x < uxArraySize && x < MAX_TASKS_COUNT; x++)
            {
                // 从usStackHighWaterMark获取未使用的最小堆栈空间
                uint32_t freeStack = xTaskStatusArray[x].usStackHighWaterMark * sizeof(StackType_t);
                
                snprintf(printBuffer, sizeof(printBuffer), "%-10s %-3lu %-5lu\r\n",
                         xTaskStatusArray[x].pcTaskName,
                         (unsigned long)xTaskStatusArray[x].uxCurrentPriority,
                         (unsigned long)freeStack);
                Serial_SendString(printBuffer);
            }
					  Serial_Printf("Free heap: %u bytes\r\n", xPortGetFreeHeapSize());
						Serial_Printf("Minimum heap memory: %d\n", xPortGetMinimumEverFreeHeapSize());
            Serial_SendString("===============\r\n\r\n");
        }
        else
        {
            Serial_SendString("Task state err!\r\n");
        }
        // 每隔10秒执行一次
        osDelay(50000);
    }
}
