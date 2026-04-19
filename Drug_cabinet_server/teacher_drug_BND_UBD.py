from flask import request, jsonify

# 师生关系管理功能
def init_teacher_student_routes(app, login_required, get_db_connection, MYSQL_TABLE_USER_1):
    """
    初始化师生关系管理路由
    
    Args:
        app (Flask): Flask应用实例
        login_required (function): 登录验证装饰器
        get_db_connection (function): 获取数据库连接的函数
        MYSQL_TABLE_USER_1 (str): 用户表名
    """
    
    # 获取用户的师生关系信息
    def get_user_relationships(user_id, role, conn):
        """获取用户的师生关系信息"""
        relationships = {}
        
        try:
            with conn.cursor() as cursor:
                if role == 1:  # 教师
                    # 获取教师的所有学生
                    sql = """
                    SELECT ws.id, ws.real_name, ws.username 
                    FROM web_user ws
                    JOIN teacher_student_relationship ts ON ws.id = ts.student_id
                    WHERE ts.teacher_id = %s AND ts.status = 1
                    """
                    cursor.execute(sql, (user_id,))
                    students = cursor.fetchall()
                    relationships['students'] = students
                elif role == 2:  # 学生
                    # 获取学生的教师
                    sql = """
                    SELECT wt.id, wt.real_name, wt.username 
                    FROM web_user wt
                    JOIN teacher_student_relationship ts ON wt.id = ts.teacher_id
                    WHERE ts.student_id = %s AND ts.status = 1
                    """
                    cursor.execute(sql, (user_id,))
                    teacher = cursor.fetchone()
                    relationships['teacher'] = teacher
        except Exception as e:
            print(f"获取师生关系信息错误: {str(e)}")
        
        return relationships
    
    # 为学生绑定教师的API端点
    @app.route('/api/teacher-student/bind', methods=['POST'])
    @login_required
    def bind_teacher_student():
        conn = None
        try:
            conn = get_db_connection()
            data = request.json
            
            # 验证必填字段
            if 'teacher_id' not in data or 'student_id' not in data:
                return jsonify({'success': False, 'message': '教师ID和学生ID是必填字段'})
            
            teacher_id = data['teacher_id']
            student_id = data['student_id']
            created_by = data.get('created_by')
            
            with conn.cursor() as cursor:
                # 验证教师是否存在且角色为教师
                cursor.execute(f"SELECT id, role FROM {MYSQL_TABLE_USER_1} WHERE id = %s", (teacher_id,))
                teacher = cursor.fetchone()
                if not teacher or teacher['role'] != 1:
                    return jsonify({'success': False, 'message': '指定的教师ID不存在或不是教师角色'})
                
                # 验证学生是否存在且角色为学生
                cursor.execute(f"SELECT id, role FROM {MYSQL_TABLE_USER_1} WHERE id = %s", (student_id,))
                student = cursor.fetchone()
                if not student or student['role'] != 2:
                    return jsonify({'success': False, 'message': '指定的学生ID不存在或不是学生角色'})
                
                # 检查是否已存在绑定关系
                cursor.execute("SELECT id FROM teacher_student_relationship WHERE student_id = %s", (student_id,))
                existing = cursor.fetchone()
                
                if existing:
                    # 更新现有关系
                    sql = "UPDATE teacher_student_relationship SET teacher_id = %s, status = 1, updated_at = NOW() WHERE student_id = %s"
                    cursor.execute(sql, (teacher_id, student_id))
                else:
                    # 创建新关系
                    sql = "INSERT INTO teacher_student_relationship (teacher_id, student_id, status, created_at, updated_at, created_by) VALUES (%s, %s, 1, NOW(), NOW(), %s)"
                    cursor.execute(sql, (teacher_id, student_id, created_by))
                
                conn.commit()
                return jsonify({'success': True, 'message': '师生绑定成功'})
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"绑定师生关系时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                conn.close()
    
    # 解除师生关系的API端点
    @app.route('/api/teacher-student/unbind', methods=['POST'])
    @login_required
    def unbind_teacher_student():
        conn = None
        try:
            conn = get_db_connection()
            data = request.json
            
            # 验证必填字段
            if 'student_id' not in data:
                return jsonify({'success': False, 'message': '学生ID是必填字段'})
            
            student_id = data['student_id']
            
            with conn.cursor() as cursor:
                # 验证学生是否存在
                cursor.execute(f"SELECT id FROM {MYSQL_TABLE_USER_1} WHERE id = %s", (student_id,))
                if not cursor.fetchone():
                    return jsonify({'success': False, 'message': '指定的学生ID不存在'})
                
                # 解除关系（软删除）
                sql = "UPDATE teacher_student_relationship SET status = 0, updated_at = NOW() WHERE student_id = %s AND status = 1"
                result = cursor.execute(sql, (student_id,))
                
                if result == 0:
                    return jsonify({'success': False, 'message': '师生关系不存在'})
                
                conn.commit()
                return jsonify({'success': True, 'message': '师生关系已解除'})
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"解除师生关系时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                conn.close()
    
    # 获取教师的学生列表
    @app.route('/api/teacher-student/students/<int:teacher_id>', methods=['GET'])
    @login_required
    def get_teacher_students(teacher_id):
        conn = None
        try:
            conn = get_db_connection()
            
            with conn.cursor() as cursor:
                # 验证教师是否存在
                cursor.execute(f"SELECT id FROM {MYSQL_TABLE_USER_1} WHERE id = %s", (teacher_id,))
                if not cursor.fetchone():
                    return jsonify({'success': False, 'message': '指定的教师ID不存在'})
                
                # 获取教师的学生列表
                sql = """
                SELECT ws.id, ws.real_name, ws.username, ws.department 
                FROM web_user ws
                JOIN teacher_student_relationship ts ON ws.id = ts.student_id
                WHERE ts.teacher_id = %s AND ts.status = 1
                """
                cursor.execute(sql, (teacher_id,))
                students = cursor.fetchall()
                
                return jsonify({'success': True, 'data': students})
        except Exception as e:
            print(f"获取教师学生列表错误: {str(e)}")
            return jsonify({'success': False, 'message': '获取学生列表失败'})
        finally:
            if conn:
                conn.close()
    
    # 获取学生的教师信息
    @app.route('/api/teacher-student/teacher/<int:student_id>', methods=['GET'])
    @login_required
    def get_student_teacher(student_id):
        conn = None
        try:
            conn = get_db_connection()
            
            with conn.cursor() as cursor:
                # 验证学生是否存在
                cursor.execute(f"SELECT id FROM {MYSQL_TABLE_USER_1} WHERE id = %s", (student_id,))
                if not cursor.fetchone():
                    return jsonify({'success': False, 'message': '指定的学生ID不存在'})
                
                # 获取学生的教师信息
                sql = """
                SELECT wt.id, wt.real_name, wt.username, wt.department 
                FROM web_user wt
                JOIN teacher_student_relationship ts ON wt.id = ts.teacher_id
                WHERE ts.student_id = %s AND ts.status = 1
                """
                cursor.execute(sql, (student_id,))
                teacher = cursor.fetchone()
                
                return jsonify({'success': True, 'data': teacher})
        except Exception as e:
            print(f"获取学生教师信息错误: {str(e)}")
            return jsonify({'success': False, 'message': '获取教师信息失败'})
        finally:
            if conn:
                conn.close()
    
    # 获取可绑定的学生列表（未绑定到任何教师的学生）
    @app.route('/api/teacher-student/available-students/<int:teacher_id>', methods=['GET'])
    @login_required
    def get_available_students(teacher_id):
        conn = None
        try:
            conn = get_db_connection()
            
            with conn.cursor() as cursor:
                # 验证教师是否存在
                cursor.execute(f"SELECT id FROM {MYSQL_TABLE_USER_1} WHERE id = %s", (teacher_id,))
                if not cursor.fetchone():
                    return jsonify({'success': False, 'message': '指定的教师ID不存在'})
                
                # 获取未绑定的学生列表
                sql = """
                SELECT id, real_name, username, department 
                FROM web_user 
                WHERE role = 2  # 学生角色
                AND id NOT IN (
                    SELECT student_id 
                    FROM teacher_student_relationship 
                    WHERE status = 1
                )
                """
                cursor.execute(sql)
                available_students = cursor.fetchall()
                
                return jsonify({'success': True, 'data': available_students})
        except Exception as e:
            print(f"获取可绑定学生列表错误: {str(e)}")
            return jsonify({'success': False, 'message': '获取可绑定学生列表失败'})
        finally:
            if conn:
                conn.close()
    
    # 导出函数供其他模块使用
    return {
        'get_user_relationships': get_user_relationships
    }

# 导出字典
export_dict = {
    'init_teacher_student_routes': init_teacher_student_routes
}