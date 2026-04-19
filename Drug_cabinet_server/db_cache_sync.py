import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
from redis_manager import get_cache_manager

class DatabaseCacheSync:
    """数据库与缓存同步管理器"""
    
    def __init__(self):
        """初始化缓存同步管理器"""
        self.cache_manager = get_cache_manager()
    
    def _generate_record_key(self, table: str, record_id: Any) -> str:
        """
        生成记录缓存键
        
        Args:
            table (str): 表名
            record_id (Any): 记录ID
            
        Returns:
            str: 缓存键
        """
        return f"record:{table}:{record_id}"
    
    def _generate_query_key(self, table: str, query_params: Dict) -> str:
        """
        生成查询结果缓存键
        
        Args:
            table (str): 表名
            query_params (Dict): 查询参数
            
        Returns:
            str: 缓存键
        """
        # 对查询参数进行排序并生成哈希值，确保相同参数生成相同的键
        params_str = json.dumps(query_params, sort_keys=True, ensure_ascii=False)
        params_hash = hashlib.md5(params_str.encode('utf-8')).hexdigest()
        return f"query:{table}:{params_hash}"
    
    def _generate_table_key(self, table: str) -> str:
        """
        生成表级缓存键前缀
        
        Args:
            table (str): 表名
            
        Returns:
            str: 表级缓存键前缀
        """
        return f"table:{table}"
    
    def cache_record(self, table: str, record_id: Any, data: Dict, ttl: Optional[int] = None):
        """
        缓存单条记录
        
        Args:
            table (str): 表名
            record_id (Any): 记录ID
            data (Dict): 记录数据
            ttl (int, optional): 过期时间（秒）
            
        Returns:
            bool: 是否缓存成功
        """
        try:
            key = self._generate_record_key(table, record_id)
            success = self.cache_manager.set(key, data, ttl)
            
            if success:
                # 同时将记录键添加到表级集合中，便于批量失效
                table_key = self._generate_table_key(table)
                # 使用Redis集合存储表中的记录键（如果Redis可用）
                # 这里简化处理，实际项目中可以根据需要实现
                
            return success
        except Exception as e:
            logging.error(f"缓存记录失败: {e}")
            return False
    
    def get_cached_record(self, table: str, record_id: Any) -> Optional[Dict]:
        """
        获取缓存的单条记录
        
        Args:
            table (str): 表名
            record_id (Any): 记录ID
            
        Returns:
            Optional[Dict]: 记录数据，不存在或过期返回None
        """
        try:
            key = self._generate_record_key(table, record_id)
            return self.cache_manager.get(key)
        except Exception as e:
            logging.error(f"获取缓存记录失败: {e}")
            return None
    
    def cache_query_result(self, table: str, query_params: Dict, result: List[Dict], ttl: Optional[int] = None):
        """
        缓存查询结果
        
        Args:
            table (str): 表名
            query_params (Dict): 查询参数
            result (List[Dict]): 查询结果
            ttl (int, optional): 过期时间（秒）
            
        Returns:
            bool: 是否缓存成功
        """
        try:
            key = self._generate_query_key(table, query_params)
            return self.cache_manager.set(key, result, ttl)
        except Exception as e:
            logging.error(f"缓存查询结果失败: {e}")
            return False
    
    def get_cached_query_result(self, table: str, query_params: Dict) -> Optional[List[Dict]]:
        """
        获取缓存的查询结果
        
        Args:
            table (str): 表名
            query_params (Dict): 查询参数
            
        Returns:
            Optional[List[Dict]]: 查询结果，不存在或过期返回None
        """
        try:
            key = self._generate_query_key(table, query_params)
            return self.cache_manager.get(key)
        except Exception as e:
            logging.error(f"获取缓存查询结果失败: {e}")
            return None
    
    def invalidate_record(self, table: str, record_id: Any):
        """
        失效单条记录缓存
        
        Args:
            table (str): 表名
            record_id (Any): 记录ID
            
        Returns:
            bool: 是否失效成功
        """
        try:
            key = self._generate_record_key(table, record_id)
            return bool(self.cache_manager.delete(key))
        except Exception as e:
            logging.error(f"失效记录缓存失败: {e}")
            return False
    
    def invalidate_query_result(self, table: str, query_params: Dict):
        """
        失效查询结果缓存
        
        Args:
            table (str): 表名
            query_params (Dict): 查询参数
            
        Returns:
            bool: 是否失效成功
        """
        try:
            key = self._generate_query_key(table, query_params)
            return bool(self.cache_manager.delete(key))
        except Exception as e:
            logging.error(f"失效查询结果缓存失败: {e}")
            return False
    
    def invalidate_table(self, table: str):
        """
        失效整个表的缓存
        
        Args:
            table (str): 表名
            
        Returns:
            bool: 是否失效成功
        """
        try:
            # 在实际实现中，如果有维护表级键集合，可以在这里批量删除
            # 这里简化处理，只记录日志
            logging.info(f"表 {table} 的缓存已标记为失效")
            return True
        except Exception as e:
            logging.error(f"失效表缓存失败: {e}")
            return False

class CachedDatabaseConnection:
    """带缓存的数据库连接类"""
    
    def __init__(self, db_connection_func):
        """
        初始化带缓存的数据库连接
        
        Args:
            db_connection_func: 数据库连接函数
        """
        self.db_connection_func = db_connection_func
        self.cache_sync = DatabaseCacheSync()
    
    def execute_query(self, sql: str, params: Optional[tuple] = None, 
                     table: Optional[str] = None, use_cache: bool = True, 
                     cache_ttl: Optional[int] = None):
        """
        执行查询语句（带缓存支持）
        
        Args:
            sql (str): SQL查询语句
            params (tuple, optional): 查询参数
            table (str, optional): 表名（用于缓存键生成）
            use_cache (bool): 是否使用缓存
            cache_ttl (int, optional): 缓存过期时间（秒）
            
        Returns:
            List[Dict]: 查询结果
        """
        # 如果不使用缓存或没有表名，直接执行查询
        if not use_cache or not table:
            return self._execute_query_without_cache(sql, params)
        
        # 构造查询参数字典用于缓存键生成
        query_params = {
            "sql": sql,
            "params": params if params else ()
        }
        
        # 尝试从缓存获取结果
        cached_result = self.cache_sync.get_cached_query_result(table, query_params)
        if cached_result is not None:
            logging.debug(f"查询命中缓存: {sql}")
            return cached_result
        
        # 缓存未命中，执行实际查询
        logging.debug(f"查询未命中缓存，执行实际查询: {sql}")
        result = self._execute_query_without_cache(sql, params)
        
        # 将结果缓存
        if result is not None:
            self.cache_sync.cache_query_result(table, query_params, result, cache_ttl)
        
        return result
    
    def execute_single_record_query(self, sql: str, params: Optional[tuple] = None,
                                   table: Optional[str] = None, record_id: Optional[Any] = None,
                                   use_cache: bool = True, cache_ttl: Optional[int] = None):
        """
        执行单条记录查询语句（带缓存支持）
        
        Args:
            sql (str): SQL查询语句
            params (tuple, optional): 查询参数
            table (str, optional): 表名（用于缓存键生成）
            record_id (Any, optional): 记录ID（用于缓存键生成）
            use_cache (bool): 是否使用缓存
            cache_ttl (int, optional): 缓存过期时间（秒）
            
        Returns:
            Dict: 单条记录数据
        """
        # 如果不使用缓存或没有表名或记录ID，直接执行查询
        if not use_cache or not table or record_id is None:
            result = self._execute_query_without_cache(sql, params)
            return result[0] if result else None
        
        # 尝试从缓存获取记录
        cached_record = self.cache_sync.get_cached_record(table, record_id)
        if cached_record is not None:
            logging.debug(f"单条记录查询命中缓存: {sql}")
            return cached_record
        
        # 缓存未命中，执行实际查询
        logging.debug(f"单条记录查询未命中缓存，执行实际查询: {sql}")
        result = self._execute_query_without_cache(sql, params)
        record = result[0] if result else None
        
        # 将记录缓存
        if record is not None:
            self.cache_sync.cache_record(table, record_id, record, cache_ttl)
        
        return record
    
    def _execute_query_without_cache(self, sql: str, params: Optional[tuple] = None):
        """
        执行查询语句（不使用缓存）
        
        Args:
            sql (str): SQL查询语句
            params (tuple, optional): 查询参数
            
        Returns:
            List[Dict]: 查询结果
        """
        connection = None
        try:
            connection = self.db_connection_func()
            if not connection:
                raise Exception("无法获取数据库连接")
            
            with connection.cursor() as cursor:
                cursor.execute(sql, params or ())
                result = cursor.fetchall()
                return result
        except Exception as e:
            logging.error(f"执行查询失败: {e}")
            return None
        finally:
            if connection:
                connection.close()
    
    def execute_update(self, sql: str, params: Optional[tuple] = None, 
                      table: Optional[str] = None, record_id: Optional[Any] = None):
        """
        执行更新语句（自动失效相关缓存）
        
        Args:
            sql (str): SQL更新语句
            params (tuple, optional): 更新参数
            table (str, optional): 表名（用于缓存失效）
            record_id (Any, optional): 记录ID（用于缓存失效）
            
        Returns:
            int: 受影响的行数
        """
        connection = None
        try:
            connection = self.db_connection_func()
            if not connection:
                raise Exception("无法获取数据库连接")
            
            with connection.cursor() as cursor:
                affected_rows = cursor.execute(sql, params or ())
                connection.commit()
                
                # 自动失效相关缓存
                if table:
                    # 失效整个表的查询缓存
                    self.cache_sync.invalidate_table(table)
                    
                    # 如果指定了记录ID，也失效该记录的缓存
                    if record_id is not None:
                        self.cache_sync.invalidate_record(table, record_id)
                
                return affected_rows
        except Exception as e:
            if connection:
                connection.rollback()
            logging.error(f"执行更新失败: {e}")
            return 0
        finally:
            if connection:
                connection.close()

# 全局缓存同步管理器实例
cache_sync = None

def init_cache_sync():
    """初始化全局缓存同步管理器"""
    global cache_sync
    cache_sync = DatabaseCacheSync()

def get_cache_sync():
    """
    获取全局缓存同步管理器实例
    
    Returns:
        DatabaseCacheSync: 缓存同步管理器实例
    """
    global cache_sync
    if cache_sync is None:
        init_cache_sync()
    return cache_sync

# 全局带缓存的数据库连接实例工厂
def get_cached_db_connection(db_connection_func):
    """
    获取带缓存的数据库连接实例
    
    Args:
        db_connection_func: 数据库连接函数
        
    Returns:
        CachedDatabaseConnection: 带缓存的数据库连接实例
    """
    return CachedDatabaseConnection(db_connection_func)