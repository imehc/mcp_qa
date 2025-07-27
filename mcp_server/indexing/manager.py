"""
MCP 服务器索引管理

该模块提供高级索引管理功能，
协调嵌入生成和向量存储。
"""

import os
import logging
import threading
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..config import config
from ..types import TextChunk, IndexStatus
from ..exceptions import IndexNotFoundError
from ..utils import Timer, calculate_file_hash
from .embeddings import embedding_manager
from .storage import VectorStore
from .cache import file_index_cache, cache_file_index_result, is_file_indexed_and_current
from ..parsers.base import get_parser_for_file

logger = logging.getLogger(__name__)


class IndexManager:
    """
    MCP 服务器的高级索引管理。
    
    该类提供了一个统一的接口，用于使用嵌入向量和向量存储来构建、管理和搜索文档索引。
    """
    
    def __init__(self, index_dir: Optional[str] = None):
        """
        初始化索引管理器。
        
        参数:
            index_dir: 索引存储目录（如果为 None 则使用配置默认值）
        """
        self.index_dir = index_dir or config.index.INDEX_DIR
        self.vector_store = VectorStore(self.index_dir)
        self.lock = threading.Lock()
        
        # 文档跟踪
        self.indexed_documents: Dict[str, Dict[str, Any]] = {}
        self.document_hashes: Dict[str, str] = {}
        
        # 索引状态
        self.index_status = IndexStatus.NOT_INDEXED
        self.last_build_time: Optional[datetime] = None
        self.build_progress: Dict[str, Any] = {}
        
        # 统计信息
        self.stats = {
            "total_documents": 0,
            "total_chunks": 0,
            "last_updated": None,
            "last_search_time": None,
            "search_count": 0,
            "total_search_time": 0.0,
            "build_count": 0,
            "total_build_time": 0.0
        }
        
        # 加载现有索引（如果可用）
        self._load_index_metadata()
    
    def build_index_from_directory(
        self,
        directory: str,
        file_extensions: Optional[Set[str]] = None,
        recursive: bool = True,
        show_progress: bool = True,
        max_workers: int = 4
    ) -> Dict[str, Any]:
        """
        从目录中的所有文档构建索引。
        
        参数:
            directory: 扫描文档的目录
            file_extensions: 允许的文件扩展名集合（None 表示所有支持的扩展名）
            recursive: 是否扫描子目录
            show_progress: 处理过程中是否显示进度
            max_workers: 用于解析的最大工作线程数
            
        返回:
            包含构建结果的字典
            
        引发:
            Exception: 如果索引构建失败
        """
        with self.lock:
            self.index_status = IndexStatus.BUILDING
            self.build_progress = {"stage": "scanning", "progress": 0.0}
        
        try:
            timer = Timer()
            timer.start()
            
            logger.info(f"从目录构建索引: {directory}")
            
            # 扫描文件
            files = self._scan_directory(directory, file_extensions, recursive)
            if not files:
                raise ValueError(f"在目录中未找到支持的文件: {directory}")
            
            logger.info(f"找到 {len(files)} 个要处理的文件")
            
            # 解析文档并提取文本块
            all_chunks = []
            processed_files = 0
            cached_files = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交解析任务
                future_to_file = {}
                for file_path in files:
                    # 优先检查向量索引缓存 - 如果文件已在当前索引中且未修改，跳过
                    if self._is_file_in_current_index_and_valid(file_path):
                        cached_files += 1
                        logger.info(f"使用现有向量索引: {file_path}")
                        
                        # 确保在文档跟踪中
                        if file_path not in self.indexed_documents:
                            file_hash = calculate_file_hash(file_path)
                            file_stat = os.stat(file_path)
                            self.indexed_documents[file_path] = {
                                "hash": file_hash,
                                "chunks": 0,  # 会在后续从向量存储获取
                                "indexed_at": datetime.now().isoformat(),
                                "file_size": file_stat.st_size
                            }
                            self.document_hashes[file_path] = file_hash
                        
                        processed_files += 1
                        continue
                    
                    # 检查文件是否已缓存且仍然有效（但不在当前索引中）
                    elif is_file_indexed_and_current(file_path):
                        cached_files += 1
                        logger.info(f"使用缓存的解析结果: {file_path}")
                        
                        # 从缓存获取信息并创建虚拟块（实际块会从向量存储加载）
                        cached_info = file_index_cache.get_cached_file_info(file_path)
                        if cached_info:
                            chunks_count = cached_info.get("chunks_count", 0)
                            file_hash = cached_info.get("file_hash", "")
                            
                            # 更新文档跟踪
                            self.indexed_documents[file_path] = {
                                "hash": file_hash,
                                "chunks": chunks_count,
                                "indexed_at": cached_info.get("indexed_at", datetime.now().isoformat()),
                                "file_size": cached_info.get("size", 0)
                            }
                            self.document_hashes[file_path] = file_hash
                        
                        processed_files += 1
                        continue
                    
                    # 需要重新解析的文件
                    future_to_file[executor.submit(self._parse_file_safely, file_path)] = file_path
                
                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        chunks = future.result()
                        if chunks:
                            all_chunks.extend(chunks)
                            
                            # 更新文档跟踪
                            file_hash = calculate_file_hash(file_path)
                            self.indexed_documents[file_path] = {
                                "hash": file_hash,
                                "chunks": len(chunks),
                                "indexed_at": datetime.now().isoformat(),
                                "file_size": os.path.getsize(file_path)
                            }
                            self.document_hashes[file_path] = file_hash
                        
                        processed_files += 1
                        progress = processed_files / len(files)
                        
                        with self.lock:
                            self.build_progress.update({
                                "stage": "parsing",
                                "progress": progress * 50,  # 解析占前 50%
                                "processed_files": processed_files,
                                "total_files": len(files),
                                "cached_files": cached_files
                            })
                        
                        if show_progress and processed_files % 10 == 0:
                            logger.info(f"已处理 {processed_files}/{len(files)} 个文件 (缓存: {cached_files})")
                            
                    except Exception as e:
                        logger.warning(f"解析 {file_path} 失败: {str(e)}")
                        processed_files += 1
                        continue
            
            # 如果有新解析的文件，则构建向量索引
            if all_chunks:
                # 更新进度
                with self.lock:
                    self.build_progress.update({
                        "stage": "embedding",
                        "progress": 50.0
                    })
                
                # 构建向量索引
                index_result = self.vector_store.build_index(
                    all_chunks,
                    show_progress=show_progress
                )
                
                # 缓存新解析的文件索引结果
                for file_path in future_to_file.values():
                    if file_path in self.indexed_documents:
                        file_info = self.indexed_documents[file_path]
                        cache_file_index_result(
                            file_path,
                            {
                                "success": True,
                                "total_chunks": file_info["chunks"],
                                "build_time": index_result.get("build_time", 0.0)
                            },
                            chunks_count=file_info["chunks"],
                            metadata={"file_size": file_info["file_size"]}
                        )
            else:
                # 如果所有文件都来自缓存，直接加载现有索引
                logger.info("所有文件都来自缓存，加载现有向量索引")
                if not self.vector_store.load_index():
                    logger.warning("无法加载现有向量索引，可能需要重建")
                
                index_result = {
                    "success": True,
                    "from_cache": True,
                    "cached_files": cached_files
                }
            
            build_time = timer.stop()
            
            # 更新状态和统计信息
            with self.lock:
                self.index_status = IndexStatus.READY
                self.last_build_time = datetime.now()
                self.build_progress = {"stage": "completed", "progress": 100.0}
                
                total_chunks = sum(info.get("chunks", 0) for info in self.indexed_documents.values())
                
                self.stats.update({
                    "total_documents": len(self.indexed_documents),
                    "total_chunks": total_chunks,
                    "last_updated": self.last_build_time.isoformat(),
                    "build_count": self.stats["build_count"] + 1,
                    "total_build_time": self.stats["total_build_time"] + build_time
                })
            
            # 保存元数据
            self._save_index_metadata()
            
            logger.info(f"索引构建成功，耗时 {build_time:.2f} 秒 (新解析: {len(all_chunks)} 块, 缓存: {cached_files} 文件)")
            
            return {
                "success": True,
                "total_files": len(files),
                "processed_files": processed_files,
                "cached_files": cached_files,
                "total_chunks": self.stats["total_chunks"],
                "new_chunks": len(all_chunks),
                "build_time": build_time,
                "cache_hit_rate": cached_files / len(files) if files else 0,
                "index_result": index_result
            }
            
        except Exception as e:
            with self.lock:
                self.index_status = IndexStatus.ERROR
                self.build_progress = {"stage": "error", "error": str(e)}
            
            logger.error(f"索引构建失败: {str(e)}")
            raise
    
    def add_documents(
        self, 
        file_paths: List[str],
        update_existing: bool = True
    ) -> Dict[str, Any]:
        """
        将文档添加到现有索引中。
        
        参数:
            file_paths: 要添加的文件路径列表
            update_existing: 如果文件已更改是否更新现有文档
            
        返回:
            包含操作结果的字典
        """
        if self.index_status == IndexStatus.NOT_INDEXED:
            # 如果索引不存在，则从这些文件构建
            return self.build_index_from_files(file_paths)
        
        try:
            logger.info(f"向索引中添加 {len(file_paths)} 个文档")
            
            # 筛选需要处理的文件，使用缓存逻辑
            files_to_process = []
            cached_files = []
            
            for file_path in file_paths:
                if not os.path.exists(file_path):
                    logger.warning(f"文件未找到: {file_path}")
                    continue
                
                # 优先检查向量索引缓存 - 如果文件已在当前索引中且未修改，跳过
                if self._is_file_in_current_index_and_valid(file_path):
                    cached_files.append(file_path)
                    logger.info(f"使用现有向量索引: {file_path}")
                    continue

                # 检查文件是否已缓存且仍然有效（但不在当前索引中）
                elif is_file_indexed_and_current(file_path):
                    # 文件已缓存且未修改，检查是否在当前索引中
                    if file_path in self.indexed_documents:
                        cached_files.append(file_path)
                        logger.info(f"使用缓存的索引: {file_path}")
                        continue
                
                # 检查是否需要处理
                current_hash = calculate_file_hash(file_path)
                
                if file_path not in self.document_hashes:
                    # 新文件
                    files_to_process.append(file_path)
                elif update_existing and self.document_hashes[file_path] != current_hash:
                    # 文件已更改
                    files_to_process.append(file_path)
                    # 首先删除旧版本
                    self.remove_documents([file_path])
                    # 使文件缓存失效
                    file_index_cache.invalidate_file_cache(file_path)
            
            if not files_to_process:
                return {
                    "success": True,
                    "message": f"没有新的或更改的文档需要处理。{len(cached_files)} 个文件使用了缓存。",
                    "processed_files": 0,
                    "cached_files": len(cached_files),
                    "cached_file_list": cached_files
                }
            
            # 解析新文件
            all_chunks = []
            processed_files_info = []
            
            for file_path in files_to_process:
                try:
                    chunks = self._parse_file_safely(file_path)
                    if chunks:
                        all_chunks.extend(chunks)
                        
                        # 更新跟踪
                        file_hash = calculate_file_hash(file_path)
                        file_info = {
                            "hash": file_hash,
                            "chunks": len(chunks),
                            "indexed_at": datetime.now().isoformat(),
                            "file_size": os.path.getsize(file_path)
                        }
                        self.indexed_documents[file_path] = file_info
                        self.document_hashes[file_path] = file_hash
                        
                        processed_files_info.append({
                            "file_path": file_path,
                            "chunks_count": len(chunks),
                            "file_size": file_info["file_size"]
                        })
                        
                except Exception as e:
                    logger.warning(f"解析 {file_path} 失败: {str(e)}")
                    continue
            
            if not all_chunks:
                return {
                    "success": True,
                    "message": "从新文件中未提取到文本块",
                    "processed_files": 0,
                    "cached_files": len(cached_files)
                }
            
            # 添加到向量存储
            result = self.vector_store.add_documents(all_chunks)
            
            # 缓存索引结果
            for file_info in processed_files_info:
                cache_file_index_result(
                    file_info["file_path"],
                    {
                        "success": True,
                        "total_chunks": file_info["chunks_count"],
                        "build_time": 0.0  # 这里是增量添加，没有整体构建时间
                    },
                    chunks_count=file_info["chunks_count"],
                    metadata={"file_size": file_info["file_size"]}
                )
            
            # 更新统计信息
            with self.lock:
                self.stats.update({
                    "total_documents": len(self.indexed_documents),
                    "total_chunks": result.get("total_chunks", 0),
                    "last_updated": datetime.now().isoformat()
                })
            
            # 保存元数据
            self._save_index_metadata()
            
            logger.info(f"成功添加 {len(files_to_process)} 个文档，{len(cached_files)} 个文件使用了缓存")
            
            return {
                "success": True,
                "processed_files": len(files_to_process),
                "cached_files": len(cached_files),
                "added_chunks": result.get("added_chunks", 0),
                "total_chunks": result.get("total_chunks", 0),
                "cache_hit_rate": len(cached_files) / len(file_paths) if file_paths else 0
            }
            
        except Exception as e:
            logger.error(f"添加文档失败: {str(e)}")
            raise
    
    def remove_documents(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        从索引中删除文档。
        
        参数:
            file_paths: 要删除的文件路径列表
            
        返回:
            包含操作结果的字典
        """
        try:
            logger.info(f"从索引中删除 {len(file_paths)} 个文档")
            
            # 从向量存储中删除
            result = self.vector_store.remove_documents(file_paths)
            
            # 更新跟踪
            for file_path in file_paths:
                self.indexed_documents.pop(file_path, None)
                self.document_hashes.pop(file_path, None)
            
            # 更新统计信息
            with self.lock:
                self.stats.update({
                    "total_documents": len(self.indexed_documents),
                    "total_chunks": result.get("total_chunks", 0),
                    "last_updated": datetime.now().isoformat()
                })
            
            # 保存元数据
            self._save_index_metadata()
            
            return result
            
        except Exception as e:
            logger.error(f"删除文档失败: {str(e)}")
            raise
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        在索引中搜索相似文档。
        
        参数:
            query: 搜索查询文本
            top_k: 要返回的顶部结果数量
            filters: 搜索结果的可选过滤器
            
        返回:
            包含得分和元数据的搜索结果列表
            
        引发:
            IndexNotFoundError: 如果没有可用索引
        """
        if self.index_status not in [IndexStatus.READY, IndexStatus.UPDATING]:
            if not self.vector_store.load_index():
                raise IndexNotFoundError()
            self.index_status = IndexStatus.READY
        
        timer = Timer()
        timer.start()
        
        try:
            # 执行向量搜索
            results = self.vector_store.search(query, top_k)
            
            # 如果指定了过滤器，则应用额外的过滤器
            if filters:
                results = self._apply_filters(results, filters)
            
            search_time = timer.stop()
            
            # 更新搜索统计信息
            with self.lock:
                self.stats["search_count"] += 1
                self.stats["total_search_time"] += search_time
                self.stats["last_search_time"] = datetime.now().isoformat()
            
            logger.info(f"搜索完成，耗时 {search_time:.3f} 秒，返回 {len(results)} 个结果")
            
            return results
            
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            raise
    
    def update_document(self, file_path: str) -> Dict[str, Any]:
        """
        更新索引中的单个文档。
        
        参数:
            file_path: 要更新的文档路径
            
        返回:
            包含操作结果的字典
        """
        return self.add_documents([file_path], update_existing=True)
    
    def rebuild_index(self, directory: Optional[str] = None) -> Dict[str, Any]:
        """
        完全重建索引。
        
        参数:
            directory: 要重建的目录（如果为 None 则使用跟踪的文档）
            
        返回:
            包含重建结果的字典
        """
        logger.info("重建索引")
        
        # 清除现有索引
        self.clear_index()
        
        if directory:
            return self.build_index_from_directory(directory)
        else:
            # 从跟踪的文档重建
            file_paths = list(self.indexed_documents.keys())
            return self.build_index_from_files(file_paths)
    
    def clear_index(self) -> None:
        """清除整个索引和所有元数据。"""
        logger.info("清除索引")
        
        with self.lock:
            self.index_status = IndexStatus.NOT_BUILT
            self.indexed_documents.clear()
            self.document_hashes.clear()
            self.last_build_time = None
            self.build_progress.clear()
            
            self.stats.update({
                "total_documents": 0,
                "total_chunks": 0,
                "last_updated": None
            })
        
        # 清除向量存储
        self.vector_store.clear_index()
        
        # 删除元数据文件
        metadata_path = os.path.join(self.index_dir, "index_metadata.json")
        if os.path.exists(metadata_path):
            os.remove(metadata_path)
    
    def get_index_status(self) -> Dict[str, Any]:
        """
        获取当前索引状态和统计信息。
        
        返回:
            包含状态信息的字典
        """
        with self.lock:
            status_info = {
                "status": self.index_status.value,
                "last_build_time": self.last_build_time.isoformat() if self.last_build_time else None,
                "build_progress": self.build_progress.copy(),
                "statistics": self.stats.copy(),
                "indexed_documents": len(self.indexed_documents),
                "vector_store_stats": self.vector_store.get_statistics()
            }
        
        # 添加计算的统计信息
        if status_info["statistics"]["search_count"] > 0:
            avg_search_time = (
                status_info["statistics"]["total_search_time"] / 
                status_info["statistics"]["search_count"]
            )
            status_info["statistics"]["average_search_time"] = avg_search_time
        
        if status_info["statistics"]["build_count"] > 0:
            avg_build_time = (
                status_info["statistics"]["total_build_time"] / 
                status_info["statistics"]["build_count"]
            )
            status_info["statistics"]["average_build_time"] = avg_build_time
        
        return status_info
    
    def get_document_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        获取索引文档的信息。
        
        参数:
            file_path: 文档路径
            
        返回:
            文档信息，如果未找到则返回 None
        """
        return self.indexed_documents.get(file_path)
    
    def list_indexed_documents(self) -> List[Dict[str, Any]]:
        """
        列出所有带有元数据的索引文档。
        
        返回:
            文档信息列表
        """
        documents = []
        for file_path, info in self.indexed_documents.items():
            doc_info = info.copy()
            doc_info["file_path"] = file_path
            doc_info["exists"] = os.path.exists(file_path)
            documents.append(doc_info)
        
        return documents
    
    def find_outdated_documents(self) -> List[str]:
        """
        查找自索引以来已修改的文档。
        
        返回:
            需要更新的文件路径列表
        """
        outdated = []
        
        for file_path, stored_hash in self.document_hashes.items():
            if not os.path.exists(file_path):
                outdated.append(file_path)
                continue
            
            try:
                current_hash = calculate_file_hash(file_path)
                if current_hash != stored_hash:
                    outdated.append(file_path)
            except Exception as e:
                logger.warning(f"检查 {file_path} 的哈希值失败: {str(e)}")
                outdated.append(file_path)
        
        return outdated
    
    def _is_file_in_current_index_and_valid(self, file_path: str) -> bool:
        """
        检查文件是否已在当前向量索引中且仍然有效。
        
        参数:
            file_path: 文件路径
            
        返回:
            如果文件在当前索引中且有效则返回True
        """
        try:
            # 检查文件是否在当前索引管理器的文档跟踪中
            if file_path not in self.indexed_documents:
                return False
            
            # 检查文件是否仍然存在
            if not os.path.exists(file_path):
                return False
            
            # 检查文件是否被修改
            current_hash = calculate_file_hash(file_path)
            stored_hash = self.document_hashes.get(file_path, "")
            
            if current_hash != stored_hash:
                return False
            
            # 检查向量存储中是否实际存在该文件的向量
            if hasattr(self.vector_store, 'has_document'):
                return self.vector_store.has_document(file_path)
            
            # 如果向量存储没有has_document方法，假设文件在跟踪中就是有效的
            return True
            
        except Exception as e:
            logger.warning(f"检查文件索引状态失败 {file_path}: {e}")
            return False
    
    def refresh_index(self) -> Dict[str, Any]:
        """
        通过更新过时的文档来刷新索引。
        
        返回:
            包含刷新结果的字典
        """
        outdated = self.find_outdated_documents()
        
        if not outdated:
            return {
                "success": True,
                "message": "索引是最新的",
                "updated_documents": 0
            }
        
        logger.info(f"刷新 {len(outdated)} 个过时的文档")
        
        # 删除过时的文档
        self.remove_documents(outdated)
        
        # 重新添加现有文件（跳过已删除的文件）
        existing_files = [f for f in outdated if os.path.exists(f)]
        
        if existing_files:
            result = self.add_documents(existing_files)
            result["updated_documents"] = len(existing_files)
            result["deleted_documents"] = len(outdated) - len(existing_files)
        else:
            result = {
                "success": True,
                "updated_documents": 0,
                "deleted_documents": len(outdated)
            }
        
        return result
    
    def build_index_from_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        从特定文件列表构建索引。
        
        参数:
            file_paths: 要索引的文件路径列表
            
        返回:
            包含构建结果的字典
        """
        with self.lock:
            self.index_status = IndexStatus.BUILDING
            self.build_progress = {"stage": "parsing", "progress": 0.0}
        
        try:
            timer = Timer()
            timer.start()
            
            logger.info(f"从 {len(file_paths)} 个文件构建索引")
            
            # 解析文件并提取块
            all_chunks = []
            processed = 0
            
            for file_path in file_paths:
                try:
                    chunks = self._parse_file_safely(file_path)
                    if chunks:
                        all_chunks.extend(chunks)
                        
                        # 更新跟踪
                        file_hash = calculate_file_hash(file_path)
                        self.indexed_documents[file_path] = {
                            "hash": file_hash,
                            "chunks": len(chunks),
                            "indexed_at": datetime.now().isoformat(),
                            "file_size": os.path.getsize(file_path)
                        }
                        self.document_hashes[file_path] = file_hash
                    
                    processed += 1
                    progress = (processed / len(file_paths)) * 50
                    
                    with self.lock:
                        self.build_progress.update({
                            "progress": progress,
                            "processed_files": processed,
                            "total_files": len(file_paths)
                        })
                        
                except Exception as e:
                    logger.warning(f"解析 {file_path} 失败: {str(e)}")
                    continue
            
            if not all_chunks:
                raise ValueError("从任何文件中都未提取到文本块")
            
            # 构建向量索引
            with self.lock:
                self.build_progress.update({
                    "stage": "embedding",
                    "progress": 50.0
                })
            
            index_result = self.vector_store.build_index(all_chunks)
            
            build_time = timer.stop()
            
            # 更新状态
            with self.lock:
                self.index_status = IndexStatus.READY
                self.last_build_time = datetime.now()
                self.build_progress = {"stage": "completed", "progress": 100.0}
                
                self.stats.update({
                    "total_documents": len(self.indexed_documents),
                    "total_chunks": len(all_chunks),
                    "last_updated": self.last_build_time.isoformat(),
                    "build_count": self.stats["build_count"] + 1,
                    "total_build_time": self.stats["total_build_time"] + build_time
                })
            
            self._save_index_metadata()
            
            return {
                "success": True,
                "total_files": len(file_paths),
                "processed_files": processed,
                "total_chunks": len(all_chunks),
                "build_time": build_time,
                "index_result": index_result
            }
            
        except Exception as e:
            with self.lock:
                self.index_status = IndexStatus.ERROR
                self.build_progress = {"stage": "error", "error": str(e)}
            raise
    
    def _scan_directory(
        self, 
        directory: str, 
        file_extensions: Optional[Set[str]], 
        recursive: bool
    ) -> List[str]:
        """扫描目录以查找支持的文件。"""
        files = []
        directory_path = Path(directory)
        
        if not directory_path.exists():
            raise ValueError(f"目录不存在: {directory}")
        
        # 如果未指定扩展名，则使用默认扩展名
        if file_extensions is None:
            file_extensions = {
                '.pdf', '.docx', '.doc', '.txt', '.md', '.py', '.js', '.ts',
                '.java', '.c', '.cpp', '.h', '.css', '.html', '.xml', '.json'
            }
        
        # 扫描文件
        pattern = "**/*" if recursive else "*"
        
        for file_path in directory_path.glob(pattern):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in file_extensions:
                    files.append(str(file_path))
        
        return files
    
    def _parse_file_safely(self, file_path: str) -> List[TextChunk]:
        """安全地解析文件并返回文本块。"""
        try:
            parser = get_parser_for_file(file_path)
            if not parser:
                return []
            
            parse_result = parser.parse(file_path)
            
            if not parse_result.success or not parse_result.content:
                return []
            
            # 创建文本块
            chunks = parser.create_text_chunks(
                parse_result.content,
                file_path
            )
            
            return chunks
            
        except Exception as e:
            logger.warning(f"解析 {file_path} 失败: {str(e)}")
            return []
    
    def _apply_filters(self, results: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """将额外的过滤器应用到搜索结果。"""
        filtered_results = []
        
        for result in results:
            # 应用源文件过滤器
            if "source_pattern" in filters:
                import re
                pattern = filters["source_pattern"]
                if not re.search(pattern, result.get("source", "")):
                    continue
            
            # 应用最小得分过滤器
            if "min_score" in filters:
                if result.get("score", 0) < filters["min_score"]:
                    continue
            
            # 应用元数据过滤器
            if "metadata_filters" in filters:
                metadata = result.get("metadata", {})
                skip = False
                
                for key, value in filters["metadata_filters"].items():
                    if key not in metadata or metadata[key] != value:
                        skip = True
                        break
                
                if skip:
                    continue
            
            filtered_results.append(result)
        
        return filtered_results
    
    def _save_index_metadata(self) -> None:
        """将索引元数据保存到磁盘。"""
        import json
        
        metadata = {
            "indexed_documents": self.indexed_documents,
            "document_hashes": self.document_hashes,
            "last_build_time": self.last_build_time.isoformat() if self.last_build_time else None,
            "statistics": self.stats,
            "version": "1.0"
        }
        
        metadata_path = os.path.join(self.index_dir, "index_metadata.json")
        os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
        
        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.warning(f"保存索引元数据失败: {str(e)}")
    
    def _load_index_metadata(self) -> None:
        """从磁盘加载索引元数据。"""
        import json
        
        metadata_path = os.path.join(self.index_dir, "index_metadata.json")
        
        if not os.path.exists(metadata_path):
            return
        
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            self.indexed_documents = metadata.get("indexed_documents", {})
            self.document_hashes = metadata.get("document_hashes", {})
            
            if metadata.get("last_build_time"):
                self.last_build_time = datetime.fromisoformat(metadata["last_build_time"])
            
            self.stats.update(metadata.get("statistics", {}))
            
            # 检查向量存储是否存在
            if self.vector_store.load_index():
                self.index_status = IndexStatus.READY
            
            logger.info(f"加载了 {len(self.indexed_documents)} 个索引文档的元数据")
            
        except Exception as e:
            logger.warning(f"加载索引元数据失败: {str(e)}")
    
    def health_check(self) -> Dict[str, Any]:
        """
        对索引系统执行全面的健康检查。
        
        返回:
            健康检查结果
        """
        try:
            issues = []
            status = "healthy"
            
            # 检查向量存储健康状况
            vector_health = self.vector_store.health_check()
            if vector_health["status"] != "healthy":
                status = "degraded"
                issues.extend(vector_health.get("issues", []))
            
            # 检查嵌入系统健康状况
            embedding_health = embedding_manager.health_check()
            if embedding_health["status"] != "healthy":
                status = "unhealthy"
                issues.append("嵌入系统不健康")
            
            # 检查索引一致性
            if self.indexed_documents:
                missing_files = [
                    path for path in self.indexed_documents.keys()
                    if not os.path.exists(path)
                ]
                if missing_files:
                    status = "degraded"
                    issues.append(f"{len(missing_files)} 个索引文件不再存在")
            
            # 检查索引目录
            if not os.path.exists(self.index_dir):
                status = "unhealthy"
                issues.append("索引目录不存在")
            elif not os.access(self.index_dir, os.W_OK):
                status = "degraded"
                issues.append("索引目录不可写")
            
            return {
                "status": status,
                "issues": issues,
                "index_status": self.index_status.value,
                "statistics": self.get_index_status(),
                "vector_store_health": vector_health,
                "embedding_health": embedding_health
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "issues": ["健康检查失败"]
            }


# 全局索引管理器实例
index_manager = IndexManager()


# 便利函数
def build_index_from_directory(directory: str, **kwargs) -> Dict[str, Any]:
    """使用全局管理器从目录构建索引。"""
    return index_manager.build_index_from_directory(directory, **kwargs)


def search_index(query: str, top_k: int = 5, **kwargs) -> List[Dict[str, Any]]:
    """使用全局管理器搜索索引。"""
    return index_manager.search(query, top_k, **kwargs)


def add_documents_to_index(file_paths: List[str], **kwargs) -> Dict[str, Any]:
    """使用全局管理器将文档添加到索引。"""
    return index_manager.add_documents(file_paths, **kwargs)


def get_index_status() -> Dict[str, Any]:
    """使用全局管理器获取索引状态。"""
    return index_manager.get_index_status()