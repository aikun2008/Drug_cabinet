from flask import render_template, request, jsonify
from datetime import datetime, timedelta
import json
import pymysql
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE_1

def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE_1,
        cursorclass=pymysql.cursors.DictCursor
    )

def init_drug_log_routes(app, login_required, get_db_connection, cached_db):
    """
    初始化药品追溯日志路由
    """
    
    @app.route('/admin_drug_log.html')
    @login_required
    def admin_drug_log_html():
        # 复用仪表板菜单项，但可以调整激活状态
        from admin_dashboard import menu_items, add_url_to_menu_items
        menu_items_with_urls = add_url_to_menu_items(menu_items)
        return render_template('admin_drug_log.html', menu_items=menu_items_with_urls)
    
    @app.route('/api/drug-trace-records')
    @login_required
    def get_drug_trace_records():
        """获取药品追溯记录API"""
        try:
            # 获取请求参数
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))
            offset = (page - 1) * limit
            
            # 构建查询SQL，关联web_equipment、web_user和web_medicine_list表获取实际名称
            sql = """
            SELECT 
                mt.id,
                mt.operation_time,
                mt.equipment_id,
                we.equipment_name,
                mt.rfid_card_id,
                wu.real_name,
                mt.medicine_code,
                wml.name as medicine_name,
                mt.operation_type
            FROM medicine_trace mt
            LEFT JOIN web_equipment we ON mt.equipment_id = we.equipment_id
            LEFT JOIN web_user wu ON mt.rfid_card_id = wu.rfid_card_id
            LEFT JOIN web_medicine_list wml ON mt.medicine_code = wml.medicine_code
            ORDER BY mt.operation_time DESC 
            LIMIT %s OFFSET %s
            """
            
            # 使用带缓存的数据库连接获取数据
            if cached_db:
                result = cached_db.execute_query(sql, params=(limit, offset), table='medicine_trace', use_cache=True)
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(sql, (limit, offset))
                result = cursor.fetchall()
                cursor.close()
                conn.close()
            
            # 获取总记录数
            count_sql = "SELECT COUNT(*) as total FROM medicine_trace"
            if cached_db:
                count_result = cached_db.execute_query(count_sql, table='medicine_trace_count', use_cache=True)
                total_records = count_result[0]['total'] if count_result else 0
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(count_sql)
                count_result = cursor.fetchone()
                cursor.close()
                conn.close()
                total_records = count_result['total'] if count_result else 0
            
            # 转换为前端需要的格式
            data = []
            for row in result:
                record = {
                    'id': row['id'],
                    'operation_time': row['operation_time'].strftime('%Y-%m-%d %H:%M:%S') if row['operation_time'] else '',
                    'equipment_id': row['equipment_name'] or row['equipment_id'] or '',  # 优先显示设备名称
                    'rfid_card_id': row['real_name'] or row['rfid_card_id'] or '',  # 优先显示用户真实姓名
                    'medicine_code': row['medicine_name'] or row['medicine_code'] or '',  # 优先显示药品名称
                    'operation_type': '借出' if row['operation_type'] == 'borrow' else '归还' if row['operation_type'] == 'return' else row['operation_type']
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
                'message': f'获取药品追溯记录失败: {str(e)}'
            }), 500
    
    @app.route('/api/drug-full-life')
    @login_required
    def get_drug_full_life():
        """获取药品完整生命周期记录API"""
        try:
            # 获取请求参数
            drug_rfid = request.args.get('drug_rfid')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            if not drug_rfid:
                return jsonify({
                    'success': False,
                    'message': '药品RFID不能为空'
                }), 400
            
            # 构建查询SQL，获取药品的完整生命周期记录
            sql = """
            SELECT 
                mt.id,
                mt.operation_time,
                mt.equipment_id,
                we.equipment_name,
                mt.rfid_card_id,
                wu.real_name,
                mt.medicine_code,
                wml.name as medicine_name,
                mt.operation_type
            FROM medicine_trace mt
            LEFT JOIN web_equipment we ON mt.equipment_id = we.equipment_id
            LEFT JOIN web_user wu ON mt.rfid_card_id = wu.rfid_card_id
            LEFT JOIN web_medicine_list wml ON mt.medicine_code = wml.medicine_code
            WHERE mt.medicine_code = %s
            """
            
            params = [drug_rfid]
            
            # 添加日期范围筛选
            if start_date:
                # 如果start_date是日期格式（不含时间），设置为当天00:00:00
                if len(start_date) == 10:  # YYYY-MM-DD格式
                    start_date = start_date + " 00:00:00"
                sql += " AND mt.operation_time >= %s"
                params.append(start_date)
            
            if end_date:
                # 如果end_date是日期格式（不含时间），设置为当天23:59:59
                if len(end_date) == 10:  # YYYY-MM-DD格式
                    end_date = end_date + " 23:59:59"
                sql += " AND mt.operation_time <= %s"
                params.append(end_date)
            
            # 添加排序
            sql += " ORDER BY mt.operation_time ASC"
            
            # 执行查询
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(sql, params)
            result = cursor.fetchall()
            cursor.close()
            conn.close()
            
            # 转换为前端需要的格式
            drug_life_data = []
            for row in result:
                record = {
                    'id': row['id'],
                    'operation_time': row['operation_time'].strftime('%Y-%m-%d %H:%M:%S') if row['operation_time'] else '',
                    'equipment_id': row['equipment_name'] or row['equipment_id'] or '',  # 优先显示设备名称
                    'rfid_card_id': row['real_name'] or row['rfid_card_id'] or '',  # 优先显示用户真实姓名
                    'medicine_code': row['medicine_name'] or row['medicine_code'] or '',  # 优先显示药品名称
                    'operation_type': '借出' if row['operation_type'] == 'borrow' else '归还' if row['operation_type'] == 'return' else row['operation_type']
                }
                drug_life_data.append(record)
            
            return jsonify({
                'success': True,
                'data': drug_life_data,
                'drug_rfid': drug_rfid
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'获取药品生命周期记录失败: {str(e)}'
            }), 500
    
    @app.route('/api/person-borrow-records')
    @login_required
    def get_person_borrow_records():
        """获取人员借还记录API"""
        try:
            # 获取请求参数
            person_rfid = request.args.get('person_rfid')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            if not person_rfid:
                return jsonify({
                    'success': False,
                    'message': '人员RFID不能为空'
                }), 400
            
            # 1. 查询人员详细信息
            person_sql = """
            SELECT 
                id,
                username,
                real_name,
                email,
                role,
                status,
                rfid_card_id,
                department,
                phone
            FROM web_user
            WHERE rfid_card_id = %s
            """
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(person_sql, (person_rfid,))
            person_info = cursor.fetchone()
            
            # 2. 构建查询SQL，获取人员的借还记录
            trace_sql = """
            SELECT 
                mt.id,
                mt.operation_time,
                mt.equipment_id,
                we.equipment_name,
                mt.rfid_card_id,
                wu.real_name,
                mt.medicine_code,
                wml.name as medicine_name,
                mt.operation_type
            FROM medicine_trace mt
            LEFT JOIN web_equipment we ON mt.equipment_id = we.equipment_id
            LEFT JOIN web_user wu ON mt.rfid_card_id = wu.rfid_card_id
            LEFT JOIN web_medicine_list wml ON mt.medicine_code = wml.medicine_code
            WHERE mt.rfid_card_id = %s
            """
            
            params = [person_rfid]
            
            # 添加日期范围筛选
            if start_date:
                # 如果start_date是日期格式（不含时间），设置为当天00:00:00
                if len(start_date) == 10:  # YYYY-MM-DD格式
                    start_date = start_date + " 00:00:00"
                trace_sql += " AND mt.operation_time >= %s"
                params.append(start_date)
            
            if end_date:
                # 如果end_date是日期格式（不含时间），设置为当天23:59:59
                if len(end_date) == 10:  # YYYY-MM-DD格式
                    end_date = end_date + " 23:59:59"
                trace_sql += " AND mt.operation_time <= %s"
                params.append(end_date)
            
            # 添加排序
            trace_sql += " ORDER BY mt.operation_time DESC"
            
            cursor.execute(trace_sql, params)
            result = cursor.fetchall()
            cursor.close()
            conn.close()
            
            # 转换为前端需要的格式
            borrow_data = []
            for row in result:
                record = {
                    'id': row['id'],
                    'operation_time': row['operation_time'].strftime('%Y-%m-%d %H:%M:%S') if row['operation_time'] else '',
                    'equipment_id': row['equipment_name'] or row['equipment_id'] or '',
                    'rfid_card_id': row['real_name'] or row['rfid_card_id'] or '',
                    'medicine_code': row['medicine_name'] or row['medicine_code'] or '',
                    'operation_type': '借出' if row['operation_type'] == 'borrow' else '归还' if row['operation_type'] == 'return' else row['operation_type']
                }
                borrow_data.append(record)
            
            # 计算统计数据（支持日期范围筛选）
            monthly_sql = """
            SELECT 
                COUNT(*) as total_borrows,
                AVG(TIMESTAMPDIFF(HOUR, borrow_time, return_time)) as avg_duration
            FROM (
                SELECT 
                    mt1.operation_time as borrow_time,
                    (SELECT MIN(mt2.operation_time) 
                     FROM medicine_trace mt2 
                     WHERE mt2.medicine_code = mt1.medicine_code 
                     AND mt2.operation_type = 'return' 
                     AND mt2.operation_time > mt1.operation_time) as return_time
                FROM medicine_trace mt1
                WHERE mt1.rfid_card_id = %s 
                AND mt1.operation_type = 'borrow'
            """
            
            monthly_params = [person_rfid]
            
            # 添加日期范围筛选
            if start_date:
                # 如果start_date是日期格式（不含时间），设置为当天00:00:00
                if len(start_date) == 10:  # YYYY-MM-DD格式
                    start_date = start_date + " 00:00:00"
                monthly_sql += " AND mt1.operation_time >= %s"
                monthly_params.append(start_date)
            
            if end_date:
                # 如果end_date是日期格式（不含时间），设置为当天23:59:59
                if len(end_date) == 10:  # YYYY-MM-DD格式
                    end_date = end_date + " 23:59:59"
                monthly_sql += " AND mt1.operation_time <= %s"
                monthly_params.append(end_date)
            
            monthly_sql += ") as borrow_return_pairs"
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(monthly_sql, monthly_params)
            monthly_stats = cursor.fetchone()
            cursor.close()
            conn.close()
            
            # 角色转换
            role_map = {
                0: '管理员',
                1: '教师',
                2: '学生'
            }
            
            # 状态转换
            status_map = {
                0: '禁用',
                1: '启用'
            }
            
            # 准备人员详细信息
            person_details = {
                'real_name': person_info['real_name'] or '未知',
                'username': person_info['username'] or '未知',
                'role': role_map.get(person_info['role'], '未知'),
                'rfid_card_id': person_info['rfid_card_id'] or '未知',
                'department': person_info['department'] or '未知',
                'email': person_info['email'] or '未知',
                'phone': person_info['phone'] or '未知',
                'status': status_map.get(person_info['status'], '未知')
            }
            
            return jsonify({
                'success': True,
                'data': borrow_data,
                'person_rfid': person_rfid,
                'person_details': person_details,
                'monthly_stats': {
                    'total_borrows': monthly_stats['total_borrows'] or 0,
                    'avg_duration': round(monthly_stats['avg_duration'] or 0, 1)
                }
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'获取人员借还记录失败: {str(e)}'
            }), 500
    
    @app.route('/api/cabinet-activity-logs')
    @login_required
    def get_cabinet_activity_logs():
        """获取药柜活动日志API"""
        try:
            # 获取请求参数
            cabinet_id = request.args.get('cabinet_id')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            if not cabinet_id:
                return jsonify({
                    'success': False,
                    'message': '药柜ID不能为空'
                }), 400
            
            # 构建查询SQL，获取药柜的活动日志
            sql = """
            SELECT 
                mt.id,
                mt.operation_time,
                mt.equipment_id,
                we.equipment_name,
                mt.rfid_card_id,
                wu.real_name,
                mt.medicine_code,
                wml.name as medicine_name,
                mt.operation_type
            FROM medicine_trace mt
            LEFT JOIN web_equipment we ON mt.equipment_id = we.equipment_id
            LEFT JOIN web_user wu ON mt.rfid_card_id = wu.rfid_card_id
            LEFT JOIN web_medicine_list wml ON mt.medicine_code = wml.medicine_code
            WHERE mt.equipment_id = %s
            """
            
            params = [cabinet_id]
            
            # 添加日期范围筛选
            if start_date:
                # 如果start_date是日期格式（不含时间），设置为当天00:00:00
                if len(start_date) == 10:  # YYYY-MM-DD格式
                    start_date = start_date + " 00:00:00"
                sql += " AND mt.operation_time >= %s"
                params.append(start_date)
            
            if end_date:
                # 如果end_date是日期格式（不含时间），设置为当天23:59:59
                if len(end_date) == 10:  # YYYY-MM-DD格式
                    end_date = end_date + " 23:59:59"
                sql += " AND mt.operation_time <= %s"
                params.append(end_date)
            
            # 添加排序
            sql += " ORDER BY mt.operation_time DESC"
            
            # 执行查询
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(sql, params)
            result = cursor.fetchall()
            cursor.close()
            conn.close()
            
            # 转换为前端需要的格式
            activity_logs = []
            for row in result:
                record = {
                    'id': row['id'],
                    'operation_time': row['operation_time'].strftime('%Y-%m-%d %H:%M:%S') if row['operation_time'] else '',
                    'equipment_id': row['equipment_name'] or row['equipment_id'] or '',
                    'rfid_card_id': row['real_name'] or row['rfid_card_id'] or '',
                    'medicine_code': row['medicine_name'] or row['medicine_code'] or '',
                    'operation_type': '借出' if row['operation_type'] == 'borrow' else '归还' if row['operation_type'] == 'return' else row['operation_type']
                }
                activity_logs.append(record)
            
            # 生成静态异常行为数据（根据需求）
            abnormal_behaviors = [
                {
                    'time': '2025-11-20 14:30:00',
                    'type': '非法开锁尝试',
                    'description': '曾尝试非法开锁2号柜',
                    'severity': 'high'
                },
                {
                    'time': '2025-11-18 09:15:00',
                    'type': '超时归还',
                    'description': '张三归还药品超时2小时',
                    'severity': 'medium'
                },
                {
                    'time': '2025-11-15 16:45:00',
                    'type': '频繁借药',
                    'description': '李四在1小时内借药3次',
                    'severity': 'low'
                }
            ]
            
            return jsonify({
                'success': True,
                'data': activity_logs,
                'cabinet_id': cabinet_id,
                'abnormal_behaviors': abnormal_behaviors
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'获取药柜活动日志失败: {str(e)}'
            }), 500