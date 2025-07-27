"""
MCP 服务器向量存储管理

该模块使用 FAISS 提供向量存储和检索功能，
用于高效的相似度搜索和文档索引。
"""

import os
import pickle
import logging
import numpy as np
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

try:
    import faiss
except ImportError:
    faiss = None

from ..config import config
from ..types import TextChunk
from ..exceptions import IndexNotFoundError, IndexCorruptedError
from ..utils import Timer
from .embeddings import embedding_manager

logger = logging.getLogger(__name__)


class VectorStore:
    """
    使用 FAISS 管理向量存储和检索。
    
    该类处理文档嵌入的存储、搜索索引的构建，
    以及执行高效的相似度搜索操作。
    """
    
    def __init__(self, index_dir: Optional[str] = None):
        """
        初始化向量存储。
        
        参数:
            index_dir: 存储索引文件的目录（如果为 None 则使用配置默认值）
        """
        self.index_dir = index_dir or config.index.INDEX_DIR
        self.faiss_index = None
        self.document_store: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
        self.index_loaded = False
        
        # 文件路径
        self.index_path = os.path.join(self.index_dir, config.index.FAISS_INDEX_FILE)
        self.store_path = os.path.join(self.index_dir, config.index.DOCUMENT_STORE_FILE)
        self.metadata_path = os.path.join(self.index_dir, config.index.METADATA_FILE)
        
        # 确保索引目录存在
        os.makedirs(self.index_dir, exist_ok=True)
        
        # 统计信息
        self.stats = {
            "total_documents": 0,
            "total_chunks": 0,
            "index_size_mb": 0,
            "last_updated": None,
            "build_time": 0.0,
            "search_count": 0,
            "total_search_time": 0.0
        }
    
    def build_index(
        self,
        text_chunks: List[TextChunk],
        model_name: Optional[str] = None,
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        从文本块构建向量索引。
        
        参数:
            text_chunks: 要索引的文本块列表
            model_name: 要使用的嵌入模型
            show_progress: 嵌入过程中是否显示进度
            
        返回:
            包含构建结果和统计信息的字典
            
        引发:
            Exception: 如果索引构建失败
        """
        if faiss is None:
            raise ImportError("FAISS 库未安装。使用以下命令安装: pip install faiss-cpu")
        
        if not text_chunks:
            raise ValueError("未提供用于索引的文本块")
        
        timer = Timer()
        timer.start()
        
        try:
            logger.info(f"从 {len(text_chunks)} 个文本块构建索引")
            
            # 提取文本用于嵌入
            texts = [chunk.content for chunk in text_chunks]
            
            # 生成嵌入向量
            embedding_result = embedding_manager.generate_embeddings(
                texts,
                model_name=model_name,
                show_progress=show_progress
            )
            
            # 创建 FAISS 索引
            dimension = embedding_result.dimension
            self.faiss_index = faiss.IndexFlatL2(dimension)
            
            # 将嵌入向量添加到索引
            embeddings_array = embedding_result.embeddings.astype('float32')
            self.faiss_index.add(embeddings_array)
            
            # 存储文档信息
            self.document_store = []
            for i, chunk in enumerate(text_chunks):
                doc_info = {
                    "id": i,
                    "content": chunk.content,
                    "source": chunk.source,
                    "metadata": chunk.metadata,
                    "chunk_id": chunk.chunk_id
                }
                self.document_store.append(doc_info)
            
            # 更新元数据
            self.metadata = {
                "dimension": dimension,
                "model_name": embedding_result.model_name,
                "total_documents": len(set(chunk.source for chunk in text_chunks)),
                "total_chunks": len(text_chunks),
                "created_at": datetime.now().isoformat(),
                "embedding_time": embedding_result.processing_time,
                "index_version": "1.0"
            }
            
            # 将索引保存到磁盘
            self._save_index()
            
            build_time = timer.stop()
            
            # 更新统计信息
            self.stats.update({
                "total_documents": self.metadata["total_documents"],
                "total_chunks": self.metadata["total_chunks"],
                "last_updated": self.metadata["created_at"],
                "build_time": build_time,
                "index_size_mb": self._get_index_size_mb()
            })
            
            self.index_loaded = True
            
            logger.info(f"索引构建成功，耗时 {build_time:.2f} 秒")
            
            return {
                "success": True,
                "total_documents": self.metadata["total_documents"],
                "total_chunks": self.metadata["total_chunks"],
                "dimension": dimension,
                "model_name": embedding_result.model_name,
                "build_time": build_time,
                "embedding_time": embedding_result.processing_time,
                "index_size_mb": self.stats["index_size_mb"]
            }
            
        except Exception as e:
            logger.error(f"索引构建失败: {str(e)}")
            raise
    
    def load_index(self) -> bool:
        """
        从磁盘加载现有索引。
        
        返回:
            如果索引成功加载则返回 True，否则返回 False
            
        引发:
            IndexNotFoundError: 如果索引文件不存在
            IndexCorruptedError: 如果索引文件已损坏
        """
        if faiss is None:
            raise ImportError("FAISS 库未安装")
        
        try:
            # 检查索引文件是否存在
            if not all(os.path.exists(path) for path in [self.index_path, self.store_path]):
                return False
            
            logger.info("从磁盘加载现有索引")
            
            # 加载 FAISS 索引
            self.faiss_index = faiss.read_index(self.index_path)
            
            # 加载文档存储
            with open(self.store_path, 'rb') as f:
                self.document_store = pickle.load(f)
            
            # 如果存在则加载元数据
            if os.path.exists(self.metadata_path):
                with open(self.metadata_path, 'r') as f:
                    self.metadata = json.load(f)
            else:
                # 如果文件不存在则创建基本元数据
                self.metadata = {
                    "total_chunks": len(self.document_store),
                    "dimension": self.faiss_index.d if self.faiss_index else 0,
                    "created_at": datetime.now().isoformat()
                }
            
            # 更新统计信息
            self.stats.update({
                "total_chunks": len(self.document_store),
                "total_documents": len(set(doc["source"] for doc in self.document_store)),
                "index_size_mb": self._get_index_size_mb(),
                "last_updated": self.metadata.get("created_at")
            })
            
            self.index_loaded = True
            logger.info(f"索引已加载: {self.stats['total_chunks']} 个块, {self.stats['total_documents']} 个文档")
            
            return True
            
        except Exception as e:
            error_msg = f"加载索引失败: {str(e)}"
            logger.error(error_msg)
            raise IndexCorruptedError(
                index_path=self.index_dir,
                error_details=error_msg
            )
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        model_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        使用向量相似度搜索相似文档。
        
        参数:
            query: 搜索查询文本
            top_k: 要返回的顶部结果数量
            model_name: 用于查询的嵌入模型
            
        返回:
            包含得分和元数据的搜索结果列表
            
        引发:
            IndexNotFoundError: 如果未加载索引
        """
        if not self.index_loaded or self.faiss_index is None:
            if not self.load_index():
                raise IndexNotFoundError()
        
        timer = Timer()
        timer.start()
        
        try:
            # 生成查询嵌入向量
            query_embedding = embedding_manager.generate_single_embedding(query, model_name)
            query_vector = np.array([query_embedding]).astype('float32')
            
            # 执行搜索
            distances, indices = self.faiss_index.search(query_vector, min(top_k, len(self.document_store)))
            
            # 格式化结果
            results = []
            for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                if idx < len(self.document_store):
                    doc_info = self.document_store[idx]
                    
                    # 将距离转换为相似度得分
                    similarity = float(1 / (1 + distance))
                    
                    result = {
                        "rank": i + 1,
                        "score": similarity,
                        "distance": float(distance),
                        "content": doc_info["content"],
                        "source": doc_info["source"],
                        "metadata": doc_info.get("metadata", {}),
                        "chunk_id": doc_info.get("chunk_id", idx)
                    }
                    results.append(result)
            
            search_time = timer.stop()
            
            # 更新搜索统计信息
            self.stats["search_count"] += 1
            self.stats["total_search_time"] += search_time
            
            logger.info(f"搜索完成，耗时 {search_time:.3f} 秒，找到 {len(results)} 个结果")
            
            return results
            
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            raise
    
    def add_documents(
        self,
        text_chunks: List[TextChunk],
        model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        将新文档添加到现有索引中。
        
        参数:
            text_chunks: 要添加的文本块列表
            model_name: 要使用的嵌入模型
            
        返回:
            包含操作结果的字典
        """
        if not self.index_loaded or self.faiss_index is None:
            # 如果索引不存在，则构建一个新索引
            return self.build_index(text_chunks, model_name)
        
        try:
            logger.info(f"向现有索引中添加 {len(text_chunks)} 个新块")
            
            # 为新块生成嵌入向量
            texts = [chunk.content for chunk in text_chunks]
            embedding_result = embedding_manager.generate_embeddings(texts, model_name)
            
            # 添加到 FAISS 索引
            embeddings_array = embedding_result.embeddings.astype('float32')
            self.faiss_index.add(embeddings_array)
            
            # 添加到文档存储
            start_id = len(self.document_store)
            for i, chunk in enumerate(text_chunks):
                doc_info = {
                    "id": start_id + i,
                    "content": chunk.content,
                    "source": chunk.source,
                    "metadata": chunk.metadata,
                    "chunk_id": chunk.chunk_id
                }
                self.document_store.append(doc_info)
            
            # 更新元数据
            self.metadata["total_chunks"] = len(self.document_store)
            self.metadata["total_documents"] = len(set(doc["source"] for doc in self.document_store))
            self.metadata["last_updated"] = datetime.now().isoformat()
            
            # 保存更新后的索引
            self._save_index()
            
            # 更新统计信息
            self.stats.update({
                "total_chunks": self.metadata["total_chunks"],
                "total_documents": self.metadata["total_documents"],
                "last_updated": self.metadata["last_updated"],
                "index_size_mb": self._get_index_size_mb()
            })
            
            logger.info(f"成功向索引中添加 {len(text_chunks)} 个块")
            
            return {
                "success": True,
                "added_chunks": len(text_chunks),
                "total_chunks": self.metadata["total_chunks"],
                "total_documents": self.metadata["total_documents"]
            }
            
        except Exception as e:
            logger.error(f"添加文档失败: {str(e)}")
            raise
    
    def remove_documents(self, source_paths: List[str]) -> Dict[str, Any]:
        """
        按源路径从索引中删除文档。
        
        注意: 此操作需要重建索引。
        
        参数:
            source_paths: 要删除的源文件路径列表
            
        返回:
            包含操作结果的字典
        """
        if not self.index_loaded:
            raise IndexNotFoundError()
        
        try:
            logger.info(f"从 {len(source_paths)} 个源中删除文档")
            
            # 过滤掉指定源的文档
            original_count = len(self.document_store)
            filtered_docs = [
                doc for doc in self.document_store
                if doc["source"] not in source_paths
            ]
            
            removed_count = original_count - len(filtered_docs)
            
            if removed_count == 0:
                return {
                    "success": True,
                    "removed_chunks": 0,
                    "message": "未找到指定源的文档"
                }
            
            # 使用剩余文档重建索引
            if filtered_docs:
                # 转换回 TextChunk 对象
                text_chunks = []
                for doc in filtered_docs:
                    chunk = TextChunk(
                        content=doc["content"],
                        chunk_id=doc.get("chunk_id", 0),
                        source=doc["source"],
                        metadata=doc.get("metadata", {})
                    )
                    text_chunks.append(chunk)
                
                # 重建索引
                build_result = self.build_index(text_chunks)
                build_result["removed_chunks"] = removed_count
                return build_result
            else:
                # 没有剩余文档，清除索引
                self.clear_index()
                return {
                    "success": True,
                    "removed_chunks": removed_count,
                    "total_chunks": 0,
                    "total_documents": 0,
                    "message": "所有文档已删除，索引已清除"
                }
                
        except Exception as e:
            logger.error(f"删除文档失败: {str(e)}")
            raise
    
    def clear_index(self) -> None:
        """清除整个索引并删除所有数据。"""
        try:
            logger.info("清除向量索引")
            
            # 清除内存中的数据
            self.faiss_index = None
            self.document_store = []
            self.metadata = {}
            self.index_loaded = False
            
            # 删除索引文件
            for file_path in [self.index_path, self.store_path, self.metadata_path]:
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            # 重置统计信息
            self.stats.update({
                "total_documents": 0,
                "total_chunks": 0,
                "index_size_mb": 0,
                "last_updated": None
            })
            
            logger.info("索引清除成功")
            
        except Exception as e:
            logger.error(f"清除索引失败: {str(e)}")
            raise
    
    def get_document_by_source(self, source_path: str) -> List[Dict[str, Any]]:
        """
        获取特定源文档的所有块。
        
        参数:
            source_path: 源文档的路径
            
        返回:
            来自指定源的文档块列表
        """
        if not self.index_loaded:
            if not self.load_index():
                return []
        
        return [doc for doc in self.document_store if doc["source"] == source_path]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取向量存储统计信息。
        
        返回:
            包含统计信息和元数据的字典
        """
        stats = self.stats.copy()
        
        # 添加计算的统计信息
        if stats["search_count"] > 0:
            stats["average_search_time"] = stats["total_search_time"] / stats["search_count"]
        else:
            stats["average_search_time"] = 0.0
        
        # 添加元数据
        stats.update({
            "index_loaded": self.index_loaded,
            "metadata": self.metadata,
            "index_directory": self.index_dir
        })
        
        return stats
    
    def _save_index(self) -> None:
        """将索引和文档存储保存到磁盘。"""
        try:
            # 保存 FAISS 索引
            faiss.write_index(self.faiss_index, self.index_path)
            
            # 保存文档存储
            with open(self.store_path, 'wb') as f:
                pickle.dump(self.document_store, f)
            
            # 保存元数据
            with open(self.metadata_path, 'w') as f:
                json.dump(self.metadata, f, indent=2)
            
            logger.debug("索引已保存到磁盘")
            
        except Exception as e:
            logger.error(f"保存索引失败: {str(e)}")
            raise
    
    def _get_index_size_mb(self) -> float:
        """计算索引文件的总大小（MB）。"""
        total_size = 0
        
        for file_path in [self.index_path, self.store_path, self.metadata_path]:
            if os.path.exists(file_path):
                total_size += os.path.getsize(file_path)
        
        return total_size / (1024 * 1024)  # 转换为 MB
    
    def health_check(self) -> Dict[str, Any]:
        """
        对向量存储执行健康检查。
        
        返回:
            健康检查结果
        """
        try:
            status = "healthy"
            issues = []
            
            # 检查 FAISS 是否可用
            if faiss is None:
                status = "unhealthy"
                issues.append("FAISS 库未安装")
            
            # 检查索引目录是否存在且可写
            if not os.path.exists(self.index_dir):
                try:
                    os.makedirs(self.index_dir, exist_ok=True)
                except Exception:
                    status = "unhealthy"
                    issues.append("无法创建索引目录")
            
            # 检查索引是否可以加载
            if self.index_loaded or self.load_index():
                # 如果索引已加载则测试搜索功能
                try:
                    if self.document_store:
                        self.search("测试查询", top_k=1)
                except Exception as e:
                    status = "degraded"
                    issues.append(f"搜索功能受损: {str(e)}")
            else:
                issues.append("无可用索引")
            
            return {
                "status": status,
                "issues": issues,
                "statistics": self.get_statistics(),
                "faiss_available": faiss is not None,
                "index_directory_writable": os.access(self.index_dir, os.W_OK)
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "issues": ["健康检查失败"],
                "faiss_available": faiss is not None
            }


# 全局向量存储实例
vector_store = VectorStore()