#include "RFID_Task.h"
#include "MFRC522_HAL.h"
#include "OLED_HAL.h"
#include "Serial_HAL.h"
#include "cmsis_os.h"
#include "string.h"
#include "stdio.h"

// 全局变量定义
RFID_DataTypeDef rfidData = {0};
uint8_t cardDetected = 0;  // 卡片检测标志，0表示无卡，1表示有卡
uint32_t lastCardTime = 0; // 上次检测到卡的时间

// 任务句柄和属性
osThreadId_t rfidTaskHandle;
const osThreadAttr_t rfidTask_attributes = {
  .name = "rfidTask",
  .stack_size = 120 * 4,  // 增加堆栈大小
  .priority = (osPriority_t) osPriorityAboveNormal, // 比普通任务优先级高
};

// 引用OLED互斥锁
extern osMutexId_t oledMutexHandle;

// RFID密钥
unsigned char key[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};



/**
  * @brief  RFID任务初始化
  * @param  None
  * @retval None
  */
void RFID_Task_Init(void)
{
    // 初始化MFRC522模块
    MFRC522_Init();
    MFRC522_Reset();
    MFRC522_AntennaOn();
    
    // 初始化RFID数据结构
    memset(&rfidData, 0, sizeof(RFID_DataTypeDef));
    rfidData.state = RFID_STATE_READY;
    cardDetected = 0;  // 初始化无卡状态
}

/**
  * @brief  RFID任务函数
  * @param  argument: Not used
  * @retval None
  */
void StartRFIDTask(void *argument)
{
    unsigned char status;
    unsigned char buf[20];       // 缓冲区
    static unsigned char lastCardSN[4] = {0}; // 记录上一张卡的ID
    unsigned char i;
    unsigned char isSameCard = 1;
    const uint32_t CARD_TIMEOUT = 2000; // 卡片超时时间(毫秒)
    uint8_t shouldSendData = 0;  // 标志是否应该发送数据
    
    // 短暂延迟确保初始化完成
    osDelay(500);
    
    /* Infinite loop */
    for(;;)
    {
        // 请求卡片
        status = MFRC522_Request(PICC_REQALL, buf);
        if (status != MI_OK) {
            // 没有检测到卡片，检查是否超时
            if (cardDetected && (osKernelGetTickCount() - lastCardTime > CARD_TIMEOUT)) {
                // 卡片已移除且超时，清除卡片标志
                cardDetected = 0;
                
                // 获取OLED互斥锁并清除卡片信息显示
                if (osMutexAcquire(oledMutexHandle, osWaitForever) == osOK) {
                    OLED_ShowString(1, 1, "   ENV MON   ");  // 显示环境监测标题
                    OLED_ShowString(2, 1, "                ");
                    OLED_ShowString(3, 1, "                ");
                    OLED_ShowString(4, 1, "                ");
                    osMutexRelease(oledMutexHandle);
                }
            }
            // 没有检测到卡片，短暂延迟后继续
            osDelay(100);
        } else {
            // 防冲突获取卡号
            status = MFRC522_Anticoll(rfidData.cardSN);
            if (status == MI_OK) {
                // 更新上次检测到卡的时间
                lastCardTime = osKernelGetTickCount();
                
                // 设置卡片检测标志
                cardDetected = 1;
                
                // 检查是否为同一张卡
                isSameCard = 1;
                for(i = 0; i < 4; i++) {
                    if(lastCardSN[i] != rfidData.cardSN[i]) {
                        isSameCard = 0;
                        break;
                    }
                }
                
                // 如果不是同一张卡，则更新显示并准备发送数据
                if(!isSameCard) {
                    shouldSendData = 1;  // 标记需要发送数据
                    
                    // 保存当前卡号
                    for(i = 0; i < 4; i++) {
                        lastCardSN[i] = rfidData.cardSN[i];
                    }
                    
                    // 格式化并显示卡号
                    sprintf(rfidData.cardSNStr, "%02X%02X%02X%02X", 
                            rfidData.cardSN[0], rfidData.cardSN[1], 
                            rfidData.cardSN[2], rfidData.cardSN[3]);
                    
                    // 获取OLED互斥锁并显示卡号到OLED
                    if (osMutexAcquire(oledMutexHandle, osWaitForever) == osOK) {
                        OLED_Clear();
                        OLED_ShowString(1, 1, "ID:");
                        OLED_ShowString(2, 1, rfidData.cardSNStr);
                        OLED_ShowString(3, 1, "                ");
                        OLED_ShowString(4, 1, "                ");
                        osMutexRelease(oledMutexHandle);
                    }
                } else {
                    shouldSendData = 0;  // 相同卡片不需要发送数据
                }
                
                // 只有在新卡片时才发送JSON数据
                if(shouldSendData) {
                    Serial_Printf("{\"cardid\":\"%s\"}\r\n", rfidData.cardSNStr);
                }
            }
            // 短暂延迟避免重复读取，但不至于太慢
            osDelay(300);
        }
    }
}


