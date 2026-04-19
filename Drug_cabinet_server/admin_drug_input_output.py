from flask import Blueprint, render_template, request, jsonify
import pandas as pd
from datetime import datetime
import os

# 导入Redis缓存管理器
try:
    from redis_manager import get_cache_manager
except Exception as e:
    print(f"导入Redis缓存管理器失败: {e}")
    get_cache_manager = None

admin_drug_input_output_bp = Blueprint('admin_drug_input_output', __name__)

@admin_drug_input_output_bp.route('/admin_drug_input_output.html', methods=['GET'])
def drug_input_output():
    return render_template('admin_drug_input_output.html')

@admin_drug_input_output_bp.route('/api/drugs/import/history', methods=['GET'])
def get_import_history():
    from main import get_db_connection
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'})
        
        cursor = conn.cursor()
        
        # 查询导入历史记录
        sql = """
            SELECT id, import_time, file_name, total_count, success_count, error_count, error_details
            FROM batch_import_record
            ORDER BY import_time DESC
            LIMIT 50
        """
        cursor.execute(sql)
        records = cursor.fetchall()
        
        # 处理错误详情，将JSON字符串转换为对象
        for record in records:
            if record.get('error_details'):
                try:
                    import json
                    record['error_details'] = json.loads(record['error_details'])
                except:
                    record['error_details'] = []
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': records
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取导入历史失败: {str(e)}'})

@admin_drug_input_output_bp.route('/api/drugs/locations', methods=['GET'])
def get_locations():
    from main import get_db_connection
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'})
        
        cursor = conn.cursor()
        
        # 查询所有药柜位置
        sql = """
            SELECT DISTINCT location
            FROM web_medicine_list
            WHERE location IS NOT NULL AND location != ''
            ORDER BY location
        """
        cursor.execute(sql)
        locations = [row['location'] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': locations
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取药柜列表失败: {str(e)}'})

@admin_drug_input_output_bp.route('/api/drugs/export', methods=['GET', 'POST'])
def export_drugs():
    from main import get_db_connection
    import json
    
    if request.method == 'GET':
        # 获取药品列表
        try:
            conn = get_db_connection()
            if not conn:
                return jsonify({'success': False, 'message': '数据库连接失败'})
            
            cursor = conn.cursor()
            
            # 获取查询参数
            location = request.args.get('location', '')
            expiry = request.args.get('expiry', '')
            
            # 构建SQL查询
            sql = """
                SELECT medicine_code, name, expiry_date
                FROM web_medicine_list
                WHERE status != 'lent_out'  -- 排除已借出的药品
            """
            params = []
            
            if location:
                sql += " AND location = %s"
                params.append(location)
            
            if expiry:
                from datetime import datetime, timedelta
                today = datetime.now().date()
                
                if expiry == 'expired':
                    sql += " AND expiry_date < %s"
                    params.append(today)
                elif expiry == 'expiring_30':
                    sql += " AND expiry_date BETWEEN %s AND %s"
                    params.append(today)
                    params.append(today + timedelta(days=30))
                elif expiry == 'expiring_60':
                    sql += " AND expiry_date BETWEEN %s AND %s"
                    params.append(today)
                    params.append(today + timedelta(days=60))
                elif expiry == 'expiring_90':
                    sql += " AND expiry_date BETWEEN %s AND %s"
                    params.append(today)
                    params.append(today + timedelta(days=90))
            
            sql += " ORDER BY expiry_date ASC"
            
            cursor.execute(sql, params)
            drugs = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'data': drugs
            })
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'获取药品列表失败: {str(e)}'})
    
    elif request.method == 'POST':
        # 批量出库
        try:
            conn = get_db_connection()
            if not conn:
                return jsonify({'success': False, 'message': '数据库连接失败'})
            
            cursor = conn.cursor()
            
            # 获取请求数据
            data = request.get_json()
            if not data or 'medicine_codes' not in data:
                return jsonify({'success': False, 'message': '缺少必要参数'})
            
            medicine_codes = data['medicine_codes']
            if not medicine_codes:
                return jsonify({'success': False, 'message': '请选择要出库的药品'})
            
            # 批量删除药品
            success_count = 0
            for code in medicine_codes:
                try:
                    sql = "DELETE FROM web_medicine_list WHERE medicine_code = %s AND status != 'lent_out'"
                    cursor.execute(sql, (code,))
                    if cursor.rowcount > 0:
                        success_count += 1
                except Exception as e:
                    print(f"删除药品 {code} 失败: {str(e)}")
                    continue
            
            conn.commit()
            cursor.close()
            conn.close()

            # 清除药品缓存，确保下次查询时获取最新数据
            if get_cache_manager:
                cache_manager = get_cache_manager()
                try:
                    # 清除药品列表缓存
                    cache_manager.delete_drug_list_ids()
                    print("批量出库后清除了药品列表缓存")
                except Exception as e:
                    print(f"清除缓存失败: {e}")

            return jsonify({
                'success': True,
                'message': f'出库成功，共出库 {success_count} 个药品',
                'success_count': success_count
            })
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'出库失败: {str(e)}'})

@admin_drug_input_output_bp.route('/api/drugs/import', methods=['POST'])
def import_drugs():
    from main import get_db_connection
    
    try:
        # 检查是否有文件上传
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '请选择要上传的文件'})
        
        file = request.files['file']
        
        # 检查文件是否为空
        if file.filename == '':
            return jsonify({'success': False, 'message': '请选择要上传的文件'})
        
        # 检查文件类型
        if not file.filename.endswith(('.xlsx', '.xls')):
            return jsonify({'success': False, 'message': '只支持 .xlsx 和 .xls 格式的文件'})
        
        # 保存文件到临时目录
        temp_dir = 'temp'
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        file_path = os.path.join(temp_dir, file.filename)
        file.save(file_path)
        
        # 读取Excel文件
        try:
            df = pd.read_excel(file_path)
        except Exception as e:
            os.remove(file_path)
            return jsonify({'success': False, 'message': f'文件读取失败: {str(e)}'})
        
        # 检查必填列
        required_columns = ['medicine_code', 'name']
        for col in required_columns:
            if col not in df.columns:
                os.remove(file_path)
                return jsonify({'success': False, 'message': f'文件缺少必填列: {col}'})
        
        # 连接数据库
        conn = get_db_connection()
        if not conn:
            os.remove(file_path)
            return jsonify({'success': False, 'message': '数据库连接失败'})
        
        cursor = conn.cursor()
        
        # 统计导入结果
        total = len(df)
        errors = []
        
        # 第一步：检查数据规范性和唯一性
        # 1. 检查文件中的medicine_code是否重复
        medicine_codes = []
        for index, row in df.iterrows():
            medicine_code = str(row.get('medicine_code', '')).strip()
            if medicine_code:
                if medicine_code in medicine_codes:
                    errors.append(f'第{index+2}行: 药品编码 {medicine_code} 与文件中其他记录重复')
                medicine_codes.append(medicine_code)
            else:
                errors.append(f'第{index+2}行: 药品编码为空')
            
            # 检查必填字段
            name = str(row.get('name', '')).strip()
            if not name:
                errors.append(f'第{index+2}行: 药品名称为空')
            
            # 检查药品类型
            drug_type = str(row.get('type', '0')).strip()
            if drug_type not in ['0', '1', '2']:
                errors.append(f'第{index+2}行: 药品类型必须是 0、1 或 2')
            
            # 检查日期格式
            production_date = row.get('production_date')
            if production_date:
                if isinstance(production_date, str):
                    try:
                        datetime.strptime(production_date, '%Y-%m-%d')
                    except:
                        errors.append(f'第{index+2}行: 生产日期格式错误，应为 YYYY-MM-DD')
            
            expiry_date = row.get('expiry_date')
            if expiry_date:
                if isinstance(expiry_date, str):
                    try:
                        datetime.strptime(expiry_date, '%Y-%m-%d')
                    except:
                        errors.append(f'第{index+2}行: 有效期格式错误，应为 YYYY-MM-DD')
        
        # 2. 检查medicine_code是否与数据库中已有的重复
        if medicine_codes:
            # 批量查询数据库中已存在的药品编码，减少数据库查询次数
            # 注意：IN语句有参数数量限制，这里假设药品编码数量不会超过限制
            # 如果数量很大，可以考虑分批查询
            placeholders = ','.join(['%s'] * len(medicine_codes))
            sql = f"SELECT medicine_code FROM web_medicine_list WHERE medicine_code IN ({placeholders})"
            cursor.execute(sql, medicine_codes)
            existing_codes = [row['medicine_code'] for row in cursor.fetchall()]
            
            # 在内存中比对，找出重复的编码
            for code in existing_codes:
                # 找到文件中对应的行
                for index, row in df.iterrows():
                    if str(row.get('medicine_code', '')).strip() == code:
                        errors.append(f'第{index+2}行: 药品编码 {code} 与数据库中已有的记录重复')
                        break
        
        # 如果有错误，返回错误信息
        if errors:
            # 记录批量导入操作到batch_import_record表
            import json
            error_details = json.dumps(errors) if errors else None
            
            try:
                # 插入导入记录
                insert_record_sql = """
                    INSERT INTO batch_import_record (
                        file_name, total_count, success_count, error_count, error_details
                    ) VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(insert_record_sql, (
                    file.filename, total, 0, len(errors), error_details
                ))
                conn.commit()
            except Exception as e:
                print(f"记录导入操作失败: {str(e)}")
                # 不影响主流程，继续执行
            
            cursor.close()
            conn.close()
            os.remove(file_path)
            return jsonify({
                'success': False,
                'message': f'数据验证失败，共 {len(errors)} 个错误',
                'errors': errors
            })
        
        # 第二步：导入数据
        success_count = 0
        try:
            for index, row in df.iterrows():
                # 提取数据
                medicine_code = str(row.get('medicine_code', '')).strip()
                name = str(row.get('name', '')).strip()
                
                # 其他字段
                drug_type = str(row.get('type', '0')).strip()
                specification = str(row.get('specification', '')).strip()
                manufacturer = str(row.get('manufacturer', '')).strip()
                batch_number = str(row.get('batch_number', '')).strip()
                
                # 处理日期字段
                production_date = row.get('production_date')
                if isinstance(production_date, str):
                    try:
                        production_date = datetime.strptime(production_date, '%Y-%m-%d').date()
                    except:
                        production_date = None
                
                expiry_date = row.get('expiry_date')
                if isinstance(expiry_date, str):
                    try:
                        expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                    except:
                        expiry_date = None
                
                storage_condition = str(row.get('storage_condition', '')).strip()
                location = str(row.get('location', '')).strip()
                unit = str(row.get('unit', '')).strip()
                
                # 插入数据
                sql = """
                    INSERT INTO web_medicine_list (
                        medicine_code, name, type, specification, manufacturer, 
                        batch_number, production_date, expiry_date, storage_condition, 
                        status, location, unit, last_operation_time
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, 'in_stock', %s, %s, NOW()
                    ) ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        type = VALUES(type),
                        specification = VALUES(specification),
                        manufacturer = VALUES(manufacturer),
                        batch_number = VALUES(batch_number),
                        production_date = VALUES(production_date),
                        expiry_date = VALUES(expiry_date),
                        storage_condition = VALUES(storage_condition),
                        status = 'in_stock',
                        location = VALUES(location),
                        unit = VALUES(unit),
                        last_operation_time = NOW()
                """
                
                cursor.execute(sql, (
                    medicine_code, name, drug_type, specification, manufacturer, 
                    batch_number, production_date, expiry_date, storage_condition, 
                    location, unit
                ))
                
                success_count += 1
                
        except Exception as e:
            conn.rollback()
            cursor.close()
            conn.close()
            os.remove(file_path)
            return jsonify({'success': False, 'message': f'导入过程中出错: {str(e)}'})
        
        # 记录批量导入操作到batch_import_record表
        import json
        error_details = json.dumps(errors) if errors else None
        
        try:
            # 插入导入记录
            insert_record_sql = """
                INSERT INTO batch_import_record (
                    file_name, total_count, success_count, error_count, error_details
                ) VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_record_sql, (
                file.filename, total, success_count, len(errors), error_details
            ))
            conn.commit()
        except Exception as e:
            print(f"记录导入操作失败: {str(e)}")
            # 不影响主流程，继续执行
        
        # 关闭连接
        cursor.close()
        conn.close()

        # 删除临时文件
        os.remove(file_path)

        # 清除药品缓存，确保下次查询时获取最新数据
        if get_cache_manager:
            cache_manager = get_cache_manager()
            try:
                # 清除药品列表缓存
                cache_manager.delete_drug_list_ids()
                print("批量导入后清除了药品列表缓存")
            except Exception as e:
                print(f"清除缓存失败: {e}")

        # 返回结果
        return jsonify({
            'success': True,
            'message': f'导入完成，成功: {success_count}, 失败: {len(errors)}',
            'total': total,
            'success_count': success_count,
            'error_count': len(errors),
            'errors': errors
        })
        
    except Exception as e:
        # 清理临时文件
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        
        return jsonify({'success': False, 'message': f'导入失败: {str(e)}'})
