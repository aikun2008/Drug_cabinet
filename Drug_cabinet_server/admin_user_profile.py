from flask import request, jsonify, render_template
import bcrypt
from datetime import datetime

# 导入师生关系管理功能
from teacher_drug_BND_UBD import init_teacher_student_routes

# 用户相关功能

def init_user_routes(app, login_required, get_db_connection, MYSQL_TABLE_USER_1):
    # 从admin_dashboard导入menu_items和add_url_to_menu_items
    from admin_dashboard import menu_items, add_url_to_menu_items
    
    # 初始化师生关系管理路由
    teacher_student_utils = init_teacher_student_routes(app, login_required, get_db_connection, MYSQL_TABLE_USER_1)
    get_user_relationships = teacher_student_utils['get_user_relationships']
    
    # 角色映射常量
    ROLE_MAP = {
        0: '管理员',
        1: '教师', 
        2: '学生'
    }
    
    # 状态映射常量
    STATUS_MAP = {
        0: '禁用',
        1: '启用'
    }
    
    # 为用户数据添加显示信息的辅助函数
    def enhance_user_data(user):
        """为用户数据添加显示字段"""
        if user:
            user['role_name'] = ROLE_MAP.get(user.get('role', 0), '未知')
            user['status_name'] = STATUS_MAP.get(user.get('status', 0), '未知')
        return user
    
    # 用户档案页面路由
    @app.route('/admin_user_profile.html')
    @login_required
    def admin_user_interface():
        # 使用辅助函数为菜单项添加URL
        menu_items_with_urls = add_url_to_menu_items(menu_items)
        return render_template('admin_user_profile.html', 
                              menu_items=menu_items_with_urls, 
                              active_menu='users')
    
    # 获取用户列表的API端点
    @app.route('/api/users')
    @login_required
    def get_users():
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 查询用户数据
                sql = f"SELECT id, rfid_card_id, username, real_name, role, status, department FROM {MYSQL_TABLE_USER_1}"
                cursor.execute(sql)
                users = cursor.fetchall()
                
                # 使用辅助函数处理角色和状态的显示名称，并获取师生关系信息
                for user in users:
                    enhance_user_data(user)
                    # 获取师生关系信息
                    relationships = get_user_relationships(user['id'], user['role'], conn)
                    user.update(relationships)
                
                return jsonify({'success': True, 'data': users})
        except Exception as e:
            print(f"获取用户列表错误: {str(e)}")
            return jsonify({'success': False, 'message': '获取用户列表失败'})
        finally:
            if conn:
                conn.close()
    


    # 获取单个用户详情的API端点
    @app.route('/api/users/<int:user_id>', methods=['GET'])
    @login_required
    def get_user(user_id):
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 查询用户数据，包括所有字段信息
                sql = f"SELECT id, username, password, real_name, email, role, status, rfid_card_id, department, phone, last_login, login_attempts, locked_until, created_by, created_at, updated_at FROM {MYSQL_TABLE_USER_1} WHERE id = %s"
                cursor.execute(sql, (user_id,))
                user = cursor.fetchone()
                
                if not user:
                    return jsonify({'success': False, 'message': '用户不存在'})
                
                # 使用辅助函数处理角色和状态的显示名称
                enhance_user_data(user)
                
                # 获取师生关系信息
                relationships = get_user_relationships(user_id, user['role'], conn)
                user.update(relationships)
                
                return jsonify({'success': True, 'data': user})
        except Exception as e:
            print(f"获取用户详情错误: {str(e)}")
            return jsonify({'success': False, 'message': '获取用户详情失败'})
        finally:
            if conn:
                conn.close()

    # 删除用户的API端点
    @app.route('/api/users/<int:user_id>', methods=['DELETE'])
    @login_required
    def delete_user(user_id):
        conn = None
        try:
            conn = get_db_connection()
            
            with conn.cursor() as cursor:
                # 检查用户是否存在
                cursor.execute(f"SELECT id FROM {MYSQL_TABLE_USER_1} WHERE id = %s", (user_id,))
                if not cursor.fetchone():
                    return jsonify({'success': False, 'message': '用户不存在'})
                
                # 执行删除操作
                cursor.execute(f"DELETE FROM {MYSQL_TABLE_USER_1} WHERE id = %s", (user_id,))
                conn.commit()
                
                return jsonify({'success': True, 'message': '用户删除成功'})
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"删除用户时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                conn.close()

    # 更新用户信息的API端点
    @app.route('/api/users/<int:user_id>', methods=['PUT'])
    @login_required
    def update_user(user_id):
        conn = None
        try:
            conn = get_db_connection()
            data = request.json
            
            # 准备更新字段
            update_fields = []
            update_values = []
            
            with conn.cursor() as cursor:
                # 检查用户名是否已被其他用户使用
                if 'username' in data:
                    cursor.execute(f"SELECT id FROM {MYSQL_TABLE_USER_1} WHERE username = %s AND id != %s", 
                                  (data['username'], user_id))
                    if cursor.fetchone():
                        return jsonify({'success': False, 'message': '用户名已存在'})
                
                # 检查RFID卡号是否已被其他用户使用
                if 'rfid_card_id' in data and data['rfid_card_id']:
                    cursor.execute(f"SELECT id FROM {MYSQL_TABLE_USER_1} WHERE rfid_card_id = %s AND id != %s", 
                                  (data['rfid_card_id'], user_id))
                    if cursor.fetchone():
                        return jsonify({'success': False, 'message': 'RFID卡号已存在'})
                
                # 检查用户是否存在
                cursor.execute(f"SELECT id FROM {MYSQL_TABLE_USER_1} WHERE id = %s", (user_id,))
                if not cursor.fetchone():
                    return jsonify({'success': False, 'message': '用户不存在'})
            
            # 检查并添加需要更新的字段
            updateable_fields = ['real_name', 'username', 'role', 'department', 'status', 
                                'email', 'phone', 'rfid_card_id']
            
            for field in updateable_fields:
                if field in data:
                    update_fields.append(f'{field} = %s')
                    update_values.append(data[field])
            
            if 'password' in data and data['password']:
                # 使用明文存储密码（仅用于测试环境）
                update_fields.append('password = %s')
                update_values.append(data['password'])
            
            # 添加更新时间
            update_fields.append('updated_at = NOW()')
            
            if not update_fields:
                return jsonify({'success': False, 'message': '没有需要更新的字段'})
            
            # 构建SQL语句
            update_values.append(user_id)
            sql = f"UPDATE {MYSQL_TABLE_USER_1} SET {', '.join(update_fields)} WHERE id = %s"
            
            with conn.cursor() as cursor:
                # 执行更新
                cursor.execute(sql, update_values)
                conn.commit()
                
                # 获取更新后的用户信息
                cursor.execute(f"SELECT id, real_name, username, role, department, status, email, phone, rfid_card_id, created_at, updated_at FROM {MYSQL_TABLE_USER_1} WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                
                if user:
                    # 使用辅助函数处理角色和状态的显示名称
                    enhance_user_data(user)
                    return jsonify({'success': True, 'data': user, 'message': '用户信息更新成功'})
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"更新用户时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                conn.close()

    # 创建新用户的API端点
    @app.route('/api/users', methods=['POST'])
    @login_required
    def create_user():
        conn = None
        try:
            conn = get_db_connection()
            data = request.json
            
            # 验证必填字段
            required_fields = ['real_name', 'username', 'role', 'status']
            for field in required_fields:
                if field not in data:
                    return jsonify({'success': False, 'message': f'{field} 是必填字段'})
            
            with conn.cursor() as cursor:
                # 检查用户名是否已存在
                cursor.execute(f"SELECT id FROM {MYSQL_TABLE_USER_1} WHERE username = %s", (data['username'],))
                if cursor.fetchone():
                    return jsonify({'success': False, 'message': '用户名已存在'})
                
                # 检查RFID卡号是否已存在
                if 'rfid_card_id' in data and data['rfid_card_id']:
                    cursor.execute(f"SELECT id FROM {MYSQL_TABLE_USER_1} WHERE rfid_card_id = %s", (data['rfid_card_id'],))
                    if cursor.fetchone():
                        return jsonify({'success': False, 'message': 'RFID卡号已存在'})
                
                # 准备插入字段和值
                insert_fields = ['real_name', 'username', 'role', 'status', 'created_at', 'updated_at']
                insert_values = [data['real_name'], data['username'], data['role'], data['status'], datetime.now(), datetime.now()]
                
                # 添加可选字段
                optional_fields = ['department', 'email', 'phone', 'rfid_card_id']
                for field in optional_fields:
                    if field in data:
                        insert_fields.append(field)
                        insert_values.append(data[field])
                
                # 密码处理 - 如果提供了密码
                if 'password' in data and data['password']:
                    # 使用明文存储密码（仅用于测试环境）
                    insert_fields.append('password')
                    insert_values.append(data['password'])
                
                # 构建SQL语句
                placeholders = ', '.join(['%s'] * len(insert_values))
                sql = f"INSERT INTO {MYSQL_TABLE_USER_1} ({', '.join(insert_fields)}) VALUES ({placeholders})"
                
                # 执行插入
                cursor.execute(sql, insert_values)
                conn.commit()
                
                # 获取新创建的用户ID
                new_user_id = cursor.lastrowid
                
                # 获取新创建的用户信息
                cursor.execute(f"SELECT id, real_name, username, role, department, status, email, phone, rfid_card_id, created_at, updated_at FROM {MYSQL_TABLE_USER_1} WHERE id = %s", (new_user_id,))
                user = cursor.fetchone()
                
                if user:
                    # 使用辅助函数处理角色和状态的显示名称
                    enhance_user_data(user)
                    return jsonify({'success': True, 'data': user, 'message': '用户创建成功'})
                else:
                    return jsonify({'success': False, 'message': '创建用户后无法获取用户信息'})
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"创建用户时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                conn.close()
