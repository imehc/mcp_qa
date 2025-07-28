"""
索引管理命令处理器
"""

import time
from typing import List
import chainlit as cl
from .base import BaseCommandHandler
from ..clients import mcp_client
from ..utils.logger import get_logger, ProgressLogger, ui_logger

logger = get_logger(__name__)

class BuildCommandHandler(BaseCommandHandler):
    """构建索引命令处理器"""
    
    def __init__(self):
        super().__init__(
            name="build",
            description="构建知识库索引",
            usage="/build [目录]"
        )
    
    async def execute(self, args: List[str]) -> None:
        """执行构建索引命令"""
        # 获取目录参数
        directory = args[0] if args else "docs"
        
        ui_logger.log_user_action("build_index", {"directory": directory})
        
        # 显示进度消息
        progress_msg = cl.Message(content="🔄 正在构建知识库索引...")
        await progress_msg.send()
        
        start_time = time.time()
        
        try:
            # 调用MCP服务器构建索引
            result = await mcp_client.build_index(directory)
            
            duration = time.time() - start_time
            
            if "error" in result:
                error_msg = f"❌ 索引构建失败: {result['error']}"
                await progress_msg.update(content=error_msg)
                ui_logger.log_mcp_call("build_index", {"directory": directory}, False, duration)
                logger.error(f"索引构建失败: {result['error']}")
            else:
                # 格式化成功消息
                processed_files = result.get('processed_files', 0)
                total_chunks = result.get('total_chunks', 0)
                index_size = result.get('index_size', 0)
                
                success_msg = f"""✅ **索引构建完成！**
                
📊 **统计信息**:
- 处理文件数: {processed_files}
- 文本片段数: {total_chunks}
- 索引大小: {index_size} MB
- 用时: {duration:.2f} 秒

💡 现在可以开始智能问答了！"""
                
                await progress_msg.update(content=success_msg)
                ui_logger.log_mcp_call("build_index", {"directory": directory}, True, duration)
                logger.info(f"索引构建成功，处理了 {processed_files} 个文件")
                
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"❌ 索引构建异常: {str(e)}"
            await progress_msg.update(content=error_msg)
            ui_logger.log_error(e, f"构建索引时发生异常，目录: {directory}")

class SearchCommandHandler(BaseCommandHandler):
    """搜索命令处理器"""
    
    def __init__(self):
        super().__init__(
            name="search",
            description="搜索文档内容",
            usage="/search <关键词> [数量]"
        )
    
    async def execute(self, args: List[str]) -> None:
        """执行搜索命令"""
        if not args:
            await cl.Message(content="❌ 请提供搜索关键词: `/search 关键词`").send()
            return
        
        # 解析参数
        query = " ".join(args[:-1]) if len(args) > 1 and args[-1].isdigit() else " ".join(args)
        top_k = int(args[-1]) if len(args) > 1 and args[-1].isdigit() else 5
        
        ui_logger.log_user_action("search_documents", {"query": query, "top_k": top_k})
        
        # 显示搜索过程
        search_msg = cl.Message(content=f"🔍 正在搜索: **{query}**")
        await search_msg.send()
        
        start_time = time.time()
        
        try:
            # 执行搜索
            result = await mcp_client.search_documents(query, top_k)
            
            duration = time.time() - start_time
            
            if "error" in result:
                error_msg = f"❌ 搜索失败: {result['error']}"
                await search_msg.update(content=error_msg)
                ui_logger.log_mcp_call("search_documents", {"query": query}, False, duration)
            else:
                # 格式化搜索结果
                if result.get("results"):
                    content = f"🔍 **搜索结果** (关键词: **{query}**):\n\n"
                    
                    for i, doc in enumerate(result["results"], 1):
                        title = doc.get('title', '未知文档')
                        score = doc.get('score', 0)
                        content_snippet = doc.get('content', '')[:200]
                        
                        content += f"**{i}. {title}**\n"
                        content += f"📊 相似度: {score:.3f}\n"
                        content += f"📄 内容片段: {content_snippet}...\n\n"
                    
                    content += f"⏱️ 搜索用时: {duration:.2f} 秒"
                else:
                    content = f"🔍 未找到与 '**{query}**' 相关的文档\n\n💡 建议:\n- 尝试使用不同的关键词\n- 检查是否已构建索引\n- 确认文档已上传"
                
                await search_msg.update(content=content)
                ui_logger.log_mcp_call("search_documents", {"query": query}, True, duration)
                
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"❌ 搜索异常: {str(e)}"
            await search_msg.update(content=error_msg)
            ui_logger.log_error(e, f"搜索时发生异常，查询: {query}")