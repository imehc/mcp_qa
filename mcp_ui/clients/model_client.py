"""
统一模型客户端
支持Ollama、OpenAI、Anthropic、Google、Azure等多种模型提供商
"""

import asyncio
import time
from typing import Dict, List, Optional, AsyncGenerator, Any
from abc import ABC, abstractmethod

from ..config import ModelProvider, ModelConfig
from ..utils.logger import get_logger

logger = get_logger(__name__)

class BaseModelClient(ABC):
    """模型客户端基类"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.provider = config.provider
        self.model_name = config.model_name
        
    @abstractmethod
    async def generate(self, prompt: str, system: str = None, **kwargs) -> str:
        """生成文本回答"""
        pass
    
    @abstractmethod
    async def generate_stream(self, prompt: str, system: str = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成文本"""
        pass
    
    @abstractmethod
    async def list_models(self) -> List[str]:
        """获取可用模型列表"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """检查服务健康状态"""
        pass

class OllamaModelClient(BaseModelClient):
    """Ollama本地模型客户端"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        import httpx
        self.client = httpx.AsyncClient(timeout=config.timeout)
        self.base_url = config.base_url
        
    async def generate(self, prompt: str, system: str = None, **kwargs) -> str:
        """生成文本回答"""
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", self.config.temperature),
                    "num_predict": kwargs.get("max_tokens", self.config.max_tokens)
                }
            }
            
            if system:
                payload["system"] = system
                
            response = await self.client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
            
        except Exception as e:
            logger.error(f"Ollama生成失败: {e}")
            return f"模型调用失败: {e}"
    
    async def generate_stream(self, prompt: str, system: str = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成文本"""
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": kwargs.get("temperature", self.config.temperature),
                    "num_predict": kwargs.get("max_tokens", self.config.max_tokens)
                }
            }
            
            if system:
                payload["system"] = system
                
            async with self.client.stream("POST", f"{self.base_url}/api/generate", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        try:
                            import json
                            chunk = json.loads(line)
                            if "response" in chunk:
                                yield chunk["response"]
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error(f"Ollama流式生成失败: {e}")
            yield f"错误: {e}"
    
    async def list_models(self) -> List[str]:
        """获取可用模型列表"""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            result = response.json()
            return [model["name"] for model in result.get("models", [])]
        except Exception as e:
            logger.error(f"获取Ollama模型列表失败: {e}")
            return []
    
    async def health_check(self) -> bool:
        """检查Ollama服务健康状态"""
        try:
            models = await self.list_models()
            return isinstance(models, list)
        except:
            return False

class OpenAIModelClient(BaseModelClient):
    """OpenAI模型客户端"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        
    async def _get_client(self):
        """获取OpenAI客户端"""
        try:
            import openai
            return openai.AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout
            )
        except ImportError:
            raise ImportError("请安装openai包: pip install openai")
    
    async def generate(self, prompt: str, system: str = None, **kwargs) -> str:
        """生成文本回答"""
        try:
            client = await self._get_client()
            
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens)
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI生成失败: {e}")
            return f"模型调用失败: {e}"
    
    async def generate_stream(self, prompt: str, system: str = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成文本"""
        try:
            client = await self._get_client()
            
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            
            stream = await client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"OpenAI流式生成失败: {e}")
            yield f"错误: {e}"
    
    async def list_models(self) -> List[str]:
        """获取可用模型列表"""
        try:
            client = await self._get_client()
            models = await client.models.list()
            return [model.id for model in models.data]
        except Exception as e:
            logger.error(f"获取OpenAI模型列表失败: {e}")
            return []
    
    async def health_check(self) -> bool:
        """检查OpenAI服务健康状态"""
        try:
            client = await self._get_client()
            await client.models.list()
            return True
        except:
            return False

class AnthropicModelClient(BaseModelClient):
    """Anthropic模型客户端"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        
    async def _get_client(self):
        """获取Anthropic客户端"""
        try:
            import anthropic
            return anthropic.AsyncAnthropic(
                api_key=self.config.api_key,
                timeout=self.config.timeout
            )
        except ImportError:
            raise ImportError("请安装anthropic包: pip install anthropic")
    
    async def generate(self, prompt: str, system: str = None, **kwargs) -> str:
        """生成文本回答"""
        try:
            client = await self._get_client()
            
            messages = [{"role": "user", "content": prompt}]
            
            response = await client.messages.create(
                model=self.model_name,
                messages=messages,
                system=system,
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens)
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Anthropic生成失败: {e}")
            return f"模型调用失败: {e}"
    
    async def generate_stream(self, prompt: str, system: str = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成文本"""
        try:
            client = await self._get_client()
            
            messages = [{"role": "user", "content": prompt}]
            
            async with client.messages.stream(
                model=self.model_name,
                messages=messages,
                system=system,
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens)
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                    
        except Exception as e:
            logger.error(f"Anthropic流式生成失败: {e}")
            yield f"错误: {e}"
    
    async def list_models(self) -> List[str]:
        """获取可用模型列表"""
        # Anthropic不提供模型列表API，返回常用模型
        return [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229", 
            "claude-3-haiku-20240307",
            "claude-2.1",
            "claude-2.0"
        ]
    
    async def health_check(self) -> bool:
        """检查Anthropic服务健康状态"""
        try:
            client = await self._get_client()
            # 发送一个简单的测试请求
            await client.messages.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            return True
        except:
            return False

class GoogleModelClient(BaseModelClient):
    """Google模型客户端"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        
    async def _get_client(self):
        """获取Google客户端"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.config.api_key)
            return genai.GenerativeModel(self.model_name)
        except ImportError:
            raise ImportError("请安装google-generativeai包: pip install google-generativeai")
    
    async def generate(self, prompt: str, system: str = None, **kwargs) -> str:
        """生成文本回答"""
        try:
            model = await self._get_client()
            
            full_prompt = prompt
            if system:
                full_prompt = f"{system}\n\n{prompt}"
            
            response = await asyncio.to_thread(
                model.generate_content,
                full_prompt,
                generation_config={
                    "temperature": kwargs.get("temperature", self.config.temperature),
                    "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens)
                }
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Google生成失败: {e}")
            return f"模型调用失败: {e}"
    
    async def generate_stream(self, prompt: str, system: str = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成文本"""
        try:
            model = await self._get_client()
            
            full_prompt = prompt
            if system:
                full_prompt = f"{system}\n\n{prompt}"
            
            response = await asyncio.to_thread(
                model.generate_content,
                full_prompt,
                generation_config={
                    "temperature": kwargs.get("temperature", self.config.temperature),
                    "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens)
                },
                stream=True
            )
            
            for chunk in response:
                if chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            logger.error(f"Google流式生成失败: {e}")
            yield f"错误: {e}"
    
    async def list_models(self) -> List[str]:
        """获取可用模型列表"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.config.api_key)
            models = await asyncio.to_thread(genai.list_models)
            return [model.name.split('/')[-1] for model in models]
        except Exception as e:
            logger.error(f"获取Google模型列表失败: {e}")
            return ["gemini-pro", "gemini-pro-vision"]
    
    async def health_check(self) -> bool:
        """检查Google服务健康状态"""
        try:
            model = await self._get_client()
            await asyncio.to_thread(
                model.generate_content,
                "test",
                generation_config={"max_output_tokens": 1}
            )
            return True
        except:
            return False

class UnifiedModelClient:
    """统一模型客户端"""
    
    def __init__(self):
        self.clients: Dict[str, BaseModelClient] = {}
        self.default_client: Optional[BaseModelClient] = None
        
    def add_client(self, name: str, client: BaseModelClient, is_default: bool = False):
        """添加模型客户端"""
        self.clients[name] = client
        if is_default or not self.default_client:
            self.default_client = client
        logger.info(f"添加模型客户端: {name} ({client.provider.value})")
    
    def get_client(self, name: str = None) -> Optional[BaseModelClient]:
        """获取模型客户端"""
        if name:
            return self.clients.get(name)
        return self.default_client
    
    async def generate(self, prompt: str, model_name: str = None, system: str = None, **kwargs) -> str:
        """生成文本回答"""
        client = self.get_client(model_name)
        if not client:
            return f"未找到模型客户端: {model_name}"
        
        return await client.generate(prompt, system, **kwargs)
    
    async def generate_stream(self, prompt: str, model_name: str = None, system: str = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成文本"""
        client = self.get_client(model_name)
        if not client:
            yield f"未找到模型客户端: {model_name}"
            return
        
        async for chunk in client.generate_stream(prompt, system, **kwargs):
            yield chunk
    
    async def list_all_models(self) -> Dict[str, List[str]]:
        """获取所有客户端的模型列表"""
        results = {}
        for name, client in self.clients.items():
            try:
                models = await client.list_models()
                results[name] = models
            except Exception as e:
                logger.error(f"获取{name}模型列表失败: {e}")
                results[name] = []
        return results
    
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

def create_model_client(config: ModelConfig) -> BaseModelClient:
    """根据配置创建模型客户端"""
    if config.provider == ModelProvider.OLLAMA:
        return OllamaModelClient(config)
    elif config.provider == ModelProvider.OPENAI:
        return OpenAIModelClient(config)
    elif config.provider == ModelProvider.ANTHROPIC:
        return AnthropicModelClient(config)
    elif config.provider == ModelProvider.GOOGLE:
        return GoogleModelClient(config)
    else:
        raise ValueError(f"不支持的模型提供商: {config.provider}")

# 全局统一客户端实例
unified_model_client = UnifiedModelClient()