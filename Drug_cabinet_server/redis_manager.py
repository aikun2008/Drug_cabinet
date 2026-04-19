import redis
import json
import logging
from datetime import datetime, date
from functools import wraps
from config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB, REDIS_DEFAULT_TTL

class RedisCacheManager:
    """Redis缓存管理器"""
    
    def __init__(self, host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, 
                 password=REDIS_PASSWORD, default_ttl=REDIS_DEFAULT_TTL, 
                 key_prefix='drug_cabinet:'):
        """
        初始化Redis缓存管理器
        
        Args:
            host (str): Redis服务器主机地址
            port (int): Redis服务器端口
            db (int): Redis数据库索引
            password (str): Redis密码（可选）
            default_ttl (int): 默认过期时间（秒）
            key_prefix (str): 键前缀，用于避免键名冲突
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self.redis_client = None
        self.is_available = False
        self._connect()
    
    def _connect(self):
        """连接Redis服务器"""
        try:
            self.redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=False,  # 不自动解码，我们在序列化/反序列化时处理
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            # 测试连接
            self.redis_client.ping()
            self.is_available = True
            logging.info("Redis连接成功")
        except Exception as e:
            self.is_available = False
            logging.error(f"Redis连接失败: {e}")
    
    def _get_key(self, key):
        """获取带前缀的键名"""
        return f"{self.key_prefix}{key}"
    
    def _serialize(self, data):
        """序列化数据为字节串"""
        try:
            # 定义一个自定义的JSON编码器，用于处理datetime类型
            class DateTimeEncoder(json.JSONEncoder):
                def default(self, obj):
                    if isinstance(obj, (datetime, date)):
                        return obj.isoformat()
                    return super().default(obj)
            return json.dumps(data, ensure_ascii=False, cls=DateTimeEncoder).encode('utf-8')
        except Exception as e:
            logging.error(f"数据序列化失败: {e}")
            raise
    
    def _deserialize(self, data):
        """从字节串反序列化数据"""
        try:
            if data is None:
                return None
            return json.loads(data.decode('utf-8'))
        except Exception as e:
            logging.error(f"数据反序列化失败: {e}")
            return None
    
    def set(self, key, value, ttl=None):
        """
        设置缓存值
        
        Args:
            key (str): 缓存键
            value (any): 缓存值
            ttl (int): 过期时间（秒），默认使用default_ttl
            
        Returns:
            bool: 是否设置成功
        """
        if not self.is_available:
            return False
        
        try:
            serialized_value = self._serialize(value)
            actual_ttl = ttl if ttl is not None else self.default_ttl
            result = self.redis_client.setex(
                self._get_key(key), 
                actual_ttl, 
                serialized_value
            )
            return result
        except Exception as e:
            logging.error(f"设置缓存失败: {e}")
            return False
    
    def get(self, key):
        """
        获取缓存值
        
        Args:
            key (str): 缓存键
            
        Returns:
            any: 缓存值，不存在或过期返回None
        """
        if not self.is_available:
            return None
        
        try:
            serialized_value = self.redis_client.get(self._get_key(key))
            return self._deserialize(serialized_value)
        except Exception as e:
            logging.error(f"获取缓存失败: {e}")
            return None
    
    def delete(self, key):
        """
        删除缓存
        
        Args:
            key (str): 缓存键
            
        Returns:
            int: 删除的键数量
        """
        if not self.is_available:
            return 0
        
        try:
            return self.redis_client.delete(self._get_key(key))
        except Exception as e:
            logging.error(f"删除缓存失败: {e}")
            return 0
    
    def exists(self, key):
        """
        检查缓存键是否存在
        
        Args:
            key (str): 缓存键
            
        Returns:
            bool: 键是否存在
        """
        if not self.is_available:
            return False
        
        try:
            return bool(self.redis_client.exists(self._get_key(key)))
        except Exception as e:
            logging.error(f"检查缓存键存在性失败: {e}")
            return False
    
    def expire(self, key, ttl):
        """
        设置缓存过期时间
        
        Args:
            key (str): 缓存键
            ttl (int): 过期时间（秒）
            
        Returns:
            bool: 是否设置成功
        """
        if not self.is_available:
            return False
        
        try:
            return bool(self.redis_client.expire(self._get_key(key), ttl))
        except Exception as e:
            logging.error(f"设置缓存过期时间失败: {e}")
            return False
    
    def delete_by_pattern(self, pattern):
        """
        根据模式删除缓存键
        
        Args:
            pattern (str): 键模式，支持通配符 *
            
        Returns:
            int: 删除的键数量
        """
        if not self.is_available:
            return 0
        
        try:
            # 构建完整的键模式（包含前缀）
            full_pattern = f"{self.key_prefix}{pattern}"
            # 获取所有匹配的键
            keys = self.redis_client.keys(full_pattern)
            if keys:
                # 删除所有匹配的键
                deleted_count = self.redis_client.delete(*keys)
                logging.info(f"删除了 {deleted_count} 个匹配模式 '{pattern}' 的缓存键")
                return deleted_count
            return 0
        except Exception as e:
            logging.error(f"根据模式删除缓存失败: {e}")
            return 0
    
    def set_drug_detail(self, drug_id, drug_data, ttl=3600):
        """
        缓存单个药品的详细信息
        
        Args:
            drug_id: 药品ID
            drug_data: 药品数据
            ttl: 过期时间（秒）
            
        Returns:
            bool: 是否设置成功
        """
        key = f"mini:drug:detail:{drug_id}"
        return self.set(key, drug_data, ttl)
    
    def get_drug_detail(self, drug_id):
        """
        获取单个药品的详细信息
        
        Args:
            drug_id: 药品ID
            
        Returns:
            药品数据，不存在返回None
        """
        key = f"mini:drug:detail:{drug_id}"
        return self.get(key)
    
    def delete_drug_detail(self, drug_id):
        """
        删除单个药品的详细信息缓存
        
        Args:
            drug_id: 药品ID
            
        Returns:
            int: 删除的键数量（0或1）
        """
        key = f"mini:drug:detail:{drug_id}"
        return self.delete(key)
    
    def set_drug_list_ids(self, keyword, page, limit, drug_ids, ttl=300):
        """
        缓存药品列表的药品ID索引
        
        Args:
            keyword: 搜索关键词
            page: 页码
            limit: 每页数量
            drug_ids: 药品ID列表
            ttl: 过期时间（秒）
            
        Returns:
            bool: 是否设置成功
        """
        key = f"mini:drugs:list:ids:v2:{keyword}:{page}:{limit}"
        return self.set(key, drug_ids, ttl)
    
    def get_drug_list_ids(self, keyword, page, limit):
        """
        获取药品列表的药品ID索引
        
        Args:
            keyword: 搜索关键词
            page: 页码
            limit: 每页数量
            
        Returns:
            药品ID列表，不存在返回None
        """
        key = f"mini:drugs:list:ids:v2:{keyword}:{page}:{limit}"
        return self.get(key)
    
    def delete_drug_list_ids(self):
        """
        删除所有药品列表ID索引缓存
        
        Returns:
            int: 删除的键数量
        """
        return self.delete_by_pattern("mini:drugs:list:ids:v2:*")
    
    def flush_all(self):
        """
        清空所有缓存（谨慎使用）
        
        Returns:
            bool: 是否清空成功
        """
        if not self.is_available:
            return False
        
        try:
            return bool(self.redis_client.flushdb())
        except Exception as e:
            logging.error(f"清空缓存失败: {e}")
            return False
    
    def info(self):
        """
        获取Redis服务器信息
        
        Returns:
            dict: Redis服务器信息
        """
        if not self.is_available:
            return {"status": "unavailable"}
        
        try:
            info = self.redis_client.info()
            return {
                "status": "available",
                "redis_version": info.get("redis_version"),
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "uptime": info.get("uptime_in_seconds")
            }
        except Exception as e:
            logging.error(f"获取Redis信息失败: {e}")
            return {"status": "error", "message": str(e)}

# 模拟缓存管理器（Redis不可用时的降级方案）
class MockCacheManager:
    """模拟缓存管理器，用于Redis不可用时的降级"""
    
    def __init__(self):
        self.data = {}
        self.is_available = True
    
    def set(self, key, value, ttl=None):
        self.data[key] = value
        return True
    
    def get(self, key):
        return self.data.get(key)
    
    def delete(self, key):
        return self.data.pop(key, None) is not None
    
    def exists(self, key):
        return key in self.data
    
    def expire(self, key, ttl):
        # 模拟实现中不实际处理过期
        return True
    
    def flush_all(self):
        self.data.clear()
        return True
    
    def info(self):
        return {
            "status": "mock",
            "message": "Using mock cache manager (Redis unavailable)"
        }

# 全局缓存管理器实例
cache_manager = None

def init_cache_manager(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, 
                      password=REDIS_PASSWORD, default_ttl=REDIS_DEFAULT_TTL):
    """
    初始化全局缓存管理器
    
    Args:
        host (str): Redis服务器主机地址
        port (int): Redis服务器端口
        db (int): Redis数据库索引
        password (str): Redis密码（可选）
        default_ttl (int): 默认过期时间（秒）
    """
    global cache_manager
    try:
        cache_manager = RedisCacheManager(
            host=host, port=port, db=db, 
            password=password, default_ttl=default_ttl
        )
        if not cache_manager.is_available:
            # Redis不可用时使用模拟缓存管理器
            cache_manager = MockCacheManager()
            logging.warning("Redis不可用，使用模拟缓存管理器")
    except Exception as e:
        # 初始化失败时使用模拟缓存管理器
        cache_manager = MockCacheManager()
        logging.error(f"Redis缓存管理器初始化失败: {e}")

def get_cache_manager():
    """
    获取全局缓存管理器实例
    
    Returns:
        RedisCacheManager or MockCacheManager: 缓存管理器实例
    """
    global cache_manager
    if cache_manager is None:
        init_cache_manager()
    return cache_manager