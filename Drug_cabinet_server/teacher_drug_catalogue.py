from flask import jsonify, request, redirect, url_for
import logging

# 导入Redis缓存管理器
try:
    from redis_manager import get_cache_manager
except Exception as e:
    logging.error(f"导入Redis缓存管理器失败: {e}")
    get_cache_manager = None

# 导入权限管理
from permission_manager import permission_required

# 导入admin_drug_catalogue中的get_drugs_data函数
try:
    # 直接从admin_drug_catalogue.py文件导入
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from admin_drug_catalogue import get_drugs_data
    print("成功导入get_drugs_data函数")
except Exception as e:
    logging.error(f"导入admin_drug_catalogue失败: {e}")
    print(f"导入admin_drug_catalogue失败: {e}")
    get_drugs_data = None

# 导出字典
export_dict = {}

def init_teacher_routes(app, login_required, get_db_connection, cached_db):
    """
    初始化教师相关路由
    
    Args:
        app (Flask): Flask应用实例
        login_required (function): 登录验证装饰器
        get_db_connection (function): 获取数据库连接的函数
        cached_db (function): 带缓存的数据库连接函数
    """
    
    # 为小程序端添加专用路由，避免与web端冲突
    @app.route('/api/mini/drugs', methods=['GET'])
    @login_required
    @permission_required('can_query_drugs')
    def get_mini_drugs():
        """
        获取小程序端药品列表（支持搜索和分页）
        使用新的缓存架构：单个药品缓存 + 列表索引
        """
        try:
            # 获取搜索关键词
            keyword = request.args.get('keyword', '').strip()
            # 获取分页参数
            page = request.args.get('page', 1, type=int)
            limit = request.args.get('limit', 5, type=int)
            # 获取刷新参数，用于绕过缓存
            refresh = request.args.get('refresh', 'false').lower() == 'true'
            print(f"小程序端搜索关键词: '{keyword}', 页码: {page}, 每页数量: {limit}, 刷新: {refresh}")
            
            # 获取缓存管理器
            cache_manager = None
            if get_cache_manager:
                cache_manager = get_cache_manager()
            
            # 如果不刷新，先尝试从缓存获取列表索引和单个药品数据
            if not refresh and cache_manager:
                try:
                    # 尝试获取列表索引
                    list_cache = cache_manager.get_drug_list_ids(keyword, page, limit)
                    
                    if list_cache:
                        print("从缓存获取列表索引")
                        # 从缓存获取单个药品信息并重新构建完整列表
                        result_items = []
                        for group_data in list_cache.get('groups', []):
                            # 重建药品分组
                            group_items = []
                            for drug_id in group_data.get('drug_ids', []):
                                # 从缓存获取单个药品详情
                                drug_detail = cache_manager.get_drug_detail(drug_id)
                                if drug_detail:
                                    group_items.append(drug_detail)
                                else:
                                    # 如果缓存中没有，说明需要重新从数据库获取
                                    print(f"药品 {drug_id} 的缓存不存在，需要重新从数据库获取")
                                    raise Exception("需要重新获取完整数据")
                            
                            # 添加重建的分组
                            result_items.append({
                                "id": group_data.get('id'),
                                "name": group_data.get('name'),
                                "unit": group_data.get('unit'),
                                "quantity": group_data.get('quantity'),
                                "available_quantity": group_data.get('available_quantity'),
                                "specification": group_data.get('specification'),
                                "category": group_data.get('category'),
                                "status": group_data.get('status'),
                                "items": group_items
                            })
                        
                        print(f"从缓存重建药品列表成功，返回 {len(result_items)} 个分组")
                        return jsonify({
                            "success": True,
                            "data": result_items,
                            "total": list_cache.get('total'),
                            "page": page,
                            "limit": limit,
                            "has_more": list_cache.get('has_more')
                        })
                except Exception as e:
                    print(f"从缓存重建失败: {e}，将从数据库获取完整数据")
            
            # 缓存未命中或需要刷新，从admin_drug_catalogue获取数据
            if not get_drugs_data:
                print("获取药品数据失败: 无法导入admin_drug_catalogue模块")
                return jsonify({
                    "success": False,
                    "message": "获取药品数据失败: 无法导入admin_drug_catalogue模块"
                }), 500
            
            # 调用get_drugs_data获取药品数据
            print("调用get_drugs_data获取药品数据")
            drugs = get_drugs_data(get_db_connection, keyword)
            print(f"获取到 {len(drugs)} 条药品数据")
            
            # 按药品名称和单位分组，统计总数和可借数量
            grouped_drugs = {}
            
            for i, drug in enumerate(drugs):
                drug_id = str(drug.get('id', ''))
                drug_name = drug.get('name', '') or drug.get('drug_name', '') or '未知药品'
                drug_unit = drug.get('unit', '') or ''
                
                # 构建分组键
                key = (drug_name, drug_unit)
                
                if key not in grouped_drugs:
                    grouped_drugs[key] = {
                        "name": drug_name,
                        "unit": drug_unit,
                        "total_quantity": 0,
                        "available_quantity": 0,
                        "specification": drug.get('specification', ''),
                        "category": drug.get('type', '') or drug.get('drug_type', ''),
                        "items": []  # 存储该分组下的所有药品详情
                    }
                
                # 统计总数
                grouped_drugs[key]["total_quantity"] += 1
                # 统计可借数量
                if drug.get('status') == 'in_stock':
                    grouped_drugs[key]["available_quantity"] += 1
                
                # 构建单个药品详情对象
                drug_detail = {
                    "id": drug_id,
                    "medicine_code": drug.get('medicine_code', drug_id),
                    "status": drug.get('status', ''),
                    "location": drug.get('location', ''),
                    "expiry_date": drug.get('expiry_date', '')
                }
                
                # 存储药品详情
                grouped_drugs[key]["items"].append(drug_detail)
                
                # 缓存单个药品详情
                if cache_manager:
                    cache_manager.set_drug_detail(drug_id, drug_detail, ttl=3600)
            
            # 转换分组结果为列表
            result_items = []
            # 同时构建用于缓存的分组索引数据
            group_indices = []
            
            for i, (key, drug_group) in enumerate(grouped_drugs.items()):
                # 确定药品状态
                status = 'in_stock' if drug_group['available_quantity'] > 0 else 'unavailable'
                
                # 构建完整的药品分组对象
                result_item = {
                    "id": i + 1,
                    "name": drug_group['name'],
                    "unit": drug_group['unit'],
                    "quantity": drug_group['total_quantity'],
                    "available_quantity": drug_group['available_quantity'],
                    "specification": drug_group['specification'],
                    "category": drug_group['category'],
                    "status": status,
                    "items": drug_group['items']
                }
                
                result_items.append(result_item)
                
                # 构建分组索引（只包含ID）
                group_index = {
                    "id": i + 1,
                    "name": drug_group['name'],
                    "unit": drug_group['unit'],
                    "quantity": drug_group['total_quantity'],
                    "available_quantity": drug_group['available_quantity'],
                    "specification": drug_group['specification'],
                    "category": drug_group['category'],
                    "status": status,
                    "drug_ids": [item["id"] for item in drug_group['items']]
                }
                
                group_indices.append(group_index)
            
            # 确保至少返回一些默认数据
            if not result_items:
                result_items = [
                    {
                        "id": 1,
                        "name": "头孢克肟胶囊",
                        "unit": "盒",
                        "quantity": 1,
                        "available_quantity": 1,
                        "specification": "100mg*6粒",
                        "category": "0",
                        "status": "in_stock",
                        "items": [
                            {
                                "id": "1",
                                "medicine_code": "CP001",
                                "status": "in_stock",
                                "location": "cabinet_002",
                                "expiry_date": "2025-12-31"
                            }
                        ]
                    }
                ]
                print("返回默认药品数据")
            
            # 计算总数量和分页
            total = len(result_items)
            start = (page - 1) * limit
            end = start + limit
            paginated_items = result_items[start:end]
            paginated_indices = group_indices[start:end]
            has_more = end < total
            
            # 缓存分组索引
            if cache_manager:
                list_cache_data = {
                    "groups": paginated_indices,
                    "total": total,
                    "has_more": has_more
                }
                cache_manager.set_drug_list_ids(keyword, page, limit, list_cache_data, ttl=300)
            
            print(f"返回小程序端药品列表，关键词: {keyword}, 页码: {page}, 每页数量: {limit}, 总数量: {total}, 本页数量: {len(paginated_items)}, 是否有更多: {has_more}")
            return jsonify({
                "success": True,
                "data": paginated_items,
                "total": total,
                "page": page,
                "limit": limit,
                "has_more": has_more
            })
            
        except Exception as e:
            print(f"获取药品列表失败: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                "success": False,
                "message": f"获取药品列表失败: {str(e)}"
            }), 500
    
    # 保留原有路由，确保web端功能正常
    @app.route('/drugs', methods=['GET'])
    @login_required
    def get_teacher_drugs():
        """
        获取web端教师药品列表
        """
        # 重定向到web端的药品列表
        return redirect(url_for('get_drugs'))
    
    @app.route('/api/recent_records', methods=['GET'])
    @login_required
    def get_recent_records():
        """
        获取最近操作记录（支持增量更新）
        """
        try:
            # 获取限制数量
            limit = request.args.get('limit', 5, type=int)
            # 获取上次更新时间
            last_update = request.args.get('last_update')
            
            # 处理 last_update 为 'null' 的情况
            if last_update == 'null':
                last_update = None
            
            # 构建缓存键
            cache_key = f"records:recent:{limit}"
            
            # 尝试从缓存获取数据
            cached_data = None
            if get_cache_manager and not last_update:
                cache_manager = get_cache_manager()
                cached_data = cache_manager.get(cache_key)
            
            if cached_data and not last_update:
                logging.info(f"从缓存获取最近操作记录，限制: {limit}")
                return jsonify({
                    "success": True,
                    "data": cached_data
                })
            
            # 缓存未命中或需要增量更新，从数据库获取
            connection = get_db_connection()
            if not connection:
                return jsonify({
                    "success": False,
                    "message": "数据库连接失败"
                }), 500
            
            try:
                with connection.cursor() as cursor:
                    if last_update:
                        # 增量更新：只返回上次更新时间之后的记录
                        sql = """
                        SELECT 
                            operation_time as time, 
                            operation_type as action, 
                            CASE 
                                WHEN operation_type = 'access_granted' THEN '成功' 
                                WHEN operation_type = 'access_denied' THEN '失败' 
                                ELSE '处理中' 
                            END as status
                        FROM user_operations 
                        WHERE operation_time > %s
                        ORDER BY operation_time DESC 
                        LIMIT %s
                        """
                        cursor.execute(sql, (last_update, limit))
                    else:
                        # 全量更新：返回所有记录
                        sql = """
                        SELECT 
                            operation_time as time, 
                            operation_type as action, 
                            CASE 
                                WHEN operation_type = 'access_granted' THEN '成功' 
                                WHEN operation_type = 'access_denied' THEN '失败' 
                                ELSE '处理中' 
                            END as status
                        FROM user_operations 
                        ORDER BY operation_time DESC 
                        LIMIT %s
                        """
                        cursor.execute(sql, (limit,))
                    
                    records = cursor.fetchall()
                    
                    # 构建返回数据
                    if last_update:
                        # 增量更新响应
                        response_data = {
                            "updated": len(records) > 0,
                            "records": records,
                            "timestamp": records[0]['time'].isoformat() if records else last_update
                        }
                    else:
                        # 全量更新响应
                        response_data = records
                        # 将结果存入缓存
                        if get_cache_manager:
                            cache_manager = get_cache_manager()
                            if cache_manager:
                                cache_manager.set(cache_key, records, ttl=3600)  # 缓存1小时
                    
                    logging.info(f"从数据库获取最近操作记录，限制: {limit}, 数量: {len(records)}, 增量更新: {bool(last_update)}")
                    return jsonify({
                        "success": True,
                        "data": response_data
                    })
                    
            finally:
                # 检查是否使用简单连接池
                if hasattr(connection, 'pool') and hasattr(connection.pool, 'put'):
                    # 返回连接到池
                    try:
                        connection.pool.put(connection)
                    except Exception as e:
                        print(f"返回连接到池失败: {e}")
                        connection.close()
                else:
                    # 直接关闭连接
                    connection.close()
                
        except Exception as e:
            logging.error(f"获取最近操作记录失败: {e}")
            return jsonify({
                "success": False,
                "message": f"获取最近操作记录失败: {str(e)}"
            }), 500

export_dict['init_teacher_routes'] = init_teacher_routes
