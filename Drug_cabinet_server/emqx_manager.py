"""
EMQX连接管理器
负责在应用启动时自动连接EMQX，并在整个应用生命周期内保持连接
参考MQTT.py实现，优化连接稳定性和功能
"""
import paho.mqtt.client as mqtt
import time
import base64
from datetime import datetime
import json
import pymysql
import requests
import threading
from requests.auth import HTTPBasicAuth
# 导入配置
from config import (
    EMQX_BROKER_IP, EMQX_BROKER_PORT, EMQX_USERNAME, EMQX_PASSWORD, EMQX_CLIENT_ID,
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE_1, MYSQL_DATABASE_2,
    EMQX_DASHBOARD_USERNAME, EMQX_DASHBOARD_PASSWORD, EMQX_API_KEY, EMQX_API_SECRET, EMQX_API_BASE_URL
)
# 导入健康状态评估函数
from admin_equip_config import evaluate_equipment_health_status
# 导入报警处理模块
from alarm_handler import export_dict as alarm_handler_export
handle_environment_data = alarm_handler_export['handle_environment_data']
get_threshold_config_response = alarm_handler_export['get_threshold_config_response']
reset_device_alarm_count = alarm_handler_export['reset_device_alarm_count']

# 主题常量定义 - 系统级默认订阅主题
DEFAULT_SUBSCRIBE_TOPICS = [
    ("/esp32/environment_data/server", 0),
    ("/esp32/rfid_data/server", 0),
    ("/esp32/door_lock_data/server", 0),
    ("/esp32/medicine_operation/server", 0),
    ("/esp32/ota_status/server", 0),
    ("/esp32/alarm_data/server", 1),       # 订阅报警数据（主动上报）
    ("/esp32/device_request/server", 1),   # 订阅设备请求（阈值配置等）
    ("/esp32/ota/request/+", 1),          # 订阅所有设备的OTA请求
    ("/esp32/ota/ack/+", 1)                # 订阅所有设备的OTA确认
]
# 设备实时数据查询相关主题
TOPIC_ENVIRONMENT_DATA_NOW = "/esp32/environment_data_now/server"#eg: 预期返回 {"time": "2025/11/11 02:37:35", "equipment_id": "cabinet_002", "temp": 21.5, "humi": 48.2, "AQI": 1}
TOPIC_DOOR_LOCK_DATA_NOW = "/esp32/door_lock_data_now/server"#eg：预期返回 {"time": "2025/11/11 02:37:35", "equipment_id": "cabinet_002", "door": 0, "lock": 1, "buzzer": 0}
TOPIC_PUBLISH_COMMAND = "/server/command/esp32" #eg: {"equipment_id": equipment_id,"query": "environment_data_now"} 查询设备实时数据

# MQTT OTA 相关主题
TOPIC_OTA_REQUEST = "/esp32/ota/request/{}"      # 设备->服务器: 请求数据包
TOPIC_OTA_ACK = "/esp32/ota/ack/{}"              # 设备->服务器: 确认收到

class EMQXManager:
    """EMQX连接管理器类"""   
    def __init__(self):
        self.client = None
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5  # 重连延迟（秒）     
        # EMQX配置
        self.broker_ip = EMQX_BROKER_IP
        self.broker_port = EMQX_BROKER_PORT
        self.username = EMQX_USERNAME
        self.password = EMQX_PASSWORD
        self.client_id = EMQX_CLIENT_ID
        # EMQX REST API配置 - 使用v5版本
        self.emqx_api_base_url = EMQX_API_BASE_URL
        # EMQX Dashboard默认凭据
        self.emqx_api_username = EMQX_DASHBOARD_USERNAME
        self.emqx_api_password = EMQX_DASHBOARD_PASSWORD
        # EMQX 5.x API密钥
        self.emqx_api_key = EMQX_API_KEY
        self.emqx_api_secret = EMQX_API_SECRET
        # 设备占用状态跟踪（确保同一时间只有一个设备在使用）
        self.device_usage_status = {}  # key: equipment_id, value: session_id
        # 记录设备最近开门时间，避免误触发会话结束
        self.device_last_open_time = {}  # key: equipment_id, value: timestamp
        # 线程池用于异步处理MQTT消息
        from concurrent.futures import ThreadPoolExecutor
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="mqtt_handler")
        # 定时任务相关
        self.periodic_query_timer = None
        self.periodic_query_interval = 30 * 60  # 30分钟（秒）
        self.periodic_query_running = False
        
    def _is_device_exist(self, equipment_id):
        """验证设备是否存在"""
        try:
            conn = self.get_db_connection(MYSQL_DATABASE_1)
            try:
                with conn.cursor() as cursor:
                    sql = "SELECT COUNT(*) as count FROM web_equipment WHERE equipment_id = %s"
                    cursor.execute(sql, (equipment_id,))
                    result = cursor.fetchone()
                    return result and result['count'] > 0
            finally:
                conn.close()
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 验证设备存在性时出错: {str(e)}")
            return False
            
    def _is_device_available(self, equipment_id):
        """检查设备是否可用（未被占用）"""
        return equipment_id not in self.device_usage_status
        
    def _get_session_user_by_equipment(self, equipment_id):
        """获取设备当前会话的用户信息"""
        try:
            conn = self.get_db_connection(MYSQL_DATABASE_1)
            try:
                with conn.cursor() as cursor:
                    # 查询最新的用户操作记录来获取当前会话的用户
                    sql = """
                        SELECT rfid_card_id, operation_type, target_id, description 
                        FROM user_operations 
                        WHERE equipment_id = %s 
                        AND operation_time > DATE_SUB(NOW(), INTERVAL 10 MINUTE)
                        AND operation_type IN ('access_granted', 'rfid_validated')
                        ORDER BY operation_time DESC 
                        LIMIT 1
                    """
                    cursor.execute(sql, (equipment_id,))
                    result = cursor.fetchone()
                    
                    if result:
                        # 获取用户信息，通过rfid_card_id查找
                        user_sql = "SELECT id, username, rfid_card_id FROM web_user WHERE rfid_card_id = %s"
                        cursor.execute(user_sql, (result['rfid_card_id'],))
                        user_info = cursor.fetchone()
                        return user_info
                    
                    return None
            finally:
                conn.close()
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 获取会话用户信息时出错: {str(e)}")
            return None
        
    def _validate_rfid_user(self, rfid):
        """验证RFID用户是否存在且启用"""
        try:
            conn = self.get_db_connection(MYSQL_DATABASE_1)
            try:
                with conn.cursor() as cursor:
                    # 查询用户信息，包含rfid_card_id字段
                    sql = "SELECT id, username, role, status, rfid_card_id FROM web_user WHERE rfid_card_id = %s AND status = 1"
                    cursor.execute(sql, (rfid,))
                    user_info = cursor.fetchone()
                    return user_info
            finally:
                conn.close()
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 验证RFID用户时出错: {str(e)}")
            return None
            
    def _log_access_denied(self, equipment_id, rfid):
        """记录拒绝访问的操作"""
        try:
            conn = self.get_db_connection(MYSQL_DATABASE_1)
            try:
                with conn.cursor() as cursor:
                    # 插入操作记录，使用rfid_card_id作为用户标识，target_id为空（仅拒绝访问）
                    log_sql = """
                        INSERT INTO user_operations 
                        (operation_time, rfid_card_id, operation_type, equipment_id, target_id, description)
                        VALUES (NOW(), %s, 'access_denied', %s, %s, %s)
                    """
                    description = f"RFID卡 {rfid} 尝试访问设备 {equipment_id} 被拒绝"
                    cursor.execute(log_sql, (rfid, equipment_id, None, description))
                    conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 记录拒绝访问操作时出错: {str(e)}")
            
    def _create_new_session(self, equipment_id, rfid, user_info):
        """创建新的会话"""
        try:
            import uuid
            session_id = str(uuid.uuid4())
            
            # 这里可以添加将会话信息保存到数据库的逻辑
            # 由于缺少medication_sessions表的完整定义，暂时只在内存中跟踪
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 创建新会话: {session_id} for user {user_info['username']} on equipment {equipment_id}")
            
            # 记录用户操作，使用RFID卡号作为用户标识，target_id为空（仅开关操作）
            self._log_user_operation(equipment_id, user_info['rfid_card_id'], 'access_granted', None, f"用户 {user_info['username']} 通过RFID卡访问设备 {equipment_id}")
            
            return session_id
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 创建新会话时出错: {str(e)}")
            return None
            
    def _mark_device_as_used(self, equipment_id, session_id):
        """标记设备为使用中"""
        self.device_usage_status[equipment_id] = session_id
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 设备 {equipment_id} 已标记为使用中，会话ID: {session_id}")
        
        # 更新设备状态为开启
        self._update_equipment_status(equipment_id, door_status=1, lock_status=1)
    
    def _log_illegal_door_open(self, equipment_id):
        """记录非法开门操作到报警日志"""
        try:
            conn = self.get_db_connection(MYSQL_DATABASE_1)
            try:
                with conn.cursor() as cursor:
                    # 插入非法开门报警记录到 web_alarm_log
                    log_sql = """
                        INSERT INTO web_alarm_log 
                        (equipment_id, alarm_category, alarm_content, status, save_time)
                        VALUES (%s, %s, %s, '未处理', NOW())
                    """
                    alarm_content = f"检测到非法开门，未经过刷卡验证"
                    cursor.execute(log_sql, (equipment_id, '门锁报警', alarm_content))
                    conn.commit()
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [报警] 非法开门记录已保存到 web_alarm_log")
            finally:
                conn.close()
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 记录非法开门报警时出错: {str(e)}")
    
    def _update_or_create_door_alarm(self, equipment_id, timeout):
        """更新或创建门锁异常报警记录
        如果存在未处理的报警，更新持续时间
        如果不存在，创建新记录
        """
        try:
            conn = self.get_db_connection(MYSQL_DATABASE_1)
            try:
                with conn.cursor() as cursor:
                    # 先查询是否存在未处理的门锁异常报警
                    check_sql = """
                        SELECT id FROM web_alarm_log 
                        WHERE equipment_id = %s 
                        AND alarm_category IN ('门锁异常', '门锁报警')
                        AND status = '未处理'
                        AND save_time > DATE_SUB(NOW(), INTERVAL 5 MINUTE)
                        ORDER BY save_time DESC
                        LIMIT 1
                    """
                    cursor.execute(check_sql, (equipment_id,))
                    existing_alarm = cursor.fetchone()
                    
                    alarm_content = f"门打开超过30秒未关闭（已持续{timeout}秒）"
                    
                    if existing_alarm:
                        # 更新已有报警记录的持续时间
                        update_sql = """
                            UPDATE web_alarm_log 
                            SET alarm_content = %s, save_time = NOW()
                            WHERE id = %s
                        """
                        cursor.execute(update_sql, (alarm_content, existing_alarm['id']))
                        conn.commit()
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [报警] 更新门锁异常持续时间: {timeout}秒")
                    else:
                        # 创建新报警记录
                        insert_sql = """
                            INSERT INTO web_alarm_log 
                            (equipment_id, alarm_category, alarm_content, status, save_time)
                            VALUES (%s, %s, %s, '未处理', NOW())
                        """
                        cursor.execute(insert_sql, (equipment_id, '门锁异常', alarm_content))
                        conn.commit()
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [报警] 门锁超时记录已保存到 web_alarm_log")
            finally:
                conn.close()
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 记录门锁超时报警时出错: {str(e)}")
    
    def _resolve_pending_door_alarm(self, equipment_id):
        """门关闭时，自动处理未解决的门锁异常报警
        注意：只自动处理'门锁异常'（长时间开门），不处理'门锁报警'（非法开门）
        门锁报警需要管理员手动处理
        """
        try:
            conn = self.get_db_connection(MYSQL_DATABASE_1)
            try:
                with conn.cursor() as cursor:
                    # 只查询'门锁异常'（长时间开门），不查询'门锁报警'（非法开门）
                    check_sql = """
                        SELECT id, alarm_content FROM web_alarm_log 
                        WHERE equipment_id = %s 
                        AND alarm_category = '门锁异常'
                        AND status = '未处理'
                    """
                    cursor.execute(check_sql, (equipment_id,))
                    pending_alarms = cursor.fetchall()
                    
                    if pending_alarms:
                        for alarm in pending_alarms:
                            # 更新报警状态为已处理，并在handle_result中记录处理说明
                            update_sql = """
                                UPDATE web_alarm_log 
                                SET status = '已处理', 
                                    handled_time = NOW(),
                                    handle_result = '门已关闭，系统自动处理'
                                WHERE id = %s
                            """
                            cursor.execute(update_sql, (alarm['id'],))
                        conn.commit()
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [处理] 设备 {equipment_id} 的门锁异常报警已自动处理（门已关闭）")
            finally:
                conn.close()
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 自动处理门锁异常报警时出错: {str(e)}")
            
    def _log_user_operation(self, equipment_id, rfid_card_id, operation_type, target_id, description):
        """记录用户操作"""
        try:
            conn = self.get_db_connection(MYSQL_DATABASE_1)
            try:
                with conn.cursor() as cursor:
                    sql = """
                        INSERT INTO user_operations 
                        (operation_time, rfid_card_id, operation_type, equipment_id, target_id, description)
                        VALUES (NOW(), %s, %s, %s, %s, %s)
                    """
                    cursor.execute(sql, (rfid_card_id, operation_type, equipment_id, target_id, description))
                    conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 记录用户操作时出错: {str(e)}")
            
    def _update_equipment_status(self, equipment_id, door_status=None, lock_status=None):
        """更新设备状态"""
        try:
            conn = self.get_db_connection(MYSQL_DATABASE_1)
            try:
                with conn.cursor() as cursor:
                    # 构建更新语句
                    updates = []
                    params = []
                    
                    if door_status is not None:
                        updates.append("door_status = %s")
                        params.append(door_status)
                    
                    if lock_status is not None:
                        updates.append("lock_status = %s")
                        params.append(lock_status)
                    
                    if updates:
                        params.append(equipment_id)
                        sql = f"UPDATE web_equipment SET {', '.join(updates)} WHERE equipment_id = %s"
                        cursor.execute(sql, params)
                        conn.commit()
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 设备 {equipment_id} 状态已更新")
            finally:
                conn.close()
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 更新设备状态时出错: {str(e)}")
            
    def _send_open_door_command(self, equipment_id, session_id):
        """发送开锁指令"""
        try:
            # 构造开锁指令消息
            command_message = {
                "session_id": session_id,
                "equipment_id": equipment_id,
                "command": "open_door",
                "enum": "AT"  # 添加自动模式标记
            }
            
            # 发布开锁指令到ESP32
            topic = f"/server/command/esp32"
            message = json.dumps(command_message, ensure_ascii=False)
            
            if self.publish(topic, message, qos=1):
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已发送开锁指令到设备 {equipment_id}")
                # 记录最近开锁时间，避免误触发会话结束
                self.device_last_open_time[equipment_id] = time.time()
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 发送开锁指令到设备 {equipment_id} 失败")
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 发送开锁指令时出错: {str(e)}")
            
    def _send_lock_door_command(self, equipment_id, session_id):
        """发送上锁指令"""
        try:
            # 构造上锁指令消息
            command_message = {
                "session_id": session_id,
                "equipment_id": equipment_id,
                "command": "close_door_lock",
                "enum": "AT"  # 添加自动模式标记
            }
            
            # 发布上锁指令到ESP32
            topic = f"/server/command/esp32"
            message = json.dumps(command_message, ensure_ascii=False)
            
            if self.publish(topic, message, qos=1):
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已发送上锁指令到设备 {equipment_id}")
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 发送上锁指令到设备 {equipment_id} 失败")
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 发送上锁指令时出错: {str(e)}")
            
    def _end_session_and_lock_device(self, equipment_id, session_id):
        """结束会话并锁闭设备"""
        try:
            # 从设备使用状态中移除
            if equipment_id in self.device_usage_status:
                del self.device_usage_status[equipment_id]
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 设备 {equipment_id} 的会话已结束")
            
            # 获取当前会话的用户信息
            user_info = self._get_session_user_by_equipment(equipment_id)
            if user_info:
                # 记录用户结束访问的操作
                username = user_info['username']
                rfid_card_id = user_info['rfid_card_id']
                self._log_user_operation(
                    equipment_id=equipment_id,
                    rfid_card_id=rfid_card_id,
                    operation_type='access_granted',  # 使用现有枚举类型
                    target_id=None,
                    description=f"用户 {username} 结束了对设备 {equipment_id} 的访问"
                )
            
            # 更新设备状态为关闭和锁定
            self._update_equipment_status(equipment_id, door_status=0, lock_status=0)
            
            # 发送上锁指令
            self._send_lock_door_command(equipment_id, session_id)
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 设备 {equipment_id} 已锁闭")
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 结束会话并锁闭设备时出错: {str(e)}")
            
    def _handle_medicine_operation(self, equipment_id, rfid, user_info, medicine_code):
        """处理药品操作（借出/归还）"""
        try:
            conn = self.get_db_connection(MYSQL_DATABASE_1)
            try:
                with conn.cursor() as cursor:
                    # 1. 验证药品是否存在
                    medicine_sql = "SELECT id, name, status, current_holder_id FROM web_medicine_list WHERE medicine_code = %s"
                    cursor.execute(medicine_sql, (medicine_code,))
                    medicine_result = cursor.fetchone()
                    
                    if not medicine_result:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 药品 {medicine_code} 不存在")
                        return False
                    
                    medicine_id = medicine_result['id']
                    medicine_name = medicine_result['name']
                    current_status = medicine_result['status']
                    current_holder_id = medicine_result['current_holder_id']
                    
                    user_id = user_info['id']  # 使用用户ID作为外键
                    username = user_info['username']
                    rfid_card_id = user_info['rfid_card_id']  # 获取RFID卡号
                    # 注意：current_holder_id现在存储RFID卡号，以便显示时更直观
                    
                    # 2. 根据药品当前状态自动判断操作类型
                    if current_status == 'in_stock':
                        # 药品在库存中，执行借出操作
                        operation_type = 'borrow'
                        
                        # 更新药品状态为已借出，存储RFID卡号作为持有人
                        update_medicine_sql = """
                            UPDATE web_medicine_list 
                            SET status = 'lent_out', current_holder_id = %s, last_operation_time = NOW()
                            WHERE medicine_code = %s
                        """
                        cursor.execute(update_medicine_sql, (rfid_card_id, medicine_code))
                        
                        # 记录操作日志
                        description = f"用户 {username} 从设备 {equipment_id} 借出药品 {medicine_name}({medicine_code})"
                        
                    elif current_status == 'lent_out':
                        # 药品已借出，执行归还操作
                        operation_type = 'return'
                        
                        if str(current_holder_id) != str(rfid_card_id):
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 药品 {medicine_code} 不属于当前用户，当前持有人RFID卡号: {current_holder_id}")
                            return False
                        
                        # 更新药品状态为在库存
                        update_medicine_sql = """
                            UPDATE web_medicine_list 
                            SET status = 'in_stock', current_holder_id = NULL, last_operation_time = NOW()
                            WHERE medicine_code = %s
                        """
                        cursor.execute(update_medicine_sql, (medicine_code,))
                        
                        # 记录操作日志
                        description = f"用户 {username} 向设备 {equipment_id} 归还药品 {medicine_name}({medicine_code})"
                    elif current_status == 'reserved':
                        # 检查是否是预定人本人操作
                        check_reservation_sql = """
                            SELECT wmr.rfid_card_id 
                            FROM web_medicine_reservation wmr
                            JOIN web_medicine_list wml ON wmr.drug_id = wml.id
                            WHERE wml.medicine_code = %s AND wmr.status = 'completed'
                            ORDER BY wmr.reservation_time DESC
                            LIMIT 1
                        """
                        cursor.execute(check_reservation_sql, (medicine_code,))
                        reservation = cursor.fetchone()
                        
                        if not reservation:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 药品 {medicine_code} 已被预定，无法借出")
                            return False
                        
                        # 检查当前操作人是否是预定人
                        if reservation['rfid_card_id'] != rfid:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 药品 {medicine_code} 已被他人预定，无法借出")
                            return False
                        
                        # 预定人本人操作，允许借出
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [信息] 预定人 {rfid} 借出自己预定的药品 {medicine_code}")
                        # 定义操作描述
                        description = f"预定人 {username} 从设备 {equipment_id} 借出自己预定的药品 {medicine_name}({medicine_code})"
                    else:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 药品 {medicine_code} 当前状态异常: {current_status}")
                        return False
                    
                    # 3. 记录用户操作到user_operations表
                    log_sql = """
                        INSERT INTO user_operations 
                        (operation_time, rfid_card_id, operation_type, equipment_id, target_id, description)
                        VALUES (NOW(), %s, %s, %s, %s, %s)
                    """
                    operation_type_db = 'access_granted'  # 使用现有的枚举值
                    cursor.execute(log_sql, (rfid_card_id, operation_type_db, equipment_id, medicine_code, description))
                    
                    # 4. 记录药品追溯信息到medicine_trace表
                    trace_sql = """
                        INSERT INTO medicine_trace 
                        (operation_time, equipment_id, rfid_card_id, medicine_code, operation_type)
                        VALUES (NOW(), %s, %s, %s, %s)
                    """
                    cursor.execute(trace_sql, (equipment_id, rfid, medicine_code, operation_type))
                    
                    # 提交事务
                    conn.commit()
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [成功] {description}")
                    return True
                    
            finally:
                conn.close()
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 处理药品操作时出错: {str(e)}")
            return False      
        
    def on_connect(self, client, userdata, flags, rc):
        """连接回调函数"""
        if rc == 0:
            self.is_connected = True
            self.reconnect_attempts = 0
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] EMQX连接成功")
            # 批量订阅主题
            result, _ = client.subscribe(DEFAULT_SUBSCRIBE_TOPICS)
            if result == mqtt.MQTT_ERR_SUCCESS:
                pass
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 订阅主题失败，错误码: {result}")   
            # 连接成功后获取客户端ID名单
            self.get_clients_list()
            # 启动定时查询任务
            self.start_periodic_query()
        else:
            self.is_connected = False
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] EMQX连接失败，错误码: {rc}. 错误原因: {mqtt.connack_string(rc)}") 
    def on_disconnect(self, client, userdata, rc):
        """连接断开回调函数"""
        error_msg = mqtt.connack_string(rc) if hasattr(mqtt, 'connack_string') else f"未知错误({rc})"
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] EMQX连接断开，错误码: {rc} ({error_msg})") 
        # 只有在非正常断开的情况下才尝试重连
        if rc != 0:  # 0表示正常断开
            # 检查是否已经超过最大重连尝试次数
            if self.reconnect_attempts < self.max_reconnect_attempts:
                # 增加重连尝试计数
                self.reconnect_attempts += 1
                # 延迟2秒后再尝试重连，避免频繁重连
                time.sleep(2)
                self.attempt_reconnect()
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已达到最大重连尝试次数 ({self.max_reconnect_attempts})，停止自动重连")
                self.is_connected = False
        else:
            # 正常断开连接
            self.is_connected = False
            self.reconnect_attempts = 0  # 重置重连计数
            
    def get_db_connection(self, database_name):
        """获取数据库连接"""
        return pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=database_name,
            cursorclass=pymysql.cursors.DictCursor
        )
    
    def get_history_db_connection(self):
        """获取历史数据库连接"""
        return self.get_db_connection(MYSQL_DATABASE_2)
    
    def save_environment_data(self, data):
        """保存环境数据到数据库"""
        try:
            # 提取设备ID和环境数据
            equipment_id = data.get('equipment_id')
            if not equipment_id:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 环境数据缺少equipment_id")
                return False
            
            # 检查是否是版本信息
            if 'version' in data:
                # 处理版本信息
                version = data.get('version')
                
                # 验证版本号是否有效
                if version and isinstance(version, str) and version.strip():
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [成功] 收到设备 {equipment_id} 的版本信息: {version}")
                else:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] 收到设备 {equipment_id} 的无效版本信息: {version}")
                    version = None  # 设置为None表示无效版本号
                
                # 通知admin_equip_ota模块处理版本响应
                try:
                    from admin_equip_ota import handle_version_response
                    handle_version_response(equipment_id, version)
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] 通知版本响应处理失败: {str(e)}")
                
                # 保存版本信息到web_equipment表
                conn = self.get_db_connection(MYSQL_DATABASE_1)
                try:
                    with conn.cursor() as cursor:
                        update_sql = """
                        UPDATE web_equipment 
                        SET firmware_version = %s, last_online = NOW() 
                        WHERE equipment_id = %s
                        """
                        cursor.execute(update_sql, (version, equipment_id))
                        conn.commit()
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [成功] 设备 {equipment_id} 的版本信息已更新到数据库")
                finally:
                    conn.close()
                return True
            
            # 表名格式：history_environment_data_{equipment_id}
            table_name = f"history_environment_data_{equipment_id}"
            
            # 获取连接
            conn = self.get_history_db_connection()
            
            try:
                # 先连接系统数据库，然后检查并创建history数据库
                with conn.cursor() as cursor:
                    # 创建history数据库（如果不存在）
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE_2} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                    # 切换到history数据库
                    conn.select_db(MYSQL_DATABASE_2)
                    
                    # 创建表（如果不存在）
                    create_table_sql = f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        temperature FLOAT NOT NULL COMMENT '温度',
                        humidity FLOAT NOT NULL COMMENT '湿度',
                        aqi INT NOT NULL COMMENT '空气质量指数',
                        save_time DATETIME NOT NULL COMMENT '保存时间',
                        INDEX idx_save_time (save_time)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                    cursor.execute(create_table_sql)
                    
                    # 插入数据
                    insert_sql = f"""
                    INSERT INTO {table_name} (temperature, humidity, aqi, save_time)
                    VALUES (%s, %s, %s, NOW())
                    """
                    cursor.execute(insert_sql, (
                        data.get('temp', 0),
                        data.get('humi', 0),
                        data.get('AQI', 0)
                    ))
                    
                    conn.commit()
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [成功] 环境数据已保存到表 {table_name}")
                    # 保存成功后，触发健康状态评估
                    try:
                        evaluate_equipment_health_status(equipment_id, lambda: self.get_db_connection(MYSQL_DATABASE_1))
                    except Exception as e:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] 健康状态评估失败: {str(e)}")
                    return True
                    
            except Exception as e:
                if conn:
                    conn.rollback()
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 保存环境数据时出错: {str(e)}")
                return False
            finally:
                if conn:
                    conn.close()
                    
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 数据库连接或操作失败: {str(e)}")
            return False
    
    def _clear_remote_operation_monitor(self, equipment_id, cursor):
        """清除远程操作监控记录和定时器"""
        try:
            # 延迟导入以避免循环导入
            import admin_equip_montior
            
            # 取消定时器（如果存在）
            if equipment_id in admin_equip_montior.remote_operation_timers:
                admin_equip_montior.remote_operation_timers[equipment_id].cancel()
                del admin_equip_montior.remote_operation_timers[equipment_id]
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已取消设备 {equipment_id} 的远程操作监控定时器")
            
            # 更新监控记录状态为已完成
            cursor.execute("""
                UPDATE remote_operation_monitor
                SET status = 'completed', completed_time = NOW()
                WHERE equipment_id = %s AND status = 'active'
            """, (equipment_id,))
            
            if cursor.rowcount > 0:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已更新设备 {equipment_id} 的远程操作监控记录为已完成")
            
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] 清除远程操作监控时出错: {str(e)}")
    
    def update_door_lock_status(self, data):
        """更新门锁状态到数据库"""
        try:
            # 提取设备ID和门锁状态
            equipment_id = data.get('equipment_id')
            door_status = data.get('door')
            lock_status = data.get('lock')
            timeout = data.get('timeout')
            
            # 将timeout转换为整数（从JSON解析的可能是字符串）
            if timeout is not None:
                try:
                    timeout = int(timeout)
                except (ValueError, TypeError):
                    timeout = 0 
            
            if not equipment_id:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 门锁数据缺少equipment_id")
                return False
            
            # 首先验证设备是否存在
            if not self._is_device_exist(equipment_id):
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 设备 {equipment_id} 不存在，无法更新门锁状态")
                return False
            
            # 检查是否是从开启状态变为关闭状态，如果是则结束会话
            # 先获取当前设备的状态
            old_door_status = None
            old_lock_status = None
            conn_check = self.get_db_connection(MYSQL_DATABASE_1)
            try:
                with conn_check.cursor() as cursor:
                    cursor.execute("SELECT door_status, lock_status FROM web_equipment WHERE equipment_id = %s", (equipment_id,))
                    result = cursor.fetchone()
                    if result:
                        old_door_status = result['door_status']
                        old_lock_status = result['lock_status']
            except Exception as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] 查询设备旧状态时出错: {str(e)}")
            finally:
                if conn_check:
                    conn_check.close()
            
            # 获取web数据库连接
            conn = self.get_db_connection(MYSQL_DATABASE_1)
            
            try:
                with conn.cursor() as cursor:
                    # 更新web_equipment表
                    update_sql = """
                    UPDATE web_equipment 
                    SET door_status = %s, lock_status = %s, timeout = %s, last_online = NOW() 
                    WHERE equipment_id = %s
                    """
                    affected_rows = cursor.execute(update_sql, (door_status, lock_status, timeout, equipment_id))
                    
                    if affected_rows > 0:
                        conn.commit()
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}][成功]设备{equipment_id}门锁状态已更新-门状态:{door_status},锁状态:{lock_status},超时时间:{timeout}")
                        
                        # 检查锁状态是否从解锁变为锁定（0表示锁定），如果是则清除远程操作监控
                        if old_lock_status == 1 and lock_status == 0:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 检测到设备 {equipment_id} 已上锁，清除远程操作监控")
                            self._clear_remote_operation_monitor(equipment_id, cursor)
                            conn.commit()
                        
                        # 检查是否非法开门（门打开但没有活动会话）
                        if old_door_status == 0 and door_status == 1:
                            # 门被打开，检查是否有合法会话
                            if equipment_id not in self.device_usage_status:
                                # 没有活动会话，属于非法开门
                                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [报警] 检测到设备 {equipment_id} 非法开门！没有有效的刷卡记录")
                                # 记录非法开门操作
                                self._log_illegal_door_open(equipment_id)
                        
                        # 检查门是否打开超过30秒（门锁异常）
                        if door_status == 1 and timeout and timeout > 30:
                            # 更新或创建门锁异常报警记录
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [报警] 检测到设备 {equipment_id} 门打开超过30秒，触发门锁异常")
                            self._update_or_create_door_alarm(equipment_id, timeout)
                        
                        # 检查是否是从开启状态变为关闭状态，如果是则结束会话
                        # 并且确保不是刚发送开门指令后立即触发
                        if old_door_status == 1 and door_status == 0:
                            # 检查是否刚发送过开门指令（1秒内）
                            last_open_time = self.device_last_open_time.get(equipment_id, 0)
                            current_time = time.time()
                            if current_time - last_open_time > 1:  # 1秒后才允许触发会话结束
                                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 检测到设备 {equipment_id} 门已关闭，准备结束会话")
                                # 查找该设备的会话ID
                                session_id = self.device_usage_status.get(equipment_id)
                                if session_id:
                                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 找到设备 {equipment_id} 的会话 {session_id}，正在结束会话并锁闭设备")
                                    # 结束会话并锁闭设备
                                    self._end_session_and_lock_device(equipment_id, session_id)
                                else:
                                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 未找到设备 {equipment_id} 的活动会话")
                                
                                # 门关闭时，自动处理未解决的门锁异常报警
                                self._resolve_pending_door_alarm(equipment_id)
                            else:
                                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 忽略刚发送开门指令后的门状态变化，避免误触发会话结束")
                        
                        # 更新成功后，触发健康状态评估
                        try:
                            evaluate_equipment_health_status(equipment_id, lambda: self.get_db_connection(MYSQL_DATABASE_1))
                        except Exception as e:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] 健康状态评估失败: {str(e)}")
                        return True
                    else:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] 未找到设备 {equipment_id}")
                        return False
                        
            except Exception as e:
                if conn:
                    conn.rollback()
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 更新门锁状态时出错: {str(e)}")
                return False
            finally:
                if conn:
                    conn.close()
                    
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 数据库连接或操作失败: {str(e)}")
            return False
    
    def on_message(self, client, userdata, msg):
        """消息接收回调函数 - 使用线程池异步处理"""
        # 解码消息内容
        payload = msg.payload.decode()
        
        # 检查是否是我们关心的主题
        if msg.topic in ["/esp32/environment_data/server", "/esp32/rfid_data/server", "/esp32/door_lock_data/server", "/esp32/medicine_operation/server", "/esp32/ota_status/server", "/esp32/alarm_data/server", "/esp32/device_request/server"]:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [重要消息] 收到指定主题消息 - 主题: {msg.topic}")
            print(f"  内容: {payload}")
            
            # 使用线程池异步处理消息，避免阻塞MQTT接收
            self.executor.submit(self._process_message_async, msg.topic, payload)
        elif msg.topic.startswith("/esp32/ota/request/") or msg.topic.startswith("/esp32/ota/ack/"):
            # OTA 相关主题也需要异步处理
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [重要消息] 收到OTA主题消息 - 主题: {msg.topic}")
            print(f"  内容: {payload}")
            
            # 使用线程池异步处理消息，避免阻塞MQTT接收
            self.executor.submit(self._process_message_async, msg.topic, payload)
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 收到消息 - 主题: {msg.topic}, 内容: {payload}")
    
    def _process_message_async(self, topic, payload):
        """异步处理MQTT消息"""
        try:
            # 处理环境数据（ESP32上报的数据，服务器判断是否需要报警）
            if topic == "/esp32/environment_data/server":
                try:
                    data = json.loads(payload)
                    equipment_id = data.get('equipment_id')
                    if equipment_id:
                        # 保存环境数据到历史数据库
                        self.save_environment_data(data)
                        # 服务器端判断是否需要生成报警
                        handle_environment_data(equipment_id, data)
                except json.JSONDecodeError:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 环境数据JSON格式无效")
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 处理环境数据时出错: {str(e)}")
            
            # 处理设备请求（阈值配置等）
            elif topic == "/esp32/device_request/server":
                try:
                    data = json.loads(payload)
                    equipment_id = data.get('equipment_id')
                    query = data.get('query')
                    
                    if equipment_id and query:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 收到设备请求 - 设备: {equipment_id}, 查询: {query}")
                        
                        if query == "threshold_config":
                            # 处理阈值配置请求
                            self.handle_threshold_config_request(equipment_id)
                        else:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] 未知的查询类型: {query}")
                            
                except json.JSONDecodeError:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 设备请求JSON格式无效")
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 处理设备请求时出错: {str(e)}")
            
            # 报警数据主题（ESP32异常时专门上报的报警数据）
            elif topic == "/esp32/alarm_data/server":
                try:
                    data = json.loads(payload)
                    equipment_id = data.get('equipment_id')
                    if equipment_id:
                        # 保存到历史数据库并处理报警（不打印日志，由alarm_handler打印关键信息）
                        self.save_environment_data(data)
                        handle_environment_data(equipment_id, data)
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 处理报警数据: {str(e)}")
            
            # 如果是门锁数据主题，解析并更新
            elif topic == "/esp32/door_lock_data/server":
                try:
                    # 解析JSON数据
                    data = json.loads(payload)
                    # 更新门锁状态
                    self.update_door_lock_status(data)
                except json.JSONDecodeError:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 门锁数据JSON格式无效")
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 处理门锁数据时出错: {str(e)}")
            
            # 如果是OTA状态主题，解析并更新OTA状态
            elif topic == "/esp32/ota_status/server":
                try:
                    # 解析JSON数据
                    data = json.loads(payload)
                    # 从admin_equip_ota导入ota_status字典
                    from admin_equip_ota import ota_status
                    
                    # 获取设备ID和状态信息
                    equipment_id = data.get('equipment_id')
                    status = data.get('status')
                    progress = data.get('progress', 0)
                    message = data.get('message', '')
                    
                    if equipment_id and status:
                        # 更新OTA状态
                        if equipment_id in ota_status:
                            ota_status[equipment_id]['status'] = status
                            ota_status[equipment_id]['progress'] = progress
                            ota_status[equipment_id]['message'] = message
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] OTA状态更新 - 设备: {equipment_id}, 状态: {status}, 进度: {progress}%, 消息: {message}")
                except json.JSONDecodeError:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] OTA状态数据JSON格式无效")
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 处理OTA状态数据时出错: {str(e)}")
            
            elif topic == "/esp32/rfid_data/server":
                try:
                    # 解析JSON数据
                    data = json.loads(payload)
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 收到RFID数据: {data}")
                    
                    # 获取设备ID和RFID
                    equipment_id = data.get('equipment_id')
                    rfid = data.get('rfid')
                    
                    if not equipment_id or not rfid:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] RFID数据缺少必要字段")
                        return
                    
                    # 首先验证设备是否存在
                    if not self._is_device_exist(equipment_id):
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 设备 {equipment_id} 不存在，拒绝访问")
                        self._log_access_denied(equipment_id, rfid)
                        return
                    
                    # 检查设备是否正在使用中
                    if self._is_device_available(equipment_id):
                        # 设备可用，处理用户RFID，创建会话
                        # 验证RFID用户是否存在且启用
                        user_info = self._validate_rfid_user(rfid)
                        if not user_info:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 无效的RFID用户: {rfid}")
                            # 记录拒绝访问的操作
                            self._log_access_denied(equipment_id, rfid)
                            return
                        
                        # 创建新的会话
                        session_id = self._create_new_session(equipment_id, rfid, user_info)
                        if not session_id:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 无法创建新会话")
                            return
                        
                        # 标记设备为使用中
                        self._mark_device_as_used(equipment_id, session_id)
                        
                        # 发送开门指令
                        self._send_open_door_command(equipment_id, session_id)
                    else:
                        # 设备正在使用中，处理药品RFID
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 设备 {equipment_id} 正在使用中，处理药品RFID: {rfid}")
                        
                        # 检查门状态，只有门打开才能处理药品操作
                        try:
                            conn = self.get_db_connection(MYSQL_DATABASE_1)
                            with conn.cursor() as cursor:
                                cursor.execute("SELECT door_status FROM web_equipment WHERE equipment_id = %s", (equipment_id,))
                                result = cursor.fetchone()
                                if result and result['door_status'] != 1:
                                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] 设备 {equipment_id} 门未打开，拒绝处理药品操作")
                                    conn.close()
                                    return
                        except Exception as e:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 查询门状态时出错: {str(e)}")
                            return
                        
                        # 将RFID作为药品代码处理
                        medicine_code = rfid
                        
                        # 获取当前会话的用户信息
                        session_user_info = self._get_session_user_by_equipment(equipment_id)
                        if not session_user_info:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] 设备 {equipment_id} 没有有效的会话用户")
                            return
                        
                        # 验证当前用户是否存在且启用
                        user_info = self._validate_rfid_user(session_user_info['rfid_card_id'])
                        if not user_info:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 无效的会话用户: {session_user_info['rfid_card_id']}")
                            return
                        
                        # 处理药品操作（借出/归还）
                        success = self._handle_medicine_operation(equipment_id, session_user_info['rfid_card_id'], user_info, medicine_code)
                        if success:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [成功] 药品操作处理完成")
                        else:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 药品操作处理失败")
                    
                except json.JSONDecodeError:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] RFID数据JSON格式无效")
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 处理RFID数据时出错: {str(e)}")

            elif topic == "/esp32/medicine_operation/server":
                try:
                    # 解析JSON数据
                    data = json.loads(payload)
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 收到药品操作数据: {data}")
                    
                    # 获取必要字段
                    equipment_id = data.get('equipment_id')
                    rfid = data.get('rfid')
                    medicine_code = data.get('medicine_code')
                    operation_type = data.get('operation_type')  # 'borrow' 或 'return'
                    
                    if not equipment_id or not rfid or not medicine_code or not operation_type:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 药品操作数据缺少必要字段")
                        return
                    
                    # 首先验证设备是否存在
                    if not self._is_device_exist(equipment_id):
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 设备 {equipment_id} 不存在，无法进行药品操作")
                        self._log_access_denied(equipment_id, rfid)
                        return
                    
                    # 验证设备是否已有有效会话（设备应该在使用中）
                    if self._is_device_available(equipment_id):
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] 设备 {equipment_id} 没有有效的会话，无法进行药品操作")
                        return
                    
                    # 验证RFID用户是否存在且启用
                    user_info = self._validate_rfid_user(rfid)
                    if not user_info:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 无效的RFID用户: {rfid}")
                        # 记录拒绝访问的操作
                        self._log_access_denied(equipment_id, rfid)
                        return
                    
                    # 验证当前用户是否与会话创建用户一致
                    session_user_info = self._get_session_user_by_equipment(equipment_id)
                    if not session_user_info:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] 设备 {equipment_id} 没有有效的会话用户")
                        return
                    
                    if session_user_info['rfid_card_id'] != rfid:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [警告] RFID用户 {rfid} 与当前会话用户 {session_user_info['rfid_card_id']} 不匹配")
                        self._log_access_denied(equipment_id, rfid)
                        return
                    
                    # 处理药品操作（借出/归还）
                    # 现在服务器根据药品状态自动判断操作类型，不需要客户端提供
                    success = self._handle_medicine_operation(equipment_id, rfid, user_info, medicine_code)
                    if success:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [成功] 药品操作处理完成")
                    else:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 药品操作处理失败")
                        
                except json.JSONDecodeError:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 药品操作数据JSON格式无效")
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 处理药品操作数据时出错: {str(e)}")

            # 处理MQTT OTA请求
            elif topic.startswith("/esp32/ota/request/"):
                try:
                    data = json.loads(payload)
                    equipment_id = data.get('equipment_id')
                    packet_index = data.get('packet_index')
                    total_packets = data.get('total_packets')
                    current_progress = data.get('current_progress')
                    
                    if equipment_id is not None and packet_index is not None:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 收到OTA请求 - 设备: {equipment_id}, 包序号: {packet_index}, 进度: {current_progress}%")
                        # 调用admin_equip_ota中的处理函数
                        from admin_equip_ota import handle_ota_request
                        handle_ota_request(equipment_id, packet_index, total_packets, current_progress)
                except json.JSONDecodeError:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] OTA请求JSON格式无效")
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 处理OTA请求时出错: {str(e)}")

            # 处理MQTT OTA确认
            elif topic.startswith("/esp32/ota/ack/"):
                try:
                    data = json.loads(payload)
                    equipment_id = data.get('equipment_id')
                    packet_index = data.get('packet_index')
                    status = data.get('status')
                    
                    if equipment_id is not None and packet_index is not None and status:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 收到OTA确认 - 设备: {equipment_id}, 包序号: {packet_index}, 状态: {status}")
                        # 调用admin_equip_ota中的处理函数
                        from admin_equip_ota import handle_ota_ack
                        handle_ota_ack(equipment_id, packet_index, status)
                except json.JSONDecodeError:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] OTA确认JSON格式无效")
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 处理OTA确认时出错: {str(e)}")

            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 收到消息 - 主题: {topic}, 内容: {payload}")

        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 异步处理消息时出错: {str(e)}")
        
    def connect(self):
        """连接到EMQX Broker（带异步和重试机制）"""
        retry_count = 2
        max_retries = 3
        
        # 在开始连接前，先检查是否已有连接
        if self.client and self.is_connected:
            print("[INFO] EMQX连接已存在")
            return True
            
        # 重置连接状态
        self.is_connected = False
        
        while retry_count < max_retries:
            try:
                print(f"[DEBUG] 连接参数 - IP: {self.broker_ip}, Port: {self.broker_port}, Username: {self.username}, ClientID: {self.client_id}")
                
                # 如果已有客户端实例，先清理
                if self.client:
                    try:
                        self.client.loop_stop()
                        self.client.disconnect()
                    except:
                        pass  # 忽略断开连接时的异常
                
                # 创建新的MQTT客户端
                self.client = mqtt.Client(client_id=self.client_id)
                
                # 设置用户名和密码
                self.client.username_pw_set(self.username, self.password)

                # 设置回调函数
                self.client.on_connect = self.on_connect
                self.client.on_disconnect = self.on_disconnect
                self.client.on_message = self.on_message
                
                # 连接EMQX Broker
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 正在尝试连接到 {self.broker_ip}:{self.broker_port}（第{retry_count + 1}次）")
                try:
                    result = self.client.connect(self.broker_ip, self.broker_port, 60)
                    
                    # 检查连接是否成功启动
                    if result != mqtt.MQTT_ERR_SUCCESS:
                        error_msg = mqtt.error_string(result) if hasattr(mqtt, 'error_string') else f"未知错误({result})"
                        print(f"[ERROR] 连接启动失败，错误码: {result} ({error_msg})")
                        raise ConnectionError(f"Failed to start connection with MQTT broker, error code: {result} ({error_msg})")
                except Exception as e:
                    print(f"[ERROR] 调用connect时发生异常: {e}")
                    raise ConnectionError(f"Exception occurred while calling connect: {e}")
                
                self.client.loop_start()
                print("[INFO] 已调用 connect，正在等待连接...")
                
                # 等待连接完成，最多等待 5 秒
                timeout = 1
                start_time = time.time()
                while not self.is_connected:
                    if time.time() - start_time > timeout:
                        print("[ERROR] MQTT连接超时")
                        raise ConnectionError("Failed to establish a connection with the MQTT broker within the timeout period.")
                    time.sleep(0.1)

                print("[INFO] 成功连接到 MQTT Broker")
                # 重置重连尝试计数
                self.reconnect_attempts = 0
                return True  # 成功则退出方法
                
            except Exception as e:
                print(f"[ERROR] 第{retry_count + 1}次连接失败: {e}")
                retry_count += 1
                
                if retry_count < max_retries:
                    print("[INFO] 2秒后重试...")
                    time.sleep(2)
                else:
                    print("[ERROR] 达到最大重试次数，放弃连接。")
                    return False
        
        return False
            
    def attempt_reconnect(self):
        """尝试重连"""
        # 检查是否已经超过最大重连尝试次数
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 达到最大重连次数，停止重连")
            self.is_connected = False
            return False
            
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 尝试重连 ({self.reconnect_attempts}/{self.max_reconnect_attempts})...")
        
        # 延迟后重连
        time.sleep(self.reconnect_delay)
        
        # 直接使用client.reconnect()而不是重新调用connect()
        try:
            if self.client:
                result = self.client.reconnect()
                if result == mqtt.MQTT_ERR_SUCCESS:
                    self.client.loop_start()
                    self.reconnect_attempts = 0
                    return True
                else:
                    print(f"[ERROR] 重连失败，错误码: {result}")
                    return False
        except Exception as e:
            print(f"[ERROR] 重连过程中发生异常: {e}")
            return False
            
    def disconnect(self):
        """断开连接"""
        self.stop_periodic_query()
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
                self.is_connected = False
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] EMQX连接已断开")
            except Exception as e:
                print(f"断开EMQX连接时发生错误: {str(e)}")
    
    def query_online_devices(self):
        """向所有在线设备发送查询命令（环境数据和门锁数据）"""
        try:
            url = f"{self.emqx_api_base_url}/clients"
            auth = HTTPBasicAuth(self.emqx_api_key, self.emqx_api_secret)
            
            response = requests.get(url, auth=auth, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json()
                
                if isinstance(response_data, list):
                    clients = response_data
                elif isinstance(response_data, dict) and 'data' in response_data:
                    clients = response_data['data']
                else:
                    clients = []
                
                device_clients = []
                for client in clients:
                    client_id = client.get('clientid', '未知')
                    if client_id and not client_id.endswith('_system') and not client_id.startswith('web_') and client_id != 'server':
                        device_clients.append(client)
                
                for client in device_clients:
                    client_id = client.get('clientid', '未知')
                    is_connected = client.get('connected', False)
                    
                    if client_id.startswith('cabinet_') and is_connected:
                        env_query = {
                            "equipment_id": client_id,
                            "query": "environment_data"
                        }
                        self.publish("/server/command/esp32", json.dumps(env_query))
                        
                        door_lock_query = {
                            "equipment_id": client_id,
                            "query": "door_lock_data"
                        }
                        self.publish("/server/command/esp32", json.dumps(door_lock_query))
                        
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [定时查询] 已向 {client_id} 发送查询命令")
                        
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 定时查询设备时出错: {str(e)}")
    
    def _periodic_query_task(self):
        """定时查询任务（内部函数）"""
        while self.periodic_query_running:
            try:
                self.query_online_devices()
            except Exception as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 定时查询任务异常: {str(e)}")
            
            for _ in range(self.periodic_query_interval):
                if not self.periodic_query_running:
                    break
                time.sleep(1)
    
    def start_periodic_query(self):
        """启动定时查询任务"""
        if self.periodic_query_running:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 定时查询任务已在运行")
            return
        
        self.periodic_query_running = True
        self.periodic_query_timer = threading.Thread(target=self._periodic_query_task, daemon=True)
        self.periodic_query_timer.start()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 定时查询任务已启动（间隔：{self.periodic_query_interval // 60} 分钟）")
    
    def stop_periodic_query(self):
        """停止定时查询任务"""
        if not self.periodic_query_running:
            return
        
        self.periodic_query_running = False
        if self.periodic_query_timer and self.periodic_query_timer.is_alive():
            self.periodic_query_timer.join(timeout=2)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 定时查询任务已停止")
                
    def publish(self, topic, message, qos=0, retain=False):
        """发布消息"""
        if self.is_connected and self.client:
            try:
                result = self.client.publish(topic, message, qos=qos, retain=retain)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    return True
                else:
                    print(f"发布消息失败，错误码: {result.rc}")
                    return False
            except Exception as e:
                print(f"发布消息时发生错误: {str(e)}")
                return False
        else:
            print("EMQX未连接，无法发布消息")
            return False
            
    def subscribe(self, topic, qos=0):
        """订阅主题"""
        if self.is_connected and self.client:
            try:
                result = self.client.subscribe(topic, qos=qos)
                if result[0] == mqtt.MQTT_ERR_SUCCESS:
                    print(f"已订阅主题: {topic}")
                    return True
                else:
                    print(f"订阅主题失败，错误码: {result[0]}")
                    return False
            except Exception as e:
                print(f"订阅主题时发生错误: {str(e)}")
                return False
        else:
            print("EMQX未连接，无法订阅主题")
            return False
    
    def initialize_connection_status(self):
        """初始化所有设备连接状态为离线"""
        try:
            # 获取web数据库连接
            conn = self.get_db_connection(MYSQL_DATABASE_1)
            
            try:
                with conn.cursor() as cursor:
                    # 将所有设备的连接状态设置为离线(1)
                    update_sql = "UPDATE web_equipment SET connection_status = 1"
                    cursor.execute(update_sql)
                    conn.commit()
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已将所有设备连接状态初始化为离线")
            except Exception as e:
                if conn:
                    conn.rollback()
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 初始化设备连接状态时出错: {str(e)}")
            finally:
                if conn:
                    conn.close()
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 数据库连接失败: {str(e)}")
    
    def update_device_connection_status(self, equipment_id, status):
        """更新单个设备的连接状态"""
        try:
            # 获取web数据库连接
            conn = self.get_db_connection(MYSQL_DATABASE_1)
            
            try:
                with conn.cursor() as cursor:
                    # 更新指定设备的连接状态
                    update_sql = "UPDATE web_equipment SET connection_status = %s WHERE equipment_id = %s"
                    affected_rows = cursor.execute(update_sql, (status, equipment_id))
                    
                    if affected_rows > 0:
                        conn.commit()
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 设备 {equipment_id} 连接状态已更新为 {status}")
                        return True
                    else:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 未找到设备 {equipment_id}")
                        return False
            except Exception as e:
                if conn:
                    conn.rollback()
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 更新设备 {equipment_id} 连接状态时出错: {str(e)}")
                return False
            finally:
                if conn:
                    conn.close()
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 数据库连接失败: {str(e)}")
            return False
    
    def get_clients_list(self):
        """获取EMQX上的客户端ID名单并打印到终端，同时向每个设备发送查询命令"""
        try:
            # 首先将所有设备状态设置为离线
            self.initialize_connection_status()
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 正在获取EMQX客户端列表...")
            
            # 调用EMQX REST API获取客户端列表
            url = f"{self.emqx_api_base_url}/clients"
            
            # 准备请求参数
            headers = {}
            auth = None
            
            # 优先尝试API密钥认证（EMQX 5.x推荐方式）
            if self.emqx_api_key and self.emqx_api_secret:
                headers = {
                    "Authorization": f"Basic {base64.b64encode(f'{self.emqx_api_key}:{self.emqx_api_secret}'.encode()).decode()}"
                }
            else:
                # 备选使用HTTP基本认证
                auth = HTTPBasicAuth(self.emqx_api_username, self.emqx_api_password)
            
            # 发送GET请求
            response = requests.get(url, headers=headers, auth=auth, timeout=10)
            
            # 检查响应状态码
            if response.status_code == 200:
                # 解析JSON响应 - EMQX 5.x的响应格式
                response_data = response.json()
                
                # 处理不同的响应格式（可能是列表或带有data字段的对象）
                if isinstance(response_data, list):
                    clients = response_data
                elif isinstance(response_data, dict) and 'data' in response_data:
                    clients = response_data['data']
                else:
                    clients = []
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 响应格式不符合预期: {response_data}")
                
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 成功获取到 {len(clients)} 个客户端连接：")
                
                # 过滤设备类型客户端（如cabinet_002格式）
                device_clients = []
                for client in clients:
                    client_id = client.get('clientid', '未知')
                    # 过滤只保留设备类型客户端，排除系统类客户端和server自身
                    if client_id and not client_id.endswith('_system') and not client_id.startswith('web_') and client_id != 'server':
                        device_clients.append(client)
                
                # 打印设备客户端列表
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 成功获取到 {len(device_clients)} 个设备客户端连接：")
                for client in device_clients:
                    client_id = client.get('clientid', '未知')
                    # 检查客户端是否真的在线（EMQX 5.x中connected字段表示连接状态）
                    is_connected = client.get('connected', False)
                    connected_at = client.get('connected_at', '')
                    
                    print(f"  - 客户端ID: {client_id}, 连接状态: {is_connected}, 连接时间: {connected_at}")
                    
                    # 只更新以"cabinet_"开头的设备客户端
                    if client_id.startswith('cabinet_'):
                        if is_connected:
                            # 设备真正在线，更新状态为在线(0)
                            self.update_device_connection_status(client_id, 0)
                            
                            # 向在线设备发送查询命令
                            # 发送环境数据查询命令
                            env_query = {
                                "equipment_id": client_id,
                                "query": "environment_data"
                            }
                            self.publish("/server/command/esp32", json.dumps(env_query))
                            
                            # 发送门锁数据查询命令
                            door_lock_query = {
                                "equipment_id": client_id,
                                "query": "door_lock_data"
                            }
                            self.publish("/server/command/esp32", json.dumps(door_lock_query))
                            
                            print(f"  - 已向 {client_id} 发送查询命令")
                        else:
                            # 设备虽然出现在列表中，但connected为false，保持离线状态
                            print(f"  - 设备 {client_id} 在列表中但已断开连接，保持离线状态")
            elif response.status_code == 401:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 认证失败，请检查EMQX API凭据：")
                print(f"  响应内容: {response.text}")
                print(f"  请在EMQX 5.x控制台创建API密钥并配置到emqx_manager.py中")
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] HTTP请求失败，状态码: {response.status_code}")
                print(f"  响应内容: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 获取客户端列表时发生网络错误: {str(e)}")
        except json.JSONDecodeError:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 解析响应数据失败")
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 获取客户端列表时发生未知错误: {str(e)}")

    def handle_threshold_config_request(self, equipment_id):
        """
        处理ESP32的阈值配置请求
        查询数据库并返回阈值配置
        """
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 处理阈值配置请求 - 设备: {equipment_id}")
            
            # 获取阈值配置响应
            config_response = get_threshold_config_response(equipment_id)
            
            # 发布到设备
            response_topic = f"/server/command/esp32"
            self.publish(response_topic, json.dumps(config_response), qos=1)
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已发送阈值配置到 {equipment_id}")
            return True
            
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 处理阈值配置请求失败: {str(e)}")
            return False

# 全局EMQX管理器实例
emqx_manager = None
def init_emqx_connection():
    """初始化EMQX连接"""
    global emqx_manager
    
    # 如果已经存在连接管理器且已连接，先断开再重新连接
    if emqx_manager and emqx_manager.is_connected:
        print("[INFO] 发现现有EMQX连接，先断开再重新连接")
        emqx_manager.disconnect()
    
    # 创建新的连接管理器
    if emqx_manager is None:
        emqx_manager = EMQXManager()
    
    return emqx_manager.connect()

def get_emqx_manager():
    """获取EMQX管理器实例"""
    global emqx_manager
    return emqx_manager
