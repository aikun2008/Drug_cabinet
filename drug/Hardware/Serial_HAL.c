#include "Serial_HAL.h"
#include "usart.h"
#include <stdarg.h>






/**
  * 函    数：串口初始化
  * 参    数：无
  * 返 回 值：无
  */
void Serial_Init(void)
{
    // USART1 已经在 usart.c 的 MX_USART1_UART_Init() 中初始化完成
    // 这里不需要重复配置，直接引用外部定义的 huart1 即可
}

/**
  * 函    数：串口发送一个字节
  * 参    数：Byte 要发送的一个字节
  * 返 回 值：无
  */
void Serial_SendByte(uint8_t Byte)
{
    HAL_UART_Transmit(&huart1, &Byte, 1, HAL_MAX_DELAY); //使用HAL库发送一个字节
}

/**
  * 函    数：串口发送一个数组
  * 参    数：Array 要发送数组的首地址
  * 参    数：Length 要发送数组的长度
  * 返 回 值：无
  */
void Serial_SendArray(uint8_t *Array, uint16_t Length)
{
    HAL_UART_Transmit(&huart1, Array, Length, HAL_MAX_DELAY);
}

/**
  * 函    数：串口发送字符串
  * 参    数：String 要发送字符串的首地址
  * 返 回 值：无
  */
void Serial_SendString(char *String)
{
    uint16_t i;
    for (i = 0; String[i] != '\0'; i++)
    {
        Serial_SendByte(String[i]);
    }
}

/**
  * 函    数：串口发送数字
  * 参    数：Number 要发送的数字
  * 参    数：Length 要发送数字的长度 1~10
  * 返 回 值：无
  */
void Serial_SendNumber(uint32_t Number, uint8_t Length)
{
    uint32_t i;
    for (i = 0; i < Length; i++)
    {
        Serial_SendByte(Number / Serial_Pow(10, Length - i - 1) % 10 + '0');
    }
}

/**
  * 函    数：次方函数
  * 参    数：Base 底数
  * 参    数：Power 指数
  * 返 回 值：底数的指数次方
  */
uint32_t Serial_Pow(uint32_t Base, uint32_t Power)
{
    uint32_t Result = 1;
    while (Power--)
    {
        Result *= Base;
    }
    return Result;
}

/**
  * 函    数：串口格式化打印
  * 参    数：format 格式化字符串
  * 参    数：... 可变参数
  * 返 回 值：无
  * 注意事项：该函数会调用stdio.h中的vsprintf函数，会占用较多资源，不建议频繁调用
  */
void Serial_Printf(char *format, ...)
{
    char String[100];
    va_list arg;
    va_start(arg, format);
    vsprintf(String, format, arg);
    va_end(arg);
    Serial_SendString(String);
}

/**
  * 函    数：串口接收一个字节
  * 参    数：无
  * 返 回 值：接收到的字节
  * 注意事项：该函数会阻塞等待，直到接收到数据
  */
uint8_t Serial_ReceiveByte(void)
{
    uint8_t Byte;
    HAL_UART_Receive(&huart1, &Byte, 1, HAL_MAX_DELAY);
    return Byte;
}

/**
  * 函    数：串口接收一个字节（非阻塞）
  * 参    数：Byte 存储接收到的字节的指针
  * 返 回 值：1表示接收到数据，0表示未接收到数据
  */
uint8_t Serial_ReceiveByteNonBlocking(uint8_t *Byte)
{
    return HAL_UART_Receive(&huart1, Byte, 1, 0) == HAL_OK;
}






