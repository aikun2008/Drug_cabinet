#ifndef __SERIAL_H
#define __SERIAL_H

#include "stm32f1xx_hal.h"
#include "usart.h"
#include <stdio.h>

void Serial_Init(void);
void Serial_SendByte(uint8_t Byte);
void Serial_SendArray(uint8_t *Array, uint16_t Length);
void Serial_SendString(char *String);
void Serial_SendNumber(uint32_t Number, uint8_t Length);
void Serial_Printf(char *format, ...);
uint32_t Serial_Pow(uint32_t Base, uint32_t Power);
uint8_t Serial_ReceiveByte(void);
uint8_t Serial_ReceiveByteNonBlocking(uint8_t *Byte);


#endif
