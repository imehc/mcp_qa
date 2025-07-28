"""
MCP客户端模块
提供与本地和远程MCP服务器通信的功能
"""

import httpx
from typing import Dict, List, Optional, Any
import json
from ..config.settings import UIConfig, MCPServerConfig, MCPServerType
from ..utils.logger import get_logger

logger = get_logger(__name__)

class MCPClient:
    """支持多服务器的MCP客户端"""
    
    def __init__(self, server_config: MCPServerConfig):
        self.config = server_config
        self.base_url = server_config.url
        self.timeout = server_config.timeout
        self.api_key = server_config.api_key
        self.server_type = server_config.server_type
        
    async def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """发起HTTP请求"""
        try:
            headers = {"Content-Type": "application/json"}
            
            # 添加API密钥认证
            if self.api_key:
                if self.server_type == MCPServerType.REMOTE:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                else:
                    headers["X-API-Key"] = self.api_key
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}{endpoint}"
                
                if method.upper() == "GET":
                    response = await client.get(url, params=data, headers=headers)
                else:
                    response = await client.post(url, json=data, headers=headers)
                
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
    
    async def list_tools(self) -> Dict[str, Any]:
        """列出可用工具"""
        return await self._make_request("GET", "/tools/list")
    
    async def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """调用特定工具"""
        return await self._make_request("POST", f"/tools/call/{tool_name}", parameters)
    
    async def get_server_info(self) -> Dict[str, Any]:
        """获取服务器信息"""
        return await self._make_request("GET", "/info")

class UnifiedMCPClient:
    """统一MCP客户端管理器"""
    
    def __init__(self):
        self.clients: Dict[str, MCPClient] = {}
        self.default_client: Optional[MCPClient] = None
        
    def add_client(self, name: str, client: MCPClient, is_default: bool = False):
        """添加MCP客户端"""
        self.clients[name] = client
        if is_default or not self.default_client:
            self.default_client = client
        logger.info(f"添加MCP客户端: {name} ({client.server_type.value})")
    
    def get_client(self, name: str = None) -> Optional[MCPClient]:
        """获取MCP客户端"""
        if name:
            return self.clients.get(name)
        return self.default_client
    
    async def health_check_all(self) -> Dict[str, bool]:
        """检查所有客户端健康状态"""
        results = {}
        for name, client in self.clients.items():
            try:
                results[name] = await client.health_check()
            except Exception as e:
                logger.error(f"检查{name}健康状态失败: {e}")
                results[name] = False
        return results
    
    async def parse_document(self, file_path: str, server_name: str = None) -> Dict[str, Any]:
        """解析文档"""
        client = self.get_client(server_name)
        if not client:
            return {"error": f"未找到MCP服务器: {server_name}"}
        return await client.parse_document(file_path)
    
    async def search_documents(self, query: str, top_k: int = 5, server_name: str = None) -> Dict[str, Any]:
        """搜索文档"""
        client = self.get_client(server_name)
        if not client:
            return {"error": f"未找到MCP服务器: {server_name}"}
        return await client.search_documents(query, top_k)
    
    async def build_index(self, directory: str, recursive: bool = True, server_name: str = None) -> Dict[str, Any]:
        """构建文档索引"""
        client = self.get_client(server_name)
        if not client:
            return {"error": f"未找到MCP服务器: {server_name}"}
        return await client.build_index(directory, recursive)
    
    async def list_directory(self, path: str, server_name: str = None) -> Dict[str, Any]:
        """列出目录内容"""
        client = self.get_client(server_name)
        if not client:
            return {"error": f"未找到MCP服务器: {server_name}"}
        return await client.list_directory(path)
    
    async def read_file(self, file_path: str, server_name: str = None) -> Dict[str, Any]:
        """读取文件内容"""
        client = self.get_client(server_name)
        if not client:
            return {"error": f"未找到MCP服务器: {server_name}"}
        return await client.read_file(file_path)
    
    async def get_cache_stats(self, server_name: str = None) -> Dict[str, Any]:
        """获取缓存统计信息"""
        client = self.get_client(server_name)
        if not client:
            return {"error": f"未找到MCP服务器: {server_name}"}
        return await client.get_cache_stats()
    
    async def clear_cache(self, server_name: str = None) -> Dict[str, Any]:
        """清空缓存"""
        client = self.get_client(server_name)
        if not client:
            return {"error": f"未找到MCP服务器: {server_name}"}
        return await client.clear_cache()
    
    async def list_all_tools(self) -> Dict[str, Any]:
        """列出所有服务器的可用工具"""
        results = {}
        for name, client in self.clients.items():
            try:
                tools = await client.list_tools()
                results[name] = tools
            except Exception as e:
                logger.error(f"获取{name}工具列表失败: {e}")
                results[name] = {"error": str(e)}
        return results
    
    async def call_tool(self, tool_name: str, parameters: Dict[str, Any], server_name: str = None) -> Dict[str, Any]:
        """调用特定工具"""
        client = self.get_client(server_name)
        if not client:
            return {"error": f"未找到MCP服务器: {server_name}"}
        return await client.call_tool(tool_name, parameters)
    
    async def get_all_server_info(self) -> Dict[str, Any]:
        """获取所有服务器信息"""
        results = {}
        for name, client in self.clients.items():
            try:
                info = await client.get_server_info()
                results[name] = info
            except Exception as e:
                logger.error(f"获取{name}服务器信息失败: {e}")
                results[name] = {"error": str(e)}
        return results

def create_mcp_client(config: MCPServerConfig) -> MCPClient:
    """根据配置创建MCP客户端"""
    return MCPClient(config)

# 创建统一MCP客户端实例
unified_mcp_client = UnifiedMCPClient()

# 向后兼容的单一客户端实例
mcp_client = MCPClient(MCPServerConfig(
    name="default",
    server_type=MCPServerType.LOCAL,
    url=UIConfig.MCP_SERVER_URL,
    timeout=UIConfig.REQUEST_TIMEOUT
))