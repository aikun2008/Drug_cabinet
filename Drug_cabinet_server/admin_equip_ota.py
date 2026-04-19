from flask import Blueprint, render_template, request, jsonify
import os
import uuid
import base64
import hashlib
import threading
import time
from datetime import datetime

# 创建蓝图
admin_equip_ota_bp = Blueprint('admin_equip_ota', __name__)

# 存储OTA升级状态
ota_status = {}

# 存储版本查询结果
version_queries = {}

# 固件存储目录 - 使用绝对路径，确保固件文件能被正确访问
FIRMWARE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'firmware')
if not os.path.exists(FIRMWARE_DIR):
    os.makedirs(FIRMWARE_DIR)

# MQTT OTA 配置
MQTT_OTA_PACKET_SIZE = 256  # 每包 256 字节（更小的包，更稳定的传输）
MQTT_OTA_TIMEOUT = 10  # 超时时间（秒）
MQTT_OTA_MAX_RETRY = 3  # 最大重试次数

# OTA 主题定义
TOPIC_OTA_COMMAND = "/server/ota/command/{equipment_id}"  # 服务器->设备: 开始OTA命令
TOPIC_OTA_REQUEST = "/esp32/ota/request/{equipment_id}"    # 设备->服务器: 请求数据包
TOPIC_OTA_DATA = "/server/ota/data/{equipment_id}"         # 服务器->设备: 发送固件数据
TOPIC_OTA_ACK = "/esp32/ota/ack/{equipment_id}"            # 设备->服务器: 确认收到
TOPIC_OTA_STATUS = "/esp32/ota_status/server"              # 设备->服务器: OTA状态上报

class MqttOtaSession:
    """MQTT OTA 会话管理类"""
    def __init__(self, equipment_id, firmware_path, firmware_size, total_packets, md5_hash):
        self.equipment_id = equipment_id
        self.firmware_path = firmware_path
        self.firmware_size = firmware_size
        self.total_packets = total_packets
        self.md5_hash = md5_hash
        self.current_packet = 0
        self.retry_count = 0
        self.is_active = False
        self.lock = threading.Lock()
        self.last_activity = time.time()
        self.firmware_data = None  # 固件数据缓存
        self.pending_packet = None  # 待确认的包序号
        self.pending_timer = None   # 超时定时器
        
    def load_firmware(self):
        """加载固件文件到内存"""
        try:
            with open(self.firmware_path, 'rb') as f:
                self.firmware_data = f.read()
            return True
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 加载固件文件失败: {str(e)}")
            return False
    
    def get_packet_data(self, packet_index):
        """获取指定包的数据"""
        if self.firmware_data is None:
            return None
        
        start_pos = packet_index * MQTT_OTA_PACKET_SIZE
        end_pos = min(start_pos + MQTT_OTA_PACKET_SIZE, self.firmware_size)
        
        if start_pos >= self.firmware_size:
            return None
            
        return self.firmware_data[start_pos:end_pos]
    
    def update_activity(self):
        """更新最后活动时间"""
        self.last_activity = time.time()
    
    def set_pending_packet(self, packet_index):
        """设置待确认的包，启动超时定时器"""
        self.pending_packet = packet_index
        # 取消之前的定时器
        if self.pending_timer:
            self.pending_timer.cancel()
        # 启动新的超时定时器
        self.pending_timer = threading.Timer(MQTT_OTA_TIMEOUT, self._on_packet_timeout)
        self.pending_timer.start()
    
    def clear_pending_packet(self):
        """清除待确认的包"""
        self.pending_packet = None
        if self.pending_timer:
            self.pending_timer.cancel()
            self.pending_timer = None
    
    def _on_packet_timeout(self):
        """包发送超时回调"""
        if self.pending_packet is not None and self.is_active:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 包 {self.pending_packet} 超时，准备重传")
            # 触发重传
            handle_ota_request(self.equipment_id, self.pending_packet)

# 全局OTA会话字典
ota_sessions = {}

def init_equip_ota_routes(app, login_required, get_db_connection):
    """
    初始化远程升级相关的路由
    """
    
    @app.route('/admin_equip_ota.html')
    @login_required
    def admin_equip_ota():
        """
        远程升级页面
        """
        return render_template('admin_equip_ota.html')
    
    @app.route('/api/start-ota', methods=['POST'])
    @login_required
    def start_ota():
        """
        开始MQTT OTA升级
        1. 接收固件文件
        2. 保存固件文件
        3. 计算MD5和分包信息
        4. 发送OTA开始命令到设备
        5. 等待设备请求数据包
        """
        try:
            # 检查请求中是否包含文件
            if 'firmware' not in request.files:
                return jsonify({'success': False, 'message': '未找到固件文件'})
            
            # 获取设备ID
            equipment_id = request.form.get('equipment_id')
            if not equipment_id:
                return jsonify({'success': False, 'message': '未指定设备ID'})
            
            # 获取升级描述
            description = request.form.get('description', '')
            
            # 获取固件文件
            firmware_file = request.files['firmware']
            if firmware_file.filename == '':
                return jsonify({'success': False, 'message': '未选择固件文件'})
            
            # 检查文件扩展名
            if not firmware_file.filename.endswith('.bin'):
                return jsonify({'success': False, 'message': '请上传.bin格式的固件文件'})
            
            # 生成唯一的固件文件名
            firmware_uuid = str(uuid.uuid4())
            firmware_filename = f"{firmware_uuid}_{firmware_file.filename}"
            firmware_path = os.path.join(FIRMWARE_DIR, firmware_filename)
            
            # 保存固件文件
            firmware_file.save(firmware_path)
            
            # 计算固件大小和MD5
            firmware_size = os.path.getsize(firmware_path)
            total_packets = (firmware_size + MQTT_OTA_PACKET_SIZE - 1) // MQTT_OTA_PACKET_SIZE
            
            with open(firmware_path, 'rb') as f:
                md5_hash = hashlib.md5(f.read()).hexdigest()
            
            # 初始化OTA状态
            ota_status[equipment_id] = {
                'status': 'started',
                'progress': 0,
                'message': '准备开始OTA升级...',
                'firmware_path': firmware_path,
                'firmware_size': firmware_size,
                'total_packets': total_packets,
                'md5_hash': md5_hash,
                'description': description,
                'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'current_packet': 0,
                'retry_count': 0
            }
            
            # 创建OTA会话
            session = MqttOtaSession(equipment_id, firmware_path, firmware_size, total_packets, md5_hash)
            if not session.load_firmware():
                return jsonify({'success': False, 'message': '加载固件文件失败'})
            
            ota_sessions[equipment_id] = session
            
            # 从emqx_manager导入get_emqx_manager
            from emqx_manager import get_emqx_manager
            
            # 获取EMQX管理器实例
            emqx_manager = get_emqx_manager()
            
            # 构建OTA开始命令
            ota_command = {
                "equipment_id": equipment_id,
                "command": "mqtt_ota_start",
                "firmware_size": firmware_size,
                "total_packets": total_packets,
                "packet_size": MQTT_OTA_PACKET_SIZE,
                "md5": md5_hash,
                "description": description
            }
            
            # 发送OTA开始命令到设备
            import json
            topic = TOPIC_OTA_COMMAND.format(equipment_id=equipment_id)
            success = emqx_manager.publish(topic, json.dumps(ota_command), qos=1)
            
            if success:
                session.is_active = True
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] OTA开始命令已发送到设备 {equipment_id}")
                print(f"  固件大小: {firmware_size} bytes")
                print(f"  总包数: {total_packets}")
                print(f"  MD5: {md5_hash}")
                
                return jsonify({
                    'success': True,
                    'message': 'OTA升级命令已发送，等待设备响应',
                    'equipment_id': equipment_id,
                    'firmware_size': firmware_size,
                    'total_packets': total_packets
                })
            else:
                # 清理会话
                if equipment_id in ota_sessions:
                    del ota_sessions[equipment_id]
                return jsonify({'success': False, 'message': '发送OTA命令失败'})
                
        except Exception as e:
            return jsonify({'success': False, 'message': f'处理OTA升级时出错: {str(e)}'})
    
    @app.route('/api/ota-status/<equipment_id>', methods=['GET'])
    @login_required
    def get_ota_status(equipment_id):
        """
        获取OTA升级状态
        """
        try:
            if equipment_id in ota_status:
                return jsonify({
                    'success': True,
                    'status': ota_status[equipment_id]['status'],
                    'progress': ota_status[equipment_id]['progress'],
                    'message': ota_status[equipment_id]['message'],
                    'current_packet': ota_status[equipment_id].get('current_packet', 0),
                    'total_packets': ota_status[equipment_id].get('total_packets', 0)
                })
            else:
                return jsonify({
                    'success': True,
                    'status': 'idle',
                    'progress': 0,
                    'message': '设备当前没有OTA升级任务'
                })
        except Exception as e:
            return jsonify({'success': False, 'message': f'获取OTA状态时出错: {str(e)}'})
    
    @app.route('/api/update-ota-status', methods=['POST'])
    def update_ota_status():
        """
        更新OTA升级状态（由设备调用）
        """
        try:
            data = request.get_json()
            equipment_id = data.get('equipment_id')
            status = data.get('status')
            progress = data.get('progress', 0)
            message = data.get('message', '')
            
            if not equipment_id or not status:
                return jsonify({'success': False, 'message': '缺少必要参数'})
            
            if equipment_id in ota_status:
                ota_status[equipment_id]['status'] = status
                ota_status[equipment_id]['progress'] = progress
                ota_status[equipment_id]['message'] = message
                
                # 如果升级完成或失败，添加结束时间
                if status in ['completed', 'failed']:
                    ota_status[equipment_id]['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    # 清理会话
                    if equipment_id in ota_sessions:
                        del ota_sessions[equipment_id]
            else:
                # 如果是新的升级任务，初始化状态
                ota_status[equipment_id] = {
                    'status': status,
                    'progress': progress,
                    'message': message,
                    'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            
            return jsonify({'success': True, 'message': 'OTA状态已更新'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'更新OTA状态时出错: {str(e)}'})
    
    @app.route('/api/cancel-ota', methods=['POST'])
    @login_required
    def cancel_ota():
        """
        取消OTA升级
        """
        try:
            data = request.get_json()
            equipment_id = data.get('equipment_id')
            
            if not equipment_id:
                return jsonify({'success': False, 'message': '未指定设备ID'})
            
            # 发送取消命令到设备
            from emqx_manager import get_emqx_manager
            import json
            
            emqx_manager = get_emqx_manager()
            cancel_command = {
                "equipment_id": equipment_id,
                "command": "mqtt_ota_cancel"
            }
            
            topic = TOPIC_OTA_COMMAND.format(equipment_id=equipment_id)
            emqx_manager.publish(topic, json.dumps(cancel_command), qos=1)
            
            # 清理状态
            if equipment_id in ota_status:
                ota_status[equipment_id]['status'] = 'cancelled'
                ota_status[equipment_id]['message'] = 'OTA升级已取消'
            
            if equipment_id in ota_sessions:
                del ota_sessions[equipment_id]
            
            return jsonify({'success': True, 'message': 'OTA升级已取消'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'取消OTA升级时出错: {str(e)}'})
    
    @app.route('/api/equipment-version/<equipment_id>', methods=['GET'])
    @login_required
    def get_equipment_version(equipment_id):
        """
        获取设备版本号
        先查询数据库获取缓存的版本，同时发送MQTT命令请求最新版本
        如果设备在线，会更新数据库中的版本号
        """
        try:
            # 首先从数据库获取当前缓存的版本号
            conn = get_db_connection()
            cached_version = None
            last_online = None
            
            try:
                with conn.cursor() as cursor:
                    # 查询设备的固件版本和最后在线时间
                    sql = "SELECT firmware_version, last_online FROM web_equipment WHERE equipment_id = %s"
                    cursor.execute(sql, (equipment_id,))
                    result = cursor.fetchone()
                    if result:
                        cached_version = result['firmware_version']
                        last_online = result['last_online']
            finally:
                conn.close()
            
            # 从emqx_manager导入get_emqx_manager
            from emqx_manager import get_emqx_manager
            
            # 获取EMQX管理器实例
            emqx_manager = get_emqx_manager()
            
            # 构建版本查询命令
            version_query = {
                "equipment_id": equipment_id,
                "query": "version"
            }
            
            # 发送版本查询命令到设备
            from emqx_manager import TOPIC_PUBLISH_COMMAND
            import json
            
            success = emqx_manager.publish(TOPIC_PUBLISH_COMMAND, json.dumps(version_query))
            
            if success:
                # 初始化版本查询记录
                query_id = f"{equipment_id}_{int(time.time())}"
                version_queries[query_id] = {
                    'equipment_id': equipment_id,
                    'status': 'pending',
                    'version': None,
                    'timestamp': time.time()
                }
                
                # 等待设备响应（最多等待3秒）
                max_wait = 3
                waited = 0
                while waited < max_wait:
                    time.sleep(0.5)
                    waited += 0.5
                    
                    # 检查是否收到版本响应
                    if query_id in version_queries and version_queries[query_id]['status'] == 'received':
                        version = version_queries[query_id]['version']
                        # 清理查询记录
                        del version_queries[query_id]
                        return jsonify({
                            'success': True,
                            'version': version if version else '未知版本',
                            'source': 'device',
                            'message': '已获取设备实时版本'
                        })
                
                # 超时，清理查询记录
                if query_id in version_queries:
                    del version_queries[query_id]
                
                # 未收到设备响应，返回缓存的版本（如果有）
                if cached_version:
                    return jsonify({
                        'success': True,
                        'version': cached_version,
                        'source': 'cache',
                        'last_online': last_online.strftime('%Y-%m-%d %H:%M:%S') if last_online else None,
                        'message': '设备未响应，显示缓存版本'
                    })
                else:
                    return jsonify({
                        'success': True,
                        'version': None,
                        'source': 'none',
                        'message': '设备未响应，且无缓存版本'
                    })
            else:
                # MQTT发送失败，返回缓存版本（如果有）
                if cached_version:
                    return jsonify({
                        'success': True,
                        'version': cached_version,
                        'source': 'cache',
                        'message': '无法连接设备，显示缓存版本'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'version': None,
                        'message': '无法连接设备，且无缓存版本'
                    })
                
        except Exception as e:
            return jsonify({'success': False, 'message': f'获取设备版本号时出错: {str(e)}'})


def handle_ota_request(equipment_id, packet_index, total_packets=None, current_progress=None):
    """
    处理设备的OTA数据包请求
    由emqx_manager在收到设备请求时调用
    支持断点续传：根据设备报告的进度调整发送位置
    """
    try:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [DEBUG] handle_ota_request 被调用: equipment_id={equipment_id}, packet_index={packet_index}")
        
        if equipment_id not in ota_sessions:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 未找到设备 {equipment_id} 的OTA会话")
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [DEBUG] 当前会话列表: {list(ota_sessions.keys())}")
            return False
        
        session = ota_sessions[equipment_id]
        
        if not session.is_active:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 设备 {equipment_id} 的 OTA 会话未激活")
            # 会话未激活但设备请求数据，可能设备重启了，需要重新发送开始命令
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 设备可能重启了，重新发送 OTA 开始命令")
            
            # 重新激活会话
            session.is_active = True
            session.current_packet = packet_index  # 从设备请求的位置开始
            
            # 重新发送开始命令
            from emqx_manager import get_emqx_manager
            emqx = get_emqx_manager()
            if emqx:
                start_message = {
                    "equipment_id": equipment_id,
                    "command": "mqtt_ota_start",
                    "firmware_size": session.firmware_size,
                    "total_packets": session.total_packets,
                    "packet_size": MQTT_OTA_PACKET_SIZE,
                    "md5": session.md5_hash,
                    "description": "OTA 恢复"
                }
                topic = TOPIC_OTA_COMMAND.format(equipment_id=equipment_id)
                emqx.publish(topic, json.dumps(start_message))
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] OTA 开始命令已重新发送到设备 {equipment_id}")
                
            # 继续发送数据包
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 继续发送包 {packet_index + 1}/{session.total_packets}")
        
        # 更新活动时间
        session.update_activity()
        
        # 断点续传：如果设备报告的进度和会话不一致，以设备为准
        if total_packets is not None and total_packets != session.total_packets:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 设备 {equipment_id} 总包数不匹配: {total_packets} vs {session.total_packets}")
        
        # 如果设备请求的包序号和会话当前位置差距太大，可能是断线重连
        if abs(packet_index - session.current_packet) > 10:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 设备 {equipment_id} 断点续传: 从 {session.current_packet} 跳到 {packet_index}")
            session.current_packet = packet_index
        
        # 获取请求的数据包
        packet_data = session.get_packet_data(packet_index)
        if packet_data is None:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 无效的包序号: {packet_index}")
            return False
        
        # 构建数据包消息
        import json
        from emqx_manager import get_emqx_manager
        
        # Base64 编码数据
        encoded_data = base64.b64encode(packet_data).decode('utf-8')
        
        data_message = {
            "equipment_id": equipment_id,
            "packet_index": packet_index,
            "total_packets": session.total_packets,
            "data": encoded_data,
            "data_len": len(packet_data),          # 原始数据长度
            "encoded_len": len(encoded_data)       # Base64 编码后长度
        }
        
        # 发送数据包到设备
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [DEBUG] 准备发送数据包到主题: {TOPIC_OTA_DATA.format(equipment_id=equipment_id)}")
        emqx_manager = get_emqx_manager()
        if not emqx_manager:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 无法获取EMQX管理器")
            return False
        
        topic = TOPIC_OTA_DATA.format(equipment_id=equipment_id)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [DEBUG] 正在发布消息到主题: {topic}")
        success = emqx_manager.publish(topic, json.dumps(data_message), qos=1)
        
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [DEBUG] 发布结果: {success}")
        
        if success:
            # 更新状态
            session.current_packet = packet_index
            if equipment_id in ota_status:
                progress = int((packet_index + 1) * 100 / session.total_packets)
                ota_status[equipment_id]['current_packet'] = packet_index + 1
                ota_status[equipment_id]['progress'] = progress
                ota_status[equipment_id]['message'] = f'正在传输固件... ({packet_index + 1}/{session.total_packets})'
            
            # 设置待确认包，启动超时定时器
            session.set_pending_packet(packet_index)
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已发送包 {packet_index + 1}/{session.total_packets} 到设备 {equipment_id}")
            
            # 添加延迟，给 ESP32 处理时间（Flash 写入需要较长时间）
            import time
            time.sleep(0.2)  # 200ms 延迟，确保 ESP32 有足够时间处理
            
            return True
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 发送包 {packet_index} 到设备 {equipment_id} 失败")
            return False
            
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 处理OTA请求时出错: {str(e)}")
        return False


def handle_ota_ack(equipment_id, packet_index, status):
    """
    处理设备的OTA确认
    由emqx_manager在收到设备确认时调用
    """
    try:
        if equipment_id not in ota_sessions:
            return
        
        session = ota_sessions[equipment_id]
        session.update_activity()
        
        if status == 'ok':
            # 包接收成功，清除待确认状态
            session.clear_pending_packet()
            # 重置重试计数
            session.retry_count = 0
            
            # 检查是否所有包都已发送
            if packet_index + 1 >= session.total_packets:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 设备 {equipment_id} 所有固件包发送完成")
            else:
                # 自动发送下一包
                next_packet = packet_index + 1
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 收到ACK，自动发送下一包 {next_packet + 1}/{session.total_packets}")
                handle_ota_request(equipment_id, next_packet)
        elif status == 'error':
            # 包接收失败，增加重试计数
            session.retry_count += 1
            if session.retry_count > MQTT_OTA_MAX_RETRY:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 设备 {equipment_id} 超过最大重试次数")
                if equipment_id in ota_status:
                    ota_status[equipment_id]['status'] = 'failed'
                    ota_status[equipment_id]['message'] = '超过最大重试次数'
                session.is_active = False
            else:
                # 重新发送该包
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 重新发送包 {packet_index} 到设备 {equipment_id} (重试 {session.retry_count})")
                handle_ota_request(equipment_id, packet_index)
                
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 处理OTA确认时出错: {str(e)}")


def cleanup_inactive_sessions():
    """
    清理不活跃的OTA会话
    可以定期调用此函数
    """
    current_time = time.time()
    inactive_sessions = []
    
    for equipment_id, session in ota_sessions.items():
        if current_time - session.last_activity > MQTT_OTA_TIMEOUT * 3:
            inactive_sessions.append(equipment_id)
    
    for equipment_id in inactive_sessions:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 清理不活跃的OTA会话: {equipment_id}")
        if equipment_id in ota_sessions:
            del ota_sessions[equipment_id]
        if equipment_id in ota_status:
            ota_status[equipment_id]['status'] = 'timeout'
            ota_status[equipment_id]['message'] = 'OTA会话超时'


def handle_version_response(equipment_id, version):
    """
    处理设备返回的版本信息
    由emqx_manager在收到设备版本响应时调用
    """
    try:
        # 查找对应的版本查询记录
        for query_id, query_info in list(version_queries.items()):
            if query_info['equipment_id'] == equipment_id and query_info['status'] == 'pending':
                # 更新查询记录
                version_queries[query_id]['status'] = 'received'
                version_queries[query_id]['version'] = version
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 收到设备 {equipment_id} 的版本响应: {version}")
                return True
        
        # 如果没有找到对应的查询记录，可能是主动上报的版本
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 收到设备 {equipment_id} 的主动版本上报: {version}")
        return False
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 处理版本响应时出错: {str(e)}")
        return False


def cleanup_expired_version_queries():
    """
    清理过期的版本查询记录
    可以定期调用此函数
    """
    current_time = time.time()
    expired_queries = []
    
    for query_id, query_info in version_queries.items():
        # 超过10分钟的查询记录视为过期
        if current_time - query_info['timestamp'] > 600:
            expired_queries.append(query_id)
    
    for query_id in expired_queries:
        del version_queries[query_id]
