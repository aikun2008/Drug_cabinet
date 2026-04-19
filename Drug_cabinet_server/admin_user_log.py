from flask import render_template, request, jsonify
from datetime import datetime
import pymysql


def init_user_log_routes(app, login_required, get_db_connection, cached_db):
    """
    初始化用户操作日志路由
    """
    
    @app.route('/admin_user_log.html')
    @login_required
    def admin_user_log_html():
        # 复用仪表板菜单项，但可以调整激活状态
        from admin_dashboard import menu_items, add_url_to_menu_items
        menu_items_with_urls = add_url_to_menu_items(menu_items)
        return render_template('admin_user_log.html', menu_items=menu_items_with_urls)
    
    @app.route('/api/user-operations')
    @login_required
    def get_user_operations():
        """获取用户操作记录API"""
        try:
            # 获取请求参数
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 10))
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            rfid_card_id = request.args.get('rfid_card_id')
            offset = (page - 1) * limit
            
            # 构建查询SQL
            sql = """
            SELECT 
                operation_time,
                rfid_card_id,
                description
            FROM user_operations
            WHERE 1=1
            """
            
            params = []
            
            # 添加日期范围筛选
            if start_date:
                # 如果start_date是日期格式（不含时间），设置为当天00:00:00
                if len(start_date) == 10:  # YYYY-MM-DD格式
                    start_date = start_date + " 00:00:00"
                sql += " AND operation_time >= %s"
                params.append(start_date)
            
            if end_date:
                # 如果end_date是日期格式（不含时间），设置为当天23:59:59
                if len(end_date) == 10:  # YYYY-MM-DD格式
                    end_date = end_date + " 23:59:59"
                sql += " AND operation_time <= %s"
                params.append(end_date)
            
            # 添加RFID筛选
            if rfid_card_id:
                sql += " AND rfid_card_id LIKE %s"
                params.append(f"%{rfid_card_id}%")
            
            # 添加排序和分页
            sql += " ORDER BY operation_time DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            
            # 执行查询
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(sql, params)
            result = cursor.fetchall()
            
            # 获取总记录数
            count_sql = "SELECT COUNT(*) as total FROM user_operations WHERE 1=1"
            count_params = []
            
            # 同样的筛选条件应用到总记录数查询
            if start_date:
                if len(start_date) == 10:
                    start_date = start_date + " 00:00:00"
                count_sql += " AND operation_time >= %s"
                count_params.append(start_date)
            
            if end_date:
                if len(end_date) == 10:
                    end_date = end_date + " 23:59:59"
                count_sql += " AND operation_time <= %s"
                count_params.append(end_date)
            
            if rfid_card_id:
                count_sql += " AND rfid_card_id LIKE %s"
                count_params.append(f"%{rfid_card_id}%")
            
            cursor.execute(count_sql, count_params)
            count_result = cursor.fetchone()
            total_records = count_result['total'] if count_result else 0
            
            cursor.close()
            conn.close()
            
            # 转换为前端需要的格式
            data = []
            for row in result:
                record = {
                    'operation_time': row['operation_time'].strftime('%Y-%m-%d %H:%M:%S') if row['operation_time'] else '',
                    'rfid_card_id': row['rfid_card_id'] or '',
                    'description': row['description'] or ''
                }
                data.append(record)
            
            return jsonify({
                'success': True,
                'data': data,
                'total': total_records,
                'page': page,
                'limit': limit
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'获取用户操作记录失败: {str(e)}'
            }), 500

# 导出字典，方便在main.py中导入
export_dict = {
    'init_user_log_routes': init_user_log_routes
}
