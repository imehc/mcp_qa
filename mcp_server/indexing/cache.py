"""
MCP 服务器索引缓存管理

该模块提供智能缓存机制，避免重复解析和索引未修改的文件。
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Set, List
from datetime import datetime, timedelta
from pathlib import Path

from ..config import config
from ..utils import calculate_file_hash, get_current_timestamp

logger = logging.getLogger(__name__)


class FileIndexCache:
    """
    文件索引缓存管理器
    
    跟踪文件的修改时间、哈希值和索引状态，
    以避免重复解析和索引未修改的文件。
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        初始化缓存管理器。
        
        参数:
            cache_dir: 缓存目录（如果为 None 则使用配置默认值）
        """
        self.cache_dir = cache_dir or os.path.join(config.index.INDEX_DIR, "cache")
        self.cache_file = os.path.join(self.cache_dir, "file_index_cache.json")
        
        # 缓存数据结构
        self.cache_data: Dict[str, Dict[str, Any]] = {}
        
        # 缓存配置
        self.cache_ttl = int(os.getenv("MCP_CACHE_TTL", str(24 * 3600)))  # 24小时默认TTL
        self.max_cache_entries = int(os.getenv("MCP_MAX_CACHE_ENTRIES", "10000"))
        
        # 确保缓存目录存在
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 加载现有缓存
        self._load_cache()
    
    def is_file_cached_and_valid(self, file_path: str) -> bool:
        """
        检查文件是否已缓存且仍然有效。
        
        参数:
            file_path: 文件路径
            
        返回:
            如果文件已缓存且有效则返回 True，否则返回 False
        """
        try:
            # 规范化路径
            normalized_path = os.path.normpath(os.path.abspath(file_path))
            
            # 检查文件是否存在
            if not os.path.exists(normalized_path):
                self._remove_from_cache(normalized_path)
                return False
            
            # 检查缓存中是否存在
            if normalized_path not in self.cache_data:
                return False
            
            cache_entry = self.cache_data[normalized_path]
            
            # 检查缓存是否过期
            if self._is_cache_expired(cache_entry):
                self._remove_from_cache(normalized_path)
                return False
            
            # 检查文件是否被修改
            current_stat = os.stat(normalized_path)
            current_mtime = current_stat.st_mtime
            current_size = current_stat.st_size
            
            cached_mtime = cache_entry.get("mtime", 0)
            cached_size = cache_entry.get("size", 0)
            
            # 如果修改时间或大小发生变化，需要重新验证
            if current_mtime != cached_mtime or current_size != cached_size:
                # 计算当前文件哈希来确认是否真的发生了变化
                current_hash = calculate_file_hash(normalized_path)
                cached_hash = cache_entry.get("file_hash", "")
                
                if current_hash != cached_hash:
                    # 文件确实发生了变化
                    self._remove_from_cache(normalized_path)
                    return False
                else:
                    # 文件内容未变化，更新统计信息
                    cache_entry.update({
                        "mtime": current_mtime,
                        "size": current_size,
                        "last_checked": get_current_timestamp()
                    })
                    self._save_cache()
            
            # 更新最后检查时间
            cache_entry["last_checked"] = get_current_timestamp()
            
            return True
            
        except Exception as e:
            logger.warning(f"检查文件缓存失败 {file_path}: {str(e)}")
            return False
    
    def cache_file_index(
        self,
        file_path: str,
        index_result: Dict[str, Any],
        chunks_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        parse_content: Optional[str] = None,
        parse_chunks: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        将文件索引结果存储到缓存中。
        
        参数:
            file_path: 文件路径
            index_result: 索引结果
            chunks_count: 生成的文本块数量
            metadata: 可选的元数据
            parse_content: 解析的文本内容（可选）
            parse_chunks: 解析的文本块（可选）
        """
        try:
            # 规范化路径
            normalized_path = os.path.normpath(os.path.abspath(file_path))
            
            # 检查文件是否存在
            if not os.path.exists(normalized_path):
                logger.warning(f"尝试缓存不存在的文件: {normalized_path}")
                return
            
            # 获取文件统计信息
            stat_info = os.stat(normalized_path)
            file_hash = calculate_file_hash(normalized_path)
            
            # 创建缓存条目
            cache_entry = {
                "file_path": normalized_path,
                "file_hash": file_hash,
                "mtime": stat_info.st_mtime,
                "size": stat_info.st_size,
                "indexed_at": get_current_timestamp(),
                "last_checked": get_current_timestamp(),
                "chunks_count": chunks_count,
                "index_success": index_result.get("success", False),
                "metadata": metadata or {}
            }
            
            # 如果索引成功，存储更多详细信息
            if index_result.get("success", False):
                cache_entry.update({
                    "vector_index_built": True,
                    "total_chunks": index_result.get("total_chunks", chunks_count),
                    "build_time": index_result.get("build_time", 0.0)
                })
            
            # 如果提供了解析内容，存储（但限制大小以避免缓存过大）
            if parse_content and len(parse_content) < 50000:  # 限制50KB
                cache_entry["parse_content"] = parse_content
            
            # 存储文本块信息（仅存储元数据，不存储完整内容）
            if parse_chunks:
                cache_entry["chunks_info"] = [
                    {
                        "chunk_id": chunk.get("chunk_id", i),
                        "content_length": len(chunk.get("content", "")),
                        "metadata": chunk.get("metadata", {})
                    }
                    for i, chunk in enumerate(parse_chunks)
                ]
            
            # 存储到缓存
            self.cache_data[normalized_path] = cache_entry
            
            # 清理过期和过多的缓存条目
            self._cleanup_cache()
            
            # 保存到磁盘
            self._save_cache()
            
            logger.info(f"文件索引已缓存: {normalized_path}")
            
        except Exception as e:
            logger.error(f"缓存文件索引失败 {file_path}: {str(e)}")
    
    def get_cached_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        获取文件的缓存信息。
        
        参数:
            file_path: 文件路径
            
        返回:
            缓存信息字典，如果未缓存则返回 None
        """
        normalized_path = os.path.normpath(os.path.abspath(file_path))
        return self.cache_data.get(normalized_path)
    
    def invalidate_file_cache(self, file_path: str) -> None:
        """
        使特定文件的缓存失效。
        
        参数:
            file_path: 文件路径
        """
        normalized_path = os.path.normpath(os.path.abspath(file_path))
        self._remove_from_cache(normalized_path)
        self._save_cache()
        logger.info(f"文件缓存已失效: {normalized_path}")
    
    def invalidate_all_cache(self) -> None:
        """使所有缓存失效。"""
        self.cache_data.clear()
        self._save_cache()
        logger.info("所有文件缓存已失效")
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        获取缓存统计信息。
        
        返回:
            包含缓存统计信息的字典
        """
        total_entries = len(self.cache_data)
        valid_entries = 0
        expired_entries = 0
        total_size = 0
        
        current_time = get_current_timestamp()
        
        for file_path, cache_entry in self.cache_data.items():
            if os.path.exists(file_path):
                if self._is_cache_expired(cache_entry):
                    expired_entries += 1
                else:
                    valid_entries += 1
                total_size += cache_entry.get("size", 0)
        
        return {
            "total_entries": total_entries,
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "cache_hit_potential": valid_entries / total_entries if total_entries > 0 else 0,
            "total_cached_file_size": total_size,
            "cache_file_size": os.path.getsize(self.cache_file) if os.path.exists(self.cache_file) else 0,
            "cache_ttl_hours": self.cache_ttl / 3600,
            "max_entries": self.max_cache_entries
        }
    
    def cleanup_invalid_entries(self) -> int:
        """
        清理无效的缓存条目。
        
        返回:
            清理的条目数量
        """
        removed_count = 0
        entries_to_remove = []
        
        for file_path, cache_entry in self.cache_data.items():
            # 检查文件是否仍然存在
            if not os.path.exists(file_path):
                entries_to_remove.append(file_path)
                continue
            
            # 检查缓存是否过期
            if self._is_cache_expired(cache_entry):
                entries_to_remove.append(file_path)
        
        # 移除无效条目
        for file_path in entries_to_remove:
            self._remove_from_cache(file_path)
            removed_count += 1
        
        if removed_count > 0:
            self._save_cache()
            logger.info(f"清理了 {removed_count} 个无效缓存条目")
        
        return removed_count
    
    def find_outdated_files(self) -> Set[str]:
        """
        查找需要重新索引的过期文件。
        
        返回:
            需要重新索引的文件路径集合
        """
        outdated_files = set()
        
        for file_path, cache_entry in self.cache_data.items():
            if not os.path.exists(file_path):
                continue
            
            # 检查文件是否被修改
            if not self.is_file_cached_and_valid(file_path):
                outdated_files.add(file_path)
        
        return outdated_files
    
    def _load_cache(self) -> None:
        """从磁盘加载缓存数据。"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache_data = data.get("cache_entries", {})
                    
                logger.info(f"加载了 {len(self.cache_data)} 个缓存条目")
            else:
                self.cache_data = {}
                
        except Exception as e:
            logger.warning(f"加载缓存失败: {str(e)}")
            self.cache_data = {}
    
    def _save_cache(self) -> None:
        """将缓存数据保存到磁盘。"""
        try:
            cache_metadata = {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "cache_ttl": self.cache_ttl,
                "max_entries": self.max_cache_entries,
                "total_entries": len(self.cache_data),
                "cache_entries": self.cache_data
            }
            
            # 原子写入
            temp_file = self.cache_file + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_metadata, f, indent=2, ensure_ascii=False)
            
            # 原子替换
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
            os.rename(temp_file, self.cache_file)
            
        except Exception as e:
            logger.error(f"保存缓存失败: {str(e)}")
    
    def _is_cache_expired(self, cache_entry: Dict[str, Any]) -> bool:
        """检查缓存条目是否过期。"""
        if self.cache_ttl <= 0:
            return False  # 永不过期
        
        indexed_at = cache_entry.get("indexed_at", 0)
        current_time = get_current_timestamp()
        
        return (current_time - indexed_at) > self.cache_ttl
    
    def _remove_from_cache(self, file_path: str) -> None:
        """从缓存中移除文件。"""
        if file_path in self.cache_data:
            del self.cache_data[file_path]
    
    def _cleanup_cache(self) -> None:
        """清理缓存以保持在最大条目限制内。"""
        if len(self.cache_data) <= self.max_cache_entries:
            return
        
        # 按最后检查时间排序，移除最旧的条目
        sorted_entries = sorted(
            self.cache_data.items(),
            key=lambda x: x[1].get("last_checked", 0)
        )
        
        # 保留最新的条目
        entries_to_keep = sorted_entries[-self.max_cache_entries:]
        
        # 重建缓存数据
        self.cache_data = dict(entries_to_keep)
        
        removed_count = len(sorted_entries) - len(entries_to_keep)
        if removed_count > 0:
            logger.info(f"为保持缓存大小限制，移除了 {removed_count} 个最旧的缓存条目")


# 全局缓存管理器实例
file_index_cache = FileIndexCache()


def is_file_indexed_and_current(file_path: str) -> bool:
    """
    便利函数：检查文件是否已索引且是最新的。
    
    参数:
        file_path: 文件路径
        
    返回:
        如果文件已索引且是最新的则返回 True，否则返回 False
    """
    return file_index_cache.is_file_cached_and_valid(file_path)


def cache_file_index_result(
    file_path: str,
    index_result: Dict[str, Any],
    chunks_count: int = 0,
    metadata: Optional[Dict[str, Any]] = None,
    parse_content: Optional[str] = None,
    parse_chunks: Optional[List[Dict[str, Any]]] = None
) -> None:
    """
    便利函数：缓存文件索引结果。
    
    参数:
        file_path: 文件路径
        index_result: 索引结果
        chunks_count: 生成的文本块数量
        metadata: 可选的元数据
        parse_content: 解析的文本内容（可选）
        parse_chunks: 解析的文本块（可选）
    """
    file_index_cache.cache_file_index(
        file_path, index_result, chunks_count, metadata, parse_content, parse_chunks
    )


def invalidate_file_cache(file_path: str) -> None:
    """
    便利函数：使文件缓存失效。
    
    参数:
        file_path: 文件路径
    """
    file_index_cache.invalidate_file_cache(file_path)


def get_cache_stats() -> Dict[str, Any]:
    """
    便利函数：获取缓存统计信息。
    
    返回:
        缓存统计信息字典
    """
    return file_index_cache.get_cache_statistics()