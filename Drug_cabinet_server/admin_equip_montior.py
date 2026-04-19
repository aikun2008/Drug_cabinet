from flask import render_template, jsonify
from datetime import datetime, timedelta
import threading
import time
import json
import queue

# 从emqx_manager导入发布消息的功能和主题常量
from emqx_manager import get_emqx_manager, TOPIC_PUBLISH_COMMAND, TOPIC_ENVIRONMENT_DATA_NOW, TOPIC_DOOR_LOCK_DATA_NOW

# 存储定时发布任务的字典，key为设备ID，value为线程对象和停止标志
equipment_publish_tasks = {}

# 存储设备实时数据的字典
equipment_realtime_data = {}

# 存储MQTT订阅任务的字典
equipment_subscription_tasks = {}

# 存储远程操作监控定时器
remote_operation_timers = {}

# 初始化设备相关路由
def init_equipment_routes(app, login_required, get_db_connection):
    # 导入需要的模块
    from flask import request
    # 从admin_dashboard导入menu_items和add_url_to_menu_items
    from admin_dashboard import menu_items, add_url_to_menu_items
    
    # 设备状态映射常量 - 根据新的表结构定义（基于connection_status和health_status）
    STATUS_EMOJI = {
        # (连接状态, 健康状态): (emoji, 状态名称)
        (0, 0): ('🟢', '在线正常'),   # 在线且正常
        (0, 1): ('🟡', '在线异常'),   # 在线但异常
        (0, 2): ('🔴', '在线报警'),   # 在线且报警
        (1, 0): ('⚪', '离线正常'),   # 离线但正常
        (1, 1): ('🟠', '离线异常'),   # 离线且异常
        (1, 2): ('🔴', '离线报警')    # 离线且报警
    }
    
    # 格式化时间的辅助函数
    def format_time_ago(timestamp):
        """将时间戳格式化为相对时间描述"""
        if isinstance(timestamp, datetime):
            time_diff = datetime.now() - timestamp
            if time_diff < timedelta(minutes=1):
                return '刚刚'
            elif time_diff < timedelta(hours=1):
                return f'{int(time_diff.total_seconds() / 60)}分钟前'
            elif time_diff < timedelta(days=1):
                return f'{int(time_diff.total_seconds() / 3600)}小时前'
            else:
                return timestamp.strftime('%Y-%m-%d %H:%M:%S')
        return '未知'
    
    # 设备监控页面路由
    @app.route('/admin/device-monitoring')
    @login_required
    def admin_equipment_interface():
        menu_items_with_urls = add_url_to_menu_items(menu_items, 'device_monitoring')
        return render_template('admin_equip_montior.html', 
                              menu_items=menu_items_with_urls, 
                              active_menu='device_monitoring')
    
    # 添加对admin_equip_montior.html的直接访问支持
    @app.route('/admin_equip_montior.html')
    @login_required
    def admin_dashboard_equipment_html():
        # 复用admin_equipment_interface函数的逻辑
        return admin_equipment_interface()
    
    # 获取设备列表API - 从web_equipment表读取数据
    @app.route('/api/equipment', methods=['GET'])
    @login_required
    def get_equipment():
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 从web_equipment表查询数据
                cursor.execute("SELECT * FROM web_equipment ORDER BY last_online DESC")
                equipment_list = cursor.fetchall()
                
                # 格式化数据为前端需要的格式
                formatted_equipment = [{
                    'id': eq.get('id'),
                    'equipment_name': eq.get('equipment_name'),
                    'equipment_id': eq.get('equipment_id'),
                    'equipment_address': eq.get('equipment_address'),
                    'connection_status': eq.get('connection_status', 1),  # 连接状态：0-在线，1-离线
                    'health_status': eq.get('health_status', 0),          # 健康状态：0-正常，1-异常，2-报警
                    'status_emoji': STATUS_EMOJI.get((eq.get('connection_status', 1), eq.get('health_status', 0)), ('❓', '未知'))[0],  # 状态emoji
                    'status_name': STATUS_EMOJI.get((eq.get('connection_status', 1), eq.get('health_status', 0)), ('❓', '未知'))[1],   # 状态名称
                    'door_status': eq.get('door_status', 0),  # 门状态
                    'lock_status': eq.get('lock_status', 0),  # 锁状态
                    'last_online': eq.get('last_online'),  # 原始时间戳
                    'last_online_display': format_time_ago(eq.get('last_online')),  # 格式化后的时间
                    'created_at': eq.get('created_at'),
                    'updated_at': eq.get('updated_at')
                } for eq in equipment_list]
                
                return jsonify({'success': True, 'data': formatted_equipment})
        except Exception as e:
            print(f"Error fetching equipment: {e}")
            return jsonify({'success': False, 'message': '获取设备数据失败'})
        finally:
            if conn:
                conn.close()
    
    # 新增设备API
    @app.route('/admin/equipment/add', methods=['POST'])
    @login_required
    def add_equipment():
        conn = None
        try:
            # 获取请求数据
            data = request.get_json()
            
            # 验证必填字段
            required_fields = ['equipment_name', 'equipment_id', 'equipment_address']
            for field in required_fields:
                if field not in data or not data[field]:
                    return jsonify({'success': False, 'message': f'缺少必填字段: {field}'})
            
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 检查设备ID是否已存在
                cursor.execute("SELECT id FROM web_equipment WHERE equipment_id = %s", (data['equipment_id'],))
                if cursor.fetchone():
                    return jsonify({'success': False, 'message': '设备ID已存在'})
                
                # 插入新设备
                sql = """
                INSERT INTO web_equipment 
                (equipment_name, equipment_id, equipment_address, connection_status, health_status, door_status, lock_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                values = (
                    data['equipment_name'],
                    data['equipment_id'],
                    data['equipment_address'],
                    data.get('connection_status', 1),  # 默认离线
                    data.get('health_status', 0),      # 默认正常
                    data.get('door_status', 0),        # 默认关闭
                    data.get('lock_status', 0)         # 默认锁定
                )
                
                cursor.execute(sql, values)
                conn.commit()
                
                return jsonify({'success': True, 'message': '设备添加成功'})
        except Exception as e:
            print(f"Error adding equipment: {e}")
            if conn:
                conn.rollback()
            return jsonify({'success': False, 'message': f'添加设备失败: {str(e)}'})
        finally:
            if conn:
                conn.close()
    
    def publish_environment_query(equipment_id, stop_event):
        """定时向EMQX发布环境数据和门锁数据查询消息"""
        topic = TOPIC_PUBLISH_COMMAND
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 定时任务开始运行，设备ID: {equipment_id}")
        
        # 导入需要的模块
        from emqx_manager import get_emqx_manager
        import json
        import time
        
        try:
            while not stop_event.is_set():
                try:
                    # 获取EMQX管理器
                    emqx_manager = get_emqx_manager()
                    
                    if emqx_manager:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 获取到EMQX管理器，准备发布消息")
                        if emqx_manager.is_connected:
                            # 1. 发布环境数据查询消息
                            env_message = json.dumps({
                                "equipment_id": equipment_id,
                                "query": "environment_data_now"
                            })
                            success = emqx_manager.publish(topic, env_message)
                            if success:
                                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✓ 成功向主题 {topic} 发布环境数据查询消息: {env_message}")
                            else:
                                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ 发布环境数据查询消息失败")
                            
                            # 2. 发布门锁数据查询消息
                            door_message = json.dumps({
                                "equipment_id": equipment_id,
                                "query": "door_lock_data_now"
                            })
                            success = emqx_manager.publish(topic, door_message)
                            if success:
                                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✓ 成功向主题 {topic} 发布门锁数据查询消息: {door_message}")
                            else:
                                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ 发布门锁数据查询消息失败")
                        else:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ EMQX未连接")
                    else:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ 无法获取EMQX管理器")
                    
                    # 等待5秒，每秒检查一次停止标志
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 等待5秒...")
                    for _ in range(5):
                        if stop_event.is_set():
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 收到停止信号")
                            break
                        time.sleep(1)
                    
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 定时发布任务循环异常: {str(e)}")
                    time.sleep(1)
        finally:
            # 任务结束后从字典中移除
            if equipment_id in equipment_publish_tasks:
                del equipment_publish_tasks[equipment_id]
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 设备 {equipment_id} 的定时发布任务已停止")
    
    # 打印设备ID到终端的API
    @app.route('/api/print-equipment-id/<equipment_id>', methods=['GET'])
    @login_required
    def print_equipment_id(equipment_id):
        # 直接打印设备ID到服务器终端
        print(f"设备ID: {equipment_id}")
        # 返回成功响应给前端
        return jsonify({'success': True, 'message': '设备ID已打印到终端'})
    
    # 启动定时发布环境数据查询命令的API
    @app.route('/api/start-publish/<equipment_id>', methods=['POST'])
    @login_required
    def start_publish(equipment_id):
        try:
            # 检查是否已有该设备的任务在运行
            if equipment_id in equipment_publish_tasks:
                return jsonify({'success': False, 'message': '该设备已存在发布任务'})
            
            # 创建停止标志
            stop_event = threading.Event()
            
            # 创建并启动线程
            publish_thread = threading.Thread(
                target=publish_environment_query,
                args=(equipment_id, stop_event),
                daemon=True
            )
            
            # 存储任务信息
            equipment_publish_tasks[equipment_id] = {
                'thread': publish_thread,
                'stop_event': stop_event
            }
            
            # 启动线程
            publish_thread.start()
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始向设备 {equipment_id} 定时发布环境数据查询命令")
            return jsonify({'success': True, 'message': '定时发布任务已启动'})
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 启动发布任务异常: {str(e)}")
            return jsonify({'success': False, 'message': f'启动任务失败: {str(e)}'})
    
    def subscribe_equipment_topics(equipment_id, stop_event):
        """订阅设备相关的MQTT主题并处理接收到的消息"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始订阅设备 {equipment_id} 的MQTT主题")
        
        # 需要订阅的主题
        topics = [
            (TOPIC_ENVIRONMENT_DATA_NOW, 0),
            (TOPIC_DOOR_LOCK_DATA_NOW, 0)
        ]
        
        # 获取EMQX管理器
        emqx_manager = get_emqx_manager()
        
        if not emqx_manager or not emqx_manager.is_connected:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ EMQX未连接，无法订阅主题")
            return
        
        # 本地消息处理函数
        def handle_mqtt_message(client, userdata, msg):
            try:
                payload = msg.payload.decode()
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 收到主题 {msg.topic} 的消息: {payload}")
                
                # 解析JSON消息
                data = json.loads(payload)
                
                # 只处理我们关心的主题
                if msg.topic not in [TOPIC_ENVIRONMENT_DATA_NOW, TOPIC_DOOR_LOCK_DATA_NOW]:
                    return
                
                # 检查消息格式：必须包含equipment_id字段
                if 'equipment_id' not in data:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ 消息格式错误，缺少必要字段 equipment_id")
                    return
                
                # 检查equipment_id是否匹配
                if data['equipment_id'] != equipment_id:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ 设备ID不匹配，忽略消息")
                    return
                
                # 初始化设备数据字典
                if equipment_id not in equipment_realtime_data:
                    equipment_realtime_data[equipment_id] = {}
                
                # 根据主题类型更新数据
                if msg.topic == TOPIC_ENVIRONMENT_DATA_NOW:
                    # 更新环境数据
                    if 'temp' in data:
                        equipment_realtime_data[equipment_id]['temperature'] = f"{data['temp']}°C"
                    if 'humi' in data:
                        equipment_realtime_data[equipment_id]['humidity'] = f"{data['humi']}%"
                    if 'AQI' in data:
                        equipment_realtime_data[equipment_id]['aqi'] = str(data['AQI'])
                    # 更新时间戳
                    equipment_realtime_data[equipment_id]['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✓ 已更新设备 {equipment_id} 的环境数据")
                
                elif msg.topic == TOPIC_DOOR_LOCK_DATA_NOW:
                    # 更新门锁状态
                    if 'door' in data:
                        equipment_realtime_data[equipment_id]['door_status'] = '开启' if data['door'] == 1 else '关闭'
                    if 'lock' in data:
                        equipment_realtime_data[equipment_id]['lock_status'] = '解锁' if data['lock'] == 1 else '锁定'
                    if 'buzzer' in data:
                        equipment_realtime_data[equipment_id]['buzzer_status'] = '开启' if data['buzzer'] == 1 else '关闭'
                    # 更新时间戳
                    equipment_realtime_data[equipment_id]['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✓ 已更新设备 {equipment_id} 的门锁状态数据")
                
            except json.JSONDecodeError:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ JSON格式错误")
            except Exception as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ 处理MQTT消息异常: {str(e)}")
        
        # 保存原始的on_message回调
        original_on_message = emqx_manager.client._on_message
        
        try:
            # 订阅主题
            for topic, qos in topics:
                success = emqx_manager.subscribe(topic, qos)
                if not success:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ 订阅主题 {topic} 失败")
                else:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✓ 已订阅主题 {topic}")
            
            # 临时替换消息处理回调
            def combined_on_message(client, userdata, msg):
                # 调用原始回调
                if original_on_message:
                    original_on_message(client, userdata, msg)
                # 调用本地处理函数
                handle_mqtt_message(client, userdata, msg)
            
            emqx_manager.client.on_message = combined_on_message
            
            # 等待停止信号
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 设备 {equipment_id} 订阅任务开始运行")
            while not stop_event.is_set():
                time.sleep(0.5)
            
        finally:
            # 恢复原始的on_message回调
            emqx_manager.client.on_message = original_on_message
            
            # 取消订阅主题
            for topic, qos in topics:
                try:
                    emqx_manager.client.unsubscribe(topic)
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✓ 已取消订阅主题 {topic}")
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ 取消订阅主题 {topic} 时出错: {str(e)}")
            
            # 从字典中移除任务信息
            if equipment_id in equipment_subscription_tasks:
                del equipment_subscription_tasks[equipment_id]
            
            # 清理设备数据
            if equipment_id in equipment_realtime_data:
                del equipment_realtime_data[equipment_id]
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 设备 {equipment_id} 的订阅任务已停止")
    
    # 停止定时发布环境数据查询命令的API
    @app.route('/api/stop-publish/<equipment_id>', methods=['POST'])
    @login_required
    def stop_publish(equipment_id):
        try:
            # 检查任务是否存在
            if equipment_id not in equipment_publish_tasks:
                return jsonify({'success': False, 'message': '该设备没有运行的发布任务'})
            
            # 设置停止标志
            equipment_publish_tasks[equipment_id]['stop_event'].set()
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 停止向设备 {equipment_id} 定时发布环境数据查询命令")
            return jsonify({'success': True, 'message': '定时发布任务已停止'})
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 停止发布任务异常: {str(e)}")
            return jsonify({'success': False, 'message': f'停止任务失败: {str(e)}'})
    
    # 启动设备MQTT主题订阅的API
    @app.route('/api/start-subscription/<equipment_id>', methods=['POST'])
    @login_required
    def start_subscription(equipment_id):
        try:
            # 检查是否已有该设备的订阅任务在运行
            if equipment_id in equipment_subscription_tasks:
                return jsonify({'success': False, 'message': '该设备已存在订阅任务'})
            
            # 创建停止标志
            stop_event = threading.Event()
            
            # 创建并启动线程
            subscription_thread = threading.Thread(
                target=subscribe_equipment_topics,
                args=(equipment_id, stop_event),
                daemon=True
            )
            
            # 存储任务信息
            equipment_subscription_tasks[equipment_id] = {
                'thread': subscription_thread,
                'stop_event': stop_event
            }
            
            # 启动线程
            subscription_thread.start()
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始订阅设备 {equipment_id} 的MQTT主题")
            return jsonify({'success': True, 'message': '订阅任务已启动'})
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 启动订阅任务异常: {str(e)}")
            return jsonify({'success': False, 'message': f'启动订阅任务失败: {str(e)}'})
    
    # 停止设备MQTT主题订阅的API
    @app.route('/api/stop-subscription/<equipment_id>', methods=['POST'])
    @login_required
    def stop_subscription(equipment_id):
        try:
            # 检查任务是否存在
            if equipment_id not in equipment_subscription_tasks:
                return jsonify({'success': False, 'message': '该设备没有运行的订阅任务'})
            
            # 设置停止标志
            equipment_subscription_tasks[equipment_id]['stop_event'].set()
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 停止订阅设备 {equipment_id} 的MQTT主题")
            return jsonify({'success': True, 'message': '订阅任务已停止'})
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 停止订阅任务异常: {str(e)}")
            return jsonify({'success': False, 'message': f'停止订阅任务失败: {str(e)}'})
    
    # 获取设备实时数据的API
    @app.route('/api/equipment-realtime-data/<equipment_id>', methods=['GET'])
    @login_required
    def get_equipment_realtime_data(equipment_id):
        try:
            # 检查是否有该设备的实时数据
            if equipment_id in equipment_realtime_data:
                backend_data = equipment_realtime_data[equipment_id]
                # 字段名映射，将后端存储的字段名转换为前端期望的字段名
                frontend_data = {
                    # 环境数据字段映射
                    'temp': backend_data.get('temperature', '').replace('°C', '') if isinstance(backend_data.get('temperature'), str) else backend_data.get('temperature'),
                    'humi': backend_data.get('humidity', '').replace('%', '') if isinstance(backend_data.get('humidity'), str) else backend_data.get('humidity'),
                    'AQI': backend_data.get('aqi'),
                    # 设备状态字段映射（需要转换回数值形式）
                    'door': 1 if backend_data.get('door_status') == '开启' else 0,
                    'lock': 1 if backend_data.get('lock_status') == '解锁' else 0,
                    'buzzer': 1 if backend_data.get('buzzer_status') == '开启' else 0,
                    # 时间字段映射
                    'time': backend_data.get('update_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                }
                return jsonify({'success': True, 'data': frontend_data})
            else:
                return jsonify({'success': False, 'message': '暂无实时数据', 'data': {}})
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 获取实时数据异常: {str(e)}")
            return jsonify({'success': False, 'message': f'获取实时数据失败: {str(e)}'})
    
    # 获取单个设备详情API
    @app.route('/api/equipment/<equipment_id>', methods=['GET'])
    @login_required
    def get_equipment_detail(equipment_id):
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 从web_equipment表查询指定设备的数据
                cursor.execute("SELECT * FROM web_equipment WHERE equipment_id = %s", (equipment_id,))
                equipment = cursor.fetchone()
                
                if not equipment:
                    return jsonify({'success': False, 'message': '设备不存在'})
                
                # 格式化数据为前端需要的格式
                formatted_equipment = {
                    'id': equipment.get('id'),
                    'equipment_name': equipment.get('equipment_name'),
                    'equipment_id': equipment.get('equipment_id'),
                    'equipment_address': equipment.get('equipment_address'),
                    'connection_status': equipment.get('connection_status', 1),  # 连接状态
                    'health_status': equipment.get('health_status', 0),          # 健康状态
                    'status_emoji': STATUS_EMOJI.get((equipment.get('connection_status', 1), equipment.get('health_status', 0)), ('❓', '未知'))[0],  # 状态emoji
                    'status_name': STATUS_EMOJI.get((equipment.get('connection_status', 1), equipment.get('health_status', 0)), ('❓', '未知'))[1],   # 状态名称
                    'door_status': '开启' if equipment.get('door_status', 0) == 1 else '关闭',
                    'lock_status': '解锁' if equipment.get('lock_status', 0) == 1 else '锁定',
                    'last_online': equipment.get('last_online').strftime('%Y-%m-%d %H:%M:%S') if equipment.get('last_online') else '未知',
                    'created_at': equipment.get('created_at').strftime('%Y-%m-%d %H:%M:%S') if equipment.get('created_at') else '未知',
                    'updated_at': equipment.get('updated_at').strftime('%Y-%m-%d %H:%M:%S') if equipment.get('updated_at') else '未知'
                }
                
                return jsonify({'success': True, 'data': formatted_equipment})
        except Exception as e:
            print(f"Error fetching equipment detail: {e}")
            return jsonify({'success': False, 'message': '获取设备详情失败'})
        finally:
            if conn:
                conn.close()

    # 远程控制设备锁API
    @app.route('/api/equipment/remote-control', methods=['POST'])
    @login_required
    def remote_control_equipment():
        conn = None
        try:
            data = request.get_json()
            equipment_id = data.get('equipment_id')
            action = data.get('action')  # 'unlock' 或 'lock'

            if not equipment_id or action not in ['unlock', 'lock']:
                return jsonify({'success': False, 'message': '参数错误'})

            # 检查设备是否存在和在线
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT connection_status, door_status, lock_status FROM web_equipment WHERE equipment_id = %s", (equipment_id,))
                equipment = cursor.fetchone()

                if not equipment:
                    return jsonify({'success': False, 'message': '设备不存在'})

                # 检查设备是否在线
                if equipment['connection_status'] != 0:
                    return jsonify({'success': False, 'message': '设备离线，无法远程控制'})

                # 安全机制：如果门是打开状态，禁止远程上锁（防止夹伤或损坏）
                if action == 'lock' and equipment['door_status'] == 1:
                    return jsonify({'success': False, 'message': '门处于打开状态，无法远程上锁'})

                # 检查是否已经有活动会话（用户正在使用）
                # 如果门开着且锁开着，说明用户可能正在使用
                if action == 'lock' and equipment['door_status'] == 0 and equipment['lock_status'] == 1:
                    # 门关闭但锁是开的，可能是正常使用中
                    pass  # 允许远程上锁，这是正常的远程锁门操作

            # 获取EMQX管理器
            emqx_manager = get_emqx_manager()
            if not emqx_manager or not emqx_manager.is_connected:
                return jsonify({'success': False, 'message': 'MQTT连接不可用'})

            # 构建控制命令
            command = {
                'equipment_id': equipment_id,
                'command': 'remote_unlock' if action == 'unlock' else 'remote_lock',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'web_admin',
                'require_ack': True,  # 要求设备确认
                'timeout': 10  # 10秒超时
            }

            # 发布控制命令到设备（使用通用主题，ESP32已订阅）
            topic = "/server/command/esp32"
            message = json.dumps(command, ensure_ascii=False)
            result = emqx_manager.publish(topic, message, qos=1)

            if result:
                # 记录操作日志
                try:
                    with conn.cursor() as cursor:
                        sql = """
                            INSERT INTO user_operations
                            (operation_time, rfid_card_id, operation_type, equipment_id, target_id, description)
                            VALUES (NOW(), %s, %s, %s, %s, %s)
                        """
                        from flask import session
                        user_id = session.get('user_id', 0)
                        operation_type = 'remote_unlock' if action == 'unlock' else 'remote_lock'
                        description = f"远程{'开锁' if action == 'unlock' else '上锁'}操作"
                        ip_address = request.remote_addr
                        # 使用 user_id 作为 rfid_card_id，ip_address 作为 target_id
                        cursor.execute(sql, (str(user_id), operation_type, equipment_id, ip_address, description))
                        conn.commit()

                        # 如果是远程开锁，记录到远程操作监控表
                        if action == 'unlock':
                            # 先删除该设备的旧记录
                            cursor.execute("DELETE FROM remote_operation_monitor WHERE equipment_id = %s", (equipment_id,))
                            # 插入新记录
                            cursor.execute("""
                                INSERT INTO remote_operation_monitor
                                (equipment_id, operation_time, operator_id, status, timeout_seconds)
                                VALUES (%s, NOW(), %s, 'active', 60)
                            """, (equipment_id, user_id))
                            conn.commit()

                            # 启动超时监控定时器
                            start_remote_operation_monitor(equipment_id, 60)
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 记录操作日志失败: {str(e)}")

                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 远程控制命令已发送: {equipment_id} - {action}")
                return jsonify({'success': True, 'message': f"远程{'开锁' if action == 'unlock' else '上锁'}命令已发送"})
            else:
                return jsonify({'success': False, 'message': '发送命令失败'})

        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 远程控制异常: {str(e)}")
            return jsonify({'success': False, 'message': f'操作失败: {str(e)}'})
        finally:
            if conn:
                conn.close()

    # 启动远程操作监控
    def start_remote_operation_monitor(equipment_id, timeout_seconds):
        """启动远程操作超时监控"""
        # 取消之前的定时器（如果存在）
        if equipment_id in remote_operation_timers:
            remote_operation_timers[equipment_id].cancel()

        # 创建新的定时器
        timer = threading.Timer(timeout_seconds, check_remote_operation_timeout, args=[equipment_id])
        timer.daemon = True
        timer.start()
        remote_operation_timers[equipment_id] = timer
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 启动远程操作监控: {equipment_id}, 超时时间: {timeout_seconds}秒")

    # 检查远程操作超时
    def check_remote_operation_timeout(equipment_id):
        """检查远程操作是否超时，如果超时则生成报警"""
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 查询该设备的远程操作记录
                cursor.execute("""
                    SELECT * FROM remote_operation_monitor
                    WHERE equipment_id = %s AND status = 'active'
                """, (equipment_id,))
                record = cursor.fetchone()

                if record:
                    # 检查是否已超时
                    operation_time = record['operation_time']
                    timeout_seconds = record['timeout_seconds']
                    elapsed = (datetime.now() - operation_time).total_seconds()

                    if elapsed >= timeout_seconds:
                        # 已超时，生成报警
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [报警] 远程开锁超时: {equipment_id}")

                        # 插入报警记录
                        cursor.execute("""
                            INSERT INTO web_alarm_log
                            (equipment_id, alarm_category, alarm_content, save_time, status)
                            VALUES (%s, %s, %s, NOW(), %s)
                        """, (equipment_id, '远程操作超时', f'远程开锁后超过{timeout_seconds}秒未上锁，请检查设备状态', '未处理'))

                        # 更新监控记录状态
                        cursor.execute("""
                            UPDATE remote_operation_monitor
                            SET status = 'timeout', alarm_generated = TRUE
                            WHERE equipment_id = %s
                        """, (equipment_id,))

                        conn.commit()

                        # 发送报警通知到设备（可选）
                        emqx_manager = get_emqx_manager()
                        if emqx_manager and emqx_manager.is_connected:
                            command = {
                                'equipment_id': equipment_id,
                                'command': 'remote_operation_timeout',
                                'message': '远程开锁超时，请尽快处理',
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            emqx_manager.publish("/server/command/esp32", json.dumps(command), qos=1)
                    else:
                        # 还未超时，重新启动定时器
                        remaining = timeout_seconds - elapsed
                        start_remote_operation_monitor(equipment_id, remaining)

        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 检查远程操作超时异常: {str(e)}")
        finally:
            if conn:
                conn.close()

    # 处理远程上锁确认（清除监控）
    @app.route('/api/equipment/remote-lock-ack', methods=['POST'])
    @login_required
    def remote_lock_ack():
        """接收远程上锁确认，清除监控记录"""
        conn = None
        try:
            data = request.get_json()
            equipment_id = data.get('equipment_id')

            if not equipment_id:
                return jsonify({'success': False, 'message': '参数错误'})

            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 取消定时器
                if equipment_id in remote_operation_timers:
                    remote_operation_timers[equipment_id].cancel()
                    del remote_operation_timers[equipment_id]

                # 更新监控记录状态
                cursor.execute("""
                    UPDATE remote_operation_monitor
                    SET status = 'completed', completed_time = NOW()
                    WHERE equipment_id = %s AND status = 'active'
                """, (equipment_id,))
                conn.commit()

            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 远程上锁确认: {equipment_id}")
            return jsonify({'success': True, 'message': '远程上锁已确认'})

        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 远程上锁确认异常: {str(e)}")
            return jsonify({'success': False, 'message': f'操作失败: {str(e)}'})
        finally:
            if conn:
                conn.close()
