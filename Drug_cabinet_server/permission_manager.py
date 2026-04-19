from datetime import datetime
import pymysql
from functools import wraps
from flask import request, jsonify
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE_1


def get_db_connection():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE_1,
        cursorclass=pymysql.cursors.DictCursor
    )


def get_permission_settings(group_id):
    """
    获取指定权限组的权限设置
    
    Args:
        group_id (int): 权限组ID
        
    Returns:
        dict: 权限设置字典，如果不存在返回None
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
                SELECT can_login, login_time_range, can_query_drugs, 
                       can_book_drugs, can_borrow_return_drugs
                FROM permission_settings
                WHERE group_id = %s
            """
            cursor.execute(sql, (group_id,))
            result = cursor.fetchone()
            return result
    except Exception as e:
        print(f"获取权限设置失败: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()


def update_permission_settings(group_id, permissions):
    """
    更新指定权限组的权限设置
    
    Args:
        group_id (int): 权限组ID
        permissions (dict): 权限设置字典
        
    Returns:
        bool: 是否更新成功
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
                UPDATE permission_settings
                SET can_login = %s,
                    login_time_range = %s,
                    can_query_drugs = %s,
                    can_book_drugs = %s,
                    can_borrow_return_drugs = %s
                WHERE group_id = %s
            """
            cursor.execute(sql, (
                permissions.get('can_login', True),
                permissions.get('login_time_range', '00:00-23:59'),
                permissions.get('can_query_drugs', True),
                permissions.get('can_book_drugs', True),
                permissions.get('can_borrow_return_drugs', True),
                group_id
            ))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"更新权限设置失败: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()


def check_login_time(time_range):
    """
    检查当前时间是否在允许的登录时间范围内
    
    Args:
        time_range (str): 时间范围，格式 "HH:MM-HH:MM"
        
    Returns:
        bool: 是否在允许的时间范围内
    """
    try:
        now = datetime.now()
        current_time = now.time()
        
        start_str, end_str = time_range.split('-')
        
        start_hour, start_minute = map(int, start_str.split(':'))
        end_hour, end_minute = map(int, end_str.split(':'))
        
        start_time = datetime.now().replace(hour=start_hour, minute=start_minute, second=0, microsecond=0).time()
        end_time = datetime.now().replace(hour=end_hour, minute=end_minute, second=0, microsecond=0).time()
        
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:
            return current_time >= start_time or current_time <= end_time
    except Exception as e:
        print(f"检查登录时间失败: {e}")
        return True


def get_user_permissions(user_id):
    """
    根据用户ID获取用户的权限设置
    
    Args:
        user_id (int): 用户ID
        
    Returns:
        dict: 权限设置字典，如果失败返回None
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
                SELECT ps.can_login, ps.login_time_range, ps.can_query_drugs,
                       ps.can_book_drugs, ps.can_borrow_return_drugs
                FROM web_user wu
                JOIN permission_settings ps ON wu.role = ps.group_id
                WHERE wu.id = %s
            """
            cursor.execute(sql, (user_id,))
            result = cursor.fetchone()
            return result
    except Exception as e:
        print(f"获取用户权限失败: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()


def get_permission_groups():
    """
    获取所有权限组列表
    
    Returns:
        list: 权限组列表
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = "SELECT id, name, description FROM permission_groups ORDER BY id"
            cursor.execute(sql)
            return cursor.fetchall()
    except Exception as e:
        print(f"获取权限组列表失败: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()


from flask import session

def permission_required(permission_name):
    """
    权限检查装饰器
    
    Args:
        permission_name (str): 需要检查的权限名称
        
    Returns:
        function: 装饰器函数
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # 从session中获取用户ID
                user_id = session.get('user_id')
                
                # 如果session中没有，尝试从Authorization头中获取token
                if not user_id:
                    auth_header = request.headers.get('Authorization', '')
                    if auth_header.startswith('Bearer '):
                        # 从token中提取用户ID（简化处理，实际项目中应该验证token）
                        token = auth_header.split(' ')[1]
                        if token:
                            # 假设token格式为 "user_id_timestamp"
                            user_id = token.split('_')[0]
                
                # 如果还是没有，尝试从请求参数中获取
                if not user_id:
                    if request.method == 'GET':
                        user_id = request.args.get('user_id')
                    elif request.method in ['POST', 'PUT']:
                        if request.is_json:
                            data = request.get_json(silent=True)
                            if data:
                                user_id = data.get('user_id')
                
                if not user_id:
                    return jsonify({'success': False, 'message': '用户ID缺失'}), 400
                
                # 获取用户权限
                permissions = get_user_permissions(int(user_id))
                if not permissions:
                    return jsonify({'success': False, 'message': '获取用户权限失败'}), 500
                
                # 检查权限
                if not permissions.get(permission_name, True):
                    permission_messages = {
                        'can_query_drugs': '您所在的用户组暂不允许查询药品',
                        'can_book_drugs': '您所在的用户组暂不允许预定药品',
                        'can_borrow_return_drugs': '您所在的用户组暂不允许借还药品'
                    }
                    return jsonify({'success': False, 'message': permission_messages.get(permission_name, '权限不足')}), 403
                
                return f(*args, **kwargs)
            except Exception as e:
                print(f"权限检查失败: {e}")
                return jsonify({'success': False, 'message': '权限检查失败'}), 500
        return decorated_function
    return decorator
