from flask import render_template, jsonify
import pymysql
from datetime import datetime

# 导入配置
from config import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, 
    MYSQL_DATABASE_1, MYSQL_TABLE_USER_1
)

# 导航菜单项
menu_items = [
    {'id': 'dashboard', 'name': '系统首页', 'icon': '&#9776;'},
    {'id': 'device_monitoring', 'name': '设备监控', 'icon': '&#128246;'},
    {'id': 'basic_table', 'name': '基础表格', 'icon': '&#128202;'},
    {'id': 'tabs', 'name': 'tab选项卡', 'icon': '&#128444;'}
]

# 数据库连接函数
def get_db_connection():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE_1,
        cursorclass=pymysql.cursors.DictCursor
    )

# 为菜单项添加URL的辅助函数
def add_url_to_menu_items(items, active_id=None):
    """为菜单项列表添加URL属性"""
    url_map = {
        'device_monitoring': '/admin/device-monitoring',
        'dashboard': '/dashboard'
        # 可以根据需要添加更多映射
    }
    
    return [{
        **item,
        'url': url_map.get(item['id'], f"/admin/{item['id']}"),
        'active': item['id'] == active_id if active_id else False
    } for item in items]

# 初始化admin相关路由的函数
def init_admin_routes(app, login_required):
    # 导入分离的模块
    from admin_equip_montior import init_equipment_routes
    from admin_user_profile import init_user_routes
    from admin_equip_config import init_equip_config_routes
    from admin_equip_ota import init_equip_ota_routes
    from admin_user_config import init_user_config_routes
    from admin_drug_catalogue import init_drug_catalogue_routes
    from admin_drug_log import init_drug_log_routes
    
    # 管理员首页（需要登录）
    @app.route('/dashboard')
    @login_required
    def dashboard():
        menu_items_with_urls = add_url_to_menu_items(menu_items, 'dashboard')
        return render_template('admin_dashboard.html', menu_items=menu_items_with_urls, active_menu='dashboard')
    
    # 添加对admin_dashboard.html的直接访问支持
    @app.route('/admin_dashboard.html')
    @login_required
    def admin_dashboard_html():
        # 复用dashboard函数的逻辑
        return dashboard()
    
    # 添加对admin_drug_catalogue.html的直接访问支持
    @app.route('/admin_drug_catalogue.html')
    @login_required
    def admin_drug_catalogue_html():
        menu_items_with_urls = add_url_to_menu_items(menu_items, 'medicine-catalog')
        return render_template('admin_drug_catalogue.html', menu_items=menu_items_with_urls, active_menu='medicine-catalog')
    
    # ==================== 仪表盘统计数据API ====================
    
    @app.route('/api/dashboard/stats')
    @login_required
    def get_dashboard_stats():
        """获取仪表盘统计数据"""
        conn = None
        try:
            conn = get_db_connection()
            stats = {}
            
            # 1. 设备在线数量 (connection_status = 0 表示在线)
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN connection_status = 0 THEN 1 ELSE 0 END) as online
                    FROM web_equipment
                """)
                result = cursor.fetchone()
                stats['equipment'] = {
                    'online': result['online'] or 0,
                    'total': result['total'] or 0
                }
            
            # 2. 药品总数
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as total FROM web_medicine_list")
                result = cursor.fetchone()
                stats['drugs'] = {
                    'total': result['total'] or 0
                }
            
            # 3. 当前报警数量 (未处理的报警)
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) as total 
                    FROM web_alarm_log 
                    WHERE status = '未处理'
                """)
                result = cursor.fetchone()
                stats['alarms'] = {
                    'total': result['total'] or 0
                }
            
            # 4. 用户总数
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) as total FROM {MYSQL_TABLE_USER_1}")
                result = cursor.fetchone()
                stats['users'] = {
                    'total': result['total'] or 0
                }
            
            return jsonify({
                'success': True,
                'data': stats,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [错误] 获取仪表盘统计数据失败: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'获取统计数据失败: {str(e)}'
            }), 500
        finally:
            if conn:
                conn.close()
    
    # 初始化设备相关路由
    init_equipment_routes(app, login_required, get_db_connection)
    
    # 初始化用户相关路由
    init_user_routes(app, login_required, get_db_connection, MYSQL_TABLE_USER_1)
    # 初始化设备配置路由
    init_equip_config_routes(app, login_required, get_db_connection)
    # 初始化远程升级路由
    init_equip_ota_routes(app, login_required, get_db_connection)
    # 初始化权限组配置路由
    init_user_config_routes(app, login_required, get_db_connection, MYSQL_TABLE_USER_1)
    # 初始化药品目录路由
    init_drug_catalogue_routes(app, login_required, get_db_connection)
    # 初始化药品追溯日志路由
    from db_cache_sync import get_cached_db_connection
    cached_db = get_cached_db_connection(get_db_connection)
    init_drug_log_routes(app, login_required, get_db_connection, cached_db)

# 导出需要在main.py中使用的函数
export_dict = {
    'init_admin_routes': init_admin_routes,
    'menu_items': menu_items,
    'add_url_to_menu_items': add_url_to_menu_items
}