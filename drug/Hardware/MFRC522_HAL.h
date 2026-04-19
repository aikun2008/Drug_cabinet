#ifndef __MFRC522_HAL_H
#define __MFRC522_HAL_H

#include "stm32f1xx_hal.h"
#include "cmsis_os.h"

/***************** MFRC522 外设定义 ******************
 * 文件名     : MFRC522_HAL.h                   
 * 版本       : V1.0
 * MCU        : STM32F1系列
 ******************************************************/

/*************** GPIO 引脚定义 ****************/
// MFRC522 SPI 接口 GPIO 定义
#define MFRC522_GPIO_SDA_PORT                  GPIOB
#define MFRC522_GPIO_SDA_PIN                   GPIO_PIN_7

#define MFRC522_GPIO_SCK_PORT                  GPIOB
#define MFRC522_GPIO_SCK_PIN                   GPIO_PIN_6

#define MFRC522_GPIO_MOSI_PORT                 GPIOB
#define MFRC522_GPIO_MOSI_PIN                  GPIO_PIN_5

#define MFRC522_GPIO_MISO_PORT                 GPIOB
#define MFRC522_GPIO_MISO_PIN                  GPIO_PIN_4

#define MFRC522_GPIO_RST_PORT                  GPIOB
#define MFRC522_GPIO_RST_PIN                   GPIO_PIN_3

/********************* 控制信号宏定义 **********************/
#define MFRC522_SDA_L           HAL_GPIO_WritePin(MFRC522_GPIO_SDA_PORT, MFRC522_GPIO_SDA_PIN, GPIO_PIN_RESET)
#define MFRC522_SDA_H           HAL_GPIO_WritePin(MFRC522_GPIO_SDA_PORT, MFRC522_GPIO_SDA_PIN, GPIO_PIN_SET)

#define MFRC522_RST_L           HAL_GPIO_WritePin(MFRC522_GPIO_RST_PORT, MFRC522_GPIO_RST_PIN, GPIO_PIN_RESET)
#define MFRC522_RST_H           HAL_GPIO_WritePin(MFRC522_GPIO_RST_PORT, MFRC522_GPIO_RST_PIN, GPIO_PIN_SET)

#define MFRC522_SCK_L           HAL_GPIO_WritePin(MFRC522_GPIO_SCK_PORT, MFRC522_GPIO_SCK_PIN, GPIO_PIN_RESET)
#define MFRC522_SCK_H           HAL_GPIO_WritePin(MFRC522_GPIO_SCK_PORT, MFRC522_GPIO_SCK_PIN, GPIO_PIN_SET)

#define MFRC522_MOSI_L          HAL_GPIO_WritePin(MFRC522_GPIO_MOSI_PORT, MFRC522_GPIO_MOSI_PIN, GPIO_PIN_RESET)
#define MFRC522_MOSI_H          HAL_GPIO_WritePin(MFRC522_GPIO_MOSI_PORT, MFRC522_GPIO_MOSI_PIN, GPIO_PIN_SET)

#define MFRC522_MISO_READ       HAL_GPIO_ReadPin(MFRC522_GPIO_MISO_PORT, MFRC522_GPIO_MISO_PIN)

/////////////////////////////////////////////////////////////////////
//MF522命令字
/////////////////////////////////////////////////////////////////////
#define PCD_IDLE              0x00               //取消当前命令
#define PCD_AUTHENT           0x0E               //验证密钥
#define PCD_RECEIVE           0x08               //接收数据
#define PCD_TRANSMIT          0x04               //发送数据
#define PCD_TRANSCEIVE        0x0C               //发送并接收数据
#define PCD_RESETPHASE        0x0F               //复位
#define PCD_CALCCRC           0x03               //CRC计算

/////////////////////////////////////////////////////////////////////
//Mifare_One卡片命令字
/////////////////////////////////////////////////////////////////////
#define PICC_REQIDL           0x26               //寻天线区内未休眠状态的卡
#define PICC_REQALL           0x52               //寻天线区内所有卡
#define PICC_ANTICOLL1        0x93               //防冲撞1
#define PICC_ANTICOLL2        0x95               //防冲撞2
#define PICC_AUTHENT1A        0x60               //验证A密钥
#define PICC_AUTHENT1B        0x61               //验证B密钥
#define PICC_READ             0x30               //读块
#define PICC_WRITE            0xA0               //写块
#define PICC_DECREMENT        0xC0               //减值
#define PICC_INCREMENT        0xC1               //增值
#define PICC_RESTORE          0xC2               //调块数据到缓冲区
#define PICC_TRANSFER         0xB0               //保存缓冲区数据
#define PICC_HALT             0x50               //休眠

/////////////////////////////////////////////////////////////////////
//MF522 FIFO长度定义
/////////////////////////////////////////////////////////////////////
#define DEF_FIFO_LENGTH       64                 //FIFO size=64byte
#define MAXRLEN               18

/////////////////////////////////////////////////////////////////////
//MF522寄存器定义
/////////////////////////////////////////////////////////////////////
// PAGE 0
#define RFU00                 0x00    
#define CommandReg            0x01    
#define ComIEnReg             0x02    
#define DivlEnReg             0x03    
#define ComIrqReg             0x04    
#define DivIrqReg             0x05
#define ErrorReg              0x06    
#define Status1Reg            0x07    
#define Status2Reg            0x08    
#define FIFODataReg           0x09
#define FIFOLevelReg          0x0A
#define WaterLevelReg         0x0B
#define ControlReg            0x0C
#define BitFramingReg         0x0D
#define CollReg               0x0E
#define RFU0F                 0x0F
// PAGE 1     
#define RFU10                 0x10
#define ModeReg               0x11
#define TxModeReg             0x12
#define RxModeReg             0x13
#define TxControlReg          0x14
#define TxAutoReg             0x15
#define TxSelReg              0x16
#define RxSelReg              0x17
#define RxThresholdReg        0x18
#define DemodReg              0x19
#define RFU1A                 0x1A
#define RFU1B                 0x1B
#define MifareReg             0x1C
#define RFU1D                 0x1D
#define RFU1E                 0x1E
#define SerialSpeedReg        0x1F
// PAGE 2    
#define RFU20                 0x20  
#define CRCResultRegM         0x21
#define CRCResultRegL         0x22
#define RFU23                 0x23
#define ModWidthReg           0x24
#define RFU25                 0x25
#define RFCfgReg              0x26
#define GsNReg                0x27
#define CWGsCfgReg            0x28
#define ModGsCfgReg           0x29
#define TModeReg              0x2A
#define TPrescalerReg         0x2B
#define TReloadRegH           0x2C
#define TReloadRegL           0x2D
#define TCounterValueRegH     0x2E
#define TCounterValueRegL     0x2F
// PAGE 3      
#define RFU30                 0x30
#define TestSel1Reg           0x31
#define TestSel2Reg           0x32
#define TestPinEnReg          0x33
#define TestPinValueReg       0x34
#define TestBusReg            0x35
#define AutoTestReg           0x36
#define VersionReg            0x37
#define AnalogTestReg         0x38
#define TestDAC1Reg           0x39  
#define TestDAC2Reg           0x3A   
#define TestADCReg            0x3B   
#define RFU3C                 0x3C   
#define RFU3D                 0x3D   
#define RFU3E                 0x3E   
#define RFU3F                 0x3F

/////////////////////////////////////////////////////////////////////
//MF522错误代码
/////////////////////////////////////////////////////////////////////
#define MI_OK                 0x26
#define MI_NOTAGERR           0xcc
#define MI_ERR                0xbb

/////////////////////////////////////////////////////////////////////
//其他定义
/////////////////////////////////////////////////////////////////////
#define macDummy_Data         0x00

// 函数声明
void MFRC522_Init(void);
char MFRC522_Reset(void);
void Write_MFRC522(unsigned char Address, unsigned char value);
unsigned char Read_MFRC522(unsigned char Address);  
void MFRC522_AntennaOn(void);
void MFRC522_AntennaOff(void);
char MFRC522_Request(unsigned char req_code, unsigned char *pTagType);
char MFRC522_Anticoll(unsigned char *pSnr);
char MFRC522_SelectTag(unsigned char *pSnr);
char MFRC522_AuthState(unsigned char auth_mode, unsigned char addr, unsigned char *pKey, unsigned char *pSnr);
char MFRC522_Read(unsigned char addr, unsigned char *pData);
char MFRC522_Halt(void);
char MFRC522_Write(unsigned char addr, unsigned char *pData);

#endif /* __MFRC522_HAL_H */
