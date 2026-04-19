from flask import Flask, request, jsonify
import atexit
import pymysql
from datetime import datetime
import os
import platform
import subprocess
import time
from functools import lru_cache

# 导入登录相关功能
from login import export_dict as login_export
login_required = login_export['login_required']
init_login_routes = login_export['init_login_routes']

# 导入admin界面相关功能
from admin_dashboard import export_dict as admin_export
init_admin_routes = admin_export['init_admin_routes']

# 导入环境数据日志功能
from admin_env_log import export_dict as env_log_export
init_env_log_routes = env_log_export['init_env_log_routes']

# 导入用户操作日志功能
from admin_user_log import export_dict as user_log_export
init_user_log_routes = user_log_export['init_user_log_routes']

# 导入系统报警日志功能
from admin_alarm_log import export_dict as alarm_log_export
init_alarm_log_routes = alarm_log_export['init_alarm_log_routes']

# 导入用户档案功能以获取MYSQL_TABLE_USER_1
from admin_user_profile import init_user_routes

# 导入入库/出库功能
from admin_drug_input_output import admin_drug_input_output_bp

# 导入教师药品目录功能
from teacher_drug_catalogue import export_dict as teacher_export
init_teacher_routes = teacher_export['init_teacher_routes']

# 导入教师药品借阅和归还功能
from teacher_drug_BOR_RET import export_dict as teacher_bor_ret_export
init_teacher_borrow_return_routes = teacher_bor_ret_export['init_teacher_borrow_return_routes']

# 导入学生药品借阅和归还功能
from student_drug_BOR_RET import export_dict as student_bor_ret_export
init_student_borrow_return_routes = student_bor_ret_export['init_student_borrow_return_routes']

# 导入EMQX连接管理器
from emqx_manager import init_emqx_connection, get_emqx_manager

# 导入数据库配置
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE_1, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB, REDIS_DEFAULT_TTL

# 数据库表名
MYSQL_TABLE_USER_1 = 'user_1'

# 全局数据库连接池
class DatabasePool:
    """数据库连接池管理类"""
    
    def __init__(self):
        self.pool = None
        self.is_initialized = False
    
    def initialize(self):
        """初始化数据库连接池"""
        if self.is_initialized:
            return True
        
        # 检查MySQL服务是否运行
        if not self._check_mysql_service():
            print("MySQL服务未运行，正在尝试启动...")
            if not self._start_mysql_service():
                print("MySQL服务启动失败，无法初始化连接池")
                return False
            # 等待服务完全启动
            time.sleep(2)
        
        try:
            # 尝试使用pymysqlpool
            try:
                from pymysqlpool import ConnectionPool
                self.pool = ConnectionPool(
                    host=MYSQL_HOST,
                    port=MYSQL_PORT,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    database=MYSQL_DATABASE_1,
                    charset='utf8mb4',
                    cursorclass=pymysql.cursors.DictCursor,
                    maxsize=10,  # 最大连接数
                    minsize=3    # 最小连接数
                )
            except ImportError:
                # 如果pymysqlpool不可用，使用简单的连接池实现
                print("pymysqlpool不可用，使用简单连接池实现")
                from queue import Queue
                self.pool = Queue(maxsize=10)
                # 初始化连接池
                for _ in range(3):  # 初始3个连接
                    conn = pymysql.connect(
                        host=MYSQL_HOST,
                        port=MYSQL_PORT,
                        user=MYSQL_USER,
                        password=MYSQL_PASSWORD,
                        database=MYSQL_DATABASE_1,
                        charset='utf8mb4',
                        cursorclass=pymysql.cursors.DictCursor
                    )
                    self.pool.put(conn)
            self.is_initialized = True
            print("数据库连接池初始化成功")
            return True
        except Exception as e:
            print(f"初始化数据库连接池失败: {e}")
            return False
    
    def _check_mysql_service(self):
        """检查MySQL服务是否正在运行"""
        system_type = platform.system()
        
        try:
            if system_type == "Windows":
                # Windows系统：使用sc query命令检查MySQL服务状态
                result = subprocess.run(
                    ["sc", "query", "MySQL"],
                    capture_output=True,
                    text=True,
                    shell=True
                )
                return "RUNNING" in result.stdout
            elif system_type == "Linux":
                # Linux系统：使用systemctl或service命令检查MySQL服务状态
                if os.path.exists("/usr/bin/systemctl"):
                    # 使用systemctl
                    result = subprocess.run(
                        ["systemctl", "is-active", "mysql"],
                        capture_output=True,
                        text=True
                    )
                    return result.stdout.strip() == "active"
                else:
                    # 使用service命令
                    result = subprocess.run(
                        ["service", "mysql", "status"],
                        capture_output=True,
                        text=True
                    )
                    return "running" in result.stdout.lower()
            else:
                print(f"不支持的操作系统: {system_type}")
                return False
        except Exception as e:
            print(f"检查MySQL服务状态时出错: {e}")
            return False
    
    def _start_mysql_service(self):
        """启动MySQL服务"""
        system_type = platform.system()
        
        try:
            if system_type == "Windows":
                # Windows系统：使用sc start命令启动MySQL服务
                result = subprocess.run(
                    ["sc", "start", "MySQL"],
                    capture_output=True,
                    text=True,
                    shell=True
                )
                if result.returncode == 0 or "请求的服务已经启动" in result.stdout:
                    print("MySQL服务启动成功")
                    return True
                else:
                    print(f"Windows启动MySQL服务失败: {result.stderr}")
                    return False
            elif system_type == "Linux":
                # Linux系统：使用systemctl或service命令启动MySQL服务
                if os.path.exists("/usr/bin/systemctl"):
                    # 使用systemctl
                    result = subprocess.run(
                        ["sudo", "systemctl", "start", "mysql"],
                        capture_output=True,
                        text=True
                    )
                else:
                    # 使用service命令
                    result = subprocess.run(
                        ["sudo", "service", "mysql", "start"],
                        capture_output=True,
                        text=True
                    )
                
                if result.returncode == 0:
                    print("MySQL服务启动成功")
                    return True
                else:
                    print(f"Linux启动MySQL服务失败: {result.stderr}")
                    return False
            else:
                print(f"不支持的操作系统: {system_type}")
                return False
        except Exception as e:
            print(f"启动MySQL服务时出错: {e}")
            return False
    
    def get_connection(self):
        """获取数据库连接"""
        if not self.is_initialized:
            if not self.initialize():
                return None
        
        try:
            # 检查是否使用pymysqlpool
            if hasattr(self.pool, 'get_connection'):
                return self.pool.get_connection()
            else:
                # 使用简单连接池实现
                if self.pool.qsize() > 0:
                    conn = self.pool.get()
                    # 检查连接是否有效
                    try:
                        conn.ping()
                        return conn
                    except:
                        # 连接失效，创建新连接
                        print("连接失效，创建新连接")
                        conn = pymysql.connect(
                            host=MYSQL_HOST,
                            port=MYSQL_PORT,
                            user=MYSQL_USER,
                            password=MYSQL_PASSWORD,
                            database=MYSQL_DATABASE_1,
                            charset='utf8mb4',
                            cursorclass=pymysql.cursors.DictCursor
                        )
                        return conn
                else:
                    # 连接池为空，创建新连接
                    print("连接池为空，创建新连接")
                    conn = pymysql.connect(
                        host=MYSQL_HOST,
                        port=MYSQL_PORT,
                        user=MYSQL_USER,
                        password=MYSQL_PASSWORD,
                        database=MYSQL_DATABASE_1,
                        charset='utf8mb4',
                        cursorclass=pymysql.cursors.DictCursor
                    )
                    return conn
        except Exception as e:
            print(f"获取数据库连接失败: {e}")
            return None

# 创建全局数据库连接池实例
db_pool = DatabasePool()

# 数据库连接函数
def get_db_connection():
    """获取数据库连接"""
    return db_pool.get_connection()

# 导入Redis缓存管理器
try:
    from redis_manager import init_cache_manager, get_cache_manager
    from db_cache_sync import init_cache_sync, get_cached_db_connection
    # 初始化Redis缓存管理器
    init_cache_manager(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        db=REDIS_DB,
        default_ttl=REDIS_DEFAULT_TTL
    )
    # 初始化缓存同步管理器
    init_cache_sync()
    print("Redis缓存管理器初始化成功")
except Exception as e:
    print(f"Redis缓存管理器初始化失败: {e}")
    pass  # Redis初始化失败时静默处理，不影响系统运行

# 获取带缓存的数据库连接
cached_db = get_cached_db_connection(get_db_connection) if 'get_cached_db_connection' in globals() else None

# 创建Flask应用实例
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or os.urandom(32).hex()

# 初始化EMQX连接（应用启动时自动连接）
print("正在初始化EMQX连接...")
if init_emqx_connection():
    print("EMQX连接初始化成功")
else:
    print("EMQX连接初始化失败，但应用将继续启动")

# 注册退出处理函数，确保程序退出时正确断开EMQX连接
def cleanup():
    print("正在关闭EMQX连接...")
    emqx_manager = get_emqx_manager()
    emqx_manager.disconnect()
    print("EMQX连接已关闭")

atexit.register(cleanup)

# 初始化登录路由
init_login_routes(app)

# 初始化环境数据日志路由
init_env_log_routes(app, login_required)

# 初始化用户操作日志路由
init_user_log_routes(app, login_required, get_db_connection, cached_db)

# 初始化系统报警日志路由
init_alarm_log_routes(app, login_required)

# 初始化教师路由
init_teacher_routes(app, login_required, get_db_connection, cached_db)

# 初始化教师药品借阅和归还路由
init_teacher_borrow_return_routes(app, login_required, get_db_connection)

# 初始化学生药品借阅和归还路由
init_student_borrow_return_routes(app, login_required, get_db_connection)

# 初始化admin路由，传入login_required装饰器（最高优先级）
init_admin_routes(app, login_required)

# 注册入库/出库路由
app.register_blueprint(admin_drug_input_output_bp)

# EMQX webhook路由 - 处理设备连接/断开事件
@app.route('/mqtt/webhook', methods=['POST'])
def mqtt_webhook():
    """处理EMQX webhook请求"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
        
        action = data.get('action') or data.get('event')
        clientid = data.get('clientid') or data.get('client_id')
        
        # 转换 event 格式：client.connected -> client_connected
        if action:
            action = action.replace('.', '_')
        
        if not action or not clientid:
            return jsonify({"error": "Missing action or clientid"}), 400
        
        # 只处理以"cabinet_"开头的客户端ID
        if not clientid.startswith('cabinet_'):
            return jsonify({"message": "Ignored: clientid does not match pattern"}), 200
        
        connection = get_db_connection()
        if not connection:
            return jsonify({"error": "Database connection failed"}), 500
        
        try:
            with connection.cursor() as cursor:
                if action == 'client_connected':
                    # 设备上线 - 设置connection_status为0（在线）
                    # 注意：不自动重置版本号，只有在收到无效版本信息时才会重置
                    sql = """
                        UPDATE web_equipment 
                        SET connection_status = 0, last_online = %s 
                        WHERE equipment_id = %s
                    """
                    cursor.execute(sql, (datetime.now(), clientid))
                    connection.commit()
                    print(f"设备上线: {clientid}")
                    
                elif action == 'client_disconnected':
                    # 设备下线 - 设置connection_status为1（离线）
                    sql = """
                        UPDATE web_equipment 
                        SET connection_status = 1 
                        WHERE equipment_id = %s
                    """
                    cursor.execute(sql, (clientid,))
                    connection.commit()
                    print(f"设备下线: {clientid}")
                
                else:
                    return jsonify({"message": f"Ignored: unsupported action {action}"}), 200
                
                # 检查是否有记录被更新
                if cursor.rowcount > 0:
                    return jsonify({"message": f"Device {clientid} status updated successfully"}), 200
                else:
                    print(f"未找到设备记录: {clientid}")
                    return jsonify({"message": f"Device {clientid} not found in database"}), 200
                    
        finally:
            # 检查是否使用简单连接池
            if hasattr(db_pool.pool, 'put'):
                # 返回连接到池
                try:
                    db_pool.pool.put(connection)
                except Exception as e:
                    print(f"返回连接到池失败: {e}")
                    connection.close()
            else:
                # 使用pymysqlpool，连接会自动管理
                pass
            
    except Exception as e:
        print(f"webhook处理错误: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


# ==================== 最新活动API ====================
@app.route('/api/recent-activities', methods=['GET'])
@login_required
def get_recent_activities():
    """获取最新活动 - 包括报警、药品借还、入库出库"""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        # 尝试从缓存获取
        cache_key = f"recent_activities:{limit}"
        cache_manager = get_cache_manager()
        cached_result = cache_manager.get(cache_key)
        
        if cached_result:
            return jsonify({
                'success': True,
                'data': cached_result
            })
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'})
        
        activities = []
        
        # 1. 获取最新报警记录
        sql_alarm = """
            SELECT 
                'alarm' as type,
                id,
                equipment_id as device_id,
                alarm_category as category,
                alarm_content as content,
                save_time as timestamp,
                NULL as user_name,
                NULL as medicine_name,
                NULL as extra_info
            FROM web_alarm_log
            WHERE save_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            ORDER BY save_time DESC
            LIMIT %s
        """
        with conn.cursor() as cursor:
            cursor.execute(sql_alarm, (limit,))
            alarm_records = cursor.fetchall()
            for record in alarm_records:
                activities.append({
                    'type': 'alarm',
                    'id': record['id'],
                    'device_id': record['device_id'],
                    'category': record['category'],
                    'content': record['content'],
                    'timestamp': record['timestamp'].isoformat() if record['timestamp'] else None,
                    'icon': '🔔',
                    'title': f"{record['device_id']} {record['category']}",
                    'description': record['content'] or '设备异常',
                    'time': record['timestamp']
                })
        
        # 2. 获取药品借还记录
        sql_borrow = """
            SELECT 
                'borrow' as type,
                mt.id,
                mt.equipment_id as device_id,
                mt.operation_type as category,
                NULL as content,
                mt.operation_time as timestamp,
                wu.real_name as user_name,
                wml.name as medicine_name,
                NULL as extra_info
            FROM medicine_trace mt
            LEFT JOIN web_user wu ON mt.rfid_card_id = wu.rfid_card_id
            LEFT JOIN web_medicine_list wml ON mt.medicine_code = wml.medicine_code
            WHERE mt.operation_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            ORDER BY mt.operation_time DESC
            LIMIT %s
        """
        with conn.cursor() as cursor:
            cursor.execute(sql_borrow, (limit,))
            borrow_records = cursor.fetchall()
            for record in borrow_records:
                operation_text = '借用了' if record['category'] == 'borrow' else '归还了'
                activities.append({
                    'type': 'borrow',
                    'id': record['id'],
                    'device_id': record['device_id'],
                    'category': record['category'],
                    'content': None,
                    'timestamp': record['timestamp'].isoformat() if record['timestamp'] else None,
                    'icon': '👤',
                    'title': record['user_name'] or '未知用户',
                    'description': f"{operation_text} {record['medicine_name'] or '未知药品'}",
                    'time': record['timestamp']
                })
        
        # 3. 获取入库记录
        sql_import = """
            SELECT 
                'import' as type,
                id,
                NULL as device_id,
                '批量入库' as category,
                NULL as content,
                import_time as timestamp,
                NULL as user_name,
                NULL as medicine_name,
                CONCAT('成功', success_count, ', 失败', error_count) as extra_info
            FROM batch_import_record
            WHERE import_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            ORDER BY import_time DESC
            LIMIT %s
        """
        with conn.cursor() as cursor:
            cursor.execute(sql_import, (limit,))
            import_records = cursor.fetchall()
            for record in import_records:
                activities.append({
                    'type': 'import',
                    'id': record['id'],
                    'device_id': None,
                    'category': record['category'],
                    'content': None,
                    'timestamp': record['timestamp'].isoformat() if record['timestamp'] else None,
                    'icon': '📦',
                    'title': '批量药品入库',
                    'description': f"导入结果: {record['extra_info']}",
                    'time': record['timestamp']
                })
        
        # 检查是否使用简单连接池
        if hasattr(db_pool.pool, 'put'):
            # 返回连接到池
            try:
                db_pool.pool.put(conn)
            except Exception as e:
                print(f"返回连接到池失败: {e}")
                conn.close()
        else:
            # 使用pymysqlpool，连接会自动管理
            pass
        
        # 按时间排序，取最新的limit条
        activities.sort(key=lambda x: x['time'] if x['time'] else datetime.min, reverse=True)
        activities = activities[:limit]
        
        # 移除time字段（前端不需要）
        for activity in activities:
            activity.pop('time', None)
        
        # 缓存结果，设置较短的过期时间（1分钟）
        cache_manager.set(cache_key, activities, ttl=60)
        
        return jsonify({
            'success': True,
            'data': activities
        })
        
    except Exception as e:
        print(f"获取最新活动失败: {e}")
        return jsonify({'success': False, 'message': f'获取最新活动失败: {str(e)}'})


# ==================== Token 验证API ====================
@app.route('/api/check_token', methods=['GET'])
def check_token():
    """验证token有效性"""
    try:
        # 从Authorization头中获取token
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'message': '无效的token格式'})
        
        token = auth_header.split(' ')[1]
        if not token:
            return jsonify({'success': False, 'message': 'token为空'})
        
        # 使用JWT验证token
        from login import verify_jwt_token
        payload = verify_jwt_token(token)
        
        if not payload:
            return jsonify({'success': False, 'message': 'Token无效或已过期'})
        
        user_id = payload.get('user_id')
        
        # 从数据库中获取用户信息
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'})
        
        try:
            with conn.cursor() as cursor:
                # 查询用户信息
                cursor.execute("SELECT id, username, real_name, role, department, phone, email, status FROM web_user WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                
                if not user:
                    return jsonify({'success': False, 'message': '用户不存在'})
                
                # 构建用户信息
                user_info = {
                    'id': user['id'],
                    'username': user['username'],
                    'real_name': user['real_name'],
                    'role': user['role'],
                    'department': user.get('department', ''),
                    'phone': user.get('phone', ''),
                    'email': user.get('email', ''),
                    'status': user['status']
                }
                
                return jsonify({
                    'success': True,
                    'user_info': user_info
                })
        finally:
            # 检查是否使用简单连接池
            if hasattr(db_pool.pool, 'put'):
                # 返回连接到池
                try:
                    db_pool.pool.put(conn)
                except Exception as e:
                    print(f"返回连接到池失败: {e}")
                    conn.close()
            else:
                # 使用pymysqlpool，连接会自动管理
                pass
            
    except Exception as e:
        print(f"验证token失败: {e}")
        return jsonify({'success': False, 'message': f'验证token失败: {str(e)}'})


# 启动应用
if __name__ == '__main__':
    print("使用Flask默认服务器启动...")
    app.run(debug=False, host='127.0.0.1', port=5000)