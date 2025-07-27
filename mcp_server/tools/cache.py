"""
缓存相关的MCP工具
提供文件索引缓存、查询缓存等功能
"""

import logging
import os
import json
import pickle
import hashlib
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import threading

logger = logging.getLogger(__name__)


class CacheSetParams(BaseModel):
    """设置缓存参数"""
    key: str
    value: Any
    ttl: Optional[int] = None  # 生存时间（秒）
    category: Optional[str] = "default"


class CacheGetParams(BaseModel):
    """获取缓存参数"""
    key: str
    category: Optional[str] = "default"


class CacheDeleteParams(BaseModel):
    """删除缓存参数"""
    key: str
    category: Optional[str] = "default"


class CacheListParams(BaseModel):
    """列出缓存参数"""
    category: Optional[str] = None
    pattern: Optional[str] = None


class FileCacheParams(BaseModel):
    """文件缓存参数"""
    file_path: str
    cache_key: Optional[str] = None


class CacheStatsParams(BaseModel):
    """缓存统计参数"""
    category: Optional[str] = None


class MemoryCache:
    """内存缓存类"""
    
    def __init__(self):
        """初始化内存缓存"""
        self._cache = {}
        self._ttl_cache = {}
        self._lock = threading.RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0
        }
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, category: str = "default") -> bool:
        """设置缓存"""
        try:
            with self._lock:
                full_key = f"{category}:{key}"
                self._cache[full_key] = value
                
                if ttl:
                    expire_time = time.time() + ttl
                    self._ttl_cache[full_key] = expire_time
                elif full_key in self._ttl_cache:
                    del self._ttl_cache[full_key]
                
                self._stats["sets"] += 1
                return True
        except Exception as e:
            logger.error(f"设置缓存失败: {e}")
            return False
    
    def get(self, key: str, category: str = "default") -> Any:
        """获取缓存"""
        try:
            with self._lock:
                full_key = f"{category}:{key}"
                
                # 检查是否过期
                if full_key in self._ttl_cache:
                    if time.time() > self._ttl_cache[full_key]:
                        self._evict_key(full_key)
                        self._stats["misses"] += 1
                        return None
                
                if full_key in self._cache:
                    self._stats["hits"] += 1
                    return self._cache[full_key]
                else:
                    self._stats["misses"] += 1
                    return None
        except Exception as e:
            logger.error(f"获取缓存失败: {e}")
            self._stats["misses"] += 1
            return None
    
    def delete(self, key: str, category: str = "default") -> bool:
        """删除缓存"""
        try:
            with self._lock:
                full_key = f"{category}:{key}"
                deleted = False
                
                if full_key in self._cache:
                    del self._cache[full_key]
                    deleted = True
                
                if full_key in self._ttl_cache:
                    del self._ttl_cache[full_key]
                    deleted = True
                
                if deleted:
                    self._stats["deletes"] += 1
                
                return deleted
        except Exception as e:
            logger.error(f"删除缓存失败: {e}")
            return False
    
    def clear(self, category: Optional[str] = None) -> int:
        """清空缓存"""
        try:
            with self._lock:
                if category:
                    prefix = f"{category}:"
                    keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
                    count = len(keys_to_delete)
                    
                    for key in keys_to_delete:
                        if key in self._cache:
                            del self._cache[key]
                        if key in self._ttl_cache:
                            del self._ttl_cache[key]
                else:
                    count = len(self._cache)
                    self._cache.clear()
                    self._ttl_cache.clear()
                
                return count
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
            return 0
    
    def list_keys(self, category: Optional[str] = None, pattern: Optional[str] = None) -> List[str]:
        """列出缓存键"""
        try:
            with self._lock:
                keys = list(self._cache.keys())
                
                if category:
                    prefix = f"{category}:"
                    keys = [k for k in keys if k.startswith(prefix)]
                    keys = [k[len(prefix):] for k in keys]  # 移除前缀
                
                if pattern:
                    import fnmatch
                    keys = [k for k in keys if fnmatch.fnmatch(k, pattern)]
                
                return keys
        except Exception as e:
            logger.error(f"列出缓存键失败: {e}")
            return []
    
    def get_stats(self, category: Optional[str] = None) -> Dict[str, Any]:
        """获取缓存统计"""
        try:
            with self._lock:
                stats = self._stats.copy()
                
                if category:
                    prefix = f"{category}:"
                    category_keys = [k for k in self._cache.keys() if k.startswith(prefix)]
                    stats["category_keys"] = len(category_keys)
                    stats["category"] = category
                else:
                    stats["total_keys"] = len(self._cache)
                    stats["ttl_keys"] = len(self._ttl_cache)
                
                # 计算命中率
                total_requests = stats["hits"] + stats["misses"]
                stats["hit_rate"] = stats["hits"] / total_requests if total_requests > 0 else 0
                
                return stats
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {}
    
    def _evict_key(self, full_key: str):
        """驱逐过期的键"""
        if full_key in self._cache:
            del self._cache[full_key]
        if full_key in self._ttl_cache:
            del self._ttl_cache[full_key]
        self._stats["evictions"] += 1
    
    def cleanup_expired(self) -> int:
        """清理过期的缓存项"""
        try:
            with self._lock:
                current_time = time.time()
                expired_keys = []
                
                for key, expire_time in self._ttl_cache.items():
                    if current_time > expire_time:
                        expired_keys.append(key)
                
                for key in expired_keys:
                    self._evict_key(key)
                
                return len(expired_keys)
        except Exception as e:
            logger.error(f"清理过期缓存失败: {e}")
            return 0


# 全局缓存实例
_global_cache = MemoryCache()


class FileCache:
    """文件缓存类"""
    
    def __init__(self, cache_dir: str = None):
        """初始化文件缓存"""
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(__file__), "..", ".cache")
        
        self.cache_dir = cache_dir
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """确保缓存目录存在"""
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"创建缓存目录失败: {e}")
    
    def _get_cache_path(self, key: str) -> str:
        """获取缓存文件路径"""
        # 使用MD5哈希避免文件名过长或包含特殊字符
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{key_hash}.cache")
    
    def _get_meta_path(self, key: str) -> str:
        """获取元数据文件路径"""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{key_hash}.meta")
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """设置文件缓存"""
        try:
            cache_path = self._get_cache_path(key)
            meta_path = self._get_meta_path(key)
            
            # 保存数据
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
            
            # 保存元数据
            meta = {
                "key": key,
                "created_at": time.time(),
                "ttl": ttl,
                "expires_at": time.time() + ttl if ttl else None
            }
            
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f)
            
            return True
            
        except Exception as e:
            logger.error(f"设置文件缓存失败: {e}")
            return False
    
    def get(self, key: str) -> Any:
        """获取文件缓存"""
        try:
            cache_path = self._get_cache_path(key)
            meta_path = self._get_meta_path(key)
            
            if not os.path.exists(cache_path) or not os.path.exists(meta_path):
                return None
            
            # 检查元数据
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            
            # 检查是否过期
            if meta.get("expires_at") and time.time() > meta["expires_at"]:
                self.delete(key)
                return None
            
            # 读取数据
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
                
        except Exception as e:
            logger.error(f"获取文件缓存失败: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """删除文件缓存"""
        try:
            cache_path = self._get_cache_path(key)
            meta_path = self._get_meta_path(key)
            
            deleted = False
            
            if os.path.exists(cache_path):
                os.remove(cache_path)
                deleted = True
            
            if os.path.exists(meta_path):
                os.remove(meta_path)
                deleted = True
            
            return deleted
            
        except Exception as e:
            logger.error(f"删除文件缓存失败: {e}")
            return False
    
    def list_keys(self) -> List[str]:
        """列出所有缓存键"""
        try:
            keys = []
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.meta'):
                    meta_path = os.path.join(self.cache_dir, filename)
                    try:
                        with open(meta_path, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                            keys.append(meta.get("key", "unknown"))
                    except:
                        continue
            return keys
        except Exception as e:
            logger.error(f"列出文件缓存键失败: {e}")
            return []
    
    def cleanup_expired(self) -> int:
        """清理过期的文件缓存"""
        try:
            current_time = time.time()
            cleaned = 0
            
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.meta'):
                    meta_path = os.path.join(self.cache_dir, filename)
                    try:
                        with open(meta_path, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                        
                        if meta.get("expires_at") and current_time > meta["expires_at"]:
                            key = meta.get("key")
                            if key and self.delete(key):
                                cleaned += 1
                    except:
                        continue
            
            return cleaned
            
        except Exception as e:
            logger.error(f"清理过期文件缓存失败: {e}")
            return 0


# 全局文件缓存实例
_global_file_cache = FileCache()


def cache_set(params: CacheSetParams) -> Dict[str, Any]:
    """设置缓存"""
    try:
        success = _global_cache.set(
            params.key, 
            params.value, 
            params.ttl, 
            params.category
        )
        
        return {
            "success": success,
            "key": params.key,
            "category": params.category,
            "ttl": params.ttl,
            "message": "缓存设置成功" if success else "缓存设置失败"
        }
        
    except Exception as e:
        logger.error(f"设置缓存失败: {e}")
        return {"error": f"设置缓存失败: {str(e)}"}


def cache_get(params: CacheGetParams) -> Dict[str, Any]:
    """获取缓存"""
    try:
        value = _global_cache.get(params.key, params.category)
        
        return {
            "key": params.key,
            "category": params.category,
            "found": value is not None,
            "value": value,
            "message": "缓存命中" if value is not None else "缓存未命中"
        }
        
    except Exception as e:
        logger.error(f"获取缓存失败: {e}")
        return {"error": f"获取缓存失败: {str(e)}"}


def cache_delete(params: CacheDeleteParams) -> Dict[str, Any]:
    """删除缓存"""
    try:
        success = _global_cache.delete(params.key, params.category)
        
        return {
            "success": success,
            "key": params.key,
            "category": params.category,
            "message": "缓存删除成功" if success else "缓存项不存在"
        }
        
    except Exception as e:
        logger.error(f"删除缓存失败: {e}")
        return {"error": f"删除缓存失败: {str(e)}"}


def cache_list(params: CacheListParams) -> Dict[str, Any]:
    """列出缓存键"""
    try:
        keys = _global_cache.list_keys(params.category, params.pattern)
        
        return {
            "category": params.category,
            "pattern": params.pattern,
            "keys": keys,
            "count": len(keys)
        }
        
    except Exception as e:
        logger.error(f"列出缓存键失败: {e}")
        return {"error": f"列出缓存键失败: {str(e)}"}


def cache_stats(params: CacheStatsParams) -> Dict[str, Any]:
    """获取缓存统计"""
    try:
        stats = _global_cache.get_stats(params.category)
        
        return {
            "category": params.category,
            "stats": stats,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}")
        return {"error": f"获取缓存统计失败: {str(e)}"}


def cache_clear(category: Optional[str] = None) -> Dict[str, Any]:
    """清空缓存"""
    try:
        count = _global_cache.clear(category)
        
        return {
            "category": category,
            "cleared_count": count,
            "message": f"已清空 {count} 个缓存项"
        }
        
    except Exception as e:
        logger.error(f"清空缓存失败: {e}")
        return {"error": f"清空缓存失败: {str(e)}"}


def file_cache_info(params: FileCacheParams) -> Dict[str, Any]:
    """获取文件缓存信息"""
    try:
        file_path = params.file_path
        cache_key = params.cache_key or f"file:{file_path}"
        
        if not os.path.exists(file_path):
            return {"error": f"文件不存在: {file_path}"}
        
        # 获取文件信息
        file_stat = os.stat(file_path)
        file_mtime = file_stat.st_mtime
        file_size = file_stat.st_size
        
        # 检查内存缓存
        cached_info = _global_cache.get(cache_key, "file_info")
        is_cached = cached_info is not None
        
        # 检查文件是否已修改
        if is_cached and cached_info.get("mtime") == file_mtime:
            cache_status = "valid"
        elif is_cached:
            cache_status = "stale"
        else:
            cache_status = "not_cached"
        
        result = {
            "file_path": file_path,
            "cache_key": cache_key,
            "file_size": file_size,
            "file_mtime": file_mtime,
            "file_mtime_formatted": datetime.fromtimestamp(file_mtime).isoformat(),
            "is_cached": is_cached,
            "cache_status": cache_status
        }
        
        if is_cached:
            result["cached_info"] = cached_info
        
        return result
        
    except Exception as e:
        logger.error(f"获取文件缓存信息失败: {e}")
        return {"error": f"获取文件缓存信息失败: {str(e)}"}


def file_cache_set(file_path: str, data: Any, ttl: Optional[int] = None) -> Dict[str, Any]:
    """设置文件缓存"""
    try:
        cache_key = f"file:{file_path}"
        
        if not os.path.exists(file_path):
            return {"error": f"文件不存在: {file_path}"}
        
        # 获取文件信息
        file_stat = os.stat(file_path)
        
        # 准备缓存数据
        cache_data = {
            "data": data,
            "file_path": file_path,
            "mtime": file_stat.st_mtime,
            "size": file_stat.st_size,
            "cached_at": time.time()
        }
        
        # 设置缓存
        success = _global_cache.set(cache_key, cache_data, ttl, "file_data")
        
        # 同时设置文件信息缓存
        file_info = {
            "mtime": file_stat.st_mtime,
            "size": file_stat.st_size,
            "cached_at": time.time()
        }
        _global_cache.set(cache_key, file_info, ttl, "file_info")
        
        return {
            "success": success,
            "file_path": file_path,
            "cache_key": cache_key,
            "ttl": ttl,
            "message": "文件缓存设置成功" if success else "文件缓存设置失败"
        }
        
    except Exception as e:
        logger.error(f"设置文件缓存失败: {e}")
        return {"error": f"设置文件缓存失败: {str(e)}"}


def file_cache_get(file_path: str) -> Dict[str, Any]:
    """获取文件缓存"""
    try:
        cache_key = f"file:{file_path}"
        
        if not os.path.exists(file_path):
            return {"error": f"文件不存在: {file_path}"}
        
        # 获取当前文件信息
        file_stat = os.stat(file_path)
        current_mtime = file_stat.st_mtime
        
        # 获取缓存数据
        cached_data = _global_cache.get(cache_key, "file_data")
        
        if cached_data is None:
            return {
                "file_path": file_path,
                "cache_key": cache_key,
                "found": False,
                "message": "文件缓存未找到"
            }
        
        # 检查文件是否已修改
        cached_mtime = cached_data.get("mtime", 0)
        if current_mtime != cached_mtime:
            return {
                "file_path": file_path,
                "cache_key": cache_key,
                "found": True,
                "valid": False,
                "current_mtime": current_mtime,
                "cached_mtime": cached_mtime,
                "message": "文件缓存已过期（文件已修改）"
            }
        
        return {
            "file_path": file_path,
            "cache_key": cache_key,
            "found": True,
            "valid": True,
            "data": cached_data.get("data"),
            "cached_at": cached_data.get("cached_at"),
            "message": "文件缓存命中"
        }
        
    except Exception as e:
        logger.error(f"获取文件缓存失败: {e}")
        return {"error": f"获取文件缓存失败: {str(e)}"}


def cleanup_caches() -> Dict[str, Any]:
    """清理过期缓存"""
    try:
        memory_cleaned = _global_cache.cleanup_expired()
        file_cleaned = _global_file_cache.cleanup_expired()
        
        return {
            "memory_cache_cleaned": memory_cleaned,
            "file_cache_cleaned": file_cleaned,
            "total_cleaned": memory_cleaned + file_cleaned,
            "timestamp": time.time(),
            "message": f"已清理 {memory_cleaned + file_cleaned} 个过期缓存项"
        }
        
    except Exception as e:
        logger.error(f"清理缓存失败: {e}")
        return {"error": f"清理缓存失败: {str(e)}"}


def register_cache_tools(mcp):
    """注册缓存工具到MCP"""
    
    @mcp.tool()
    def cache_set(params: dict):
        """设置缓存"""
        from .cache import cache_set as cache_set_func
        return cache_set_func(CacheSetParams(**params))
    
    @mcp.tool()
    def cache_get(params: dict):
        """获取缓存"""
        from .cache import cache_get as cache_get_func
        return cache_get_func(CacheGetParams(**params))
    
    @mcp.tool()
    def cache_delete(params: dict):
        """删除缓存"""
        from .cache import cache_delete as cache_delete_func
        return cache_delete_func(CacheDeleteParams(**params))
    
    @mcp.tool()
    def cache_list(params: dict):
        """列出缓存键"""
        from .cache import cache_list as cache_list_func
        return cache_list_func(CacheListParams(**params))
    
    @mcp.tool()
    def cache_stats(params: dict):
        """获取缓存统计"""
        from .cache import cache_stats as cache_stats_func
        return cache_stats_func(CacheStatsParams(**params))
    
    @mcp.tool()
    def cleanup_caches(params: dict):
        """清理过期缓存"""
        from .cache import cleanup_caches as cleanup_caches_func
        return cleanup_caches_func()


# 测试函数
def test_cache_tools():
    """测试缓存工具"""
    try:
        # 测试内存缓存
        set_result = cache_set(CacheSetParams(key="test", value="hello", ttl=60))
        assert set_result["success"]
        
        get_result = cache_get(CacheGetParams(key="test"))
        assert get_result["found"]
        assert get_result["value"] == "hello"
        
        delete_result = cache_delete(CacheDeleteParams(key="test"))
        assert delete_result["success"]
        
        logger.info("缓存工具测试通过")
        
    except Exception as e:
        logger.error(f"缓存工具测试失败: {e}")
        raise


if __name__ == "__main__":
    test_cache_tools()