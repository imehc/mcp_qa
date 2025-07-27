"""
MCP 服务器高级搜索引擎

该模块提供复杂的搜索功能，包括语义搜索、混合搜索和结果优化。
"""

import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from ..types import SearchResult
from ..exceptions import SearchError
from ..utils import Timer
from .storage import vector_store
from .manager import index_manager

logger = logging.getLogger(__name__)


class SearchType(Enum):
    """可用的搜索类型。"""
    
    SEMANTIC = "semantic"        # 向量相似度搜索
    KEYWORD = "keyword"          # 传统关键词搜索
    HYBRID = "hybrid"           # 语义和关键词的组合
    FUZZY = "fuzzy"             # 模糊匹配搜索


@dataclass
class SearchQuery:
    """表示带有选项的搜索查询。"""
    
    text: str
    search_type: SearchType = SearchType.SEMANTIC
    top_k: int = 5
    min_score: float = 0.0
    filters: Optional[Dict[str, Any]] = None
    boost_factors: Optional[Dict[str, float]] = None
    include_metadata: bool = True
    deduplicate: bool = True


class SearchEngine:
    """
    用于文档检索的高级搜索引擎。
    
    该类提供多种搜索策略和结果优化技术，用于查找相关文档。
    """
    
    def __init__(self):
        """初始化搜索引擎。"""
        self.search_stats = {
            "total_searches": 0,
            "semantic_searches": 0,
            "keyword_searches": 0,
            "hybrid_searches": 0,
            "fuzzy_searches": 0,
            "total_search_time": 0.0,
            "average_search_time": 0.0
        }
        
        # 搜索优化设置
        self.max_results_per_document = 3  # 限制同一文档的结果数量
        self.score_threshold = 0.1  # 最小得分阈值
        self.fuzzy_threshold = 0.8  # 模糊匹配阈值
        
        # 查询预处理设置
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'shall', 'this', 'that',
            'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
        }
    
    def search(self, query: SearchQuery) -> List[SearchResult]:
        """
        使用指定的查询执行搜索。
        
        参数:
            query: 带有选项的搜索查询
            
        返回:
            搜索结果列表
            
        引发:
            SearchError: 如果搜索失败
            IndexNotFoundError: 如果没有可用索引
        """
        timer = Timer()
        timer.start()
        
        try:
            logger.info(f"执行 {query.search_type.value} 搜索: '{query.text}'")
            
            # 预处理查询
            processed_query = self._preprocess_query(query.text)
            
            # 根据类型执行搜索
            if query.search_type == SearchType.SEMANTIC:
                results = self._semantic_search(processed_query, query)
            elif query.search_type == SearchType.KEYWORD:
                results = self._keyword_search(processed_query, query)
            elif query.search_type == SearchType.HYBRID:
                results = self._hybrid_search(processed_query, query)
            elif query.search_type == SearchType.FUZZY:
                results = self._fuzzy_search(processed_query, query)
            else:
                raise SearchError(f"不支持的搜索类型: {query.search_type}")
            
            # 后处理结果
            results = self._post_process_results(results, query)
            
            search_time = timer.stop()
            
            # 更新统计信息
            self._update_search_stats(query.search_type, search_time)
            
            logger.info(f"搜索完成，耗时 {search_time:.3f} 秒，找到 {len(results)} 个结果")
            
            return results
            
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            raise SearchError(f"搜索失败: {str(e)}")
    
    def semantic_search(
        self, 
        query_text: str, 
        top_k: int = 5,
        **kwargs
    ) -> List[SearchResult]:
        """
        使用向量相似度执行语义搜索。
        
        参数:
            query_text: 搜索查询文本
            top_k: 要返回的结果数量
            **kwargs: 其他搜索选项
            
        返回:
            搜索结果列表
        """
        query = SearchQuery(
            text=query_text,
            search_type=SearchType.SEMANTIC,
            top_k=top_k,
            **kwargs
        )
        return self.search(query)
    
    def keyword_search(
        self, 
        query_text: str, 
        top_k: int = 5,
        **kwargs
    ) -> List[SearchResult]:
        """
        执行基于关键词的搜索。
        
        参数:
            query_text: 搜索查询文本
            top_k: 要返回的结果数量
            **kwargs: 其他搜索选项
            
        返回:
            搜索结果列表
        """
        query = SearchQuery(
            text=query_text,
            search_type=SearchType.KEYWORD,
            top_k=top_k,
            **kwargs
        )
        return self.search(query)
    
    def hybrid_search(
        self, 
        query_text: str, 
        top_k: int = 5,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        **kwargs
    ) -> List[SearchResult]:
        """
        执行结合语义和关键词搜索的混合搜索。
        
        参数:
            query_text: 搜索查询文本
            top_k: 要返回的结果数量
            semantic_weight: 语义搜索结果的权重
            keyword_weight: 关键词搜索结果的权重
            **kwargs: 其他搜索选项
            
        返回:
            搜索结果列表
        """
        boost_factors = kwargs.get('boost_factors', {})
        boost_factors.update({
            'semantic_weight': semantic_weight,
            'keyword_weight': keyword_weight
        })
        
        query = SearchQuery(
            text=query_text,
            search_type=SearchType.HYBRID,
            top_k=top_k,
            boost_factors=boost_factors,
            **kwargs
        )
        return self.search(query)
    
    def _semantic_search(self, query_text: str, query: SearchQuery) -> List[Dict[str, Any]]:
        """使用向量相似度执行语义搜索。"""
        try:
            # 使用向量存储进行语义搜索
            results = vector_store.search(
                query_text,
                top_k=query.top_k * 2,  # 获取更多结果用于过滤
            )
            
            # 转换为 SearchResult 格式
            search_results = []
            for result in results:
                search_result = SearchResult(
                    content=result["content"],
                    source=result["source"],
                    score=result["score"],
                    metadata=result.get("metadata", {}),
                    chunk_id=result.get("chunk_id", 0),
                    search_type=SearchType.SEMANTIC.value,
                    highlight=self._create_highlight(result["content"], query_text)
                )
                search_results.append(search_result.__dict__)
            
            return search_results
            
        except Exception as e:
            raise SearchError(f"语义搜索失败: {str(e)}")
    
    def _keyword_search(self, query_text: str, query: SearchQuery) -> List[Dict[str, Any]]:
        """执行基于关键词的搜索。"""
        try:
            # 获取所有索引文档
            indexed_docs = index_manager.list_indexed_documents()
            
            if not indexed_docs:
                return []
            
            # 从查询中提取关键词
            keywords = self._extract_keywords(query_text)
            
            if not keywords:
                return []
            
            # 搜索文档内容
            results = []
            
            for doc_info in indexed_docs:
                file_path = doc_info["file_path"]
                
                # 从向量存储中获取文档块
                doc_chunks = vector_store.get_document_by_source(file_path)
                
                for chunk_info in doc_chunks:
                    content = chunk_info["content"]
                    score = self._calculate_keyword_score(content, keywords)
                    
                    if score > query.min_score:
                        search_result = SearchResult(
                            content=content,
                            source=file_path,
                            score=score,
                            metadata=chunk_info.get("metadata", {}),
                            chunk_id=chunk_info.get("chunk_id", 0),
                            search_type=SearchType.KEYWORD.value,
                            highlight=self._create_keyword_highlight(content, keywords)
                        )
                        results.append(search_result.__dict__)
            
            # 按得分排序并返回顶部结果
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:query.top_k]
            
        except Exception as e:
            raise SearchError(f"关键词搜索失败: {str(e)}")
    
    def _hybrid_search(self, query_text: str, query: SearchQuery) -> List[Dict[str, Any]]:
        """执行结合语义和关键词搜索的混合搜索。"""
        try:
            # 获取权重
            boost_factors = query.boost_factors or {}
            semantic_weight = boost_factors.get('semantic_weight', 0.7)
            keyword_weight = boost_factors.get('keyword_weight', 0.3)
            
            # 执行两种搜索
            semantic_query = SearchQuery(
                text=query_text,
                search_type=SearchType.SEMANTIC,
                top_k=query.top_k * 2,
                min_score=query.min_score
            )
            semantic_results = self._semantic_search(query_text, semantic_query)
            
            keyword_query = SearchQuery(
                text=query_text,
                search_type=SearchType.KEYWORD,
                top_k=query.top_k * 2,
                min_score=query.min_score
            )
            keyword_results = self._keyword_search(query_text, keyword_query)
            
            # 合并并重新评分结果
            combined_results = self._combine_search_results(
                semantic_results,
                keyword_results,
                semantic_weight,
                keyword_weight
            )
            
            # 更新搜索类型
            for result in combined_results:
                result["search_type"] = SearchType.HYBRID.value
                # 合并高亮
                semantic_highlight = result.get("highlight", "")
                # 查找关键词结果以获取高亮
                for kr in keyword_results:
                    if kr["content"] == result["content"]:
                        keyword_highlight = kr.get("highlight", "")
                        result["highlight"] = self._merge_highlights(
                            semantic_highlight, keyword_highlight
                        )
                        break
            
            return combined_results[:query.top_k]
            
        except Exception as e:
            raise SearchError(f"混合搜索失败: {str(e)}")
    
    def _fuzzy_search(self, query_text: str, query: SearchQuery) -> List[Dict[str, Any]]:
        """执行模糊匹配搜索。"""
        try:
            # 获取所有索引文档
            indexed_docs = index_manager.list_indexed_documents()
            
            if not indexed_docs:
                return []
            
            results = []
            
            for doc_info in indexed_docs:
                file_path = doc_info["file_path"]
                
                # 从向量存储中获取文档块
                doc_chunks = vector_store.get_document_by_source(file_path)
                
                for chunk_info in doc_chunks:
                    content = chunk_info["content"]
                    score = self._calculate_fuzzy_score(content, query_text)
                    
                    if score >= self.fuzzy_threshold and score > query.min_score:
                        search_result = SearchResult(
                            content=content,
                            source=file_path,
                            score=score,
                            metadata=chunk_info.get("metadata", {}),
                            chunk_id=chunk_info.get("chunk_id", 0),
                            search_type=SearchType.FUZZY.value,
                            highlight=self._create_fuzzy_highlight(content, query_text)
                        )
                        results.append(search_result.__dict__)
            
            # 按得分排序并返回顶部结果
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:query.top_k]
            
        except Exception as e:
            raise SearchError(f"模糊搜索失败: {str(e)}")
    
    def _preprocess_query(self, query_text: str) -> str:
        """预处理查询文本以获得更好的搜索结果。"""
        # 转换为小写
        processed = query_text.lower().strip()
        
        # 移除多余空白
        processed = re.sub(r'\s+', ' ', processed)
        
        # 移除特殊字符用于关键词搜索
        processed = re.sub(r'[^\w\s-]', ' ', processed)
        
        return processed
    
    def _extract_keywords(self, query_text: str) -> List[str]:
        """从查询文本中提取关键词。"""
        # 分割为单词
        words = query_text.split()
        
        # 移除停用词和短词
        keywords = [
            word for word in words
            if len(word) > 2 and word.lower() not in self.stop_words
        ]
        
        return keywords
    
    def _calculate_keyword_score(self, content: str, keywords: List[str]) -> float:
        """计算内容的关键词匹配得分。"""
        if not keywords:
            return 0.0
        
        content_lower = content.lower()
        total_score = 0.0
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            
            # 精确匹配获得更高得分
            exact_matches = content_lower.count(keyword_lower)
            total_score += exact_matches * 1.0
            
            # 部分匹配获得较低得分
            if keyword_lower in content_lower:
                total_score += 0.5
        
        # 根据内容长度和关键词数量进行归一化
        content_words = len(content.split())
        normalized_score = total_score / (content_words * len(keywords))
        
        return min(normalized_score * 10, 1.0)  # 缩放并限制在 1.0
    
    def _calculate_fuzzy_score(self, content: str, query_text: str) -> float:
        """使用简单字符串相似度计算模糊匹配得分。"""
        try:
            from difflib import SequenceMatcher
            
            # 计算查询和内容之间的相似度
            matcher = SequenceMatcher(None, query_text.lower(), content.lower())
            similarity = matcher.ratio()
            
            # 还要检查最长公共子序列
            query_words = set(query_text.lower().split())
            content_words = set(content.lower().split())
            
            if query_words and content_words:
                word_overlap = len(query_words.intersection(content_words))
                word_similarity = word_overlap / len(query_words.union(content_words))
                
                # 结合字符和单词相似度
                combined_score = (similarity * 0.3) + (word_similarity * 0.7)
            else:
                combined_score = similarity
            
            return combined_score
            
        except Exception:
            # 回退到简单的子字符串匹配
            query_lower = query_text.lower()
            content_lower = content.lower()
            
            if query_lower in content_lower:
                return 0.8
            elif any(word in content_lower for word in query_lower.split()):
                return 0.6
            else:
                return 0.0
    
    def _combine_search_results(
        self,
        semantic_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        semantic_weight: float,
        keyword_weight: float
    ) -> List[Dict[str, Any]]:
        """合并并重新评分不同搜索方法的结果。"""
        # 创建内容到结果的映射
        content_to_result = {}
        
        # 添加语义结果
        for result in semantic_results:
            content = result["content"]
            if content not in content_to_result:
                content_to_result[content] = result.copy()
                content_to_result[content]["semantic_score"] = result["score"]
                content_to_result[content]["keyword_score"] = 0.0
        
        # 添加关键词结果
        for result in keyword_results:
            content = result["content"]
            if content in content_to_result:
                content_to_result[content]["keyword_score"] = result["score"]
            else:
                content_to_result[content] = result.copy()
                content_to_result[content]["semantic_score"] = 0.0
                content_to_result[content]["keyword_score"] = result["score"]
        
        # 计算组合得分
        combined_results = []
        for result in content_to_result.values():
            semantic_score = result.get("semantic_score", 0.0)
            keyword_score = result.get("keyword_score", 0.0)
            
            # 组合得分
            combined_score = (semantic_score * semantic_weight) + (keyword_score * keyword_weight)
            result["score"] = combined_score
            
            # 将单独得分添加到元数据
            if "metadata" not in result:
                result["metadata"] = {}
            result["metadata"]["semantic_score"] = semantic_score
            result["metadata"]["keyword_score"] = keyword_score
            
            combined_results.append(result)
        
        # 按组合得分排序
        combined_results.sort(key=lambda x: x["score"], reverse=True)
        
        return combined_results
    
    def _post_process_results(
        self, 
        results: List[Dict[str, Any]], 
        query: SearchQuery
    ) -> List[SearchResult]:
        """后处理搜索结果。"""
        # 按最小得分过滤
        filtered_results = [
            result for result in results
            if result["score"] >= query.min_score
        ]
        
        # 如果需要，去重
        if query.deduplicate:
            filtered_results = self._deduplicate_results(filtered_results)
        
        # 限制每个文档的结果数量
        filtered_results = self._limit_results_per_document(filtered_results)
        
        # 应用过滤器
        if query.filters:
            filtered_results = self._apply_filters(filtered_results, query.filters)
        
        # 转换为 SearchResult 对象
        search_results = []
        for i, result in enumerate(filtered_results[:query.top_k]):
            search_result = SearchResult(
                content=result["content"],
                source=result["source"],
                score=result["score"],
                metadata=result.get("metadata", {}) if query.include_metadata else {},
                chunk_id=result.get("chunk_id", 0),
                search_type=result.get("search_type", "unknown"),
                highlight=result.get("highlight", ""),
                rank=i + 1
            )
            search_results.append(search_result)
        
        return search_results
    
    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """基于内容相似度删除重复结果。"""
        unique_results = []
        seen_content = set()
        
        for result in results:
            content = result["content"]
            content_hash = hash(content.strip()[:200])  # 使用前 200 个字符进行比较
            
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_results.append(result)
        
        return unique_results
    
    def _limit_results_per_document(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """限制同一文档的结果数量。"""
        document_counts = {}
        filtered_results = []
        
        for result in results:
            source = result["source"]
            count = document_counts.get(source, 0)
            
            if count < self.max_results_per_document:
                document_counts[source] = count + 1
                filtered_results.append(result)
        
        return filtered_results
    
    def _apply_filters(self, results: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """将额外的过滤器应用到搜索结果。"""
        filtered_results = []
        
        for result in results:
            # 应用源文件过滤器
            if "source_pattern" in filters:
                pattern = filters["source_pattern"]
                if not re.search(pattern, result.get("source", "")):
                    continue
            
            # 应用文件类型过滤器
            if "file_types" in filters:
                import os
                file_ext = os.path.splitext(result.get("source", ""))[1].lower()
                if file_ext not in filters["file_types"]:
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
            
            # 应用日期过滤器
            if "date_range" in filters:
                date_range = filters["date_range"]
                # 这需要元数据中有日期信息
                # 实现取决于日期在元数据中的存储方式
            
            filtered_results.append(result)
        
        return filtered_results
    
    def _create_highlight(self, content: str, query_text: str, max_length: int = 200) -> str:
        """在匹配查询的位置周围创建内容的高亮片段。"""
        query_lower = query_text.lower()
        content_lower = content.lower()
        
        # 查找最佳匹配位置
        match_pos = content_lower.find(query_lower)
        
        if match_pos == -1:
            # 没有精确匹配，返回内容开头
            return content[:max_length] + ("..." if len(content) > max_length else "")
        
        # 计算片段边界
        start = max(0, match_pos - max_length // 4)
        end = min(len(content), match_pos + len(query_text) + max_length // 2)
        
        snippet = content[start:end]
        
        # 如需要添加省略号
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        
        return snippet
    
    def _create_keyword_highlight(self, content: str, keywords: List[str], max_length: int = 200) -> str:
        """创建显示关键词匹配的高亮片段。"""
        if not keywords:
            return content[:max_length] + ("..." if len(content) > max_length else "")
        
        content_lower = content.lower()
        
        # 查找第一个关键词匹配
        earliest_pos = len(content)
        for keyword in keywords:
            pos = content_lower.find(keyword.lower())
            if pos != -1 and pos < earliest_pos:
                earliest_pos = pos
        
        if earliest_pos == len(content):
            # 未找到匹配
            return content[:max_length] + ("..." if len(content) > max_length else "")
        
        # 在第一个匹配周围创建片段
        start = max(0, earliest_pos - max_length // 4)
        end = min(len(content), earliest_pos + max_length)
        
        snippet = content[start:end]
        
        # 如需要添加省略号
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        
        return snippet
    
    def _create_fuzzy_highlight(self, content: str, query_text: str, max_length: int = 200) -> str:
        """为模糊匹配创建高亮片段。"""
        # 对于模糊匹配，只返回内容的开头
        # 可以使用更复杂的模糊高亮技术进行增强
        return content[:max_length] + ("..." if len(content) > max_length else "")
    
    def _merge_highlights(self, highlight1: str, highlight2: str) -> str:
        """合并两个高亮，优先选择更长的。"""
        if not highlight1:
            return highlight2
        if not highlight2:
            return highlight1
        
        # 返回更长的高亮
        return highlight1 if len(highlight1) > len(highlight2) else highlight2
    
    def _update_search_stats(self, search_type: SearchType, search_time: float) -> None:
        """更新搜索统计信息。"""
        self.search_stats["total_searches"] += 1
        self.search_stats["total_search_time"] += search_time
        
        # 更新特定类型统计信息
        if search_type == SearchType.SEMANTIC:
            self.search_stats["semantic_searches"] += 1
        elif search_type == SearchType.KEYWORD:
            self.search_stats["keyword_searches"] += 1
        elif search_type == SearchType.HYBRID:
            self.search_stats["hybrid_searches"] += 1
        elif search_type == SearchType.FUZZY:
            self.search_stats["fuzzy_searches"] += 1
        
        # 更新平均值
        if self.search_stats["total_searches"] > 0:
            self.search_stats["average_search_time"] = (
                self.search_stats["total_search_time"] / 
                self.search_stats["total_searches"]
            )
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """
        获取搜索引擎统计信息。
        
        返回:
            包含搜索统计信息的字典
        """
        return self.search_stats.copy()
    
    def reset_statistics(self) -> None:
        """重置所有搜索统计信息。"""
        self.search_stats = {
            "total_searches": 0,
            "semantic_searches": 0,
            "keyword_searches": 0,
            "hybrid_searches": 0,
            "fuzzy_searches": 0,
            "total_search_time": 0.0,
            "average_search_time": 0.0
        }


# 全局搜索引擎实例
search_engine = SearchEngine()


# 便利函数
def search_documents(
    query_text: str,
    search_type: str = "semantic",
    top_k: int = 5,
    **kwargs
) -> List[SearchResult]:
    """
    使用全局搜索引擎搜索文档。
    
    参数:
        query_text: 搜索查询文本
        search_type: 搜索类型 ("semantic", "keyword", "hybrid", "fuzzy")
        top_k: 要返回的结果数量
        **kwargs: 其他搜索选项
        
    返回:
        搜索结果列表
    """
    search_type_enum = SearchType(search_type)
    query = SearchQuery(
        text=query_text,
        search_type=search_type_enum,
        top_k=top_k,
        **kwargs
    )
    return search_engine.search(query)


def semantic_search(query_text: str, top_k: int = 5, **kwargs) -> List[SearchResult]:
    """使用全局搜索引擎执行语义搜索。"""
    return search_engine.semantic_search(query_text, top_k, **kwargs)


def keyword_search(query_text: str, top_k: int = 5, **kwargs) -> List[SearchResult]:
    """使用全局搜索引擎执行关键词搜索。"""
    return search_engine.keyword_search(query_text, top_k, **kwargs)


def hybrid_search(query_text: str, top_k: int = 5, **kwargs) -> List[SearchResult]:
    """使用全局搜索引擎执行混合搜索。"""
    return search_engine.hybrid_search(query_text, top_k, **kwargs)