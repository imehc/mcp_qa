"""
MCP服务器包
提供文档问答服务的MCP实现
"""

from .server import create_server, run_server, MCPServer
from .config import Config

__version__ = "1.0.0"
__author__ = "MCP QA Team"
__description__ = "MCP文档问答服务器"

__all__ = [
    "create_server",
    "run_server", 
    "MCPServer",
    "Config",
]