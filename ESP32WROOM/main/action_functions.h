#ifndef ACTION_FUNCTIONS_H
#define ACTION_FUNCTIONS_H

#include "cJSON.h"
#include "mqtt_client.h"

// 导入统一配置文件
#include "config.h"
#include "driver/gpio.h"

// 外部声明全局变量
extern ControlMode control_model;
extern esp_mqtt_client_handle_t s_mqtt_client;

// 函数声明
void lock_gpio_init(void);                                         // 初始化锁控制GPIO
void handle_mqtt_command(const char *payload, int payload_len);    // 处理MQTT命令消息
void publish_environment_data(void);                               // 发布环境数据到MQTT主题
void publish_environment_data_now(void);                           // 发布实时环境数据到MQTT主题
void publish_door_lock_data(void);                                 // 发布门锁数据到MQTT主题
void publish_door_lock_data_realtime(void);                        // 发布实时门锁数据到MQTT主题
void publish_medicine_operation(const char *rfid, const char *medicine_code); // 发布药品操作数据
void publish_version_info(void);                                   // 发布设备版本信息到MQTT主题
void publish_remote_operation_ack(const char *operation_type, const char *equipment_id); // 发布远程操作确认消息
bool is_local_rfid_allowed(void);                                  // 检查是否允许本地RFID操作（远程开锁后禁用，直到远程上锁）
bool is_remote_operation_active(void);                             // 检查远程操作是否激活

#endif // ACTION_FUNCTIONS_H
