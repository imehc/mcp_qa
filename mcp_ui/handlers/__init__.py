"""
命令处理器模块初始化
注册所有命令处理器
"""

from .base import BaseCommandHandler, CommandRegistry, command_registry
from .index_handlers import BuildCommandHandler, SearchCommandHandler
from .system_handlers import ModelsCommandHandler, StatusCommandHandler, ConfigCommandHandler, HelpCommandHandler
from .document_handlers import ParseCommandHandler, ListCommandHandler, ReadCommandHandler

def register_all_handlers():
    """注册所有命令处理器"""
    handlers = [
        # 索引管理
        BuildCommandHandler(),
        SearchCommandHandler(),
        
        # 文档处理
        ParseCommandHandler(),
        ListCommandHandler(),
        ReadCommandHandler(),
        
        # 系统信息
        ModelsCommandHandler(),
        StatusCommandHandler(),
        ConfigCommandHandler(),
        HelpCommandHandler(),
    ]
    
    for handler in handlers:
        command_registry.register(handler)

# 自动注册所有处理器
register_all_handlers()

__all__ = [
    "BaseCommandHandler",
    "CommandRegistry", 
    "command_registry",
    "register_all_handlers"
]