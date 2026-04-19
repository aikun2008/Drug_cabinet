#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统报警中心 - 使用 web_alarm_log 表（所有设备共用）
"""

from flask import render_template, request, jsonify, session
from datetime import datetime, timedelta
import json
import pymysql
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE_1

def get_db_connection():
    """获取数据库连接（使用 web 数据库）"""
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE_1,  # 使用 web 数据库
        cursorclass=pymysql.cursors.DictCursor
    )

def get_current_user_rfid():
    """获取当前登录用户的 RFID"""
    try:
        # 从 session 获取当前用户信息
        username = session.get('username')
        if not username:
            return None
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = "SELECT rfid_card_id FROM web_user WHERE username = %s"
            cursor.execute(sql, (username,))
            result = cursor.fetchone()
            return result['rfid_card_id'] if result else None
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 获取用户RFID失败: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()

def admin_alarm_log_page():
    """系统报警中心页面"""
    return render_template('admin_alarm_log.html')

def get_alarm_data():
    """获取报警数据API"""
    try:
        # 获取请求参数
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        device_id = request.args.get('device_id')
        category = request.args.get('category')  # 分类筛选
        status = request.args.get('status')      # 状态筛选
        
        # 构建查询SQL
        sql = """
            SELECT id, equipment_id, alarm_category, alarm_content, 
                   status, handled_by, handled_time, handle_result, save_time 
            FROM web_alarm_log
        """
        params = []
        conditions = []
        
        # 添加日期范围筛选
        if start_date:
            if len(start_date) == 10:
                start_date = start_date + " 00:00:00"
            conditions.append("save_time >= %s")
            params.append(start_date)
        if end_date:
            if len(end_date) == 10:
                end_date = end_date + " 23:59:59"
            conditions.append("save_time <= %s")
            params.append(end_date)
        
        # 添加设备筛选
        if device_id:
            conditions.append("equipment_id = %s")
            params.append(device_id)
        
        # 添加分类筛选
        if category:
            conditions.append("alarm_category = %s")
            params.append(category)
        
        # 添加状态筛选
        if status:
            conditions.append("status = %s")
            params.append(status)
        
        # 添加WHERE条件
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        
        # 按时间倒序排列
        sql += " ORDER BY save_time DESC"
        
        # 连接数据库获取数据
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # 转换为前端需要的格式
        data = []
        for row in rows:
            record = {
                'id': row['id'],
                'timestamp': row['save_time'].isoformat(),
                'device_id': row['equipment_id'],
                'category': row['alarm_category'],
                'content': row['alarm_content'],
                'status': row['status'],
                'handled_by': row['handled_by'],
                'handled_time': row['handled_time'].isoformat() if row['handled_time'] else None,
                'handle_result': row['handle_result']
            }
            data.append(record)
        
        return jsonify({
            'success': True,
            'data': data,
            'total': len(data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取报警数据失败: {str(e)}'
        }), 500

def get_alarm_statistics():
    """获取报警统计数据API - 5个统计卡片"""
    try:
        device_id = request.args.get('device_id')
        
        # 获取今日日期范围
        today_start = datetime.now().strftime('%Y-%m-%d 00:00:00')
        today_end = datetime.now().strftime('%Y-%m-%d 23:59:59')
        
        # 构建基础条件
        base_conditions = "save_time >= %s AND save_time <= %s"
        base_params = [today_start, today_end]
        
        # 如果指定了设备，添加设备条件
        if device_id:
            base_conditions += " AND equipment_id = %s"
            base_params.append(device_id)
        
        # 查询统计数据
        sql = f"""
        SELECT 
            SUM(CASE WHEN alarm_category = '环境异常' THEN 1 ELSE 0 END) as env_abnormal,
            SUM(CASE WHEN alarm_category = '环境报警' THEN 1 ELSE 0 END) as env_alarm,
            SUM(CASE WHEN alarm_category = '门锁异常' THEN 1 ELSE 0 END) as door_abnormal,
            SUM(CASE WHEN alarm_category = '门锁报警' THEN 1 ELSE 0 END) as door_alarm,
            COUNT(*) as total_today
        FROM web_alarm_log
        WHERE {base_conditions}
        """
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql, base_params)
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        stats = {
            'env_abnormal': row['env_abnormal'] or 0,
            'env_alarm': row['env_alarm'] or 0,
            'door_abnormal': row['door_abnormal'] or 0,
            'door_alarm': row['door_alarm'] or 0,
            'total_today': row['total_today'] or 0
        }
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取统计数据失败: {str(e)}'
        }), 500

def handle_alarm(alarm_id):
    """处理报警API - 包含处理结果"""
    try:
        # 获取处理结果
        handle_result = request.json.get('handle_result', '')
        
        # 获取当前用户的 RFID
        handled_by = get_current_user_rfid()
        if not handled_by:
            handled_by = request.json.get('handled_by', '管理员')
        
        sql = """
            UPDATE web_alarm_log 
            SET status = '已处理', 
                handled_by = %s, 
                handled_time = NOW(),
                handle_result = %s
            WHERE id = %s
        """
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql, (handled_by, handle_result, alarm_id))
        conn.commit()
        affected = cursor.rowcount
        
        # 获取设备ID用于通知ESP32
        if affected > 0:
            cursor.execute("SELECT equipment_id FROM web_alarm_log WHERE id = %s", (alarm_id,))
            row = cursor.fetchone()
            device_id = row['equipment_id'] if row else None
        
        cursor.close()
        conn.close()
        
        if affected > 0:
            # 通知ESP32报警已处理
            if device_id:
                notify_esp32_alarm_handled(device_id, alarm_id)
            
            return jsonify({
                'success': True,
                'message': '报警已处理'
            })
        else:
            return jsonify({
                'success': False,
                'message': '报警记录不存在'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'处理报警失败: {str(e)}'
        }), 500

def notify_esp32_alarm_handled(device_id, alarm_id):
    """通知ESP32报警已处理"""
    try:
        # 导入emqx_manager发布消息
        from emqx_manager import get_emqx_manager
        
        emqx = get_emqx_manager()
        if emqx and emqx.client:
            message = {
                "equipment_id": device_id,
                "command": "alarm_handled",
                "alarm_id": alarm_id
            }
            topic = "/server/command/esp32"
            emqx.publish(topic, json.dumps(message), qos=1)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [报警] 已通知 {device_id} 报警 {alarm_id} 已处理")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 通知ESP32失败: {str(e)}")

def save_alarm(device_id, category, content):
    """保存报警记录"""
    try:
        sql = """
            INSERT INTO web_alarm_log (equipment_id, alarm_category, alarm_content, status, save_time)
            VALUES (%s, %s, %s, '未处理', NOW())
        """
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql, (device_id, category, content))
        conn.commit()
        alarm_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [报警] 报警已保存: {device_id} - {category}")
        return alarm_id
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 保存报警失败: {str(e)}")
        return None

def init_alarm_log_routes(app, login_required):
    """初始化系统报警中心路由"""
    
    # 系统报警中心页面
    @app.route('/admin_alarm_log.html')
    @login_required
    def admin_alarm_log():
        return admin_alarm_log_page()
    
    # 报警数据API
    @app.route('/api/alarm-data')
    @login_required
    def api_alarm_data():
        return get_alarm_data()
    
    # 报警统计数据API
    @app.route('/api/alarm-statistics')
    @login_required
    def api_alarm_statistics():
        return get_alarm_statistics()
    
    # 处理报警API
    @app.route('/api/alarm/<alarm_id>/handle', methods=['POST'])
    @login_required
    def api_handle_alarm(alarm_id):
        return handle_alarm(alarm_id)

# 导出函数
export_dict = {
    'init_alarm_log_routes': init_alarm_log_routes,
    'admin_alarm_log_page': admin_alarm_log_page,
    'get_alarm_data': get_alarm_data,
    'get_alarm_statistics': get_alarm_statistics,
    'handle_alarm': handle_alarm,
    'save_alarm': save_alarm
}
