from flask import request, jsonify, render_template
from datetime import datetime, date

# 药品目录相关功能

def init_drug_catalogue_routes(app, login_required, get_db_connection):
    # 从admin_dashboard导入menu_items和add_url_to_menu_items
    from admin_dashboard import menu_items, add_url_to_menu_items
    
    # 药品类型映射常量
    DRUG_TYPE_MAP = {
        0: '普通药品',
        1: '管制药品', 
        2: '危化品'
    }
    
    # 存储条件映射常量
    STORAGE_CONDITION_MAP = {
        0: '室温保存',
        1: '2-8°C保存',
        2: '-20°C保存',
        3: '-80°C保存',
        4: '避光保存',
        5: '干燥保存',
        6: '其他'
    }
    
    # 状态映射常量
    STATUS_MAP = {
        'in_stock': '库存中',
        'lent_out': '已借出',
        'discarded': '已废弃',
        'reserved': '已预定'
    }
    
    # 为药品数据添加显示信息的辅助函数
    def enhance_drug_data(drug):
        """为药品数据添加显示字段"""
        if drug:
            # 处理type字段 - 从数据库获取的type是字符串，需要转换为数字
            drug_type = drug.get('drug_type', '')
            if drug_type in ['0', '1', '2']:
                drug['type_name'] = DRUG_TYPE_MAP.get(int(drug_type), '未知')
            else:
                drug['type_name'] = '未知'
            drug['storage_name'] = STORAGE_CONDITION_MAP.get(drug.get('storage_condition', 0), '未知')
            drug['status_name'] = STATUS_MAP.get(drug.get('status', 0), '未知')
        return drug
    
    # 药品目录页面路由
    @app.route('/admin_drug_catalogue.html')
    @login_required
    def admin_drug_catalogue():
        # 使用辅助函数为菜单项添加URL
        menu_items_with_urls = add_url_to_menu_items(menu_items)
        return render_template('admin_drug_catalogue.html', 
                              menu_items=menu_items_with_urls, 
                              active_menu='drug-catalog')
    
    # 获取药品列表的API端点
    @app.route('/api/drugs')
    @login_required
    def get_drugs():
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 查询药品数据 - 使用实际的表名 web_medicine_list
                sql = "SELECT id, medicine_code, name as drug_name, type as drug_type, specification, manufacturer, batch_number, production_date, expiry_date, storage_condition, status, current_holder_id, location, unit, last_operation_time FROM web_medicine_list"
                cursor.execute(sql)
                drugs = cursor.fetchall()
                
                # 使用辅助函数处理显示名称
                for drug in drugs:
                    enhance_drug_data(drug)
                    
                    # 计算有效期状态 - 根据expiry_date字段和当前日期比较
                    expiry_date = drug.get('expiry_date')
                    if expiry_date:
                        try:
                            # 处理不同类型的日期数据
                            if isinstance(expiry_date, str):
                                # 尝试解析不同格式的日期字符串
                                try:
                                    expiry_date = datetime.strptime(expiry_date, '%Y/%m/%d')
                                except:
                                    try:
                                        expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d')
                                    except:
                                        expiry_date = datetime.strptime(expiry_date, '%Y%m%d')
                            elif isinstance(expiry_date, datetime):
                                # 如果已经是datetime对象，直接使用
                                expiry_date = expiry_date
                            elif isinstance(expiry_date, date):
                                # 如果是date对象，转换为datetime
                                expiry_date = datetime.combine(expiry_date, datetime.min.time())
                            
                            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                            if isinstance(expiry_date, datetime):
                                expiry_date = expiry_date.replace(hour=0, minute=0, second=0, microsecond=0)
                            days_remaining = (expiry_date - today).days
                            drug['days_remaining'] = days_remaining
                            
                            # 根据新的状态分类标准设置有效期状态
                            if days_remaining < 0:
                                drug['expiry_status'] = '过期'
                                drug['expiry_status_class'] = 'expired'
                                drug['expiry_status_icon'] = '⚫'
                            elif days_remaining <= 7:
                                drug['expiry_status'] = '临界'
                                drug['expiry_status_class'] = 'critical'
                                drug['expiry_status_icon'] = '🔴'
                            elif days_remaining <= 30:
                                drug['expiry_status'] = '紧急'
                                drug['expiry_status_class'] = 'urgent'
                                drug['expiry_status_icon'] = '🟠'
                            elif days_remaining <= 90:
                                drug['expiry_status'] = '预警'
                                drug['expiry_status_class'] = 'warning'
                                drug['expiry_status_icon'] = '🟡'
                            else:
                                drug['expiry_status'] = '正常'
                                drug['expiry_status_class'] = 'normal'
                                drug['expiry_status_icon'] = '✅'
                        except Exception as e:
                            print(f"日期解析错误: {e}, 日期值: {expiry_date}")
                            drug['days_remaining'] = 0
                            drug['expiry_status'] = '未知'
                            drug['expiry_status_class'] = 'secondary'
                            drug['expiry_status_icon'] = '❓'
                    else:
                        drug['days_remaining'] = 0
                        drug['expiry_status'] = '未知'
                        drug['expiry_status_class'] = 'secondary'
                        drug['expiry_status_icon'] = '❓'
                
                return jsonify({'success': True, 'data': drugs})
        except Exception as e:
            print(f"获取药品列表错误: {str(e)}")
            return jsonify({'success': False, 'message': '获取药品列表失败'})
        finally:
            if conn:
                conn.close()

    # 获取单个药品详情的API端点
    @app.route('/api/drugs/<int:drug_id>', methods=['GET'])
    @login_required
    def get_drug(drug_id):
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 查询药品数据，包括所有字段信息
                sql = "SELECT * FROM web_medicine_list WHERE id = %s"
                cursor.execute(sql, (drug_id,))
                drug = cursor.fetchone()
                
                if not drug:
                    return jsonify({'success': False, 'message': '药品不存在'})
                
                # 重命名字段以保持一致性
                if drug:
                    drug['drug_name'] = drug.get('name', '')
                    drug['drug_type'] = drug.get('type', '')
                
                # 使用辅助函数处理显示名称
                enhance_drug_data(drug)
                
                return jsonify({'success': True, 'data': drug})
        except Exception as e:
            print(f"获取药品详情错误: {str(e)}")
            return jsonify({'success': False, 'message': '获取药品详情失败'})
        finally:
            if conn:
                conn.close()

    # 删除药品的API端点
    @app.route('/api/drugs/<int:drug_id>', methods=['DELETE'])
    @login_required
    def delete_drug(drug_id):
        conn = None
        try:
            conn = get_db_connection()
            
            with conn.cursor() as cursor:
                # 检查药品是否存在
                cursor.execute("SELECT id FROM web_medicine_list WHERE id = %s", (drug_id,))
                if not cursor.fetchone():
                    return jsonify({'success': False, 'message': '药品不存在'})
                
                # 执行删除操作
                cursor.execute("DELETE FROM web_medicine_list WHERE id = %s", (drug_id,))
                conn.commit()
                
                return jsonify({'success': True, 'message': '药品删除成功'})
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"删除药品时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                conn.close()

    # 更新药品信息的API端点
    @app.route('/api/drugs/<int:drug_id>', methods=['PUT'])
    @login_required
    def update_drug(drug_id):
        conn = None
        try:
            conn = get_db_connection()
            data = request.json
            
            # 准备更新字段
            update_fields = []
            update_values = []
            
            with conn.cursor() as cursor:
                # 检查药品编码是否已被其他药品使用
                if 'medicine_code' in data:
                    cursor.execute("SELECT id FROM web_medicine_list WHERE medicine_code = %s AND id != %s", 
                                  (data['medicine_code'], drug_id))
                    if cursor.fetchone():
                        return jsonify({'success': False, 'message': '药品编码已存在'})
                
                # 检查药品是否存在
                cursor.execute("SELECT id FROM web_medicine_list WHERE id = %s", (drug_id,))
                if not cursor.fetchone():
                    return jsonify({'success': False, 'message': '药品不存在'})
            
            # 检查并添加需要更新的字段 - 使用实际的字段名
            updateable_fields = ['name', 'medicine_code', 'type', 'specification', 
                               'manufacturer', 'batch_number', 'production_date', 'expiry_date',
                               'storage_condition', 'status', 'current_holder_id', 'location', 'unit']
            
            # 当状态设置为库存中时，自动将current_holder_id设为null
            status = data.get('status')
            if status == 'in_stock':
                data['current_holder_id'] = None
            
            for field in updateable_fields:
                if field in data:
                    update_fields.append(f'{field} = %s')
                    update_values.append(data[field])
            
            # 添加最后操作时间
            update_fields.append('last_operation_time = NOW()')
            
            if not update_fields:
                return jsonify({'success': False, 'message': '没有需要更新的字段'})
            
            # 构建SQL语句
            update_values.append(drug_id)
            sql = f"UPDATE web_medicine_list SET {', '.join(update_fields)} WHERE id = %s"
            
            with conn.cursor() as cursor:
                # 执行更新
                cursor.execute(sql, update_values)
                conn.commit()
                
                # 获取更新后的药品信息
                cursor.execute("SELECT * FROM web_medicine_list WHERE id = %s", (drug_id,))
                drug = cursor.fetchone()
                
                if drug:
                    # 重命名字段以保持一致性
                    drug['drug_name'] = drug.get('name', '')
                    drug['drug_type'] = drug.get('type', '')
                    
                    # 使用辅助函数处理显示名称
                    enhance_drug_data(drug)
                    return jsonify({'success': True, 'data': drug, 'message': '药品信息更新成功'})
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"更新药品时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                conn.close()

    # 新增药品的API端点
    @app.route('/api/drugs', methods=['POST'])
    @login_required
    def add_drug():
        conn = None
        try:
            conn = get_db_connection()
            data = request.json
            
            with conn.cursor() as cursor:
                # 检查药品编码是否已存在
                if 'medicine_code' in data:
                    cursor.execute("SELECT id FROM web_medicine_list WHERE medicine_code = %s", 
                                  (data['medicine_code'],))
                    if cursor.fetchone():
                        return jsonify({'success': False, 'message': '药品编码已存在'})
                
                # 构建插入SQL语句 - 使用实际的字段名
                insert_fields = ['medicine_code', 'name', 'type', 'specification', 
                               'manufacturer', 'batch_number', 'production_date', 'expiry_date',
                               'storage_condition', 'status', 'current_holder_id', 'location', 'unit']
                
                # 检查哪些字段有值
                available_fields = []
                values = []
                placeholders = []
                
                for field in insert_fields:
                    if field in data:
                        available_fields.append(field)
                        values.append(data[field])
                        placeholders.append('%s')
                
                if not available_fields:
                    return jsonify({'success': False, 'message': '没有提供有效字段'})
                
                # 添加创建和最后操作时间
                available_fields.extend(['created_at', 'last_operation_time'])
                values.extend([datetime.now(), datetime.now()])
                placeholders.extend(['%s', '%s'])
                
                # 执行插入
                sql = f"INSERT INTO web_medicine_list ({', '.join(available_fields)}) VALUES ({', '.join(placeholders)})"
                cursor.execute(sql, values)
                conn.commit()
                
                # 获取插入的药品信息
                drug_id = cursor.lastrowid
                cursor.execute("SELECT * FROM web_medicine_list WHERE id = %s", (drug_id,))
                drug = cursor.fetchone()
                
                if drug:
                    # 重命名字段以保持一致性
                    drug['drug_name'] = drug.get('name', '')
                    drug['drug_type'] = drug.get('type', '')
                    
                    # 使用辅助函数处理显示名称
                    enhance_drug_data(drug)
                    return jsonify({'success': True, 'data': drug, 'message': '药品添加成功'})
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"添加药品时出错: {e}")
            return jsonify({'success': False, 'message': '服务器内部错误'})
        finally:
            if conn:
                conn.close()

    # 搜索药品的API端点
    @app.route('/api/drugs/search', methods=['GET'])
    @login_required
    def search_drugs():
        conn = None
        try:
            # 获取查询参数
            search_term = request.args.get('q', '').strip()
            drug_type = request.args.get('type', '').strip()
            status = request.args.get('status', '').strip()
            
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 构建查询条件
                where_conditions = []
                params = []
                
                # 搜索条件 - 使用实际的字段名
                if search_term:
                    where_conditions.append("(name LIKE %s OR medicine_code LIKE %s OR manufacturer LIKE %s)")
                    search_pattern = f"%{search_term}%"
                    params.extend([search_pattern, search_pattern, search_pattern])
                
                # 药品类型筛选
                if drug_type:
                    where_conditions.append("type = %s")
                    params.append(drug_type)
                
                # 状态筛选
                if status:
                    where_conditions.append("status = %s")
                    params.append(status)
                
                # 构建SQL语句 - 使用实际的表名和字段名
                sql = "SELECT id, medicine_code, name as drug_name, type as drug_type, specification, manufacturer, batch_number, production_date, expiry_date, storage_condition, status, current_holder_id, location, unit, last_operation_time FROM web_medicine_list"
                
                if where_conditions:
                    sql += " WHERE " + " AND ".join(where_conditions)
                
                sql += " ORDER BY id DESC"
                
                cursor.execute(sql, params)
                drugs = cursor.fetchall()
                
                # 使用辅助函数处理显示名称
                for drug in drugs:
                    enhance_drug_data(drug)
                
                return jsonify({'success': True, 'data': drugs})
        except Exception as e:
            print(f"搜索药品错误: {str(e)}")
            return jsonify({'success': False, 'message': '搜索失败'})
        finally:
            if conn:
                conn.close()

# 从web_medicine_list表获取药品数据（内部函数，供其他模块调用）
def get_drugs_data(get_db_connection, keyword=None):
    """
    从数据库获取药品数据
    
    Args:
        get_db_connection (function): 获取数据库连接的函数
        keyword (str): 搜索关键词（可选）
        
    Returns:
        list: 药品数据列表
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 构建查询条件
            where_conditions = []
            params = []
            
            # 搜索条件
            if keyword and keyword.strip():
                where_conditions.append("name LIKE %s")
                params.append(f"%{keyword.strip()}%")
                print(f"搜索关键词: '{keyword.strip()}'")  # 调试信息
            else:
                print("无搜索关键词，返回所有药品")  # 调试信息
            
            # 构建SQL语句
            sql = "SELECT id, medicine_code, name, type, specification, manufacturer, batch_number, production_date, expiry_date, storage_condition, status, current_holder_id, location, unit, last_operation_time FROM web_medicine_list"
            
            if where_conditions:
                sql += " WHERE " + " AND ".join(where_conditions)
                print(f"执行SQL: {sql}")  # 调试信息
                print(f"参数: {params}")  # 调试信息
            else:
                print("执行SQL: 返回所有药品")  # 调试信息
            
            sql += " ORDER BY name ASC"
            
            cursor.execute(sql, params)
            drugs = cursor.fetchall()
            print(f"查询到 {len(drugs)} 条药品数据")  # 调试信息
            return drugs
    except Exception as e:
        print(f"获取药品数据错误: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

# 直接导出需要在main.py中使用的函数
export_dict = {
    'init_drug_catalogue_routes': init_drug_catalogue_routes,
    'get_drugs_data': get_drugs_data
}