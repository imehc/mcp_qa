"""
系统信息命令处理器
"""

import time
from typing import List
import chainlit as cl
from .base import BaseCommandHandler, command_registry
from ..clients import mcp_client, ollama_client
from ..config.settings import UIConfig
from ..utils.logger import get_logger, ui_logger

logger = get_logger(__name__)

class ModelsCommandHandler(BaseCommandHandler):
    """模型列表命令处理器"""
    
    def __init__(self):
        super().__init__(
            name="models",
            description="查看可用模型列表",
            usage="/models"
        )
    
    async def execute(self, args: List[str]) -> None:
        """执行模型列表命令"""
        ui_logger.log_user_action("list_models")
        
        # 获取当前选择的模型
        current_model = cl.user_session.get("current_model", UIConfig.DEFAULT_MODEL)
        
        try:
            # 获取可用模型
            models = await ollama_client.list_models()
            
            if models:
                content = "🤖 **可用模型列表**:\n\n"
                for model in models:
                    marker = "✅" if model == current_model else "⚪"
                    content += f"{marker} {model}\n"
                
                content += f"\n**当前使用**: {current_model}\n\n"
                content += "💡 提示: 在聊天开始时可以重新选择模型"
            else:
                content = "❌ 未找到可用模型\n\n🔧 请检查:\n- Ollama服务是否运行\n- 是否已下载模型"
            
            await cl.Message(content=content).send()
            
        except Exception as e:
            error_msg = f"❌ 获取模型列表失败: {str(e)}"
            await cl.Message(content=error_msg).send()
            ui_logger.log_error(e, "获取模型列表时发生异常")

class StatusCommandHandler(BaseCommandHandler):
    """系统状态命令处理器"""
    
    def __init__(self):
        super().__init__(
            name="status",
            description="查看系统运行状态",
            usage="/status"
        )
    
    async def execute(self, args: List[str]) -> None:
        """执行状态检查命令"""
        ui_logger.log_user_action("check_status")
        
        status_msg = cl.Message(content="🔍 正在检查系统状态...")
        await status_msg.send()
        
        try:
            # 检查MCP服务器状态
            mcp_healthy = await mcp_client.health_check()
            
            # 检查Ollama服务状态
            ollama_healthy = await ollama_client.health_check()
            
            # 获取缓存统计
            cache_stats = await mcp_client.get_cache_stats()
            
            # 构建状态报告
            content = "📊 **系统状态报告**\n\n"
            
            # MCP服务器状态
            mcp_status = "🟢 运行正常" if mcp_healthy else "🔴 连接失败"
            content += f"**MCP服务器**: {mcp_status}\n"
            content += f"- 地址: {UIConfig.MCP_SERVER_URL}\n\n"
            
            # Ollama服务状态
            ollama_status = "🟢 运行正常" if ollama_healthy else "🔴 连接失败"
            content += f"**Ollama服务**: {ollama_status}\n"
            content += f"- 地址: {UIConfig.OLLAMA_BASE_URL}\n\n"
            
            # 缓存状态
            if "error" not in cache_stats:
                content += f"**缓存状态**: 🟢 正常\n"
                content += f"- 命中率: {cache_stats.get('hit_rate', 0):.1%}\n"
                content += f"- 缓存项数: {cache_stats.get('items', 0)}\n\n"
            else:
                content += f"**缓存状态**: 🟡 无法获取\n\n"
            
            # 配置信息
            content += f"**配置信息**:\n"
            content += f"- 当前模型: {cl.user_session.get('current_model', UIConfig.DEFAULT_MODEL)}\n"
            content += f"- 上传目录: {UIConfig.UPLOAD_DIR}\n"
            content += f"- 日志级别: {UIConfig.LOG_LEVEL}\n"
            
            await status_msg.update(content=content)
            
        except Exception as e:
            error_msg = f"❌ 状态检查异常: {str(e)}"
            await status_msg.update(content=error_msg)
            ui_logger.log_error(e, "检查系统状态时发生异常")

class ConfigCommandHandler(BaseCommandHandler):
    """配置信息命令处理器"""
    
    def __init__(self):
        super().__init__(
            name="config",
            description="查看系统配置信息",
            usage="/config"
        )
    
    async def execute(self, args: List[str]) -> None:
        """执行配置查看命令"""
        ui_logger.log_user_action("view_config")
        
        try:
            # 验证配置
            config_validation = UIConfig.validate_config()
            
            content = "⚙️ **系统配置信息**\n\n"
            
            # 服务配置
            content += "**服务端点**:\n"
            content += f"- MCP服务器: {UIConfig.MCP_SERVER_URL}\n"
            content += f"- Ollama服务: {UIConfig.OLLAMA_BASE_URL}\n"
            content += f"- UI服务: {UIConfig.APP_HOST}:{UIConfig.APP_PORT}\n\n"
            
            # 文件配置
            content += "**文件处理**:\n"
            content += f"- 上传目录: {UIConfig.UPLOAD_DIR}\n"
            content += f"- 最大文件大小: {UIConfig.MAX_FILE_SIZE / (1024*1024):.0f}MB\n"
            content += f"- 支持格式: {', '.join(UIConfig.ALLOWED_EXTENSIONS)}\n\n"
            
            # 模型配置
            content += "**模型设置**:\n"
            content += f"- 默认模型: {UIConfig.DEFAULT_MODEL}\n"
            content += f"- 最大令牌: {UIConfig.MAX_TOKENS}\n"
            content += f"- 温度系数: {UIConfig.TEMPERATURE}\n\n"
            
            # 搜索配置
            content += "**搜索设置**:\n"
            content += f"- 默认搜索数量: {UIConfig.DEFAULT_SEARCH_K}\n"
            content += f"- 最大搜索数量: {UIConfig.MAX_SEARCH_K}\n\n"
            
            # 配置验证结果
            if config_validation["valid"]:
                content += "✅ **配置验证**: 通过"
            else:
                content += "❌ **配置验证**: 失败\n"
                for issue in config_validation["issues"]:
                    content += f"- {issue}\n"
            
            await cl.Message(content=content).send()
            
        except Exception as e:
            error_msg = f"❌ 获取配置信息失败: {str(e)}"
            await cl.Message(content=error_msg).send()
            ui_logger.log_error(e, "获取配置信息时发生异常")

class HelpCommandHandler(BaseCommandHandler):
    """帮助命令处理器"""
    
    def __init__(self):
        super().__init__(
            name="help",
            description="显示帮助信息",
            usage="/help"
        )
    
    async def execute(self, args: List[str]) -> None:
        """执行帮助命令"""
        ui_logger.log_user_action("view_help")
        
        try:
            help_text = command_registry.get_help_text()
            await cl.Message(content=help_text).send()
            
        except Exception as e:
            error_msg = f"❌ 获取帮助信息失败: {str(e)}"
            await cl.Message(content=error_msg).send()
            ui_logger.log_error(e, "获取帮助信息时发生异常")