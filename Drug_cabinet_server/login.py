from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import pymysql
import bcrypt
import jwt
from datetime import datetime, timedelta
from functools import wraps
# 导入配置
import config
from permission_manager import get_permission_settings, check_login_time
# 从config中导入需要的配置项
MYSQL_HOST = config.MYSQL_HOST
MYSQL_PORT = config.MYSQL_PORT
MYSQL_USER = config.MYSQL_USER
MYSQL_PASSWORD = config.MYSQL_PASSWORD
MYSQL_DATABASE_1 = config.MYSQL_DATABASE_1
MYSQL_TABLE_USER_1 = config.MYSQL_TABLE_USER_1
MAX_LOGIN_ATTEMPTS = config.MAX_LOGIN_ATTEMPTS
LOCK_DURATION_MINUTES = config.LOCK_DURATION_MINUTES
JWT_SECRET_KEY = config.JWT_SECRET_KEY
JWT_EXPIRATION_HOURS = config.JWT_EXPIRATION_HOURS
# 数据库连接函数
def get_db_connection():
    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE_1,
        cursorclass=pymysql.cursors.DictCursor
    )
    return conn

# JWT Token生成函数
def generate_jwt_token(user_id, username, role):
    """生成JWT Token"""
    payload = {
        'user_id': user_id,
        'username': username,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')
    return token

# JWT Token验证函数
def verify_jwt_token(token):
    """验证JWT Token，返回用户信息或None"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        print("Token已过期")
        return None
    except jwt.InvalidTokenError:
        print("无效的Token")
        return None

# 登录检查装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 检查session（Web端）
        if 'user_id' in session:
            return f(*args, **kwargs)
        
        # 检查Authorization头（小程序端/API）
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            # 验证JWT Token
            user_info = verify_jwt_token(token)
            if user_info:
                # Token有效，将用户信息存入request对象供后续使用
                request.user = user_info
                return f(*args, **kwargs)
            else:
                # Token无效或过期
                if request.path.startswith('/api/') or request.path == '/drugs':
                    return jsonify({'success': False, 'message': 'Token无效或已过期'}), 401
                return redirect(url_for('login'))
        
        # 如果是API请求，返回401错误而不是重定向
        if request.path.startswith('/api/') or request.path == '/drugs':
            return jsonify({'success': False, 'message': '未授权'}), 401
        
        # 否则重定向到登录页面
        return redirect(url_for('login'))
    return decorated_function

# 初始化登录相关路由的函数
def init_login_routes(app):
    # 根路由重定向到登录页面
    @app.route('/')
    def index():
        return redirect(url_for('login'))
        
    # 登录页面
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            
            try:
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    # 检查用户是否存在
                    sql = f"SELECT * FROM {MYSQL_TABLE_USER_1} WHERE username = %s"
                    cursor.execute(sql, (username,))
                    user = cursor.fetchone()
                    
                    if not user:
                        # 用户不存在，仍然显示通用错误
                        return render_template('login.html', error='用户名或密码错误')
                    
                    # 检查账户状态
                    if user['status'] != 1:
                        return render_template('login.html', error='用户名或密码错误')
                    
                    # 检查用户角色，只有管理员(role=0)可以登录后台
                    if user['role'] != 0:
                        return render_template('login.html', error='您没有权限登录管理后台')
                    
                    # 检查登录权限
                    permissions = get_permission_settings(user['role'])
                    if permissions and not permissions.get('can_login', True):
                        return render_template('login.html', error='您所在的用户组暂不允许登录')
                    
                    # 检查登录时间范围
                    if permissions:
                        time_range = permissions.get('login_time_range', '00:00-23:59')
                        if not check_login_time(time_range):
                            return render_template('login.html', error=f'当前时间不允许登录，允许时间: {time_range}')
                    
                    # 检查是否被锁定
                    if user['locked_until'] and user['locked_until'] > datetime.now():
                        lock_time = user['locked_until'] - datetime.now()
                        minutes = lock_time.total_seconds() // 60
                        return render_template('login.html', error=f'账户已被锁定，请{int(minutes)}分钟后再试')
                    
                    # 只支持明文密码验证
                    password_match = (password == user['password'])
                    
                    if not password_match:
                        # 密码错误，更新失败次数
                        new_attempts = user['login_attempts'] + 1
                        locked_until = None
                        
                        # 检查是否需要锁定
                        if new_attempts >= MAX_LOGIN_ATTEMPTS:
                            locked_until = datetime.now() + timedelta(minutes=LOCK_DURATION_MINUTES)
                            
                        sql = f"UPDATE {MYSQL_TABLE_USER_1} SET login_attempts = %s, locked_until = %s WHERE id = %s"
                        cursor.execute(sql, (new_attempts, locked_until, user['id']))
                        conn.commit()
                        
                        return render_template('login.html', error='用户名或密码错误')
                    
                    # 登录成功，重置失败次数和锁定状态
                    sql = f"UPDATE {MYSQL_TABLE_USER_1} SET login_attempts = 0, locked_until = NULL, last_login = %s WHERE id = %s"
                    cursor.execute(sql, (datetime.now(), user['id']))
                    conn.commit()
                    
                    # 存储用户信息到session
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['role'] = user['role']
                    
                    # 构建返回数据
                    user_data = {
                        'id': user['id'],
                        'username': user['username'],
                        'real_name': user.get('real_name', ''),
                        'role': user['role'],
                        'department': user.get('department', ''),
                        'permissions': []  # 根据实际情况获取权限列表
                    }
                    
                    # 记录登录成功的用户数据到session（可选）
                    session['user_data'] = user_data
                    
                    # 不再创建新的EMQX连接，而是使用系统级的连接管理器
                    from emqx_manager import get_emqx_manager
                    emqx_manager = get_emqx_manager()
                    if emqx_manager.is_connected:
                        print(f"用户 {username} 已成功登录，复用系统级EMQX连接")
                    else:
                        print(f"用户 {username} 已成功登录，但系统EMQX连接不可用")
                    
                    # 管理员跳转到dashboard
                    return redirect(url_for('dashboard'))
                    
            except Exception as e:
                print(f"登录错误: {str(e)}")
                return render_template('login.html', error='用户名或密码错误')
            finally:
                if 'conn' in locals():
                    conn.close()
        
        return render_template('login.html')


    
    # 登录API（JSON接口，用于前端AJAX调用）
    @app.route('/api/login', methods=['POST'])
    def api_login():
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        # 判断请求来源：Web端还是小程序端
        # 通过User-Agent或自定义header判断
        user_agent = request.headers.get('User-Agent', '').lower()
        # 小程序的User-Agent通常包含 'micromessenger' 或自定义header 'X-Client-Type': 'miniapp'
        is_miniapp = 'micromessenger' in user_agent or request.headers.get('X-Client-Type') == 'miniapp'
        
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 检查用户是否存在
                sql = f"SELECT * FROM {MYSQL_TABLE_USER_1} WHERE username = %s"
                cursor.execute(sql, (username,))
                user = cursor.fetchone()
                
                if not user:
                    return jsonify({'success': False, 'message': '用户名或密码错误'})
                
                # 检查账户状态
                if user['status'] != 1:
                    return jsonify({'success': False, 'message': '用户名或密码错误'})
                
                # 检查用户角色
                # Web端：只有管理员(role=0)可以登录后台
                # 小程序端：所有角色都可以登录
                if not is_miniapp and user['role'] != 0:
                    # Web端非管理员拒绝登录
                    return jsonify({'success': False, 'message': '您没有权限登录管理后台'})
                
                # 检查登录权限
                permissions = get_permission_settings(user['role'])
                if permissions and not permissions.get('can_login', True):
                    return jsonify({'success': False, 'message': '您所在的用户组暂不允许登录'})
                
                # 检查登录时间范围
                if permissions:
                    time_range = permissions.get('login_time_range', '00:00-23:59')
                    if not check_login_time(time_range):
                        return jsonify({'success': False, 'message': f'当前时间不允许登录，允许时间: {time_range}'})
                
                # 检查是否被锁定
                if user['locked_until'] and user['locked_until'] > datetime.now():
                    lock_time = user['locked_until'] - datetime.now()
                    minutes = lock_time.total_seconds() // 60
                    return jsonify({'success': False, 'message': f'账户已被锁定，请{int(minutes)}分钟后再试'})
                
                # 只支持明文密码验证
                password_match = (password == user['password'])
                
                if not password_match:
                    # 密码错误，更新失败次数
                    new_attempts = user['login_attempts'] + 1
                    locked_until = None
                    
                    # 检查是否需要锁定
                    if new_attempts >= MAX_LOGIN_ATTEMPTS:
                        locked_until = datetime.now() + timedelta(minutes=LOCK_DURATION_MINUTES)
                        
                    sql = f"UPDATE {MYSQL_TABLE_USER_1} SET login_attempts = %s, locked_until = %s WHERE id = %s"
                    cursor.execute(sql, (new_attempts, locked_until, user['id']))
                    conn.commit()
                    
                    return jsonify({'success': False, 'message': '用户名或密码错误'})
                
                # 登录成功，重置失败次数和锁定状态
                sql = f"UPDATE {MYSQL_TABLE_USER_1} SET login_attempts = 0, locked_until = NULL, last_login = %s WHERE id = %s"
                cursor.execute(sql, (datetime.now(), user['id']))
                conn.commit()
                
                # 存储用户信息到session
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                
                # 构建返回数据
                user_data = {
                    'id': user['id'],
                    'username': user['username'],
                    'real_name': user.get('real_name', ''),
                    'role': user['role'],
                    'department': user.get('department', ''),
                    'permissions': []  # 根据实际情况获取权限列表
                }
                
                # 不再创建新的EMQX连接，而是使用系统级的连接管理器
                from emqx_manager import get_emqx_manager
                emqx_manager = get_emqx_manager()
                if emqx_manager.is_connected:
                    client_type = '小程序' if is_miniapp else 'Web端'
                    print(f"用户 {username} 已通过{client_type}API成功登录，复用系统级EMQX连接")
                else:
                    print(f"用户 {username} 已通过API成功登录，但系统EMQX连接不可用")
                
                # 生成JWT Token
                token = generate_jwt_token(user['id'], user['username'], user['role'])
                return jsonify({'success': True, 'data': user_data, 'token': token})
                
        except Exception as e:
            print(f"API登录错误: {str(e)}")
            return jsonify({'success': False, 'message': '用户名或密码错误'})
        finally:
            if 'conn' in locals():
                conn.close()

    # 登出路由
    @app.route('/logout', methods=['GET', 'POST'])
    def logout():
        # 不再断开系统级EMQX连接，因为它是全局共享的
        print(f"用户 {session.get('username', '未知')} 已登出")
        
        # 清除session中的用户信息
        session.clear()
        # 重定向到登录页面
        return redirect(url_for('login'))

# 直接导出需要在main.py中使用的函数
export_dict = {
    'login_required': login_required,
    'init_login_routes': init_login_routes
}