#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境数据日志管理页面
"""

from flask import render_template, request, jsonify
from datetime import datetime, timedelta
import json
import pymysql
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE_2

def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE_2,
        cursorclass=pymysql.cursors.DictCursor
    )

def admin_env_log_page():
    """环境数据日志页面"""
    return render_template('admin_env_log.html')

def get_environment_data():
    """获取环境数据API"""
    try:
        # 获取请求参数
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        device_id = request.args.get('device_id')
        
        # 默认显示cabinet_001的数据
        if not device_id:
            device_id = 'cabinet_001'
        
        # 构建表名
        table_name = f"history_environment_data_{device_id}"
        
        # 构建查询SQL
        sql = f"SELECT id, temperature, humidity, aqi, save_time FROM {table_name}"
        params = []
        conditions = []
        
        # 添加日期范围筛选
        if start_date:
            # 如果start_date是日期格式（不含时间），设置为当天00:00:00
            if len(start_date) == 10:  # YYYY-MM-DD格式
                start_date = start_date + " 00:00:00"
            conditions.append("save_time >= %s")
            params.append(start_date)
        if end_date:
            # 如果end_date是日期格式（不含时间），设置为当天23:59:59
            if len(end_date) == 10:  # YYYY-MM-DD格式
                end_date = end_date + " 23:59:59"
            conditions.append("save_time <= %s")
            params.append(end_date)
        
        # 添加WHERE条件
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        
        # 按时间倒序排列（最新数据在最上方）
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
                'device_id': device_id,
                'temperature': float(row['temperature']),
                'humidity': float(row['humidity']),
                'aqi': int(row['aqi'])
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
            'message': f'获取环境数据失败: {str(e)}'
        }), 500

def get_environment_statistics():
    """获取环境统计数据API"""
    try:
        # 获取请求参数
        device_id = request.args.get('device_id')
        
        # 默认使用cabinet_001
        if not device_id:
            device_id = 'cabinet_001'
        
        # 构建表名
        table_name = f"history_environment_data_{device_id}"
        
        # 查询统计数据
        sql = f"""
        SELECT 
            AVG(temperature) as avg_temperature,
            AVG(humidity) as avg_humidity,
            AVG(aqi) as avg_aqi,
            COUNT(*) as total_records
        FROM {table_name}
        """
        
        # 连接数据库获取数据
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        stats = {
            'avg_temperature': round(float(row['avg_temperature']) if row['avg_temperature'] else 0, 1),
            'avg_humidity': round(float(row['avg_humidity']) if row['avg_humidity'] else 0, 1),
            'avg_aqi': round(float(row['avg_aqi']) if row['avg_aqi'] else 0, 1),
            'total_records': row['total_records'] or 0
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

def get_environment_record_detail(record_id):
    """获取特定环境记录详情API"""
    try:
        # 获取请求参数
        device_id = request.args.get('device_id')
        
        # 默认使用cabinet_001
        if not device_id:
            device_id = 'cabinet_001'
        
        # 构建表名
        table_name = f"history_environment_data_{device_id}"
        
        # 查询特定记录
        sql = f"SELECT id, temperature, humidity, aqi, save_time FROM {table_name} WHERE id = %s"
        
        # 连接数据库获取数据
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql, (record_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
            return jsonify({
                'success': False,
                'message': '记录不存在'
            }), 404
        
        detail = {
            'id': row['id'],
            'timestamp': row['save_time'].isoformat(),
            'device_id': device_id,
            'location': f'药品储存室{device_id.split("_")[-1]}',
            'temperature': float(row['temperature']),
            'humidity': float(row['humidity']),
            'aqi': int(row['aqi']),
            'battery_level': None,  # 数据库中没有这个字段
            'signal_strength': None,  # 数据库中没有这个字段
            'notes': '设备运行正常'  # 可以后续扩展
        }
        
        return jsonify({
            'success': True,
            'data': detail
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取记录详情失败: {str(e)}'
        }), 500

def export_environment_data():
    """导出环境数据API"""
    try:
        # 获取筛选条件
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        device_id = request.args.get('device_id')
        
        # 这里应该根据筛选条件生成CSV或Excel文件
        # 暂时返回成功响应
        return jsonify({
            'success': True,
            'message': '数据导出功能开发中',
            'download_url': '/static/exports/environment_data.csv'  # 实际应该返回真实的下载链接
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'导出数据失败: {str(e)}'
        }), 500

def init_env_log_routes(app, login_required):
    """初始化环境数据日志路由"""
    
    # 环境数据日志页面
    @app.route('/admin_env_log.html')
    @login_required
    def admin_env_log():
        return admin_env_log_page()
    
    # 环境数据API
    @app.route('/api/environment-data')
    @login_required
    def api_environment_data():
        return get_environment_data()
    
    # 环境统计数据API
    @app.route('/api/environment-statistics')
    @login_required
    def api_environment_statistics():
        return get_environment_statistics()
    
    # 环境记录详情API
    @app.route('/api/environment-record/<record_id>')
    @login_required
    def api_environment_record_detail(record_id):
        return get_environment_record_detail(record_id)
    
    # 导出环境数据API
    @app.route('/api/export-environment-data')
    @login_required
    def api_export_environment_data():
        return export_environment_data()

# 导出需要在main.py中使用的函数
export_dict = {
    'init_env_log_routes': init_env_log_routes,
    'admin_env_log_page': admin_env_log_page,
    'get_environment_data': get_environment_data,
    'get_environment_statistics': get_environment_statistics,
    'get_environment_record_detail': get_environment_record_detail,
    'export_environment_data': export_environment_data
}