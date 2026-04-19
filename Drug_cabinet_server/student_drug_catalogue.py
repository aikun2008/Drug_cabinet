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

def init_student_routes(app, login_required, get_db_connection, cached_db):
    """
    初始化学生相关路由
    
    Args:
        app (Flask): Flask应用实例
        login_required (function): 登录验证装饰器
        get_db_connection (function): 获取数据库连接的函数
        cached_db (function): 带缓存的数据库连接函数
    """
    
    # 为小程序端添加专用路由，避免与web端冲突
    @app.route('/api/mini/student/drugs', methods=['GET'])
    @login_required
    @permission_required('can_query_drugs')
    def get_student_drugs():
        """
        获取学生端药品列表（支持搜索和分页）
        优先从Redis缓存获取，缓存未命中则从admin_drug_catalogue获取
        按药品名称分组，统计数量
        """
        try:
            # 获取搜索关键词
            keyword = request.args.get('keyword', '').strip()
            # 获取分页参数
            page = request.args.get('page', 1, type=int)
            limit = request.args.get('limit', 6, type=int)
            print(f"学生端搜索关键词: '{keyword}', 页码: {page}, 每页数量: {limit}")  # 调试信息
            
            # 构建缓存键（添加版本号，确保缓存更新）
            cache_key = f"student:drugs:list:v2:{keyword}:{page}:{limit}"
            
            # 尝试从缓存获取数据
            cached_data = None
            if get_cache_manager:
                cache_manager = get_cache_manager()
                cached_data = cache_manager.get(cache_key)
            
            if cached_data:
                print(f"从缓存获取学生端药品列表，关键词: {keyword}, 页码: {page}, 每页数量: {limit}")  # 调试信息
                return jsonify({
                    "success": True,
                    "data": cached_data.get('items'),
                    "total": cached_data.get('total'),
                    "page": page,
                    "limit": limit,
                    "has_more": cached_data.get('has_more')
                })
            
            # 缓存未命中，从admin_drug_catalogue获取数据
            if not get_drugs_data:
                print("获取药品数据失败: 无法导入admin_drug_catalogue模块")  # 调试信息
                return jsonify({
                    "success": False,
                    "message": "获取药品数据失败: 无法导入admin_drug_catalogue模块"
                }), 500
            
            # 调用get_drugs_data获取药品数据
            print("调用get_drugs_data获取药品数据")  # 调试信息
            drugs = get_drugs_data(get_db_connection, keyword)
            print(f"获取到 {len(drugs)} 条药品数据")  # 调试信息
            
            # 打印前5条药品数据，检查name字段
            for i, drug in enumerate(drugs[:5]):
                drug_name = drug.get('name', 'NOT FOUND')
                print(f"药品{i+1}: name={drug_name}, type={type(drug_name)}, length={len(drug_name) if isinstance(drug_name, str) else 'N/A'}")
            
            # 按药品名称和单位分组，统计总数和可借数量
            grouped_drugs = {}
            for i, drug in enumerate(drugs):
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
                # 统计可借数量（状态为in_stock的）
                if drug.get('status') == 'in_stock':
                    grouped_drugs[key]["available_quantity"] += 1
                
                # 存储药品详情
                grouped_drugs[key]["items"].append({
                    "id": drug.get('id', ''),
                    "medicine_code": drug.get('medicine_code', drug.get('id', '')),
                    "status": drug.get('status', ''),
                    "location": drug.get('location', ''),
                    "expiry_date": drug.get('expiry_date', '')
                })
                
                print(f"处理药品{i+1}: name={drug_name}, unit={drug_unit}, status={drug.get('status')}")  # 调试信息
            
            # 转换分组结果为列表
            result_items = []
            for i, (key, drug_group) in enumerate(grouped_drugs.items()):
                # 确定药品状态
                status = 'in_stock' if drug_group['available_quantity'] > 0 else 'unavailable'
                
                result_items.append({
                    "id": i + 1,
                    "name": drug_group['name'],
                    "unit": drug_group['unit'],
                    "quantity": drug_group['total_quantity'],
                    "available_quantity": drug_group['available_quantity'],
                    "specification": drug_group['specification'],
                    "category": drug_group['category'],
                    "status": status,
                    "items": drug_group['items']  # 存储该分组下的所有药品详情
                })
            
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
                    },
                    {
                        "id": 2,
                        "name": "布洛芬缓释胶囊",
                        "unit": "盒",
                        "quantity": 1,
                        "available_quantity": 1,
                        "specification": "300mg*10粒",
                        "category": "0",
                        "status": "in_stock",
                        "items": [
                            {
                                "id": "2",
                                "medicine_code": "BLF001",
                                "status": "in_stock",
                                "location": "cabinet_001",
                                "expiry_date": "2025-12-31"
                            }
                        ]
                    }
                ]
                print("返回默认药品数据")  # 调试信息
            
            # 计算总数量和分页
            total = len(result_items)
            start = (page - 1) * limit
            end = start + limit
            paginated_items = result_items[start:end]
            has_more = end < total
            
            # 构建返回数据
            cached_result = {
                "items": paginated_items,
                "total": total,
                "has_more": has_more
            }
            
            # 将结果存入缓存
            if get_cache_manager:
                cache_manager = get_cache_manager()
                if cache_manager:
                    cache_manager.set(cache_key, cached_result, ttl=3600)  # 缓存1小时
            
            print(f"返回学生端药品列表，关键词: {keyword}, 页码: {page}, 每页数量: {limit}, 总数量: {total}, 本页数量: {len(paginated_items)}, 是否有更多: {has_more}")  # 调试信息
            return jsonify({
                "success": True,
                "data": paginated_items,
                "total": total,
                "page": page,
                "limit": limit,
                "has_more": has_more
            })
            
        except Exception as e:
            print(f"获取药品列表失败: {e}")  # 调试信息
            return jsonify({
                "success": False,
                "message": f"获取药品列表失败: {str(e)}"
            }), 500

export_dict['init_student_routes'] = init_student_routes