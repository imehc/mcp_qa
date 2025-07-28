"""
文档处理命令处理器
"""

import time
from typing import List
import json
import chainlit as cl
from .base import BaseCommandHandler
from ..clients import unified_mcp_client
from ..utils.logger import get_logger, ui_logger

logger = get_logger(__name__)

class ParseCommandHandler(BaseCommandHandler):
    """文档解析命令处理器"""
    
    def __init__(self):
        super().__init__(
            name="parse",
            description="解析单个文档",
            usage="/parse <文件路径>"
        )
    
    async def execute(self, args: List[str]) -> None:
        """执行文档解析命令"""
        if not args:
            await cl.Message(content="❌ 请提供文件路径: `/parse 文件路径`").send()
            return
        
        file_path = args[0]
        ui_logger.log_user_action("parse_document", {"file_path": file_path})
        
        # 显示解析过程
        parse_msg = cl.Message(content=f"📄 正在解析文档: **{file_path}**")
        await parse_msg.send()
        
        start_time = time.time()
        
        try:
            # 执行解析
            result = await unified_mcp_client.parse_document(file_path)
            
            duration = time.time() - start_time
            
            if "error" in result:
                error_msg = f"❌ 解析失败: {result['error']}"
                await parse_msg.update(content=error_msg)
                ui_logger.log_mcp_call("parse_document", {"file_path": file_path}, False, duration)
                ui_logger.log_file_operation("parse", file_path, False)
            else:
                # 格式化解析结果
                content = f"📄 **文档解析完成**: {file_path}\n\n"
                
                # 基本信息
                content += f"**📊 基本信息**:\n"
                content += f"- 文档类型: {result.get('file_type', '未知')}\n"
                content += f"- 文本长度: {len(result.get('content', ''))} 字符\n"
                content += f"- 解析用时: {duration:.2f} 秒\n\n"
                
                # 元数据
                if result.get('metadata'):
                    content += f"**📋 元数据**:\n"
                    metadata = result['metadata']
                    for key, value in metadata.items():
                        content += f"- {key}: {value}\n"
                    content += "\n"
                
                # 内容预览
                if result.get('content'):
                    preview = result['content'][:300]
                    content += f"**📝 内容预览**:\n```\n{preview}...\n```\n\n"
                
                content += "💡 提示: 执行 `/build` 命令将此文档加入索引以启用搜索功能"
                
                await parse_msg.update(content=content)
                ui_logger.log_mcp_call("parse_document", {"file_path": file_path}, True, duration)
                ui_logger.log_file_operation("parse", file_path, True)
                
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"❌ 解析异常: {str(e)}"
            await parse_msg.update(content=error_msg)
            ui_logger.log_error(e, f"解析文档时发生异常，文件: {file_path}")

class ListCommandHandler(BaseCommandHandler):
    """目录列表命令处理器"""
    
    def __init__(self):
        super().__init__(
            name="list",
            description="列出目录内容",
            usage="/list [目录路径]"
        )
    
    async def execute(self, args: List[str]) -> None:
        """执行目录列表命令"""
        path = args[0] if args else "docs"
        ui_logger.log_user_action("list_directory", {"path": path})
        
        # 显示列表过程
        list_msg = cl.Message(content=f"📁 正在列出目录: **{path}**")
        await list_msg.send()
        
        start_time = time.time()
        
        try:
            # 执行目录列表
            result = await unified_mcp_client.list_directory(path)
            
            duration = time.time() - start_time
            
            if "error" in result:
                error_msg = f"❌ 列出目录失败: {result['error']}"
                await list_msg.update(content=error_msg)
                ui_logger.log_mcp_call("list_directory", {"path": path}, False, duration)
            else:
                # 格式化目录内容
                content = f"📁 **目录内容**: {path}\n\n"
                
                files = result.get('files', [])
                directories = result.get('directories', [])
                
                if directories:
                    content += "**📂 子目录**:\n"
                    for directory in directories:
                        content += f"- 📂 {directory}\n"
                    content += "\n"
                
                if files:
                    content += "**📄 文件**:\n"
                    for file_info in files:
                        if isinstance(file_info, dict):
                            name = file_info.get('name', '未知文件')
                            size = file_info.get('size', 0)
                            content += f"- 📄 {name} ({size} bytes)\n"
                        else:
                            content += f"- 📄 {file_info}\n"
                    content += "\n"
                
                if not files and not directories:
                    content += "📭 目录为空\n\n"
                
                content += f"⏱️ 用时: {duration:.2f} 秒"
                
                await list_msg.update(content=content)
                ui_logger.log_mcp_call("list_directory", {"path": path}, True, duration)
                
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"❌ 列出目录异常: {str(e)}"
            await list_msg.update(content=error_msg)
            ui_logger.log_error(e, f"列出目录时发生异常，路径: {path}")

class ReadCommandHandler(BaseCommandHandler):
    """文件读取命令处理器"""
    
    def __init__(self):
        super().__init__(
            name="read",
            description="读取文件内容",
            usage="/read <文件路径>"
        )
    
    async def execute(self, args: List[str]) -> None:
        """执行文件读取命令"""
        if not args:
            await cl.Message(content="❌ 请提供文件路径: `/read 文件路径`").send()
            return
        
        file_path = args[0]
        ui_logger.log_user_action("read_file", {"file_path": file_path})
        
        # 显示读取过程
        read_msg = cl.Message(content=f"📖 正在读取文件: **{file_path}**")
        await read_msg.send()
        
        start_time = time.time()
        
        try:
            # 执行文件读取
            result = await unified_mcp_client.read_file(file_path)
            
            duration = time.time() - start_time
            
            if "error" in result:
                error_msg = f"❌ 读取失败: {result['error']}"
                await read_msg.update(content=error_msg)
                ui_logger.log_mcp_call("read_file", {"file_path": file_path}, False, duration)
                ui_logger.log_file_operation("read", file_path, False)
            else:
                # 格式化文件内容
                file_content = result.get('content', '')
                file_size = len(file_content)
                
                content = f"📖 **文件内容**: {file_path}\n\n"
                content += f"**📊 文件信息**:\n"
                content += f"- 大小: {file_size} 字符\n"
                content += f"- 读取用时: {duration:.2f} 秒\n\n"
                
                # 内容显示（限制长度）
                if file_size > 2000:
                    preview_content = file_content[:2000]
                    content += f"**📝 内容预览** (前2000字符):\n```\n{preview_content}...\n```\n\n"
                    content += "💡 内容过长，仅显示前2000字符"
                else:
                    content += f"**📝 完整内容**:\n```\n{file_content}\n```"
                
                await read_msg.update(content=content)
                ui_logger.log_mcp_call("read_file", {"file_path": file_path}, True, duration)
                ui_logger.log_file_operation("read", file_path, True)
                
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"❌ 读取异常: {str(e)}"
            await read_msg.update(content=error_msg)
            ui_logger.log_error(e, f"读取文件时发生异常，文件: {file_path}")