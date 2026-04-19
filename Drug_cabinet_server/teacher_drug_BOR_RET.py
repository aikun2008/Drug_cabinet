from flask import jsonify, request
from datetime import datetime
import sys
import os

# 导入数据库连接池
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from main import db_pool
except Exception as e:
    print(f"导入数据库连接池失败: {e}")
    db_pool = None

def release_db_connection(conn):
    """
    释放数据库连接到连接池
    
    Args:
        conn: 数据库连接对象
    """
    if not conn:
        return
    
    if not db_pool:
        # 如果没有连接池，直接关闭连接
        try:
            conn.close()
        except:
            pass
        return
    
    # 检查是否使用简单连接池
    if hasattr(db_pool.pool, 'put'):
        # 返回连接到池
        try:
            db_pool.pool.put(conn)
        except Exception as e:
            print(f"返回连接到池失败: {e}")
            try:
                release_db_connection(conn)
            except:
                pass
    else:
        # 使用pymysqlpool，连接会自动管理
        pass

# 导入Redis缓存管理器
try:
    from redis_manager import get_cache_manager
except Exception as e:
    print(f"导入Redis缓存管理器失败: {e}")
    get_cache_manager = None

# 导入权限管理
from permission_manager import permission_required

# 导出字典
export_dict = {}

def init_teacher_borrow_return_routes(app, login_required, get_db_connection):
    """
    初始化教师药品借阅和归还路由
    
    Args:
        app (Flask): Flask应用实例
        login_required (function): 登录验证装饰器
        get_db_connection (function): 获取数据库连接的函数
    """
    
    # 教师预定药品的API端点
    @app.route('/api/teacher/drugs/reserve', methods=['POST'])
    @login_required
    @permission_required('can_book_drugs')
    def teacher_reserve_drug():
        """
        教师预定药品（不需要审核）
        """
        conn = None
        try:
            conn = get_db_connection()
            data = request.json
            
            # 验证必填字段
            if 'drug_id' not in data or 'user_id' not in data:
                return jsonify({'success': False, 'message': '药品ID和用户ID是必填字段'})
            
            drug_id = data['drug_id']
            user_id = data['user_id']
            
            with conn.cursor() as cursor:
                # 验证药品是否存在
                cursor.execute("SELECT id FROM web_medicine_list WHERE id = %s", (drug_id,))
                drug = cursor.fetchone()
                if not drug:
                    return jsonify({'success': False, 'message': '指定的药品不存在'})
                
                # 验证用户是否为教师
                cursor.execute("SELECT id, role, rfid_card_id FROM web_user WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if not user or user['role'] != 1:  # 1为教师角色
                    return jsonify({'success': False, 'message': '只有教师可以预定药品'})
                
                # 获取用户的rfid_card_id
                rfid_card_id = user.get('rfid_card_id', '')
                
                # 检查药品当前状态，确保不是已借出状态
                cursor.execute("SELECT id, status FROM web_medicine_list WHERE id = %s", (drug_id,))
                drug_status = cursor.fetchone()
                if not drug_status:
                    return jsonify({'success': False, 'message': '指定的药品不存在'})
                if drug_status['status'] == 'lent_out':
                    return jsonify({'success': False, 'message': '该药品已被借出，无法预定'})
                
                # 检查是否已经有已完成的预定
                cursor.execute("SELECT id FROM web_medicine_reservation WHERE drug_id = %s AND status = 'completed'", (drug_id,))
                if cursor.fetchone():
                    return jsonify({'success': False, 'message': '该药品已经被预定'})
                
                # 开始事务
                # 在预定表中插入记录
                sql = "INSERT INTO web_medicine_reservation (drug_id, rfid_card_id, reservation_time, status) VALUES (%s, %s, NOW(), 'pending')"
                cursor.execute(sql, (drug_id, rfid_card_id))
                
                # 不需要更新药品状态，保持为in_stock
                # 只有当用户确认预定后，才将药品状态更新为reserved
                
                # 不需要记录预定操作到medicine_trace表，因为medicine_trace专注于实际的借出和归还
                
                conn.commit()
                
                return jsonify({'success': True, 'message': '药品预定成功'})
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"预定药品时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            release_db_connection(conn)
    
    # 教师取消预定药品的API端点
    @app.route('/api/teacher/drugs/cancel-reserve', methods=['POST'])
    @login_required
    def teacher_cancel_reserve():
        """
        教师取消预定药品
        """
        conn = None
        try:
            conn = get_db_connection()
            data = request.json
            
            # 验证必填字段
            if 'drug_id' not in data or 'user_id' not in data:
                return jsonify({'success': False, 'message': '药品ID和用户ID是必填字段'})
            
            drug_id = data['drug_id']
            user_id = data['user_id']
            
            with conn.cursor() as cursor:
                # 验证药品是否存在
                cursor.execute("SELECT id FROM web_medicine_list WHERE id = %s", (drug_id,))
                drug = cursor.fetchone()
                if not drug:
                    return jsonify({'success': False, 'message': '指定的药品不存在'})
                
                # 获取用户的rfid_card_id
                cursor.execute("SELECT rfid_card_id FROM web_user WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if not user:
                    return jsonify({'success': False, 'message': '用户不存在'})
                rfid_card_id = user.get('rfid_card_id', '')
                
                if not rfid_card_id:
                    return jsonify({'success': False, 'message': '用户未绑定RFID卡'})
                
                # 验证该用户是否有权限取消这个预定（只能取消自己的预定）
                cursor.execute("""
                    SELECT id FROM web_medicine_reservation 
                    WHERE drug_id = %s AND rfid_card_id = %s AND status IN ('pending', 'completed')
                """, (drug_id, rfid_card_id))
                reservation = cursor.fetchone()
                
                if not reservation:
                    return jsonify({'success': False, 'message': '您没有权限取消此预定，可能该药品不是您预定的，或预定状态已变更'})
                
                # 开始事务
                # 1. 更新预定表中的状态为cancelled
                sql = "UPDATE web_medicine_reservation SET status = 'cancelled', updated_at = NOW() WHERE drug_id = %s AND rfid_card_id = %s AND status IN ('pending', 'completed')"
                cursor.execute(sql, (drug_id, rfid_card_id))
                
                # 2. 更新药品状态为in_stock
                # 因为当用户确认预定时，药品状态会被更新为reserved
                sql = "UPDATE web_medicine_list SET status = 'in_stock', current_holder_id = NULL, last_operation_time = NOW() WHERE id = %s"
                cursor.execute(sql, (drug_id,))
                
                # 不需要记录取消预定操作到medicine_trace表，因为medicine_trace专注于实际的借出和归还
                
                conn.commit()

                # 清除药品缓存，确保下次查询时获取最新数据
                if get_cache_manager:
                    cache_manager = get_cache_manager()
                    try:
                        # 清除受影响药品的单个缓存
                        deleted_count = cache_manager.delete_drug_detail(drug_id)
                        print(f"清除了药品 {drug_id} 的缓存")
                        # 清除药品列表缓存，确保列表数据也是最新的
                        cache_manager.delete_drug_list_ids()
                        print("清除了药品列表缓存")
                    except Exception as e:
                        print(f"清除缓存失败: {e}")

                return jsonify({'success': True, 'message': '取消预定成功'})
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"取消预定药品时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                release_db_connection(conn)
    
    # 教师借阅药品的API端点
    @app.route('/api/teacher/drugs/borrow', methods=['POST'])
    @login_required
    @permission_required('can_borrow_return_drugs')
    def teacher_borrow_drug():
        """
        教师借阅药品
        """
        conn = None
        try:
            conn = get_db_connection()
            data = request.json
            
            # 验证必填字段
            if 'drug_id' not in data or 'user_id' not in data:
                return jsonify({'success': False, 'message': '药品ID和用户ID是必填字段'})
            
            drug_id = data['drug_id']
            user_id = data['user_id']
            
            with conn.cursor() as cursor:
                # 验证药品是否存在且状态为in_stock或reserved
                cursor.execute("SELECT id, status, current_holder_id FROM web_medicine_list WHERE id = %s", (drug_id,))
                drug = cursor.fetchone()
                if not drug:
                    return jsonify({'success': False, 'message': '指定的药品不存在'})
                if drug['status'] not in ['in_stock', 'reserved']:
                    return jsonify({'success': False, 'message': '该药品当前不可借阅'})
                # 验证用户是否为教师
                cursor.execute("SELECT id, role, rfid_card_id FROM web_user WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if not user or user['role'] != 1:  # 1为教师角色
                    return jsonify({'success': False, 'message': '只有教师可以借阅药品'})
                
                # 获取用户的rfid_card_id
                rfid_card_id = user.get('rfid_card_id', '')
                
                # 验证已预定药品的持有者
                if drug['status'] == 'reserved' and str(drug['current_holder_id']) != str(rfid_card_id):
                    return jsonify({'success': False, 'message': '该药品已被其他用户预定'})
                
                # 开始事务
                # 1. 如果是已预定的药品，更新预定表状态为completed
                if drug['status'] == 'reserved':
                    sql = "UPDATE web_medicine_reservation SET status = 'completed', updated_at = NOW() WHERE drug_id = %s AND rfid_card_id = %s AND status = 'pending'"
                    cursor.execute(sql, (drug_id, rfid_card_id))
                
                # 2. 更新药品状态为lent_out
                sql = "UPDATE web_medicine_list SET status = 'lent_out', current_holder_id = %s, last_operation_time = NOW() WHERE id = %s"
                cursor.execute(sql, (rfid_card_id, drug_id))
                
                # 3. 记录操作日志
                cursor.execute("INSERT INTO medicine_trace (equipment_id, rfid_card_id, medicine_code, operation_type, operation_time) SELECT '', %s, medicine_code, 'borrow', NOW() FROM web_medicine_list WHERE id = %s", (rfid_card_id, drug_id))
                
                conn.commit()

                # 清除药品缓存，确保下次查询时获取最新数据
                if get_cache_manager:
                    cache_manager = get_cache_manager()
                    try:
                        # 清除受影响药品的单个缓存
                        deleted_count = cache_manager.delete_drug_detail(drug_id)
                        print(f"清除了药品 {drug_id} 的缓存")
                        # 清除药品列表缓存，确保列表数据也是最新的
                        cache_manager.delete_drug_list_ids()
                        print("清除了药品列表缓存")
                    except Exception as e:
                        print(f"清除缓存失败: {e}")

                return jsonify({'success': True, 'message': '药品借阅成功'})
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"借阅药品时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                release_db_connection(conn)
    
    # 教师归还药品的API端点
    @app.route('/api/teacher/drugs/return', methods=['POST'])
    @login_required
    @permission_required('can_borrow_return_drugs')
    def teacher_return_drug():
        """
        教师归还药品
        """
        conn = None
        try:
            conn = get_db_connection()
            data = request.json
            
            # 验证必填字段
            if 'drug_id' not in data or 'user_id' not in data:
                return jsonify({'success': False, 'message': '药品ID和用户ID是必填字段'})
            
            drug_id = data['drug_id']
            user_id = data['user_id']
            
            with conn.cursor() as cursor:
                # 获取用户的rfid_card_id
                cursor.execute("SELECT rfid_card_id FROM web_user WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                rfid_card_id = user.get('rfid_card_id', '')
                
                # 验证药品是否存在且状态为lent_out，且当前持有者为该用户
                cursor.execute("SELECT id, status, current_holder_id FROM web_medicine_list WHERE id = %s", (drug_id,))
                drug = cursor.fetchone()
                if not drug:
                    return jsonify({'success': False, 'message': '指定的药品不存在'})
                if drug['status'] != 'lent_out':
                    return jsonify({'success': False, 'message': '该药品当前不是借出状态'})
                if str(drug['current_holder_id']) != str(rfid_card_id):
                    return jsonify({'success': False, 'message': '您不是该药品的借阅者'})
                
                # 更新药品状态为in_stock
                sql = "UPDATE web_medicine_list SET status = 'in_stock', current_holder_id = NULL, last_operation_time = NOW() WHERE id = %s"
                cursor.execute(sql, (drug_id,))
                conn.commit()
                
                # 记录操作日志
                cursor.execute("INSERT INTO medicine_trace (equipment_id, rfid_card_id, medicine_code, operation_type, operation_time) SELECT '', %s, medicine_code, 'return', NOW() FROM web_medicine_list WHERE id = %s", (rfid_card_id, drug_id))
                conn.commit()

                # 清除药品缓存，确保下次查询时获取最新数据
                if get_cache_manager:
                    cache_manager = get_cache_manager()
                    try:
                        # 清除受影响药品的单个缓存
                        deleted_count = cache_manager.delete_drug_detail(drug_id)
                        print(f"清除了药品 {drug_id} 的缓存")
                        # 清除药品列表缓存，确保列表数据也是最新的
                        cache_manager.delete_drug_list_ids()
                        print("清除了药品列表缓存")
                    except Exception as e:
                        print(f"清除缓存失败: {e}")

                return jsonify({'success': True, 'message': '药品归还成功'})
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"归还药品时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                release_db_connection(conn)
    
    # 获取教师待借药品列表的API端点
    @app.route('/api/teacher/drugs/pending', methods=['GET'])
    @login_required
    def get_teacher_pending_drugs():
        """
        获取教师待借药品列表（已预定但未借阅的药品）
        """
        conn = None
        try:
            conn = get_db_connection()
            # 从请求头中获取用户ID（或从token中解析）
            # 这里假设用户ID已经通过认证中间件获取
            # 实际实现中可能需要从token中解析用户ID
            user_id = request.args.get('user_id')
            if not user_id:
                return jsonify({'success': False, 'message': '用户ID是必填字段'})
            
            with conn.cursor() as cursor:
                # 查询用户是否为教师
                cursor.execute("SELECT id, role, rfid_card_id FROM web_user WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if not user or user['role'] != 1:  # 1为教师角色
                    return jsonify({'success': False, 'message': '只有教师可以查看待借药品列表'})
                
                # 获取用户的rfid_card_id
                rfid_card_id = user.get('rfid_card_id', '')
                
                # 从预定表中查询该教师待处理的预定记录
                sql = """
                SELECT wml.id, wml.name, wml.specification, wml.location, wml.expiry_date, wml.medicine_code 
                FROM web_medicine_list wml
                JOIN web_medicine_reservation wmr ON wml.id = wmr.drug_id
                WHERE wmr.rfid_card_id = %s AND wmr.status = 'pending'
                """
                cursor.execute(sql, (rfid_card_id,))
                pending_drugs = cursor.fetchall()
                
                return jsonify({'success': True, 'data': pending_drugs})
        except Exception as e:
            print(f"获取待借药品列表时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                release_db_connection(conn)
    
    # 获取教师药品记录的API端点
    @app.route('/api/teacher/drugs/records', methods=['GET'])
    @login_required
    def get_teacher_drug_records():
        """
        获取教师药品记录（已预定、已借出、已归还的药品）
        """
        conn = None
        try:
            conn = get_db_connection()
            user_id = request.args.get('user_id')
            if not user_id:
                return jsonify({'success': False, 'message': '用户ID是必填字段'})
            
            with conn.cursor() as cursor:
                # 查询用户是否为教师以及获取用户的rfid_card_id
                cursor.execute("SELECT id, role, rfid_card_id FROM web_user WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if not user or user['role'] != 1:  # 1为教师角色
                    return jsonify({'success': False, 'message': '只有教师可以查看药品记录'})
                
                # 获取用户的rfid_card_id
                rfid_card_id = user.get('rfid_card_id', '')
                
                # 查询该教师的药品记录
                sql = """
                SELECT id, name, specification, status, last_operation_time as operation_time 
                FROM web_medicine_list 
                WHERE current_holder_id = %s AND status IN ('reserved', 'lent_out', 'returned')
                """
                cursor.execute(sql, (rfid_card_id,))
                records = cursor.fetchall()
                
                # 为每条记录添加状态名称
                for record in records:
                    if record['status'] == 'reserved':
                        record['status_name'] = '已预定'
                    elif record['status'] == 'lent_out':
                        record['status_name'] = '已借出'
                    elif record['status'] == 'returned':
                        record['status_name'] = '已归还'
                
                return jsonify({'success': True, 'data': records})
        except Exception as e:
            print(f"获取药品记录时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                release_db_connection(conn)
    
    # 获取教师借还记录的API端点（支持分页）
    @app.route('/api/teacher/drugs/borrow-return-records', methods=['GET'])
    @login_required
    def get_teacher_borrow_return_records():
        """
        获取教师的借还记录（支持分页）
        """
        conn = None
        try:
            conn = get_db_connection()
            user_id = request.args.get('user_id')
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 5))
            operation_type = request.args.get('type', '')  # 可选参数：borrow或return
            
            if not user_id:
                return jsonify({'success': False, 'message': '用户ID是必填字段'})
            
            with conn.cursor() as cursor:
                # 查询用户是否为教师以及获取用户的rfid_card_id
                cursor.execute("SELECT id, role, rfid_card_id FROM web_user WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if not user or user['role'] != 1:  # 1为教师角色
                    return jsonify({'success': False, 'message': '只有教师可以查看借还记录'})
                
                # 获取用户的rfid_card_id
                rfid_card_id = user.get('rfid_card_id', '')
                
                # 构建查询SQL，参考admin_drug_log.py中的实现
                sql = """
                SELECT 
                    mt.id, 
                    mt.operation_time, 
                    mt.medicine_code, 
                    wml.name as medicine_name, 
                    wml.specification, 
                    mt.operation_type
                FROM medicine_trace mt
                LEFT JOIN web_medicine_list wml ON mt.medicine_code = wml.medicine_code
                WHERE mt.rfid_card_id = %s
                """
                
                params = [rfid_card_id]
                
                # 添加操作类型筛选
                if operation_type in ['borrow', 'return']:
                    sql += " AND mt.operation_type = %s"
                    params.append(operation_type)
                
                # 添加排序和分页
                sql += " ORDER BY mt.operation_time DESC LIMIT %s OFFSET %s"
                offset = (page - 1) * limit
                params.extend([limit, offset])
                
                cursor.execute(sql, params)
                records = cursor.fetchall()
                
                # 获取总记录数
                count_sql = "SELECT COUNT(*) as total FROM medicine_trace WHERE rfid_card_id = %s"
                count_params = [rfid_card_id]
                
                if operation_type in ['borrow', 'return']:
                    count_sql += " AND operation_type = %s"
                    count_params.append(operation_type)
                
                cursor.execute(count_sql, count_params)
                total_records = cursor.fetchone()['total']
                
                # 转换为前端需要的格式
                result = []
                for record in records:
                    result.append({
                        'id': record['id'],
                        'medicine_name': record['medicine_name'] or record['medicine_code'],
                        'specification': record['specification'] or '',
                        'operation_time': record['operation_time'].strftime('%Y-%m-%d %H:%M:%S') if record['operation_time'] else '',
                        'operation_type': '已借出' if record['operation_type'] == 'borrow' else '已归还'
                    })
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'total': total_records,
                    'page': page,
                    'limit': limit,
                    'has_more': (page * limit) < total_records
                })
        except Exception as e:
            print(f"获取借还记录时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                release_db_connection(conn)
    
    # 教师确认预定药品的API端点
    @app.route('/api/teacher/drugs/confirm-reserve', methods=['POST'])
    @login_required
    def teacher_confirm_reserve():
        """
        教师确认预定药品（将pending状态改为completed状态）
        """
        conn = None
        try:
            conn = get_db_connection()
            data = request.json
            
            # 验证必填字段
            if 'drug_id' not in data or 'user_id' not in data:
                return jsonify({'success': False, 'message': '药品ID和用户ID是必填字段'})
            
            drug_id = data['drug_id']
            user_id = data['user_id']
            
            with conn.cursor() as cursor:
                # 验证药品是否存在
                cursor.execute("SELECT id FROM web_medicine_list WHERE id = %s", (drug_id,))
                drug = cursor.fetchone()
                if not drug:
                    return jsonify({'success': False, 'message': '指定的药品不存在'})
                
                # 验证用户是否为教师
                cursor.execute("SELECT id, role, rfid_card_id FROM web_user WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if not user or user['role'] != 1:  # 1为教师角色
                    return jsonify({'success': False, 'message': '只有教师可以确认预定药品'})
                
                # 获取用户的rfid_card_id
                rfid_card_id = user.get('rfid_card_id', '')
                
                # 开始事务
                # 1. 更新预定表中的状态为completed
                sql = "UPDATE web_medicine_reservation SET status = 'completed', updated_at = NOW() WHERE drug_id = %s AND rfid_card_id = %s AND status = 'pending'"
                cursor.execute(sql, (drug_id, rfid_card_id))
                
                # 2. 更新药品状态为reserved
                sql = "UPDATE web_medicine_list SET status = 'reserved', current_holder_id = %s, last_operation_time = NOW() WHERE id = %s"
                cursor.execute(sql, (rfid_card_id, drug_id))
                
                conn.commit()

                # 清除药品缓存，确保下次查询时获取最新数据
                if get_cache_manager:
                    cache_manager = get_cache_manager()
                    try:
                        # 清除受影响药品的单个缓存
                        deleted_count = cache_manager.delete_drug_detail(drug_id)
                        print(f"清除了药品 {drug_id} 的缓存")
                        # 清除药品列表缓存，确保列表数据也是最新的
                        cache_manager.delete_drug_list_ids()
                        print("清除了药品列表缓存")
                    except Exception as e:
                        print(f"清除缓存失败: {e}")

                return jsonify({'success': True, 'message': '确认预定成功'})
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"确认预定药品时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                release_db_connection(conn)
    
    # 教师获取待审核的学生预定列表
    @app.route('/api/teacher/drugs/pending-approval', methods=['GET'])
    @login_required
    def get_teacher_pending_approval_drugs():
        """
        获取教师待审核的学生预定列表（只显示绑定的学生）
        """
        conn = None
        try:
            conn = get_db_connection()
            
            with conn.cursor() as cursor:
                # 查询用户是否为教师
                user_id = request.args.get('user_id')
                if not user_id:
                    return jsonify({'success': False, 'message': '用户ID是必填字段'})
                
                cursor.execute("SELECT id, role FROM web_user WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if not user or user['role'] != 1:  # 1为教师角色
                    return jsonify({'success': False, 'message': '只有教师可以查看待审核的预定列表'})
                
                # 从预定表中查询待审核预定记录
                sql = """
                SELECT 
                    wml.id, 
                    wml.name, 
                    wml.specification, 
                    wml.location, 
                    wml.expiry_date, 
                    wml.medicine_code,
                    wu.id as user_id,
                    wu.real_name as student_name
                FROM web_medicine_list wml
                JOIN web_medicine_reservation wmr ON wml.id = wmr.drug_id
                JOIN web_user wu ON wmr.rfid_card_id = wu.rfid_card_id
                WHERE wmr.status = 'pending_approval'
                ORDER BY wmr.reservation_time DESC
                """
                
                cursor.execute(sql, ())
                pending_approval_drugs = cursor.fetchall()
                
                return jsonify({'success': True, 'data': pending_approval_drugs})
        except Exception as e:
            print(f"获取待审核预定列表时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                release_db_connection(conn)
    
    # 教师审核学生预定药品的API端点
    @app.route('/api/teacher/drugs/approve-reserve', methods=['POST'])
    @login_required
    def teacher_approve_reserve():
        """
        教师审核学生预定药品（通过或拒绝）
        """
        conn = None
        try:
            conn = get_db_connection()
            data = request.json
            
            # 验证必填字段
            if 'drug_id' not in data or 'user_id' not in data or 'approve' not in data:
                return jsonify({'success': False, 'message': '药品ID、用户ID和审核结果是必填字段'})
            
            drug_id = data['drug_id']
            user_id = data['user_id']
            approve = data['approve']  # true为通过，false为拒绝
            remark = data.get('remark', '')
            
            with conn.cursor() as cursor:
                # 验证药品是否存在
                cursor.execute("SELECT id FROM web_medicine_list WHERE id = %s", (drug_id,))
                drug = cursor.fetchone()
                if not drug:
                    return jsonify({'success': False, 'message': '指定的药品不存在'})
                
                # 验证用户是否为教师
                cursor.execute("SELECT id, role, rfid_card_id FROM web_user WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if not user or user['role'] != 1:  # 1为教师角色
                    return jsonify({'success': False, 'message': '只有教师可以审核预定药品'})
                
                # 开始事务
                if approve:
                    # 审核通过：更新预定状态为completed，并更新药品状态为reserved
                    # 1. 更新预定表中的状态为completed
                    sql = "UPDATE web_medicine_reservation SET status = 'completed', updated_at = NOW() WHERE drug_id = %s AND status = 'pending_approval'"
                    cursor.execute(sql, (drug_id,))
                    
                    # 2. 获取学生的rfid_card_id
                    cursor.execute("SELECT rfid_card_id FROM web_medicine_reservation WHERE drug_id = %s AND status = 'completed'", (drug_id,))
                    student = cursor.fetchone()
                    if not student:
                        return jsonify({'success': False, 'message': '学生信息不存在'})
                    student_rfid = student.get('rfid_card_id', '')
                    
                    # 3. 更新药品状态为reserved
                    sql = "UPDATE web_medicine_list SET status = 'reserved', current_holder_id = %s, last_operation_time = NOW() WHERE id = %s"
                    cursor.execute(sql, (student_rfid, drug_id))
                else:
                    # 审核拒绝：更新预定状态为cancelled
                    sql = "UPDATE web_medicine_reservation SET status = 'cancelled', updated_at = NOW() WHERE drug_id = %s AND status = 'pending_approval'"
                    cursor.execute(sql, (drug_id,))
                
                conn.commit()

                # 清除药品缓存，确保下次查询时获取最新数据
                if get_cache_manager:
                    cache_manager = get_cache_manager()
                    try:
                        # 清除受影响药品的单个缓存
                        deleted_count = cache_manager.delete_drug_detail(drug_id)
                        print(f"清除了药品 {drug_id} 的缓存")
                        # 清除药品列表缓存，确保列表数据也是最新的
                        cache_manager.delete_drug_list_ids()
                        print("清除了药品列表缓存")
                    except Exception as e:
                        print(f"清除缓存失败: {e}")

                return jsonify({'success': True, 'message': '审核成功'})
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"审核预定药品时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                release_db_connection(conn)
    
    # 导出函数供其他模块使用
    return {}


export_dict['init_teacher_borrow_return_routes'] = init_teacher_borrow_return_routes
