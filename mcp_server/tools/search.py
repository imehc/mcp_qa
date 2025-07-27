"""
MCP 服务器搜索工具

该模块提供与 MCP 兼容的工具，用于使用各种搜索策略和索引功能搜索和检索文档。
"""

import os
import logging
from typing import Dict, Any, List, Optional

from ..security.permissions import (
    Permission, AccessLevel, AccessRequest, 
    permission_manager
)
from ..exceptions import IndexNotFoundError
from ..indexing.manager import index_manager
from ..indexing.search import search_engine, SearchQuery, SearchType
from ..utils import Timer

logger = logging.getLogger(__name__)


class SearchTools:
    """
    MCP 服务器搜索工具
    
    该类提供安全的搜索操作，包含权限检查和支持各种搜索策略。
    """
    
    def __init__(self, access_level: AccessLevel = AccessLevel.USER):
        """
        初始化搜索工具。
        
        参数:
            access_level: 操作的默认访问级别
        """
        self.access_level = access_level
        self.search_stats = {
            "total_searches": 0,
            "semantic_searches": 0,
            "keyword_searches": 0,
            "hybrid_searches": 0,
            "fuzzy_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "total_search_time": 0.0,
            "average_search_time": 0.0
        }
    
    def search_documents(
        self,
        query: str,
        search_type: str = "semantic",
        top_k: int = 5,
        min_score: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
        auto_build_index: bool = True
    ) -> Dict[str, Any]:
        """
        使用指定的查询和选项搜索文档。
        
        参数:
            query: 搜索查询文本
            search_type: 搜索类型 ("semantic", "keyword", "hybrid", "fuzzy")
            top_k: 要返回的顶部结果数量
            min_score: 最小相似度分数阈值
            filters: 搜索结果的可选过滤器
            include_metadata: 是否包含文档元数据
            auto_build_index: 是否自动检测和构建索引
            
        返回:
            包含搜索结果和元数据的字典
        """
        timer = Timer()
        timer.start()
        
        try:
            # 检查搜索权限
            request = AccessRequest(permission=Permission.SEARCH_INDEX)
            permission_manager.require_permission(request, self.access_level)
            
            # 自动索引检测和构建
            if auto_build_index:
                index_status = self._check_and_build_index_if_needed()
                if not index_status.get("has_documents", False):
                    search_time = timer.stop()
                    return {
                        "success": False,
                        "error": "没有可搜索的文档。请先添加文档到索引中。",
                        "query": query,
                        "suggestion": "使用 build_index 工具从目录构建索引，或使用 add_documents_to_index 添加特定文档",
                        "auto_index_attempted": index_status.get("build_attempted", False),
                        "search_time": search_time
                    }
            
            # 验证搜索类型
            try:
                search_type_enum = SearchType(search_type)
            except ValueError:
                return {
                    "success": False,
                    "error": f"无效的搜索类型: {search_type}",
                    "valid_types": [t.value for t in SearchType]
                }
            
            # 创建搜索查询
            search_query = SearchQuery(
                text=query,
                search_type=search_type_enum,
                top_k=top_k,
                min_score=min_score,
                filters=filters,
                include_metadata=include_metadata
            )
            
            # 执行搜索
            results = search_engine.search(search_query)
            
            search_time = timer.stop()
            
            # 更新统计信息
            self._update_search_stats(search_type, search_time, True)
            
            # 格式化结果
            formatted_results = []
            for result in results:
                formatted_result = {
                    "rank": result.rank,
                    "score": result.score,
                    "content": result.content,
                    "source": result.source,
                    "chunk_id": result.chunk_id,
                    "search_type": result.search_type,
                    "highlight": result.highlight
                }
                
                if include_metadata and result.metadata:
                    formatted_result["metadata"] = result.metadata
                
                formatted_results.append(formatted_result)
            
            return {
                "success": True,
                "query": query,
                "search_type": search_type,
                "total_results": len(formatted_results),
                "search_time": search_time,
                "results": formatted_results,
                "search_metadata": {
                    "top_k": top_k,
                    "min_score": min_score,
                    "filters_applied": filters is not None,
                    "include_metadata": include_metadata
                }
            }
            
        except IndexNotFoundError:
            self._update_search_stats(search_type, 0.0, False)
            return {
                "success": False,
                "error": "没有可用的搜索索引。请先构建索引。",
                "query": query,
                "suggestion": "使用 build_index 或 add_documents 工具创建可搜索索引"
            }
        except Exception as e:
            self._update_search_stats(search_type, 0.0, False)
            logger.error(f"搜索查询 '{query}' 失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        使用向量相似性执行语义搜索。
        
        参数:
            query: 搜索查询文本
            top_k: 要返回的顶部结果数量
            min_score: 最小相似度分数阈值
            **kwargs: 其他搜索选项
            
        返回:
            包含搜索结果的字典
        """
        return self.search_documents(
            query=query,
            search_type="semantic",
            top_k=top_k,
            min_score=min_score,
            **kwargs
        )
    
    def keyword_search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行基于关键字的搜索。
        
        参数:
            query: 搜索查询文本
            top_k: 要返回的顶部结果数量
            min_score: 最小相似度分数阈值
            **kwargs: 其他搜索选项
            
        返回:
            包含搜索结果的字典
        """
        return self.search_documents(
            query=query,
            search_type="keyword",
            top_k=top_k,
            min_score=min_score,
            **kwargs
        )
    
    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        min_score: float = 0.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行结合语义和关键字搜索的混合搜索。
        
        参数:
            query: 搜索查询文本
            top_k: 要返回的顶部结果数量
            semantic_weight: 语义搜索结果的权重 (0.0-1.0)
            keyword_weight: 关键字搜索结果的权重 (0.0-1.0)
            min_score: 最小相似度分数阈值
            **kwargs: 其他搜索选项
            
        返回:
            包含搜索结果的字典
        """
        # 标准化权重
        total_weight = semantic_weight + keyword_weight
        if total_weight > 0:
            semantic_weight = semantic_weight / total_weight
            keyword_weight = keyword_weight / total_weight
        
        boost_factors = kwargs.get('boost_factors', {})
        boost_factors.update({
            'semantic_weight': semantic_weight,
            'keyword_weight': keyword_weight
        })
        kwargs['boost_factors'] = boost_factors
        
        return self.search_documents(
            query=query,
            search_type="hybrid",
            top_k=top_k,
            min_score=min_score,
            **kwargs
        )
    
    def build_index(
        self,
        directory: str,
        file_extensions: Optional[List[str]] = None,
        recursive: bool = True,
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        从目录中的文档构建搜索索引。
        
        参数:
            directory: 扫描文档的目录
            file_extensions: 要包含的文件扩展名列表
            recursive: 是否扫描子目录
            show_progress: 构建过程中是否显示进度
            
        返回:
            包含构建结果的字典
        """
        try:
            # 检查构建权限
            request = AccessRequest(permission=Permission.BUILD_INDEX)
            permission_manager.require_permission(request, self.access_level)
            
            # 如果提供了文件扩展名则转换为集合
            extension_set = set(file_extensions) if file_extensions else None
            
            # 构建索引
            result = index_manager.build_index_from_directory(
                directory=directory,
                file_extensions=extension_set,
                recursive=recursive,
                show_progress=show_progress
            )
            
            if result["success"]:
                logger.info(f"索引从 {directory} 构建成功")
            
            return result
            
        except Exception as e:
            logger.error(f"从 {directory} 构建索引失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "directory": directory
            }
    
    def add_documents_to_index(
        self,
        file_paths: List[str],
        update_existing: bool = True
    ) -> Dict[str, Any]:
        """
        将文档添加到现有搜索索引中。
        
        参数:
            file_paths: 要添加到索引中的文件路径列表
            update_existing: 是否更新已更改的现有文档
            
        返回:
            包含操作结果的字典
        """
        try:
            # 检查构建权限 (添加文档需要)
            request = AccessRequest(permission=Permission.BUILD_INDEX)
            permission_manager.require_permission(request, self.access_level)
            
            # 添加文档
            result = index_manager.add_documents(
                file_paths=file_paths,
                update_existing=update_existing
            )
            
            if result["success"]:
                logger.info(f"已将 {len(file_paths)} 个文档添加到索引中")
            
            return result
            
        except Exception as e:
            logger.error(f"添加文档到索引失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_paths": file_paths
            }
    
    def remove_documents_from_index(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        从搜索索引中移除文档。
        
        参数:
            file_paths: 要从索引中移除的文件路径列表
            
        返回:
            包含操作结果的字典
        """
        try:
            # 检查删除权限
            request = AccessRequest(permission=Permission.DELETE_INDEX)
            permission_manager.require_permission(request, self.access_level)
            
            # 移除文档
            result = index_manager.remove_documents(file_paths)
            
            if result["success"]:
                logger.info(f"已从索引中移除 {len(file_paths)} 个文档")
            
            return result
            
        except Exception as e:
            logger.error(f"从索引中移除文档失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_paths": file_paths
            }
    
    def get_index_status(self) -> Dict[str, Any]:
        """
        获取搜索索引的当前状态。
        
        返回:
            包含索引状态和统计信息的字典
        """
        try:
            # 检查系统信息权限
            request = AccessRequest(permission=Permission.GET_SYSTEM_INFO)
            permission_manager.require_permission(request, self.access_level)
            
            status = index_manager.get_index_status()
            
            return {
                "success": True,
                "index_status": status
            }
            
        except Exception as e:
            logger.error(f"获取索引状态失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def refresh_index(self) -> Dict[str, Any]:
        """
        通过更新过时文档来刷新索引。
        
        返回:
            包含刷新结果的字典
        """
        try:
            # 检查构建权限
            request = AccessRequest(permission=Permission.BUILD_INDEX)
            permission_manager.require_permission(request, self.access_level)
            
            result = index_manager.refresh_index()
            
            if result["success"]:
                logger.info("索引刷新成功")
            
            return result
            
        except Exception as e:
            logger.error(f"刷新索引失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_indexed_documents(self) -> Dict[str, Any]:
        """
        列出搜索索引中的所有文档。
        
        返回:
            包含索引文档信息的字典
        """
        try:
            # 检查系统信息权限
            request = AccessRequest(permission=Permission.GET_SYSTEM_INFO)
            permission_manager.require_permission(request, self.access_level)
            
            documents = index_manager.list_indexed_documents()
            
            return {
                "success": True,
                "total_documents": len(documents),
                "documents": documents
            }
            
        except Exception as e:
            logger.error(f"列出索引文档失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def find_similar_documents(
        self,
        file_path: str,
        top_k: int = 5,
        min_score: float = 0.1
    ) -> Dict[str, Any]:
        """
        查找与给定文档相似的文档。
        
        参数:
            file_path: 参考文档的路径
            top_k: 要返回的相似文档数量
            min_score: 最小相似度分数阈值
            
        返回:
            包含相似文档的字典
        """
        try:
            # 检查搜索权限
            request = AccessRequest(permission=Permission.SEARCH_INDEX)
            permission_manager.require_permission(request, self.access_level)
            
            # 获取文档信息
            doc_info = index_manager.get_document_info(file_path)
            if not doc_info:
                return {
                    "success": False,
                    "error": f"索引中未找到文档: {file_path}",
                    "file_path": file_path
                }
            
            # 获取文档块
            doc_chunks = index_manager.vector_store.get_document_by_source(file_path)
            if not doc_chunks:
                return {
                    "success": False,
                    "error": f"未找到文档内容: {file_path}",
                    "file_path": file_path
                }
            
            # 使用第一个块作为相似性搜索的查询
            query_content = doc_chunks[0]["content"][:500]  # 使用前500个字符
            
            # 执行语义搜索
            search_result = self.semantic_search(
                query=query_content,
                top_k=top_k + 1,  # +1 以考虑源文档本身
                min_score=min_score
            )
            
            if not search_result["success"]:
                return search_result
            
            # 过滤掉源文档本身
            similar_docs = [
                result for result in search_result["results"]
                if result["source"] != file_path
            ][:top_k]
            
            return {
                "success": True,
                "reference_document": file_path,
                "total_similar": len(similar_docs),
                "similar_documents": similar_docs,
                "search_metadata": {
                    "query_used": query_content[:100] + "...",
                    "min_score": min_score,
                    "top_k": top_k
                }
            }
            
        except Exception as e:
            logger.error(f"查找 {file_path} 的相似文档失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def search_by_metadata(
        self,
        metadata_filters: Dict[str, Any],
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        按元数据条件搜索文档。
        
        参数:
            metadata_filters: 用于过滤的元数据键值对字典
            top_k: 要返回的最大结果数
            
        返回:
            包含过滤文档的字典
        """
        try:
            # 检查搜索权限
            request = AccessRequest(permission=Permission.SEARCH_INDEX)
            permission_manager.require_permission(request, self.access_level)
            
            # 获取所有索引文档
            all_documents = index_manager.list_indexed_documents()
            
            # 按元数据过滤
            matching_docs = []
            for doc in all_documents:
                doc_metadata = doc.get("metadata", {})
                
                # 检查文档是否匹配所有过滤条件
                matches = True
                for key, value in metadata_filters.items():
                    if key not in doc_metadata or doc_metadata[key] != value:
                        matches = False
                        break
                
                if matches:
                    matching_docs.append(doc)
            
            # 限制结果数量
            matching_docs = matching_docs[:top_k]
            
            return {
                "success": True,
                "metadata_filters": metadata_filters,
                "total_matches": len(matching_docs),
                "documents": matching_docs
            }
            
        except Exception as e:
            logger.error(f"按元数据搜索失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "metadata_filters": metadata_filters
            }
    
    def _update_search_stats(self, search_type: str, search_time: float, success: bool) -> None:
        """更新搜索统计信息。"""
        self.search_stats["total_searches"] += 1
        
        if success:
            self.search_stats["successful_searches"] += 1
            self.search_stats["total_search_time"] += search_time
        else:
            self.search_stats["failed_searches"] += 1
        
        # 更新特定类型统计信息
        if search_type == "semantic":
            self.search_stats["semantic_searches"] += 1
        elif search_type == "keyword":
            self.search_stats["keyword_searches"] += 1
        elif search_type == "hybrid":
            self.search_stats["hybrid_searches"] += 1
        elif search_type == "fuzzy":
            self.search_stats["fuzzy_searches"] += 1
        
        # 更新平均值
        if self.search_stats["successful_searches"] > 0:
            self.search_stats["average_search_time"] = (
                self.search_stats["total_search_time"] / 
                self.search_stats["successful_searches"]
            )
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """
        获取搜索操作统计信息。
        
        返回:
            包含搜索统计信息的字典
        """
        return self.search_stats.copy()
    
    def _check_and_build_index_if_needed(self) -> Dict[str, Any]:
        """
        检查索引状态，如果需要则自动构建索引。
        
        返回:
            包含索引状态和构建信息的字典
        """
        try:
            # 获取当前索引状态
            status = index_manager.get_index_status()
            
            # 检查是否有文档
            total_docs = status.get("total_documents", 0)
            has_documents = total_docs > 0
            
            result = {
                "has_documents": has_documents,
                "total_documents": total_docs,
                "build_attempted": False
            }
            
            # 如果没有文档，尝试从默认目录构建索引
            if not has_documents:
                logger.info("检测到没有索引文档，尝试自动构建索引...")
                result["build_attempted"] = True
                
                # 从docs目录自动构建索引
                docs_dir = os.path.join(os.getcwd(), "docs")
                if os.path.exists(docs_dir):
                    logger.info(f"从 {docs_dir} 自动构建索引")
                    build_result = self.build_index(
                        directory=docs_dir,
                        file_extensions=[".txt", ".md", ".py", ".pdf", ".docx"],
                        recursive=True,
                        show_progress=False
                    )
                    
                    if build_result.get("success"):
                        result["auto_build_success"] = True
                        result["auto_build_result"] = build_result
                        result["has_documents"] = build_result.get("processed_files", 0) > 0
                        logger.info(f"自动索引构建成功，处理了 {build_result.get('processed_files', 0)} 个文件")
                    else:
                        result["auto_build_success"] = False
                        result["auto_build_error"] = build_result.get("error", "未知错误")
                        logger.warning(f"自动索引构建失败: {build_result.get('error', '未知错误')}")
                else:
                    result["auto_build_success"] = False
                    result["auto_build_error"] = f"docs目录不存在: {docs_dir}"
                    logger.warning(f"docs目录不存在: {docs_dir}")
            
            return result
            
        except Exception as e:
            logger.error(f"检查和构建索引失败: {str(e)}")
            return {
                "has_documents": False,
                "build_attempted": True,
                "auto_build_success": False,
                "auto_build_error": str(e)
            }
    
    def _check_file_in_index(self, file_name: str) -> Dict[str, Any]:
        """
        检查特定文件是否在索引中。
        
        参数:
            file_name: 要检查的文件名
            
        返回:
            包含检查结果的字典
        """
        try:
            # 获取所有索引文档
            indexed_docs = index_manager.list_indexed_documents()
            
            # 检查文件是否在索引中
            file_in_index = False
            indexed_file_path = None
            
            for doc in indexed_docs:
                file_path = doc.get("file_path", "")
                if file_name.lower() in os.path.basename(file_path).lower():
                    file_in_index = True
                    indexed_file_path = file_path
                    break
            
            result = {
                "in_index": file_in_index,
                "file_name": file_name,
                "auto_added": False
            }
            
            if file_in_index:
                result["file_path"] = indexed_file_path
            else:
                # 尝试在常见目录中查找文件
                potential_paths = self._find_file_paths(file_name)
                if potential_paths:
                    result["file_path"] = potential_paths[0]  # 使用第一个找到的路径
                    result["potential_paths"] = potential_paths
                else:
                    result["file_path"] = None
            
            return result
            
        except Exception as e:
            logger.error(f"检查文件索引状态失败: {str(e)}")
            return {
                "in_index": False,
                "file_name": file_name,
                "error": str(e),
                "auto_added": False
            }
    
    def _find_file_paths(self, file_name: str) -> List[str]:
        """
        在常见目录中查找文件。
        
        参数:
            file_name: 要查找的文件名
            
        返回:
            找到的文件路径列表
        """
        found_paths = []
        
        # 要搜索的目录列表
        search_dirs = [
            "docs",
            ".",
            "src",
            "scripts",
            "examples"
        ]
        
        for search_dir in search_dirs:
            if os.path.exists(search_dir):
                for root, dirs, files in os.walk(search_dir):
                    for file in files:
                        if file_name.lower() == file.lower() or file_name.lower() in file.lower():
                            found_paths.append(os.path.join(root, file))
        
        return found_paths
    
    def reset_statistics(self) -> None:
        """重置搜索统计信息。"""
        self.search_stats = {
            "total_searches": 0,
            "semantic_searches": 0,
            "keyword_searches": 0,
            "hybrid_searches": 0,
            "fuzzy_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "total_search_time": 0.0,
            "average_search_time": 0.0
        }


# 全局搜索工具实例
search_tools = SearchTools()


# MCP 工具定义
MCP_SEARCH_TOOLS = {
    "search_documents": {
        "name": "search_documents",
        "description": "使用指定的查询和选项搜索文档",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询文本"
                },
                "search_type": {
                    "type": "string",
                    "description": "要执行的搜索类型",
                    "enum": ["semantic", "keyword", "hybrid", "fuzzy"],
                    "default": "semantic"
                },
                "top_k": {
                    "type": "integer",
                    "description": "要返回的顶部结果数量 (默认: 5)",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 50
                },
                "min_score": {
                    "type": "number",
                    "description": "最小相似度分数阈值 (默认: 0.0)",
                    "default": 0.0,
                    "minimum": 0.0,
                    "maximum": 1.0
                },
                "include_metadata": {
                    "type": "boolean",
                    "description": "是否包含文档元数据 (默认: true)",
                    "default": True
                }
            },
            "required": ["query"]
        }
    },
    
    "semantic_search": {
        "name": "semantic_search",
        "description": "使用向量相似性执行语义搜索",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询文本"
                },
                "top_k": {
                    "type": "integer",
                    "description": "要返回的顶部结果数量 (默认: 5)",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 50
                },
                "min_score": {
                    "type": "number",
                    "description": "最小相似度分数阈值 (默认: 0.0)",
                    "default": 0.0,
                    "minimum": 0.0,
                    "maximum": 1.0
                }
            },
            "required": ["query"]
        }
    },
    
    "keyword_search": {
        "name": "keyword_search",
        "description": "执行基于关键字的搜索",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询文本"
                },
                "top_k": {
                    "type": "integer",
                    "description": "要返回的顶部结果数量 (默认: 5)",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 50
                },
                "min_score": {
                    "type": "number",
                    "description": "最小相似度分数阈值 (默认: 0.0)",
                    "default": 0.0,
                    "minimum": 0.0,
                    "maximum": 1.0
                }
            },
            "required": ["query"]
        }
    },
    
    "hybrid_search": {
        "name": "hybrid_search",
        "description": "执行结合语义和关键字搜索的混合搜索",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询文本"
                },
                "top_k": {
                    "type": "integer",
                    "description": "要返回的顶部结果数量 (默认: 5)",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 50
                },
                "semantic_weight": {
                    "type": "number",
                    "description": "语义搜索结果的权重 (默认: 0.7)",
                    "default": 0.7,
                    "minimum": 0.0,
                    "maximum": 1.0
                },
                "keyword_weight": {
                    "type": "number",
                    "description": "关键字搜索结果的权重 (默认: 0.3)",
                    "default": 0.3,
                    "minimum": 0.0,
                    "maximum": 1.0
                },
                "min_score": {
                    "type": "number",
                    "description": "最小相似度分数阈值 (默认: 0.0)",
                    "default": 0.0,
                    "minimum": 0.0,
                    "maximum": 1.0
                }
            },
            "required": ["query"]
        }
    },
    
    "build_index": {
        "name": "build_index",
        "description": "从目录中的文档构建搜索索引",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "扫描文档的目录"
                },
                "file_extensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要包含的文件扩展名列表 (例如, ['.pdf', '.txt'])"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "是否扫描子目录 (默认: true)",
                    "default": True
                },
                "show_progress": {
                    "type": "boolean",
                    "description": "构建过程中是否显示进度 (默认: true)",
                    "default": True
                }
            },
            "required": ["directory"]
        }
    },
    
    "add_documents_to_index": {
        "name": "add_documents_to_index",
        "description": "将文档添加到现有搜索索引中",
        "parameters": {
            "type": "object",
            "properties": {
                "file_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要添加到索引中的文件路径列表"
                },
                "update_existing": {
                    "type": "boolean",
                    "description": "是否更新已更改的现有文档 (默认: true)",
                    "default": True
                }
            },
            "required": ["file_paths"]
        }
    },
    
    "get_index_status": {
        "name": "get_index_status",
        "description": "获取搜索索引的当前状态",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    
    "refresh_index": {
        "name": "refresh_index",
        "description": "通过更新过时文档来刷新索引",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    
    "list_indexed_documents": {
        "name": "list_indexed_documents",
        "description": "列出搜索索引中的所有文档",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    
    "find_similar_documents": {
        "name": "find_similar_documents",
        "description": "查找与给定文档相似的文档",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "参考文档的路径"
                },
                "top_k": {
                    "type": "integer",
                    "description": "要返回的相似文档数量 (默认: 5)",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20
                },
                "min_score": {
                    "type": "number",
                    "description": "最小相似度分数阈值 (默认: 0.1)",
                    "default": 0.1,
                    "minimum": 0.0,
                    "maximum": 1.0
                }
            },
            "required": ["file_path"]
        }
    }
}


# 工具执行函数
def execute_search_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行搜索工具。
    
    参数:
        tool_name: 要执行的工具名称
        arguments: 工具参数
        
    返回:
        工具执行结果
    """
    try:
        if tool_name == "search_documents":
            return search_tools.search_documents(**arguments)
        elif tool_name == "semantic_search":
            return search_tools.semantic_search(**arguments)
        elif tool_name == "keyword_search":
            return search_tools.keyword_search(**arguments)
        elif tool_name == "hybrid_search":
            return search_tools.hybrid_search(**arguments)
        elif tool_name == "build_index":
            return search_tools.build_index(**arguments)
        elif tool_name == "add_documents_to_index":
            return search_tools.add_documents_to_index(**arguments)
        elif tool_name == "get_index_status":
            return search_tools.get_index_status()
        elif tool_name == "refresh_index":
            return search_tools.refresh_index()
        elif tool_name == "list_indexed_documents":
            return search_tools.list_indexed_documents()
        elif tool_name == "find_similar_documents":
            return search_tools.find_similar_documents(**arguments)
        else:
            return {
                "success": False,
                "error": f"未知搜索工具: {tool_name}"
            }
    except Exception as e:
        logger.error(f"搜索工具执行失败: {tool_name} - {str(e)}")
        return {
            "success": False,
            "error": f"工具执行失败: {str(e)}"
        }


def register_search_tools(mcp):
    """注册搜索工具到MCP"""
    
    @mcp.tool()
    async def search_documents(params: dict):
        """查找文件内容和信息：使用向量索引搜索文档中的相关信息。适用于回答"文件讲了什么"、"文件内容是什么"等问题。"""
        return search_tools.search_documents(**params)
    
    @mcp.tool()
    async def semantic_search(params: dict):
        """文件内容语义搜索：理解语义含义并查找相关文档内容。当用户问"文件主要讲了什么"或查找特定概念时使用。"""
        return search_tools.semantic_search(**params)
    
    @mcp.tool()
    async def keyword_search(params: dict):
        """执行基于关键字的搜索 - 用于查找包含特定关键词的文档内容"""
        return search_tools.keyword_search(**params)
    
    @mcp.tool()
    async def hybrid_search(params: dict):
        """执行结合语义和关键字搜索的混合搜索 - 用于综合查找文档中的相关内容"""
        return search_tools.hybrid_search(**params)
    
    @mcp.tool()
    async def build_document_index(params: dict):
        """构建文档向量索引"""
        return search_tools.build_index(**params)
    
    @mcp.tool()
    async def add_documents_to_index(params: dict):
        """将文档添加到现有搜索索引中"""
        return search_tools.add_documents_to_index(**params)
    
    @mcp.tool()
    async def get_index_status(params: dict = None):
        """获取搜索索引的当前状态"""
        return search_tools.get_index_status()
    
    @mcp.tool()
    async def list_indexed_documents(params: dict = None):
        """列出搜索索引中的所有文档"""
        return search_tools.list_indexed_documents()
    
    @mcp.tool()
    async def find_similar_documents(params: dict):
        """查找与给定文档相似的文档"""
        return search_tools.find_similar_documents(**params)
    
    @mcp.tool()
    async def refresh_index(params: dict = None):
        """通过更新过时文档来刷新索引"""
        return search_tools.refresh_index()
    
    @mcp.tool()
    async def search_file_content(params: dict):
        """查找特定文件的内容：专门用于回答"某个文件讲了什么"或"某个文件的主要内容是什么"类型的问题。优先使用此工具查看文件内容摘要。"""
        # 处理参数映射：支持 'file' 和 'file_name' 参数
        file_name = params.get('file_name', '') or params.get('file', '')
        query = params.get('query', '')
        
        # 如果query中包含文件名，尝试提取
        if not file_name and query:
            # 简单的文件名提取逻辑
            import re
            # 查找常见的文件扩展名
            file_pattern = r'(\w+\.\w+)'
            matches = re.findall(file_pattern, query)
            if matches:
                file_name = matches[0]
        
        # 如果还是没有文件名，把query当作file_name处理
        if not file_name and query:
            file_name = query
        
        if not file_name:
            return {
                "success": False,
                "error": "需要提供文件名（通过 'file' 或 'file_name' 参数）"
            }
        
        # 首先检查特定文件是否在索引中
        if file_name:
            file_status = search_tools._check_file_in_index(file_name)
            
            # 如果文件不在索引中，尝试添加
            if not file_status.get("in_index", False):
                file_path = file_status.get("file_path")
                if file_path and os.path.exists(file_path):
                    logger.info(f"文件 {file_name} 不在索引中，尝试添加...")
                    add_result = search_tools.add_documents_to_index([file_path])
                    if add_result.get("success"):
                        logger.info(f"成功将 {file_name} 添加到索引")
                    else:
                        logger.warning(f"添加 {file_name} 到索引失败: {add_result.get('error')}")
        
        # 构建搜索查询
        if file_name:
            search_query = f"{file_name} {query}".strip()
        else:
            search_query = query
        
        search_params = {
            'query': search_query,
            'search_type': 'hybrid',
            'top_k': params.get('top_k', 5),
            'min_score': params.get('min_score', 0.0),
            'auto_build_index': True
        }
        
        result = search_tools.search_documents(**search_params)
        
        # 如果指定了文件名，过滤结果
        if result.get('success') and result.get('results') and file_name:
            relevant_results = []
            for res in result['results']:
                if file_name.lower() in res.get('source', '').lower():
                    relevant_results.append(res)
            
            if relevant_results:
                result['results'] = relevant_results
                result['file_content_summary'] = True
                result['message'] = f"找到文件 {file_name} 的相关内容"
                result['auto_indexed'] = file_status.get("auto_added", False)
            else:
                # 尝试更宽泛的搜索
                broad_search_params = {
                    'query': query or file_name,
                    'search_type': 'semantic',
                    'top_k': 10,
                    'min_score': 0.0
                }
                broad_result = search_tools.search_documents(**broad_search_params)
                
                if broad_result.get('success') and broad_result.get('results'):
                    result = broad_result
                    result['message'] = f"未找到文件 {file_name}，但找到了相关内容"
                else:
                    result['message'] = f"未在索引中找到文件 {file_name} 或相关内容"
        
        return result