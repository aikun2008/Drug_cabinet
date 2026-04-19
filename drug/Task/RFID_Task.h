#ifndef __RFID_TASK_H
#define __RFID_TASK_H

#include "cmsis_os.h"

// RFID任务句柄
extern osThreadId_t rfidTaskHandle;

// RFID任务属性
extern const osThreadAttr_t rfidTask_attributes;

// RFID状态枚举
typedef enum {
    RFID_STATE_IDLE = 0,
    RFID_STATE_READY,
    RFID_STATE_CARD_DETECTED,
    RFID_STATE_READING,
    RFID_STATE_DATA_READY,
    RFID_STATE_ERROR
} RFID_StateTypeDef;

// RFID数据结构
typedef struct {
    unsigned char cardSN[4];     // 存储卡号
    unsigned char data[16];      // 存储读取到的16字节数据
    char data2[33];              // 存储读取到的32字节数据（HEX格式）
    char cardSNStr[9];           // 卡号字符串格式
    RFID_StateTypeDef state;     // RFID状态
} RFID_DataTypeDef;

// 全局RFID数据变量
extern RFID_DataTypeDef rfidData;

// 函数声明
void RFID_Task_Init(void);
void StartRFIDTask(void *argument);

#endif /* __RFID_TASK_H */
