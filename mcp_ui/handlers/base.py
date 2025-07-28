"""
命令处理器基类
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import chainlit as cl
from ..utils.logger import get_logger

logger = get_logger(__name__)

class BaseCommandHandler(ABC):
    """命令处理器基类"""
    
    def __init__(self, name: str, description: str, usage: str):
        self.name = name
        self.description = description 
        self.usage = usage
    
    @abstractmethod
    async def execute(self, args: List[str]) -> None:
        """执行命令"""
        pass
    
    def get_help(self) -> str:
        """获取帮助信息"""
        return f"**{self.name}**: {self.description}\n使用方法: `{self.usage}`"

class CommandRegistry:
    """命令注册器"""
    
    def __init__(self):
        self.handlers: Dict[str, BaseCommandHandler] = {}
    
    def register(self, handler: BaseCommandHandler):
        """注册命令处理器"""
        self.handlers[handler.name] = handler
        logger.info(f"注册命令处理器: {handler.name}")
    
    def get_handler(self, command: str) -> Optional[BaseCommandHandler]:
        """获取命令处理器"""
        return self.handlers.get(command)
    
    def list_commands(self) -> List[str]:
        """列出所有命令"""
        return list(self.handlers.keys())
    
    def get_help_text(self) -> str:
        """生成帮助文本"""
        help_text = "# 📖 命令帮助\n\n## 🔧 可用命令\n\n"
        
        # 按功能分组
        groups = {
            "索引管理": ["build", "index"],
            "文档处理": ["parse", "search"],
            "系统信息": ["models", "status", "config"],
            "其他": []
        }
        
        # 分组显示命令
        for group_name, group_commands in groups.items():
            if group_name != "其他":
                help_text += f"### {group_name}\n"
                
                for cmd_name in group_commands:
                    if cmd_name in self.handlers:
                        help_text += f"- {self.handlers[cmd_name].get_help()}\n"
                
                help_text += "\n"
        
        # 显示其他命令
        other_commands = [cmd for cmd in self.handlers.keys() 
                         if not any(cmd in group for group in groups.values() if group)]
        
        if other_commands:
            help_text += "### 其他\n"
            for cmd_name in other_commands:
                help_text += f"- {self.handlers[cmd_name].get_help()}\n"
        
        help_text += """
## 💡 使用提示
1. **上传文档**: 使用界面上传按钮添加文档
2. **构建索引**: 上传后执行 `/build` 构建搜索索引
3. **智能问答**: 直接提问，系统会自动搜索并回答
4. **命令调用**: 使用 `/` 开头的命令调用特定功能

开始你的智能知识库之旅吧！ 🚀
"""
        return help_text

# 全局命令注册器
command_registry = CommandRegistry()