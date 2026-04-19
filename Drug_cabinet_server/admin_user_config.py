from flask import Blueprint, render_template, request, jsonify
from permission_manager import (
    get_permission_groups as pm_get_permission_groups,
    get_permission_settings,
    update_permission_settings
)

# 创建蓝图
admin_user_config_bp = Blueprint('admin_user_config', __name__)

def init_user_config_routes(app, login_required, get_db_connection, MYSQL_TABLE_USER_1):
    """
    初始化权限组配置相关的路由
    """
    @app.route('/admin_user_config.html')
    @login_required
    def admin_user_config():
        """
        权限组配置页面
        """
        return render_template('admin_user_config.html')
    
    @app.route('/api/permission-groups')
    @login_required
    def get_permission_groups():
        """
        获取权限组列表
        """
        try:
            groups = pm_get_permission_groups()
            return jsonify({"success": True, "data": groups})
        except Exception as e:
            print(f"获取权限组列表错误: {str(e)}")
            return jsonify({"success": False, "message": "获取权限组列表失败"})
    
    @app.route('/api/permission-groups/<int:group_id>/users')
    @login_required
    def get_users_by_group(group_id):
        """
        根据权限组获取用户列表
        """
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 查询指定角色的用户
                sql = f"SELECT id, username, real_name, role, status, department FROM {MYSQL_TABLE_USER_1} WHERE role = %s"
                cursor.execute(sql, (group_id,))
                users = cursor.fetchall()
                
                # 角色映射
                ROLE_MAP = {0: '管理员', 1: '教师', 2: '学生'}
                STATUS_MAP = {0: '禁用', 1: '启用'}
                
                # 处理用户数据
                for user in users:
                    user['role_name'] = ROLE_MAP.get(user.get('role', 0), '未知')
                    user['status_name'] = STATUS_MAP.get(user.get('status', 0), '未知')
                
                return jsonify({"success": True, "data": users})
        except Exception as e:
            print(f"获取用户列表错误: {str(e)}")
            return jsonify({"success": False, "message": "获取用户列表失败"})
        finally:
            if conn:
                conn.close()
    
    @app.route('/api/permission-groups/<int:group_id>/permissions', methods=['GET', 'PUT'])
    @login_required
    def manage_group_permissions(group_id):
        """
        管理权限组的权限
        """
        if request.method == 'GET':
            # 获取权限组的权限设置
            try:
                permissions = get_permission_settings(group_id)
                if permissions:
                    return jsonify({"success": True, "data": permissions})
                else:
                    return jsonify({"success": False, "message": "权限设置不存在"}), 404
            except Exception as e:
                print(f"获取权限设置错误: {str(e)}")
                return jsonify({"success": False, "message": "获取权限设置失败"})
        
        elif request.method == 'PUT':
            # 更新权限组的权限设置
            try:
                data = request.json
                success = update_permission_settings(group_id, data)
                if success:
                    print(f"更新权限组 {group_id} 的权限设置: {data}")
                    return jsonify({"success": True, "message": "权限设置更新成功"})
                else:
                    return jsonify({"success": False, "message": "权限设置更新失败"}), 500
            except Exception as e:
                print(f"更新权限设置错误: {str(e)}")
                return jsonify({"success": False, "message": "更新权限设置失败"})