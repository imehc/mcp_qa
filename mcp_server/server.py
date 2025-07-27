"""
MCP服务器主模块
集成所有功能并提供统一的服务器入口
"""

import os
from typing import Optional
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse, Response
import uvicorn

# 设置环境变量以避免警告
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["FAISS_OPT_LEVEL"] = "generic"  # 抑制FAISS GPU警告

from .config import config
from .monitoring.logger import setup_logger
from .api.http_server import create_http_routes
from .tools import register_all_tools
from .exceptions import MCPServerError

# 加载环境变量
load_dotenv()

# 配置日志
logger = setup_logger(__name__)


class MCPServer:
    """MCP服务器主类"""
    
    def __init__(self):
        """初始化MCP服务器"""
        self.mcp = FastMCP("mcp_qa_server", protocol_version="1.0")
        self.server = None
        self.app = None
        self._initialized = False
        
    def initialize(self) -> None:
        """初始化服务器组件"""
        if self._initialized:
            return
            
        try:
            # 注册所有工具
            register_all_tools(self.mcp)
            
            # 创建MCP服务器实例
            self.server = self.mcp._mcp_server
            
            # 创建Starlette应用
            self.app = self._create_starlette_app()
            
            self._initialized = True
            logger.info("MCP服务器初始化完成")
            
        except Exception as e:
            logger.error(f"服务器初始化失败: {e}")
            raise MCPServerError(f"Failed to initialize server: {e}")
    
    def _create_starlette_app(self) -> Starlette:
        """创建Starlette应用"""
        sse = SseServerTransport("/messages/")
        
        async def handle_sse(request: Request) -> Response:
            """处理SSE连接"""
            try:
                logger.debug(f"收到来自 {request.client.host} 的SSE连接")
                
                async with sse.connect_sse(
                    request.scope,
                    request.receive,
                    request._send,
                ) as (read_stream, write_stream):
                    await self.server.run(
                        read_stream,
                        write_stream,
                        self.server.create_initialization_options(),
                    )
                
                return Response(status_code=200)
            except Exception as e:
                logger.error(f"SSE处理器错误: {str(e)}")
                return JSONResponse({"error": "Internal server error"}, status_code=500)
        
        # 健康检查端点
        async def health_check(request: Request):
            return JSONResponse({
                "status": "ok", 
                "service": "mcp-server",
                "version": "1.0"
            })
        
        # 获取服务器状态
        async def get_status(request: Request):
            return JSONResponse({
                "server": "mcp_qa_server",
                "status": "running",
                "initialized": self._initialized,
                "config": {
                    "host": config.server.HOST,
                    "port": config.server.PORT,
                    "debug": config.server.DEBUG,
                    "allowed_dirs": config.security.ALLOWED_DIRS
                }
            })
        
        # 基础路由
        routes = [
            Route("/sse", endpoint=handle_sse),
            Route("/health", endpoint=health_check),
            Route("/status", endpoint=get_status),
            Mount("/messages/", app=sse.handle_post_message),
        ]
        
        # 添加HTTP API路由
        try:
            http_routes = create_http_routes()
            routes.extend(http_routes)
        except Exception as e:
            logger.warning(f"HTTP API路由创建失败: {e}")
        
        return Starlette(
            debug=config.server.DEBUG,
            routes=routes,
            on_startup=[self._on_startup],
            on_shutdown=[self._on_shutdown],
        )
    
    async def _on_startup(self):
        """服务器启动时的回调"""
        logger.info("MCP服务器正在启动...")
        logger.info(f"监听地址: {config.server.HOST}:{config.server.PORT}")
        logger.info(f"白名单目录: {config.security.ALLOWED_DIRS}")
        logger.info(f"调试模式: {config.server.DEBUG}")
    
    async def _on_shutdown(self):
        """服务器关闭时的回调"""
        logger.info("MCP服务器正在关闭...")
    
    def run(self, host: Optional[str] = None, port: Optional[int] = None, 
            debug: Optional[bool] = None, **kwargs) -> None:
        """运行服务器"""
        if not self._initialized:
            self.initialize()
        
        # 使用提供的参数或默认配置
        run_host = host or config.server.HOST
        run_port = port or config.server.PORT
        run_debug = debug if debug is not None else config.server.DEBUG
        
        logger.info(f"在 {run_host}:{run_port} 启动MCP服务器")
        
        try:
            uvicorn.run(
                self.app,
                host=run_host,
                port=run_port,
                log_level="info" if not run_debug else "debug",
                **kwargs
            )
        except Exception as e:
            logger.error(f"服务器运行失败: {e}")
            raise MCPServerError(f"Failed to run server: {e}")


def create_server() -> MCPServer:
    """创建MCP服务器实例"""
    return MCPServer()


def run_server(host: Optional[str] = None, port: Optional[int] = None, 
               debug: Optional[bool] = None, **kwargs) -> None:
    """快速启动服务器的便捷函数"""
    server = create_server()
    server.run(host=host, port=port, debug=debug, **kwargs)


if __name__ == "__main__":
    # 直接运行时使用默认配置
    run_server()