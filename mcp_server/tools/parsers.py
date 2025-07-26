"""
MCP 服务器文档解析工具

该模块提供与 MCP 兼容的工具，用于解析各种文档格式并提取结构化内容。
"""

import logging
from typing import Dict, Any, List, Optional, Set

from ..config import config
from ..security.path_validator import validate_path
from ..security.permissions import (
    Permission, AccessLevel, AccessRequest, 
    permission_manager
)
from ..exceptions import ParsingError, FileAccessDeniedError
from ..parsers.base import get_parser_for_file, get_supported_extensions
from ..parsers.converters import auto_convert_doc_to_docx
from ..indexing.manager import index_manager
from ..utils import Timer

logger = logging.getLogger(__name__)


class DocumentParsingTools:
    """
    MCP 服务器文档解析工具
    
    该类提供安全的文档解析操作，包含权限检查和对多种文档格式的支持。
    """
    
    def __init__(self, access_level: AccessLevel = AccessLevel.USER):
        """
        初始化文档解析工具。
        
        参数:
            access_level: 操作的默认访问级别
        """
        self.access_level = access_level
        self.parsing_stats = {
            "total_parsed": 0,
            "successful_parses": 0,
            "failed_parses": 0,
            "pdf_parsed": 0,
            "docx_parsed": 0,
            "doc_parsed": 0,
            "markdown_parsed": 0,
            "text_parsed": 0,
            "total_parse_time": 0.0,
            "average_parse_time": 0.0
        }
    
    def _resolve_file_path(self, file_path: str) -> str:
        """
        智能解析文件路径。
        
        如果给定的路径是相对文件名（如 'ccc.txt'），
        则会在允许的目录中搜索该文件。
        
        参数:
            file_path: 原始文件路径
            
        返回:
            解析后的完整路径
        """
        # 如果路径包含目录分隔符，说明不是纯文件名，直接返回
        if '/' in file_path or '\\' in file_path:
            return file_path
        
        # 如果是纯文件名，在允许的目录中搜索
        from ..config import config
        import os
        
        for allowed_dir in config.security.ALLOWED_DIRS:
            potential_path = os.path.join(allowed_dir, file_path)
            if os.path.exists(potential_path):
                # 返回相对于当前工作目录的路径
                current_dir = os.getcwd()
                try:
                    rel_path = os.path.relpath(potential_path, current_dir)
                    return rel_path
                except ValueError:
                    # 如果无法计算相对路径，返回绝对路径
                    return potential_path
        
        # 如果未找到文件，返回原始路径（让后续验证处理错误）
        return file_path
    
    def parse_document(
        self,
        file_path: str,
        extract_metadata: bool = True,
        create_chunks: bool = False,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        build_vector_index: bool = True,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        解析文档并提取其内容。
        
        参数:
            file_path: 要解析的文档路径
            extract_metadata: 是否提取文档元数据
            create_chunks: 是否创建文本块
            chunk_size: 每个文本块的大小
            chunk_overlap: 块之间的重叠
            build_vector_index: 是否自动构建向量索引
            force_reindex: 是否强制重新构建索引（忽略缓存）
            
        返回:
            包含解析内容、元数据和索引结果的字典
        """
        timer = Timer()
        timer.start()
        
        try:
            # 智能解析文件路径
            resolved_path = self._resolve_file_path(file_path)
            
            # 验证路径和检查权限
            validated_path = validate_path(resolved_path)
            
            request = AccessRequest(
                permission=Permission.PARSE_DOCUMENT,
                resource=validated_path
            )
            permission_manager.require_permission(request, self.access_level)
            
            # 获取适当的解析器
            parser = get_parser_for_file(validated_path)
            
            if not parser:
                return {
                    "success": False,
                    "error": f"没有适用于文件类型的解析器: {validated_path}",
                    "file_path": file_path,
                    "supported_extensions": list(get_supported_extensions())
                }
            
            # 解析文档
            parse_result = parser.parse(validated_path)
            
            if not parse_result.success:
                self.parsing_stats["failed_parses"] += 1
                return {
                    "success": False,
                    "error": parse_result.error or "解析失败",
                    "file_path": file_path,
                    "parser_type": parser.__class__.__name__
                }
            
            parse_time = timer.stop()
            
            # 更新统计信息
            self._update_parsing_stats(parser.__class__.__name__, parse_time, True)
            
            result = {
                "success": True,
                "file_path": validated_path,
                "original_file_path": file_path,
                "resolved_file_path": resolved_path,
                "parser_type": parser.__class__.__name__,
                "content": parse_result.content,
                "parse_time": parse_time
            }
            
            # 如请求则添加元数据
            if extract_metadata and parse_result.metadata:
                result["metadata"] = parse_result.metadata
            
            # 如请求则创建文本块
            if create_chunks and parse_result.content:
                chunks = parser.create_text_chunks(
                    parse_result.content,
                    validated_path
                )
                
                result["chunks"] = [
                    {
                        "chunk_id": chunk.chunk_id,
                        "content": chunk.content,
                        "metadata": chunk.metadata
                    }
                    for chunk in chunks
                ]
                result["total_chunks"] = len(chunks)
            
            # 如请求则构建向量索引
            if build_vector_index:
                try:
                    # 检查是否需要重建索引
                    needs_indexing = force_reindex
                    
                    if not needs_indexing:
                        # 检查文件是否已在索引中且未修改
                        from ..utils import calculate_file_hash
                        current_hash = calculate_file_hash(validated_path)
                        
                        # 检查索引管理器中的文档跟踪
                        if (validated_path in index_manager.indexed_documents and 
                            index_manager.document_hashes.get(validated_path) == current_hash):
                            result["vector_index"] = {
                                "success": True,
                                "message": "使用现有索引（文件未修改）",
                                "from_cache": True,
                                "file_hash": current_hash
                            }
                        else:
                            needs_indexing = True
                    
                    if needs_indexing:
                        # 构建向量索引
                        logger.info(f"为文件构建向量索引: {validated_path}")
                        
                        # 使用索引管理器添加文档
                        index_result = index_manager.add_documents(
                            [validated_path], 
                            update_existing=True
                        )
                        
                        result["vector_index"] = index_result
                        
                except Exception as e:
                    logger.warning(f"向量索引构建失败 {validated_path}: {str(e)}")
                    result["vector_index"] = {
                        "success": False,
                        "error": f"索引构建失败: {str(e)}",
                        "message": "文档解析成功，但向量索引构建失败"
                    }
            
            logger.info(f"文档解析成功: {validated_path}")
            return result
            
        except Exception as e:
            self._update_parsing_stats("unknown", 0.0, False)
            logger.error(f"解析文档失败 {file_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def batch_parse_documents(
        self,
        file_paths: List[str],
        extract_metadata: bool = True,
        create_chunks: bool = False,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        continue_on_error: bool = True
    ) -> Dict[str, Any]:
        """
        批量解析多个文档。
        
        参数:
            file_paths: 要解析的文件路径列表
            extract_metadata: 是否提取文档元数据
            create_chunks: 是否创建文本块
            chunk_size: 每个文本块的大小
            chunk_overlap: 块之间的重叠
            continue_on_error: 如果一个文件失败是否继续解析
            
        返回:
            包含批量解析结果的字典
        """
        timer = Timer()
        timer.start()
        
        successful_parses = []
        failed_parses = []
        total_chunks = 0
        
        try:
            for file_path in file_paths:
                try:
                    result = self.parse_document(
                        file_path=file_path,
                        extract_metadata=extract_metadata,
                        create_chunks=create_chunks,
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap
                    )
                    
                    if result["success"]:
                        successful_parses.append(result)
                        if create_chunks and "total_chunks" in result:
                            total_chunks += result["total_chunks"]
                    else:
                        failed_parses.append(result)
                        
                        if not continue_on_error:
                            break
                            
                except Exception as e:
                    error_result = {
                        "success": False,
                        "error": str(e),
                        "file_path": file_path
                    }
                    failed_parses.append(error_result)
                    
                    if not continue_on_error:
                        break
            
            batch_time = timer.stop()
            
            return {
                "success": len(failed_parses) == 0 or continue_on_error,
                "total_files": len(file_paths),
                "successful_parses": len(successful_parses),
                "failed_parses": len(failed_parses),
                "batch_time": batch_time,
                "total_chunks": total_chunks,
                "results": {
                    "successful": successful_parses,
                    "failed": failed_parses
                }
            }
            
        except Exception as e:
            logger.error(f"批量解析失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "total_files": len(file_paths),
                "successful_parses": len(successful_parses),
                "failed_parses": len(failed_parses)
            }
    
    def convert_doc_to_docx(
        self,
        doc_file_path: str,
        output_path: Optional[str] = None,
        conversion_method: str = "auto"
    ) -> Dict[str, Any]:
        """
        将 .doc 文件转换为 .docx 格式。
        
        参数:
            doc_file_path: .doc 文件路径
            output_path: .docx 文件的输出路径 (如果为 None 则自动生成)
            conversion_method: 要使用的转换方法
            
        返回:
            包含转换结果的字典
        """
        timer = Timer()
        timer.start()
        
        try:
            # 验证路径和检查权限
            validated_path = validate_path(doc_file_path)
            
            read_request = AccessRequest(
                permission=Permission.READ_FILE,
                resource=validated_path
            )
            permission_manager.require_permission(read_request, self.access_level)
            
            convert_request = AccessRequest(
                permission=Permission.CONVERT_DOCUMENT,
                resource=validated_path
            )
            permission_manager.require_permission(convert_request, self.access_level)
            
            # 执行转换
            conversion_result = auto_convert_doc_to_docx(
                validated_path,
                output_path,
                conversion_method
            )
            
            if not conversion_result.success:
                return {
                    "success": False,
                    "error": conversion_result.error,
                    "doc_file_path": doc_file_path,
                    "conversion_method": conversion_method
                }
            
            convert_time = timer.stop()
            
            # 检查输出文件的写入权限
            if conversion_result.output_path:
                write_request = AccessRequest(
                    permission=Permission.WRITE_FILE,
                    resource=conversion_result.output_path
                )
                permission_manager.require_permission(write_request, self.access_level)
            
            result = {
                "success": True,
                "doc_file_path": validated_path,
                "docx_file_path": conversion_result.output_path,
                "conversion_method": conversion_result.method_used,
                "conversion_time": convert_time,
                "file_size_original": conversion_result.original_size,
                "file_size_converted": conversion_result.converted_size,
                "warnings": conversion_result.warnings
            }
            
            logger.info(f"DOC 到 DOCX 转换成功: {validated_path}")
            return result
            
        except Exception as e:
            logger.error(f"DOC 到 DOCX 转换失败 {doc_file_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "doc_file_path": doc_file_path
            }
    
    def extract_document_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        提取文档元数据而不解析完整内容。
        
        参数:
            file_path: 文档路径
            
        返回:
            包含文档元数据的字典
        """
        try:
            # 验证路径和检查权限
            validated_path = validate_path(file_path)
            
            request = AccessRequest(
                permission=Permission.EXTRACT_METADATA,
                resource=validated_path
            )
            permission_manager.require_permission(request, self.access_level)
            
            # 获取适当的解析器
            parser = get_parser_for_file(validated_path)
            
            if not parser:
                return {
                    "success": False,
                    "error": f"没有适用于文件类型的解析器: {validated_path}",
                    "file_path": file_path
                }
            
            # 检查解析器是否支持元数据提取
            if hasattr(parser, 'extract_metadata'):
                metadata = parser.extract_metadata(validated_path)
            else:
                # 解析文档并提取元数据
                parse_result = parser.parse(validated_path)
                metadata = parse_result.metadata if parse_result.success else {}
            
            result = {
                "success": True,
                "file_path": validated_path,
                "parser_type": parser.__class__.__name__,
                "metadata": metadata or {}
            }
            
            # 添加基本文件信息
            import os
            from datetime import datetime
            import pytz
            
            stat_info = os.stat(validated_path)
            
            # 使用Shanghai时区格式化时间
            shanghai_tz = pytz.timezone('Asia/Shanghai')
            modified_dt = datetime.fromtimestamp(stat_info.st_mtime, tz=shanghai_tz)
            created_dt = datetime.fromtimestamp(stat_info.st_ctime, tz=shanghai_tz)
            
            result["file_info"] = {
                "size_bytes": stat_info.st_size,
                "size_mb": round(stat_info.st_size / 1024 / 1024, 2),
                "modified_time": modified_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "created_time": created_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "modified_timestamp": stat_info.st_mtime,
                "created_timestamp": stat_info.st_ctime,
                "extension": os.path.splitext(validated_path)[1].lower()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"提取元数据失败 {file_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def get_supported_formats(self) -> Dict[str, Any]:
        """
        获取支持的文档格式信息。
        
        返回:
            包含支持格式信息的字典
        """
        try:
            supported_extensions = get_supported_extensions()
            
            # 按类别分组
            format_categories = {
                "text": [".txt", ".md", ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h"],
                "office": [".docx", ".doc", ".pdf"],
                "web": [".html", ".htm", ".xml"],
                "config": [".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"],
                "data": [".csv"],
                "other": []
            }
            
            categorized_formats = {}
            uncategorized = set(supported_extensions)
            
            for category, extensions in format_categories.items():
                category_extensions = [ext for ext in extensions if ext in supported_extensions]
                if category_extensions:
                    categorized_formats[category] = category_extensions
                    uncategorized -= set(category_extensions)
            
            if uncategorized:
                categorized_formats["other"] = list(uncategorized)
            
            return {
                "success": True,
                "total_formats": len(supported_extensions),
                "supported_extensions": list(supported_extensions),
                "categories": categorized_formats,
                "conversion_support": {
                    "doc_to_docx": True,
                    "methods": ["pypandoc", "libreoffice", "textutil"]
                }
            }
            
        except Exception as e:
            logger.error(f"获取支持格式失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def validate_document_format(self, file_path: str) -> Dict[str, Any]:
        """
        验证文档格式是否支持解析。
        
        参数:
            file_path: 要验证的文档路径
            
        返回:
            包含验证结果的字典
        """
        try:
            validated_path = validate_path(file_path, check_existence=False)
            
            # 检查是否有可用的解析器
            parser = get_parser_for_file(validated_path)
            
            import os
            extension = os.path.splitext(validated_path)[1].lower()
            
            result = {
                "success": True,
                "file_path": validated_path,
                "extension": extension,
                "is_supported": parser is not None,
                "parser_type": parser.__class__.__name__ if parser else None
            }
            
            if parser:
                result["capabilities"] = {
                    "can_parse": True,
                    "can_extract_metadata": hasattr(parser, 'extract_metadata'),
                    "can_create_chunks": hasattr(parser, 'create_text_chunks'),
                    "supported_file_types": parser.supported_extensions
                }
            else:
                result["capabilities"] = {
                    "can_parse": False,
                    "can_extract_metadata": False,
                    "can_create_chunks": False,
                    "supported_file_types": []
                }
                result["suggestion"] = "文件格式不受支持。请检查支持的格式。"
            
            return result
            
        except Exception as e:
            logger.error(f"验证文档格式失败 {file_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def _update_parsing_stats(self, parser_type: str, parse_time: float, success: bool) -> None:
        """更新解析统计信息。"""
        self.parsing_stats["total_parsed"] += 1
        self.parsing_stats["total_parse_time"] += parse_time
        
        if success:
            self.parsing_stats["successful_parses"] += 1
        else:
            self.parsing_stats["failed_parses"] += 1
        
        # 更新特定解析器统计信息
        if "PDF" in parser_type:
            self.parsing_stats["pdf_parsed"] += 1
        elif "DOCX" in parser_type or "Word" in parser_type:
            self.parsing_stats["docx_parsed"] += 1
        elif "DOC" in parser_type:
            self.parsing_stats["doc_parsed"] += 1
        elif "Markdown" in parser_type:
            self.parsing_stats["markdown_parsed"] += 1
        elif "Text" in parser_type:
            self.parsing_stats["text_parsed"] += 1
        
        # 更新平均值
        if self.parsing_stats["total_parsed"] > 0:
            self.parsing_stats["average_parse_time"] = (
                self.parsing_stats["total_parse_time"] / 
                self.parsing_stats["total_parsed"]
            )
    
    def get_parsing_statistics(self) -> Dict[str, Any]:
        """
        获取文档解析统计信息。
        
        返回:
            包含解析统计信息的字典
        """
        return self.parsing_stats.copy()
    
    def reset_statistics(self) -> None:
        """重置解析统计信息。"""
        self.parsing_stats = {
            "total_parsed": 0,
            "successful_parses": 0,
            "failed_parses": 0,
            "pdf_parsed": 0,
            "docx_parsed": 0,
            "doc_parsed": 0,
            "markdown_parsed": 0,
            "text_parsed": 0,
            "total_parse_time": 0.0,
            "average_parse_time": 0.0
        }


# 全局文档解析工具实例
doc_parser_tools = DocumentParsingTools()


# MCP 工具定义
MCP_PARSER_TOOLS = {
    "parse_document": {
        "name": "parse_document",
        "description": "解析文档并提取其内容",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要解析的文档路径"
                },
                "extract_metadata": {
                    "type": "boolean",
                    "description": "是否提取文档元数据 (默认: true)",
                    "default": True
                },
                "create_chunks": {
                    "type": "boolean",
                    "description": "是否创建文本块 (默认: false)",
                    "default": False
                },
                "chunk_size": {
                    "type": "integer",
                    "description": "每个文本块的大小 (默认: 1000)",
                    "default": 1000
                },
                "chunk_overlap": {
                    "type": "integer",
                    "description": "块之间的重叠 (默认: 200)",
                    "default": 200
                }
            },
            "required": ["file_path"]
        }
    },
    
    "batch_parse_documents": {
        "name": "batch_parse_documents",
        "description": "批量解析多个文档",
        "parameters": {
            "type": "object",
            "properties": {
                "file_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要解析的文件路径列表"
                },
                "extract_metadata": {
                    "type": "boolean",
                    "description": "是否提取文档元数据 (默认: true)",
                    "default": True
                },
                "create_chunks": {
                    "type": "boolean",
                    "description": "是否创建文本块 (默认: false)",
                    "default": False
                },
                "chunk_size": {
                    "type": "integer",
                    "description": "每个文本块的大小 (默认: 1000)",
                    "default": 1000
                },
                "chunk_overlap": {
                    "type": "integer",
                    "description": "块之间的重叠 (默认: 200)",
                    "default": 200
                },
                "continue_on_error": {
                    "type": "boolean",
                    "description": "如果一个文件失败是否继续解析 (默认: true)",
                    "default": True
                }
            },
            "required": ["file_paths"]
        }
    },
    
    "convert_doc_to_docx": {
        "name": "convert_doc_to_docx",
        "description": "将 .doc 文件转换为 .docx 格式",
        "parameters": {
            "type": "object",
            "properties": {
                "doc_file_path": {
                    "type": "string",
                    "description": ".doc 文件路径"
                },
                "output_path": {
                    "type": "string",
                    "description": ".docx 文件的输出路径 (如果未提供则自动生成)"
                },
                "conversion_method": {
                    "type": "string",
                    "description": "要使用的转换方法 (默认: auto)",
                    "enum": ["auto", "pypandoc", "libreoffice", "textutil"],
                    "default": "auto"
                }
            },
            "required": ["doc_file_path"]
        }
    },
    
    "extract_document_metadata": {
        "name": "extract_document_metadata",
        "description": "提取文档元数据而不解析完整内容",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文档路径"
                }
            },
            "required": ["file_path"]
        }
    },
    
    "get_supported_formats": {
        "name": "get_supported_formats",
        "description": "获取支持的文档格式信息",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    
    "validate_document_format": {
        "name": "validate_document_format",
        "description": "验证文档格式是否支持解析",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要验证的文档路径"
                }
            },
            "required": ["file_path"]
        }
    }
}


# 工具执行函数
def execute_parser_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行文档解析工具。
    
    参数:
        tool_name: 要执行的工具名称
        arguments: 工具参数
        
    返回:
        工具执行结果
    """
    try:
        if tool_name == "parse_document":
            return doc_parser_tools.parse_document(**arguments)
        elif tool_name == "batch_parse_documents":
            return doc_parser_tools.batch_parse_documents(**arguments)
        elif tool_name == "convert_doc_to_docx":
            return doc_parser_tools.convert_doc_to_docx(**arguments)
        elif tool_name == "extract_document_metadata":
            return doc_parser_tools.extract_document_metadata(**arguments)
        elif tool_name == "get_supported_formats":
            return doc_parser_tools.get_supported_formats()
        elif tool_name == "validate_document_format":
            return doc_parser_tools.validate_document_format(**arguments)
        else:
            return {
                "success": False,
                "error": f"未知解析器工具: {tool_name}"
            }
    except Exception as e:
        logger.error(f"解析器工具执行失败: {tool_name} - {str(e)}")
        return {
            "success": False,
            "error": f"工具执行失败: {str(e)}"
        }


def register_parser_tools(mcp):
    """注册解析器工具到MCP"""
    
    @mcp.tool()
    async def parse_pdf(params: dict):
        """解析PDF文档"""
        # Handle parameter mapping: 'file' -> 'file_path'
        if 'file' in params:
            params['file_path'] = params.pop('file')
        return doc_parser_tools.parse_document(**params)
    
    @mcp.tool()
    async def parse_docx(params: dict):
        """解析Word文档"""
        # Handle parameter mapping: 'file' -> 'file_path'
        if 'file' in params:
            params['file_path'] = params.pop('file')
        return doc_parser_tools.parse_document(**params)
    
    @mcp.tool()
    async def parse_md(params: dict):
        """解析Markdown文档"""
        # Handle parameter mapping: 'file' -> 'file_path'
        if 'file' in params:
            params['file_path'] = params.pop('file')
        return doc_parser_tools.parse_document(**params)
    
    @mcp.tool()
    async def parse_txt(params: dict):
        """解析文本文档"""
        # Handle parameter mapping: 'file' -> 'file_path'
        if 'file' in params:
            params['file_path'] = params.pop('file')
        return doc_parser_tools.parse_document(**params)