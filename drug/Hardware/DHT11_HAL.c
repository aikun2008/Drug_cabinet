#include "DHT11_HAL.h"
#include "stm32f1xx_hal.h"
#include "string.h"

/**
  * @brief  微秒延时函数（软件延时）
  * @param  us: 延时微秒数
  * @retval 无
  */
void Delay_us(uint32_t us)
{
    // 根据实际系统时钟调整系数，这里假设72MHz系统时钟
    uint32_t i = 0;
    for(i = 0; i < us * 12; i++)
    {   
        __NOP(); // 空操作，消耗一个时钟周期
    }
}

/**
  * @brief  毫秒延时函数
  * @param  ms: 延时毫秒数
  * @retval 无
  */
void Delay_ms(uint32_t ms)
{
    HAL_Delay(ms);
}

void DHT11_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStructure;

    __HAL_RCC_GPIOA_CLK_ENABLE(); // 开启GPIOA的时钟
    GPIO_InitStructure.Pin = DHT11_PIN;
    GPIO_InitStructure.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStructure.Pull = GPIO_NOPULL;
    GPIO_InitStructure.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(DHT11_PORT, &GPIO_InitStructure);

    HAL_GPIO_WritePin(DHT11_PORT, DHT11_PIN, GPIO_PIN_SET);
    
    // DHT11上电后需要1秒以上的稳定时间
    HAL_Delay(1500);
}

static void DHT11_Mode_IPU(void)
{
    GPIO_InitTypeDef GPIO_InitStructure;
    GPIO_InitStructure.Pin = DHT11_PIN;
    GPIO_InitStructure.Mode = GPIO_MODE_INPUT;
    GPIO_InitStructure.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(DHT11_PORT, &GPIO_InitStructure);
}

static void DHT11_Mode_Out_PP(void)
{
    GPIO_InitTypeDef GPIO_InitStructure;

    GPIO_InitStructure.Pin = DHT11_PIN;
    GPIO_InitStructure.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStructure.Pull = GPIO_NOPULL;
    GPIO_InitStructure.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(DHT11_PORT, &GPIO_InitStructure);
}

static uint8_t Read_Byte(void)
{
    uint8_t i, temp = 0;
    uint32_t timeout;
    
    for(i = 0; i < 8; i++)
    {   
        // 等待DHT11拉低的50us结束，添加超时
        timeout = 1000; // 约1ms超时
        while(DHT11_DATA_IN() == GPIO_PIN_RESET && timeout--);
        if(timeout == 0) return 0xFF; // 超时返回错误
        
        // 延时40us后读取数据位
        Delay_us(40);
        
        // 判断数据位
        if(DHT11_DATA_IN() == GPIO_PIN_SET)
        {   
            // 数据位为1，等待DHT11拉低，添加超时
            timeout = 1000;
            while(DHT11_DATA_IN() == GPIO_PIN_SET && timeout--);
            if(timeout == 0) return 0xFF; // 超时返回错误
            temp |= (uint8_t)(0x01 << (7 - i));
        }
        else
        {   
            // 数据位为0，直接继续下一位
            temp &= (uint8_t) ~ (0x01 << (7 - i));
        }
    }
    
    return temp;
}

uint8_t Read_DHT11(DHT11_Data_TypeDef *DHT11_Data)
{
    uint32_t timeout;
    
    // 清除数据结构
    memset(DHT11_Data, 0, sizeof(DHT11_Data_TypeDef));
    
    // 主机发送开始信号
    DHT11_Mode_Out_PP();
    DHT11_LOW;
    Delay_ms(18);  // 拉低至少18ms

    // 主机释放总线，等待DHT11响应
    DHT11_HIGH; 
    Delay_us(30);   // 拉高20-40us

    // 切换为输入模式，准备接收DHT11的响应
    DHT11_Mode_IPU();

    // 等待DHT11响应，添加超时
    timeout = 10000; // 约10ms超时
    while(DHT11_DATA_IN() == GPIO_PIN_SET && timeout--);
    if(timeout == 0) { 
        DHT11_Mode_Out_PP();
        DHT11_HIGH;
        return ERROR;
    }
    
    // DHT11响应，等待80us低电平结束，添加超时
    timeout = 1000; // 约1ms超时
    while(DHT11_DATA_IN() == GPIO_PIN_RESET && timeout--);
    if(timeout == 0) { 
        DHT11_Mode_Out_PP();
        DHT11_HIGH;
        return ERROR;
    }
    
    // 等待80us高电平结束，准备接收数据，添加超时
    timeout = 1000; // 约1ms超时
    while(DHT11_DATA_IN() == GPIO_PIN_SET && timeout--);
    if(timeout == 0) { 
        DHT11_Mode_Out_PP();
        DHT11_HIGH;
        return ERROR;
    }
    
    // 读取数据
    DHT11_Data->humi_int = Read_Byte();
    DHT11_Data->humi_deci = Read_Byte();
    DHT11_Data->temp_int = Read_Byte();
    DHT11_Data->temp_deci = Read_Byte();
    DHT11_Data->check_sum = Read_Byte();
    
    // 恢复总线状态
    DHT11_Mode_Out_PP();
    DHT11_HIGH;
    
    // 检查是否有读取错误
    if(DHT11_Data->humi_int == 0xFF || DHT11_Data->humi_deci == 0xFF || 
       DHT11_Data->temp_int == 0xFF || DHT11_Data->temp_deci == 0xFF || 
       DHT11_Data->check_sum == 0xFF) {
        return ERROR;
    }
    
    // 校验数据
    if(DHT11_Data->check_sum == (DHT11_Data->humi_int + DHT11_Data->humi_deci + DHT11_Data->temp_int + DHT11_Data->temp_deci))
    {   
        // 验证数据合理性
        if((DHT11_Data->humi_int <= 95) && 
           (DHT11_Data->temp_int <= 60))
        {    
            return SUCCESS;
        }
        else
        {   
            return ERROR; // 数据超出合理范围
        }
    }
    else
    {   
        return ERROR; // 校验和错误
    }
}
