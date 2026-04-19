from flask import Blueprint, render_template, jsonify, request
from decimal import Decimal
import json

# 创建蓝图
admin_equip_config_bp = Blueprint('admin_equip_config', __name__)

def init_equip_config_routes(app, login_required, get_db_connection):
    """
    初始化设备配置相关的路由
    """
    @app.route('/admin_equip_config.html')
    @login_required
    def admin_equip_config():
        """
        设备配置页面
        """
        return render_template('admin_equip_config.html')
    
    @app.route('/api/equipment-config', methods=['GET'])
    @login_required
    def get_equipment_config():
        """
        获取设备配置数据
        """
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 从web_equipment_config表查询数据
                cursor.execute("SELECT * FROM web_equipment_config ORDER BY equipment_id")
                config_list = cursor.fetchall()
                
                # 格式化数据为前端需要的格式
                formatted_config = [{
                    'id': config.get('id'),
                    'equipment_id': config.get('equipment_id'),
                    'temp_NOR_min': float(config.get('temp_NOR_min')),
                    'temp_NOR_max': float(config.get('temp_NOR_max')),
                    'temp_ABN_min': float(config.get('temp_ABN_min')),
                    'temp_ABN_max': float(config.get('temp_ABN_max')),
                    'humi_NOR_min': float(config.get('humi_NOR_min')),
                    'humi_NOR_max': float(config.get('humi_NOR_max')),
                    'humi_ABN_min': float(config.get('humi_ABN_min')),
                    'humi_ABN_max': float(config.get('humi_ABN_max')),
                    'aqi_NOR_max': float(config.get('aqi_NOR_max')),
                    'aqi_ABN_max': float(config.get('aqi_ABN_max')),
                    'timeout_NOR': config.get('timeout_NOR'),
                    'timeout_ABN': config.get('timeout_ABN'),
                    'created_at': config.get('created_at').strftime('%Y-%m-%d %H:%M:%S') if config.get('created_at') else '',
                    'updated_at': config.get('updated_at').strftime('%Y-%m-%d %H:%M:%S') if config.get('updated_at') else ''
                } for config in config_list]
                
                return jsonify({'success': True, 'data': formatted_config})
        except Exception as e:
            print(f"Error fetching equipment config: {e}")
            return jsonify({'success': False, 'message': f'获取设备配置数据失败: {str(e)}'})
        finally:
            if conn:
                conn.close()
    
    @app.route('/api/equipment-config/<int:config_id>', methods=['PUT'])
    @login_required
    def update_equipment_config(config_id):
        """
        更新设备配置数据，并主动推送给ESP32
        """
        conn = None
        try:
            # 获取请求数据
            data = request.get_json()
            
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 先查询设备ID
                cursor.execute("SELECT equipment_id FROM web_equipment_config WHERE id = %s", (config_id,))
                result = cursor.fetchone()
                if not result:
                    return jsonify({'success': False, 'message': '未找到指定的设备配置'})
                
                equipment_id = result['equipment_id']
                
                # 更新设备配置
                sql = """
                UPDATE web_equipment_config 
                SET temp_NOR_min=%s, temp_NOR_max=%s, temp_ABN_min=%s, temp_ABN_max=%s,
                    humi_NOR_min=%s, humi_NOR_max=%s, humi_ABN_min=%s, humi_ABN_max=%s,
                    aqi_NOR_max=%s, aqi_ABN_max=%s, timeout_NOR=%s, timeout_ABN=%s
                WHERE id=%s
                """
                values = (
                    data.get('temp_NOR_min'), data.get('temp_NOR_max'), 
                    data.get('temp_ABN_min'), data.get('temp_ABN_max'),
                    data.get('humi_NOR_min'), data.get('humi_NOR_max'), 
                    data.get('humi_ABN_min'), data.get('humi_ABN_max'),
                    data.get('aqi_NOR_max'), data.get('aqi_ABN_max'),
                    data.get('timeout_NOR'), data.get('timeout_ABN'),
                    config_id
                )
                
                cursor.execute(sql, values)
                conn.commit()
                
                # 主动推送新阈值给ESP32
                try:
                    from emqx_manager import get_emqx_manager
                    emqx_manager = get_emqx_manager()
                    
                    # 构建阈值配置消息
                    threshold_message = {
                        "equipment_id": equipment_id,
                        "query": "threshold_config",
                        "temp_NOR_min": float(data.get('temp_NOR_min', 18.0)),
                        "temp_NOR_max": float(data.get('temp_NOR_max', 25.0)),
                        "humi_NOR_min": float(data.get('humi_NOR_min', 40.0)),
                        "humi_NOR_max": float(data.get('humi_NOR_max', 70.0)),
                        "aqi_NOR_max": float(data.get('aqi_NOR_max', 100.0)),
                        "temp_ABN_min": float(data.get('temp_ABN_min', 15.0)),
                        "temp_ABN_max": float(data.get('temp_ABN_max', 30.0)),
                        "humi_ABN_min": float(data.get('humi_ABN_min', 30.0)),
                        "humi_ABN_max": float(data.get('humi_ABN_max', 80.0)),
                        "aqi_ABN_max": float(data.get('aqi_ABN_max', 200.0))
                    }
                    
                    topic = "/server/command/esp32"
                    message = json.dumps(threshold_message, ensure_ascii=False)
                    emqx_manager.publish(topic, message, qos=1)
                    print(f"[配置更新] 已推送新阈值配置到设备 {equipment_id}")
                except Exception as e:
                    print(f"[配置更新] 推送阈值到设备 {equipment_id} 失败: {str(e)}")
                
                return jsonify({'success': True, 'message': '设备配置更新成功'})
        except Exception as e:
            print(f"Error updating equipment config: {e}")
            if conn:
                conn.rollback()
            return jsonify({'success': False, 'message': f'更新设备配置失败: {str(e)}'})
        finally:
            if conn:
                conn.close()
    
    @app.route('/api/equipment-config', methods=['POST'])
    @login_required
    def add_equipment_config():
        """
        添加新的设备配置
        """
        conn = None
        try:
            # 获取请求数据
            data = request.get_json()
            
            # 验证必填字段
            if 'equipment_id' not in data or not data['equipment_id']:
                return jsonify({'success': False, 'message': '缺少必填字段: equipment_id'})
            
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 检查设备ID是否已存在
                cursor.execute("SELECT id FROM web_equipment_config WHERE equipment_id = %s", (data['equipment_id'],))
                if cursor.fetchone():
                    return jsonify({'success': False, 'message': '设备ID已存在'})
                
                # 插入新设备配置
                sql = """
                INSERT INTO web_equipment_config 
                (equipment_id, temp_NOR_min, temp_NOR_max, temp_ABN_min, temp_ABN_max,
                 humi_NOR_min, humi_NOR_max, humi_ABN_min, humi_ABN_max,
                 aqi_NOR_max, aqi_ABN_max, timeout_NOR, timeout_ABN)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                values = (
                    data['equipment_id'],
                    data.get('temp_NOR_min', 15.00), data.get('temp_NOR_max', 25.00),
                    data.get('temp_ABN_min', 10.00), data.get('temp_ABN_max', 30.00),
                    data.get('humi_NOR_min', 30.00), data.get('humi_NOR_max', 60.00),
                    data.get('humi_ABN_min', 20.00), data.get('humi_ABN_max', 70.00),
                    data.get('aqi_NOR_max', 100.00), data.get('aqi_ABN_max', 200.00),
                    data.get('timeout_NOR', 300), data.get('timeout_ABN', 600)
                )
                
                cursor.execute(sql, values)
                conn.commit()
                
                return jsonify({'success': True, 'message': '设备配置添加成功'})
        except Exception as e:
            print(f"Error adding equipment config: {e}")
            if conn:
                conn.rollback()
            return jsonify({'success': False, 'message': f'添加设备配置失败: {str(e)}'})
        finally:
            if conn:
                conn.close()
    
    @app.route('/api/equipment-config/<int:config_id>', methods=['DELETE'])
    @login_required
    def delete_equipment_config(config_id):
        """
        删除设备配置
        """
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 删除设备配置
                cursor.execute("DELETE FROM web_equipment_config WHERE id = %s", (config_id,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    return jsonify({'success': True, 'message': '设备配置删除成功'})
                else:
                    return jsonify({'success': False, 'message': '未找到指定的设备配置'})
        except Exception as e:
            print(f"Error deleting equipment config: {e}")
            if conn:
                conn.rollback()
            return jsonify({'success': False, 'message': f'删除设备配置失败: {str(e)}'})
        finally:
            if conn:
                conn.close()


def evaluate_equipment_health_status(equipment_id, get_db_connection_func):
    """
    评估设备健康状态
    
    Args:
        equipment_id: 设备ID
        get_db_connection_func: 获取数据库连接的函数
    """
    conn_web = None
    conn_history = None
    
    try:
        # 获取web数据库连接
        conn_web = get_db_connection_func()
        cursor_web = conn_web.cursor()
        
        # 读取设备配置信息
        config_query = "SELECT temp_NOR_min, temp_NOR_max, temp_ABN_min, temp_ABN_max, humi_NOR_min, humi_NOR_max, humi_ABN_min, humi_ABN_max, aqi_NOR_max, aqi_ABN_max, timeout_NOR, timeout_ABN FROM web_equipment_config WHERE equipment_id = %s"
        cursor_web.execute(config_query, (equipment_id,))
        config_data = cursor_web.fetchone()
        
        if not config_data:
            print(f"[健康评估] 未找到设备 {equipment_id} 的配置信息")
            return
            
        # 读取设备当前状态
        status_query = "SELECT door_status, lock_status, timeout FROM web_equipment WHERE equipment_id = %s"
        cursor_web.execute(status_query, (equipment_id,))
        status_data = cursor_web.fetchone()
        
        if not status_data:
            print(f"[健康评估] 未找到设备 {equipment_id} 的状态信息")
            return
            
        # 获取历史数据库连接并读取最新的环境数据
        from config import MYSQL_DATABASE_2
        from emqx_manager import get_emqx_manager
        emqx_manager = get_emqx_manager()
        conn_history = emqx_manager.get_db_connection(MYSQL_DATABASE_2)
        cursor_history = conn_history.cursor()
        
        # 读取最新的环境数据
        history_table = f"history_environment_data_{equipment_id}"
        env_query = f"SELECT temperature, humidity, aqi FROM {history_table} ORDER BY id DESC LIMIT 1"
        cursor_history.execute(env_query)
        env_data = cursor_history.fetchone()
        
        if not env_data:
            print(f"[健康评估] 未找到设备 {equipment_id} 的环境数据")
            return
        
        # 环境状态评估
        env_status = 0  # 0-正常, 1-异常, 2-报警
        
        # 检查温度
        temp = env_data['temperature'] if isinstance(env_data, dict) else env_data[0]
        if temp is not None:
            if temp <= float(config_data['temp_ABN_min']) or temp >= float(config_data['temp_ABN_max']):
                env_status = 2  # 报警
            elif temp <= float(config_data['temp_NOR_min']) or temp >= float(config_data['temp_NOR_max']):
                env_status = max(env_status, 1)  # 异常
                
        # 检查湿度
        humi = env_data['humidity'] if isinstance(env_data, dict) else env_data[1]
        if humi is not None:
            if humi <= float(config_data['humi_ABN_min']) or humi >= float(config_data['humi_ABN_max']):
                env_status = 2  # 报警
            elif humi <= float(config_data['humi_NOR_min']) or humi >= float(config_data['humi_NOR_max']):
                env_status = max(env_status, 1)  # 异常
                
        # 检查AQI
        aqi = env_data['aqi'] if isinstance(env_data, dict) else env_data[2]
        if aqi is not None:
            if aqi >= float(config_data['aqi_ABN_max']):
                env_status = 2  # 报警
            elif aqi >= float(config_data['aqi_NOR_max']):
                env_status = max(env_status, 1)  # 异常
        
        # 门锁状态评估
        door_lock_status = 0  # 0-正常, 1-异常, 2-报警
        
        door = status_data['door_status'] if isinstance(status_data, dict) else status_data[0]
        lock = status_data['lock_status'] if isinstance(status_data, dict) else status_data[1]
        timeout = status_data['timeout'] if isinstance(status_data, dict) else status_data[2]
        
        # 状态定义：
        # 门状态：0-关闭，1-开启
        # 锁状态：0-未锁(解锁)，1-已锁(锁定)
        
        # 检查最近是否有未处理的门锁报警（非法开门）
        try:
            alarm_query = """
                SELECT COUNT(*) as alarm_count 
                FROM web_alarm_log 
                WHERE equipment_id = %s 
                AND alarm_category = '门锁报警' 
                AND status = '未处理'
                AND save_time >= DATE_SUB(NOW(), INTERVAL 5 MINUTE)
            """
            cursor_web.execute(alarm_query, (equipment_id,))
            alarm_result = cursor_web.fetchone()
            recent_alarm_count = alarm_result['alarm_count'] if isinstance(alarm_result, dict) else alarm_result[0]
            
            if recent_alarm_count > 0:
                door_lock_status = 2  # 有未处理的门锁报警，设为报警状态
                print(f"[健康评估] 设备 {equipment_id} 检测到 {recent_alarm_count} 条未处理的门锁报警")
        except Exception as e:
            print(f"[健康评估] 检查报警记录时出错: {str(e)}")
        
        # 如果没有报警记录，再进行常规状态评估
        if door_lock_status == 0:
            # 报警条件检查
            # 1. 门开着且超时达到报警阈值
            # 2. 门开着且锁已锁（暴力开门）- 正常情况下门开着时锁应该是未锁状态
            if (door == 1 and timeout >= config_data['timeout_ABN']) or (door == 1 and lock == 1):
                door_lock_status = 2  # 报警
            # 异常条件检查
            # 1. 门开着且超时在异常范围内
            elif door == 1 and config_data['timeout_NOR'] <= timeout < config_data['timeout_ABN']:
                door_lock_status = 1  # 异常
            # 正常条件检查
            # 1. 门关着且锁关着且无超时
            # 2. 门开着且超时在正常范围内且锁打开
            # 3. 门关着且锁开着但超时在正常范围内（正常使用流程中的中间状态）
            elif (door == 0 and lock == 0 and timeout == 0) or (
                    door == 1 and lock == 1 and timeout < config_data['timeout_NOR']) or (
                    door == 0 and lock == 1 and timeout < config_data['timeout_NOR']):
                door_lock_status = 0  # 正常
            # 其他情况都视为正常
            else:
                door_lock_status = 0  # 正常
        
        # 综合评估健康状态 (报警 > 异常 > 正常)
        final_health_status = max(env_status, door_lock_status)
        
        # 更新设备健康状态
        update_query = "UPDATE web_equipment SET health_status = %s WHERE equipment_id = %s"
        cursor_web.execute(update_query, (final_health_status, equipment_id))
        conn_web.commit()
        
        # 发送健康状态到ESP32
        import json
        health_status_message = {
            "equipment_id": equipment_id,
            "health_status": final_health_status
        }
        topic = f"/server/command/esp32"
        message = json.dumps(health_status_message, ensure_ascii=False)
        emqx_manager.publish(topic, message, qos=1)
        print(f"[健康评估] 已发送健康状态 {final_health_status} 到设备 {equipment_id}")
        
        # 打印评估结果
        status_text = ["正常", "异常", "报警"]
        print(f"[健康评估] 设备 {equipment_id} 健康状态: {status_text[final_health_status]} "
              f"(环境:{status_text[env_status]}, 门锁:{status_text[door_lock_status]})")
              
    except Exception as e:
        print(f"[健康评估] 评估设备 {equipment_id} 健康状态时出错: {str(e)}")
    finally:
        # 关闭数据库连接
        if 'cursor_web' in locals():
            cursor_web.close()
        if 'conn_web' in locals():
            conn_web.close()
        if 'cursor_history' in locals():
            cursor_history.close()
        if 'conn_history' in locals():
            conn_history.close()