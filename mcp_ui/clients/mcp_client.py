"""
MCP客户端模块
提供与MCP服务器通信的功能
"""

import httpx
from typing import Dict, List, Optional, Any
import json
from ..config.settings import UIConfig
from ..utils.logger import get_logger

logger = get_logger(__name__)

class MCPClient:
    """MCP工具服务器客户端"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or UIConfig.MCP_SERVER_URL
        self.timeout = UIConfig.REQUEST_TIMEOUT
        
    async def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """发起HTTP请求"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}{endpoint}"
                
                if method.upper() == "GET":
                    response = await client.get(url, params=data)
                else:
                    response = await client.post(url, json=data)
                
                response.raise_for_status()
                return response.json()
                
        except httpx.TimeoutException:
            logger.error(f"请求超时: {endpoint}")
            return {"error": "请求超时"}
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP错误 {e.response.status_code}: {endpoint}")
            return {"error": f"HTTP错误: {e.response.status_code}"}
        except Exception as e:
            logger.error(f"请求失败: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> bool:
        """检查MCP服务器健康状态"""
        result = await self._make_request("GET", "/health")
        return "error" not in result
    
    async def parse_document(self, file_path: str) -> Dict[str, Any]:
        """解析文档"""
        return await self._make_request("POST", "/parse", {"file_path": file_path})
    
    async def search_documents(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """搜索文档"""
        return await self._make_request("POST", "/search", {
            "query": query, 
            "top_k": top_k
        })
    
    async def build_index(self, directory: str, recursive: bool = True) -> Dict[str, Any]:
        """构建文档索引"""
        return await self._make_request("POST", "/index", {
            "directory": directory,
            "recursive": recursive
        })
    
    async def list_directory(self, path: str) -> Dict[str, Any]:
        """列出目录内容"""
        return await self._make_request("POST", "/tools/list_directory", {"path": path})
    
    async def read_file(self, file_path: str) -> Dict[str, Any]:
        """读取文件内容"""
        return await self._make_request("POST", "/tools/read_file", {"file_path": file_path})
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return await self._make_request("GET", "/tools/cache_stats")
    
    async def clear_cache(self) -> Dict[str, Any]:
        """清空缓存"""
        return await self._make_request("POST", "/tools/cache_clear")

# 全局MCP客户端实例
mcp_client = MCPClient()