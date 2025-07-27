"""
MCP 服务器嵌入模型管理

该模块提供嵌入模型加载、管理和向量生成功能，
用于文档索引和搜索。
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional, Union
import time
import threading
import os
import pickle
from dataclasses import dataclass
from pathlib import Path

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

from ..config import config
from ..types import EmbeddingModelInfo
from ..exceptions import EmbeddingModelError
from ..utils import Timer, measure_memory_usage

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """嵌入生成结果。"""
    
    embeddings: np.ndarray
    model_name: str
    dimension: int
    processing_time: float
    text_count: int
    memory_usage: Dict[str, Any] = None


class EmbeddingModelManager:
    """
    管理文本向量化的嵌入模型。
    
    此类处理不同嵌入模型的加载、缓存和使用，
    用于生成文本的向量表示。
    """
    
    def __init__(self):
        """初始化嵌入模型管理器。"""
        self.models: Dict[str, SentenceTransformer] = {} # pyright: ignore[reportInvalidTypeForm]
        self.model_info: Dict[str, EmbeddingModelInfo] = {}
        self.current_model_name: str = config.embedding.DEFAULT_MODEL
        self.lock = threading.Lock()
        
        # 模型缓存目录
        self.cache_dir = Path(config.index.INDEX_DIR) / "model_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 统计信息
        self.embedding_stats = {
            "total_embeddings": 0,
            "total_texts": 0,
            "total_time": 0.0,
            "average_time_per_text": 0.0,
            "models_loaded": 0
        }
        
        # 初始化可用模型信息
        self._initialize_model_info()
        
        # 在启动时尝试从缓存加载默认模型
        self._load_cached_models()
    
    def _initialize_model_info(self) -> None:
        """初始化可用模型的信息。"""
        
        # 定义已知模型规格
        model_specs = {
            "paraphrase-multilingual-MiniLM-L12-v2": EmbeddingModelInfo(
                name="paraphrase-multilingual-MiniLM-L12-v2",
                dimension=384,
                max_sequence_length=512,
                multilingual=True,
                description="为语义相似度优化的多语言模型"
            ),
            "all-MiniLM-L6-v2": EmbeddingModelInfo(
                name="all-MiniLM-L6-v2",
                dimension=384,
                max_sequence_length=512,
                multilingual=False,
                description="用于通用嵌入的快速英语模型"
            ),
            "all-mpnet-base-v2": EmbeddingModelInfo(
                name="all-mpnet-base-v2",
                dimension=768,
                max_sequence_length=514,
                multilingual=False,
                description="高质量的英语模型，具有更大的维度"
            ),
            "paraphrase-MiniLM-L6-v2": EmbeddingModelInfo(
                name="paraphrase-MiniLM-L6-v2",
                dimension=384,
                max_sequence_length=512,
                multilingual=False,
                description="为释义检测优化的英语模型"
            )
        }
        
        # 添加可用列表中的模型
        for model_name in config.embedding.AVAILABLE_MODELS:
            if model_name in model_specs:
                self.model_info[model_name] = model_specs[model_name]
            else:
                # 为未知模型创建默认信息
                self.model_info[model_name] = EmbeddingModelInfo(
                    name=model_name,
                    dimension=384,  # 默认维度
                    max_sequence_length=512,
                    multilingual=False,
                    description="未知模型"
                )
    
    def _get_model_cache_path(self, model_name: str) -> Path:
        """获取模型缓存文件路径。"""
        # 将模型名称转换为安全的文件名
        safe_name = model_name.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{safe_name}.cache"
    
    def _save_model_to_cache(self, model_name: str, model: SentenceTransformer) -> None: # pyright: ignore[reportInvalidTypeForm]
        """将模型保存到磁盘缓存。"""
        try:
            cache_path = self._get_model_cache_path(model_name)
            
            # 保存模型到指定目录
            model_dir = self.cache_dir / f"{model_name.replace('/', '_').replace('\\', '_')}_model"
            model.save(str(model_dir))
            
            # 保存元数据
            metadata = {
                "model_name": model_name,
                "cache_time": time.time(),
                "model_dir": str(model_dir),
                "dimension": model.get_sentence_embedding_dimension() if hasattr(model, 'get_sentence_embedding_dimension') else 384
            }
            
            with open(cache_path, 'wb') as f:
                pickle.dump(metadata, f)
            
            logger.info(f"模型 {model_name} 已保存到缓存: {cache_path}")
            
        except Exception as e:
            logger.warning(f"保存模型缓存失败 {model_name}: {str(e)}")
    
    def _load_model_from_cache(self, model_name: str) -> Optional[SentenceTransformer]: # pyright: ignore[reportInvalidTypeForm]
        """从磁盘缓存加载模型。"""
        try:
            cache_path = self._get_model_cache_path(model_name)
            
            if not cache_path.exists():
                return None
            
            # 加载元数据
            with open(cache_path, 'rb') as f:
                metadata = pickle.load(f)
            
            model_dir = Path(metadata["model_dir"])
            if not model_dir.exists():
                logger.warning(f"模型目录不存在: {model_dir}")
                return None
            
            # 加载模型
            if SentenceTransformer is None:
                return None
                
            model = SentenceTransformer(str(model_dir))
            
            logger.info(f"从缓存加载模型 {model_name}: {cache_path}")
            return model
            
        except Exception as e:
            logger.warning(f"从缓存加载模型失败 {model_name}: {str(e)}")
            return None
    
    def _load_cached_models(self) -> None:
        """启动时加载缓存的模型。"""
        try:
            # 尝试加载默认模型
            if self.current_model_name:
                cached_model = self._load_model_from_cache(self.current_model_name)
                if cached_model:
                    with self.lock:
                        self.models[self.current_model_name] = cached_model
                        self.embedding_stats["models_loaded"] += 1
                    logger.info(f"启动时从缓存加载默认模型: {self.current_model_name}")
        except Exception as e:
            logger.warning(f"启动时加载缓存模型失败: {str(e)}")
    
    def _cleanup_old_cache(self, max_age_days: int = 30) -> None:
        """清理旧的缓存文件。"""
        try:
            current_time = time.time()
            max_age_seconds = max_age_days * 24 * 3600
            
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    with open(cache_file, 'rb') as f:
                        metadata = pickle.load(f)
                    
                    age = current_time - metadata.get("cache_time", 0)
                    if age > max_age_seconds:
                        # 删除缓存文件和模型目录
                        cache_file.unlink()
                        model_dir = Path(metadata.get("model_dir", ""))
                        if model_dir.exists():
                            import shutil
                            shutil.rmtree(model_dir)
                        logger.info(f"清理旧缓存: {cache_file}")
                        
                except Exception as e:
                    logger.warning(f"清理缓存文件失败 {cache_file}: {str(e)}")
                    
        except Exception as e:
            logger.warning(f"清理缓存失败: {str(e)}")
    
    def load_model(self, model_name: Optional[str] = None) -> SentenceTransformer: # pyright: ignore[reportInvalidTypeForm]
        """
        加载嵌入模型。
        
        参数:
            model_name: 要加载的模型名称（如果为 None 则使用默认模型）
            
        返回:
            加载的 SentenceTransformer 模型
            
        引发:
            EmbeddingModelError: 如果模型加载失败
        """
        if SentenceTransformer is None:
            raise EmbeddingModelError(
                model_name="sentence-transformers",
                error_details="sentence-transformers 库未安装"
            )
        
        model_name = model_name or self.current_model_name
        
        with self.lock:
            # 如果模型已加载，则返回缓存的模型
            if model_name in self.models:
                logger.debug(f"使用内存缓存模型: {model_name}")
                return self.models[model_name]
            
            # 尝试从磁盘缓存加载
            cached_model = self._load_model_from_cache(model_name)
            if cached_model:
                self.models[model_name] = cached_model
                self.embedding_stats["models_loaded"] += 1
                logger.info(f"从磁盘缓存加载模型: {model_name}")
                return cached_model
            
            # 加载新模型
            try:
                logger.info(f"正在下载并加载嵌入模型: {model_name}")
                timer = Timer()
                timer.start()
                
                model = SentenceTransformer(model_name)
                
                load_time = timer.stop()
                logger.info(f"模型 {model_name} 在 {load_time:.2f} 秒内加载完成")
                
                # 缓存模型到内存
                self.models[model_name] = model
                self.embedding_stats["models_loaded"] += 1
                
                # 保存到磁盘缓存
                self._save_model_to_cache(model_name, model)
                
                # 如果可用，使用实际维度更新模型信息
                if hasattr(model, 'get_sentence_embedding_dimension'):
                    actual_dim = model.get_sentence_embedding_dimension()
                    if model_name in self.model_info:
                        self.model_info[model_name].dimension = actual_dim
                
                return model
                
            except Exception as e:
                error_msg = f"加载模型 {model_name} 失败: {str(e)}"
                logger.error(error_msg)
                raise EmbeddingModelError(
                    model_name=model_name,
                    error_details=error_msg
                )
    
    def generate_embeddings(
        self,
        texts: Union[str, List[str]],
        model_name: Optional[str] = None,
        batch_size: Optional[int] = None,
        show_progress: bool = False
    ) -> EmbeddingResult:
        """
        为文本生成嵌入向量。
        
        参数:
            texts: 要嵌入的文本或文本列表
            model_name: 要使用的模型（如果为 None 则使用默认模型）
            batch_size: 处理的批次大小（如果为 None 则使用配置默认值）
            show_progress: 是否显示进度条
            
        返回:
            包含生成嵌入向量和元数据的 EmbeddingResult
            
        引发:
            EmbeddingModelError: 如果嵌入向量生成失败
        """
        # 确保 texts 是列表
        if isinstance(texts, str):
            texts = [texts]
        
        if not texts:
            raise EmbeddingModelError(
                model_name=model_name or self.current_model_name,
                error_details="未提供用于嵌入的文本"
            )
        
        model_name = model_name or self.current_model_name
        batch_size = batch_size or config.embedding.BATCH_SIZE
        
        try:
            # 加载模型
            model = self.load_model(model_name)
            
            # 生成嵌入向量
            timer = Timer()
            timer.start()
            
            # 嵌入前测量内存
            memory_before = measure_memory_usage()
            
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True
            )
            
            processing_time = timer.stop()
            
            # 嵌入后测量内存
            memory_after = measure_memory_usage()
            
            # 更新统计信息
            self._update_stats(len(texts), processing_time)
            
            # 获取模型维度
            dimension = embeddings.shape[1] if len(embeddings.shape) > 1 else len(embeddings)
            
            logger.info(
                f"使用 {model_name} 生成了 {len(texts)} 个嵌入向量 "
                f"耗时 {processing_time:.2f} 秒 (维度: {dimension})"
            )
            
            return EmbeddingResult(
                embeddings=embeddings,
                model_name=model_name,
                dimension=dimension,
                processing_time=processing_time,
                text_count=len(texts),
                memory_usage={
                    "before": memory_before,
                    "after": memory_after
                }
            )
            
        except Exception as e:
            error_msg = f"嵌入向量生成失败: {str(e)}"
            logger.error(error_msg)
            raise EmbeddingModelError(
                model_name=model_name,
                error_details=error_msg
            )
    
    def generate_single_embedding(
        self,
        text: str,
        model_name: Optional[str] = None
    ) -> np.ndarray:
        """
        为单个文本生成嵌入向量。
        
        参数:
            text: 要嵌入的文本
            model_name: 要使用的模型（如果为 None 则使用默认模型）
            
        返回:
            作为 numpy 数组的嵌入向量
        """
        result = self.generate_embeddings([text], model_name=model_name)
        return result.embeddings[0]
    
    def compute_similarity(
        self,
        text1: str,
        text2: str,
        model_name: Optional[str] = None
    ) -> float:
        """
        计算两个文本之间的余弦相似度。
        
        参数:
            text1: 第一个文本
            text2: 第二个文本
            model_name: 要使用的模型（如果为 None 则使用默认模型）
            
        返回:
            介于 0 和 1 之间的余弦相似度得分
        """
        embeddings = self.generate_embeddings([text1, text2], model_name=model_name)
        
        # 计算余弦相似度
        vec1, vec2 = embeddings.embeddings[0], embeddings.embeddings[1]
        
        # 归一化向量
        vec1_norm = vec1 / np.linalg.norm(vec1)
        vec2_norm = vec2 / np.linalg.norm(vec2)
        
        # 计算余弦相似度
        similarity = np.dot(vec1_norm, vec2_norm)
        
        return float(similarity)
    
    def find_most_similar(
        self,
        query_text: str,
        candidate_texts: List[str],
        model_name: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        查找与查询最相似的文本。
        
        参数:
            query_text: 查询文本
            candidate_texts: 候选文本列表
            model_name: 要使用的模型（如果为 None 则使用默认模型）
            top_k: 要返回的顶部结果数量
            
        返回:
            包含得分的相似度结果列表
        """
        all_texts = [query_text] + candidate_texts
        embeddings = self.generate_embeddings(all_texts, model_name=model_name)
        
        query_embedding = embeddings.embeddings[0]
        candidate_embeddings = embeddings.embeddings[1:]
        
        # 归一化嵌入向量
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        candidate_norms = candidate_embeddings / np.linalg.norm(candidate_embeddings, axis=1, keepdims=True)
        
        # 计算相似度
        similarities = np.dot(candidate_norms, query_norm)
        
        # 获取前 k 个结果
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for i, idx in enumerate(top_indices):
            results.append({
                "rank": i + 1,
                "text": candidate_texts[idx],
                "similarity": float(similarities[idx]),
                "index": int(idx)
            })
        
        return results
    
    def get_model_info(self, model_name: Optional[str] = None) -> EmbeddingModelInfo:
        """
        获取模型信息。
        
        参数:
            model_name: 模型名称（如果为 None 则使用默认模型）
            
        返回:
            模型信息
        """
        model_name = model_name or self.current_model_name
        return self.model_info.get(model_name, EmbeddingModelInfo(
            name=model_name,
            dimension=384,
            max_sequence_length=512,
            multilingual=False,
            description="未知模型"
        ))
    
    def list_available_models(self) -> List[str]:
        """
        列出所有可用模型。
        
        返回:
            可用模型名称列表
        """
        return list(self.model_info.keys())
    
    def set_default_model(self, model_name: str) -> None:
        """
        设置默认模型。
        
        参数:
            model_name: 要设置为默认的模型名称
            
        引发:
            EmbeddingModelError: 如果模型不可用
        """
        if model_name not in self.model_info:
            raise EmbeddingModelError(
                model_name=model_name,
                error_details=f"模型 {model_name} 不在可用模型列表中"
            )
        
        self.current_model_name = model_name
        logger.info(f"默认模型设置为: {model_name}")
    
    def unload_model(self, model_name: str) -> None:
        """
        从内存中卸载模型。
        
        参数:
            model_name: 要卸载的模型名称
        """
        with self.lock:
            if model_name in self.models:
                del self.models[model_name]
                logger.info(f"已卸载模型: {model_name}")
    
    def unload_all_models(self) -> None:
        """从内存中卸载所有模型。"""
        with self.lock:
            self.models.clear()
            logger.info("已卸载所有模型")
    
    def clear_model_cache(self, model_name: Optional[str] = None) -> None:
        """
        清理模型缓存。
        
        参数:
            model_name: 要清理的模型名称，如果为 None 则清理所有缓存
        """
        try:
            if model_name:
                # 清理特定模型的缓存
                cache_path = self._get_model_cache_path(model_name)
                if cache_path.exists():
                    with open(cache_path, 'rb') as f:
                        metadata = pickle.load(f)
                    
                    # 删除缓存文件
                    cache_path.unlink()
                    
                    # 删除模型目录
                    model_dir = Path(metadata.get("model_dir", ""))
                    if model_dir.exists():
                        import shutil
                        shutil.rmtree(model_dir)
                    
                    logger.info(f"清理模型缓存: {model_name}")
            else:
                # 清理所有缓存
                for cache_file in self.cache_dir.glob("*.cache"):
                    try:
                        with open(cache_file, 'rb') as f:
                            metadata = pickle.load(f)
                        
                        # 删除缓存文件
                        cache_file.unlink()
                        
                        # 删除模型目录
                        model_dir = Path(metadata.get("model_dir", ""))
                        if model_dir.exists():
                            import shutil
                            shutil.rmtree(model_dir)
                    except Exception as e:
                        logger.warning(f"清理缓存文件失败 {cache_file}: {str(e)}")
                
                logger.info("清理所有模型缓存")
                
        except Exception as e:
            logger.error(f"清理缓存失败: {str(e)}")

    def get_cache_info(self) -> Dict[str, Any]:
        """
        获取缓存信息。
        
        返回:
            包含缓存统计信息的字典
        """
        cache_info = {
            "cache_dir": str(self.cache_dir),
            "cached_models": [],
            "total_cache_size": 0,
            "memory_loaded_models": list(self.models.keys())
        }
        
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    with open(cache_file, 'rb') as f:
                        metadata = pickle.load(f)
                    
                    model_dir = Path(metadata.get("model_dir", ""))
                    cache_size = 0
                    if model_dir.exists():
                        for file_path in model_dir.rglob("*"):
                            if file_path.is_file():
                                cache_size += file_path.stat().st_size
                    
                    cache_info["cached_models"].append({
                        "model_name": metadata.get("model_name", "unknown"),
                        "cache_time": metadata.get("cache_time", 0),
                        "cache_size_mb": cache_size / (1024 * 1024),
                        "dimension": metadata.get("dimension", "unknown")
                    })
                    
                    cache_info["total_cache_size"] += cache_size
                    
                except Exception as e:
                    logger.warning(f"读取缓存信息失败 {cache_file}: {str(e)}")
            
            cache_info["total_cache_size_mb"] = cache_info["total_cache_size"] / (1024 * 1024)
            
        except Exception as e:
            logger.warning(f"获取缓存信息失败: {str(e)}")
        
        return cache_info
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """
        获取内存使用信息。
        
        返回:
            包含内存使用统计信息的字典
        """
        return {
            "loaded_models": list(self.models.keys()),
            "model_count": len(self.models),
            "current_memory": measure_memory_usage(),
            "default_model": self.current_model_name
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取嵌入向量生成统计信息。
        
        返回:
            包含统计信息的字典
        """
        stats = self.embedding_stats.copy()
        
        # 计算每个文本的平均时间
        if stats["total_texts"] > 0:
            stats["average_time_per_text"] = stats["total_time"] / stats["total_texts"]
        
        return stats
    
    def _update_stats(self, text_count: int, processing_time: float) -> None:
        """更新嵌入统计信息。"""
        self.embedding_stats["total_embeddings"] += 1
        self.embedding_stats["total_texts"] += text_count
        self.embedding_stats["total_time"] += processing_time
    
    def reset_statistics(self) -> None:
        """重置所有统计信息。"""
        self.embedding_stats = {
            "total_embeddings": 0,
            "total_texts": 0,
            "total_time": 0.0,
            "average_time_per_text": 0.0,
            "models_loaded": len(self.models)
        }
    
    def health_check(self) -> Dict[str, Any]:
        """
        对嵌入系统执行健康检查。
        
        返回:
            健康检查结果
        """
        try:
            # 使用默认模型测试嵌入向量生成
            test_text = "这是用于健康检查的测试句子。"
            result = self.generate_embeddings([test_text])
            
            return {
                "status": "healthy",
                "default_model": self.current_model_name,
                "embedding_dimension": result.dimension,
                "test_embedding_time": result.processing_time,
                "loaded_models": list(self.models.keys()),
                "available_models": self.list_available_models()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "default_model": self.current_model_name,
                "loaded_models": list(self.models.keys()),
                "available_models": self.list_available_models()
            }


# 全局嵌入模型管理器实例
embedding_manager = EmbeddingModelManager()


# 便利函数
def generate_embeddings(
    texts: Union[str, List[str]],
    model_name: Optional[str] = None,
    **kwargs
) -> EmbeddingResult:
    """
    使用全局管理器生成嵌入向量。
    
    参数:
        texts: 要嵌入的文本或文本列表
        model_name: 要使用的模型（如果为 None 则使用默认模型）
        **kwargs: 嵌入向量生成的附加参数
        
    返回:
        包含生成嵌入向量的 EmbeddingResult
    """
    return embedding_manager.generate_embeddings(texts, model_name, **kwargs)


def generate_single_embedding(
    text: str,
    model_name: Optional[str] = None
) -> np.ndarray:
    """
    使用全局管理器为单个文本生成嵌入向量。
    
    参数:
        text: 要嵌入的文本
        model_name: 要使用的模型（如果为 None 则使用默认模型）
        
    返回:
        作为 numpy 数组的嵌入向量
    """
    return embedding_manager.generate_single_embedding(text, model_name)


def compute_similarity(
    text1: str,
    text2: str,
    model_name: Optional[str] = None
) -> float:
    """
    使用全局管理器计算两个文本之间的余弦相似度。
    
    参数:
        text1: 第一个文本
        text2: 第二个文本
        model_name: 要使用的模型（如果为 None 则使用默认模型）
        
    返回:
        介于 0 和 1 之间的余弦相似度得分
    """
    return embedding_manager.compute_similarity(text1, text2, model_name)