"""
HTTP服务器API模块
提供基本的HTTP接口
"""

import logging
from typing import List
from starlette.routing import Route
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


async def health_check(request):
    """健康检查端点"""
    return JSONResponse({
        "status": "ok", 
        "service": "mcp-server-api",
        "version": "1.0"
    })


async def get_server_info(request):
    """获取服务器信息"""
    return JSONResponse({
        "server": "mcp_qa_server",
        "status": "running",
        "api_version": "1.0"
    })


def create_http_routes() -> List[Route]:
    """创建HTTP路由"""
    return [
        Route("/api/health", endpoint=health_check),
        Route("/api/info", endpoint=get_server_info),
    ]