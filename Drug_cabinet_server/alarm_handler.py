#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报警处理模块 - 服务器端判断异常/报警
ESP32只上报数据和状态(normal/abnormal)，服务器负责判断并生成报警
"""

import json
import time
import threading
from datetime import datetime
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE_1, MYSQL_DATABASE_2

# 设备异常计数器（用于判断连续异常）
# 结构: {equipment_id: {'abnormal_count': int, 'last_abnormal_time': timestamp, 'last_alarm_time': timestamp}}
device_abnormal_counters = {}

# 报警冷却时间（秒）
ALARM_COOLDOWN_SECONDS = 300  # 5分钟

# 连续异常阈值
CONSECUTIVE_ABNORMAL_THRESHOLD = 3  # 连续3次异常升级为报警


def get_db_connection(database=MYSQL_DATABASE_2):
    """获取数据库连接"""
    import pymysql
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=database,
        cursorclass=pymysql.cursors.DictCursor
    )


def get_equipment_config(equipment_id):
    """获取设备配置（阈值）"""
    try:
        conn = get_db_connection(MYSQL_DATABASE_1)
        with conn.cursor() as cursor:
            sql = """
            SELECT temp_NOR_min, temp_NOR_max, temp_ABN_min, temp_ABN_max,
                   humi_NOR_min, humi_NOR_max, humi_ABN_min, humi_ABN_max,
                   aqi_NOR_max, aqi_ABN_max
            FROM web_equipment_config
            WHERE equipment_id = %s
            """
            cursor.execute(sql, (equipment_id,))
            result = cursor.fetchone()
            return result
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 获取设备配置失败: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()


def check_data_level(temp, humi, aqi, config):
    """
    判断数据级别
    返回: 'normal', 'abnormal', 'critical'
    """
    if not config:
        return 'normal'

    is_critical = False
    is_abnormal = False

    # 检查温度
    if temp <= config['temp_ABN_min'] or temp >= config['temp_ABN_max']:
        is_critical = True
    elif temp <= config['temp_NOR_min'] or temp >= config['temp_NOR_max']:
        is_abnormal = True

    # 检查湿度
    if humi <= config['humi_ABN_min'] or humi >= config['humi_ABN_max']:
        is_critical = True
    elif humi <= config['humi_NOR_min'] or humi >= config['humi_NOR_max']:
        is_abnormal = True

    # 检查AQI
    if aqi >= config['aqi_ABN_max']:
        is_critical = True
    elif aqi >= config['aqi_NOR_max']:
        is_abnormal = True

    if is_critical:
        return 'critical'
    elif is_abnormal:
        return 'abnormal'
    return 'normal'


def build_alarm_content(temp, humi, aqi, config):
    """构建报警内容"""
    content_parts = []

    # 温度异常
    if temp <= config['temp_ABN_min'] or temp >= config['temp_ABN_max']:
        content_parts.append(f"[温度严重异常:{temp:.1f}°C]")
    elif temp <= config['temp_NOR_min'] or temp >= config['temp_NOR_max']:
        content_parts.append(f"[温度异常:{temp:.1f}°C]")

    # 湿度异常
    if humi <= config['humi_ABN_min'] or humi >= config['humi_ABN_max']:
        content_parts.append(f"[湿度严重异常:{humi:.1f}%]")
    elif humi <= config['humi_NOR_min'] or humi >= config['humi_NOR_max']:
        content_parts.append(f"[湿度异常:{humi:.1f}%]")

    # AQI异常
    if aqi >= config['aqi_ABN_max']:
        content_parts.append(f"[空气质量严重异常:{aqi}]")
    elif aqi >= config['aqi_NOR_max']:
        content_parts.append(f"[空气质量异常:{aqi}]")

    return " ".join(content_parts) if content_parts else "环境数据异常"


def save_alarm_to_web_db(equipment_id, category, content, temp, humi, aqi):
    """保存报警记录到web_alarm_log表"""
    try:
        conn = get_db_connection(MYSQL_DATABASE_1)
        with conn.cursor() as cursor:
            insert_sql = """
            INSERT INTO web_alarm_log
            (equipment_id, alarm_category, alarm_content, temp, humi, aqi, status, save_time)
            VALUES (%s, %s, %s, %s, %s, %s, '未处理', NOW())
            """
            cursor.execute(insert_sql, (equipment_id, category, content, temp, humi, aqi))
            conn.commit()
            alarm_id = cursor.lastrowid
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [报警] 报警记录已保存到 web_alarm_log, ID: {alarm_id}")
            return alarm_id
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 保存报警记录失败: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()


def handle_environment_data(equipment_id, data):
    """
    处理环境数据，判断是否需要生成报警
    ESP32上报: {temp, humi, aqi, avg_temp, avg_humi, avg_aqi}
    注意：服务器自己判断数据级别，不依赖ESP32的status字段
    """
    global device_abnormal_counters

    temp = data.get('avg_temp', data.get('temp', 0))
    humi = data.get('avg_humi', data.get('humi', 0))
    aqi = data.get('avg_aqi', data.get('aqi', 0))

    # 获取设备配置进行判断
    config = get_equipment_config(equipment_id)
    if not config:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] 设备 {equipment_id} 无配置，跳过报警判断")
        return

    # 服务器自己判断数据级别
    level = check_data_level(temp, humi, aqi, config)
    is_normal = (level == 'normal')

    # 数据正常，重置计数器（静默处理，不打印日志）
    if is_normal:
        if equipment_id in device_abnormal_counters:
            device_abnormal_counters[equipment_id]['abnormal_count'] = 0
        return

    # 数据异常，进行判断
    # 获取或创建设备计数器
    if equipment_id not in device_abnormal_counters:
        device_abnormal_counters[equipment_id] = {
            'abnormal_count': 0,
            'last_abnormal_time': 0,
            'last_alarm_time': 0
        }

    counter = device_abnormal_counters[equipment_id]
    current_time = time.time()

    # 增加异常计数
    counter['abnormal_count'] += 1
    counter['last_abnormal_time'] = current_time

    # 检查是否满足报警条件
    if counter['abnormal_count'] >= CONSECUTIVE_ABNORMAL_THRESHOLD:
        is_first_alarm = (counter['last_alarm_time'] == 0)
        cooldown_passed = (current_time - counter['last_alarm_time']) > ALARM_COOLDOWN_SECONDS

        if is_first_alarm or cooldown_passed:
            # 确定报警分类
            if level == 'critical':
                category = '环境报警'
            else:
                category = '环境异常'

            # 构建报警内容
            content = build_alarm_content(temp, humi, aqi, config)

            # 保存报警
            alarm_id = save_alarm_to_web_db(equipment_id, category, content, temp, humi, aqi)

            if alarm_id:
                counter['last_alarm_time'] = current_time
                counter['abnormal_count'] = 0  # 重置计数
                # 只打印关键报警信息
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [报警] {equipment_id}: {category} - {content}")
        # 冷却期间不打印日志


def get_threshold_config_response(equipment_id):
    """
    获取阈值配置响应（用于响应ESP32的请求）
    返回完整的NOR和ABN阈值配置
    """
    config = get_equipment_config(equipment_id)

    if config:
        return {
            "equipment_id": equipment_id,
            "query": "threshold_config",
            # NOR范围（正常）
            "temp_NOR_min": float(config['temp_NOR_min']),
            "temp_NOR_max": float(config['temp_NOR_max']),
            "humi_NOR_min": float(config['humi_NOR_min']),
            "humi_NOR_max": float(config['humi_NOR_max']),
            "aqi_NOR_max": float(config['aqi_NOR_max']),
            # ABN范围（异常边界）
            "temp_ABN_min": float(config['temp_ABN_min']),
            "temp_ABN_max": float(config['temp_ABN_max']),
            "humi_ABN_min": float(config['humi_ABN_min']),
            "humi_ABN_max": float(config['humi_ABN_max']),
            "aqi_ABN_max": float(config['aqi_ABN_max'])
        }
    else:
        # 返回默认配置
        return {
            "equipment_id": equipment_id,
            "query": "threshold_config",
            "temp_NOR_min": 18.0,
            "temp_NOR_max": 25.0,
            "humi_NOR_min": 40.0,
            "humi_NOR_max": 70.0,
            "aqi_NOR_max": 100.0,
            "temp_ABN_min": 15.0,
            "temp_ABN_max": 30.0,
            "humi_ABN_min": 30.0,
            "humi_ABN_max": 80.0,
            "aqi_ABN_max": 200.0
        }


def reset_device_alarm_count(equipment_id):
    """重置设备的异常计数（报警被处理后调用）"""
    global device_abnormal_counters
    if equipment_id in device_abnormal_counters:
        device_abnormal_counters[equipment_id]['abnormal_count'] = 0
        device_abnormal_counters[equipment_id]['last_alarm_time'] = 0
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [报警] 设备 {equipment_id} 报警计数已重置")


# 导出函数
export_dict = {
    'handle_environment_data': handle_environment_data,
    'get_threshold_config_response': get_threshold_config_response,
    'reset_device_alarm_count': reset_device_alarm_count
}
