"""
MCP工具模块初始化
"""

from .file_ops import *
from .parsers import *
from .search import *
from .time import *
from .cache import *

# 工具注册函数
def register_all_tools(mcp):
    """注册所有MCP工具"""
    from .file_ops import register_file_tools
    from .parsers import register_parser_tools  
    from .search import register_search_tools
    from .time import register_time_tools
    from .cache import register_cache_tools
    
    register_file_tools(mcp)
    register_parser_tools(mcp)
    register_search_tools(mcp) 
    register_time_tools(mcp)
    register_cache_tools(mcp)