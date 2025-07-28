"""
Ollama本地模型客户端
提供与Ollama服务的通信功能
"""

import httpx
from typing import Dict, List, Optional, AsyncGenerator
import json
from ..config.settings import UIConfig
from ..utils.logger import get_logger

logger = get_logger(__name__)

class OllamaClient:
    """Ollama本地大语言模型客户端"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or UIConfig.OLLAMA_BASE_URL
        self.timeout = UIConfig.MODEL_TIMEOUT
        
    async def _make_request(self, endpoint: str, data: Dict) -> Dict:
        """发起HTTP请求"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}{endpoint}", json=data)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ollama请求失败: {e}")
            return {"error": str(e)}
    
    async def _stream_request(self, endpoint: str, data: Dict) -> AsyncGenerator[Dict, None]:
        """流式请求"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", f"{self.base_url}{endpoint}", json=data) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                yield json.loads(line)
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"Ollama流式请求失败: {e}")
            yield {"error": str(e)}
    
    async def list_models(self) -> List[str]:
        """获取可用模型列表"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                result = response.json()
                return [model["name"] for model in result.get("models", [])]
        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
            return []
    
    async def generate(self, model: str, prompt: str, system: str = None, **kwargs) -> str:
        """生成文本回答"""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            **kwargs
        }
        
        if system:
            payload["system"] = system
            
        result = await self._make_request("/api/generate", payload)
        
        if "error" in result:
            return f"模型调用失败: {result['error']}"
            
        return result.get("response", "")
    
    async def generate_stream(self, model: str, prompt: str, system: str = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成文本"""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            **kwargs
        }
        
        if system:
            payload["system"] = system
            
        async for chunk in self._stream_request("/api/generate", payload):
            if "error" in chunk:
                yield f"错误: {chunk['error']}"
                break
            elif "response" in chunk:
                yield chunk["response"]
    
    async def chat(self, model: str, messages: List[Dict], **kwargs) -> str:
        """对话模式"""
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            **kwargs
        }
        
        result = await self._make_request("/api/chat", payload)
        
        if "error" in result:
            return f"对话失败: {result['error']}"
            
        return result.get("message", {}).get("content", "")
    
    async def chat_stream(self, model: str, messages: List[Dict], **kwargs) -> AsyncGenerator[str, None]:
        """流式对话"""
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            **kwargs
        }
        
        async for chunk in self._stream_request("/api/chat", payload):
            if "error" in chunk:
                yield f"错误: {chunk['error']}"
                break
            elif "message" in chunk and "content" in chunk["message"]:
                yield chunk["message"]["content"]
    
    async def pull_model(self, model: str) -> Dict:
        """拉取模型"""
        payload = {"name": model}
        return await self._make_request("/api/pull", payload)
    
    async def delete_model(self, model: str) -> Dict:
        """删除模型"""
        payload = {"name": model}
        return await self._make_request("/api/delete", payload)
    
    async def model_info(self, model: str) -> Dict:
        """获取模型信息"""
        payload = {"name": model}
        return await self._make_request("/api/show", payload)
    
    async def health_check(self) -> bool:
        """检查Ollama服务健康状态"""
        try:
            models = await self.list_models()
            return isinstance(models, list)
        except:
            return False

# 全局Ollama客户端实例
ollama_client = OllamaClient()