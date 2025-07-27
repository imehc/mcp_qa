"""
MCP 服务器搜索工具

该模块提供与 MCP 兼容的工具，用于使用各种搜索策略和索引功能搜索和检索文档。
"""

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
        include_metadata: bool = True
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
            
        返回:
            包含搜索结果和元数据的字典
        """
        timer = Timer()
        timer.start()
        
        try:
            # 检查搜索权限
            request = AccessRequest(permission=Permission.SEARCH_INDEX)
            permission_manager.require_permission(request, self.access_level)
            
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
        """在文档索引中搜索相关内容"""
        return search_tools.search_documents(**params)
    
    @mcp.tool()
    async def build_document_index(params: dict):
        """构建文档向量索引"""
        return search_tools.build_index(**params)