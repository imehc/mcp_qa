"""
通用模型适配器系统
提供统一的模型接口，支持动态添加新的模型提供商
"""

import asyncio
import time
from typing import Dict, List, Optional, AsyncGenerator, Any, Type
from abc import ABC, abstractmethod
import importlib
from dataclasses import dataclass

from ..config import ModelProvider, ModelConfig  
from ..utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class ModelResponse:
    """统一的模型响应格式"""
    content: str
    model: str
    provider: str
    usage: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

class ModelAdapter(ABC):
    """模型适配器基类"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.provider = config.provider.value
        self.model_name = config.model_name
        
    @abstractmethod
    async def generate(self, prompt: str, system: str = None, **kwargs) -> ModelResponse:
        """生成文本回答"""
        pass
    
    async def generate_stream(self, prompt: str, system: str = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成文本（默认实现，子类可重写）"""
        response = await self.generate(prompt, system, **kwargs)
        yield response.content
    
    @abstractmethod
    async def list_models(self) -> List[str]:
        """获取可用模型列表"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """检查服务健康状态"""
        pass
    
    def get_required_packages(self) -> List[str]:
        """获取所需的Python包列表"""
        return []

class OllamaAdapter(ModelAdapter):
    """Ollama模型适配器"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._client = None
        
    async def _get_client(self):
        """获取HTTP客户端"""
        if not self._client:
            import httpx
            self._client = httpx.AsyncClient(timeout=self.config.timeout)
        return self._client
        
    async def generate(self, prompt: str, system: str = None, **kwargs) -> ModelResponse:
        """生成文本回答"""
        try:
            client = await self._get_client()
            
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
                
            response = await client.post(f"{self.config.base_url}/api/generate", json=payload)
            response.raise_for_status()
            result = response.json()
            
            return ModelResponse(
                content=result.get("response", ""),
                model=self.model_name,
                provider=self.provider,
                metadata={"total_duration": result.get("total_duration")}
            )
            
        except Exception as e:
            logger.error(f"Ollama生成失败: {e}")
            return ModelResponse(
                content=f"模型调用失败: {e}",
                model=self.model_name,
                provider=self.provider
            )
    
    async def generate_stream(self, prompt: str, system: str = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成文本"""
        try:
            client = await self._get_client()
            
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
                
            async with client.stream("POST", f"{self.config.base_url}/api/generate", json=payload) as response:
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
            client = await self._get_client()
            response = await client.get(f"{self.config.base_url}/api/tags")
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

class OpenAICompatibleAdapter(ModelAdapter):
    """OpenAI兼容的模型适配器（支持OpenAI、Azure、以及其他兼容的API）"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._client = None
        
    def get_required_packages(self) -> List[str]:
        return ["openai"]
        
    async def _get_client(self):
        """获取OpenAI客户端"""
        if not self._client:
            try:
                import openai
                if self.config.provider == ModelProvider.AZURE:
                    self._client = openai.AsyncAzureOpenAI(
                        api_key=self.config.api_key,
                        azure_endpoint=self.config.base_url,
                        api_version=self.config.api_version,
                        timeout=self.config.timeout
                    )
                else:
                    self._client = openai.AsyncOpenAI(
                        api_key=self.config.api_key,
                        base_url=self.config.base_url,
                        timeout=self.config.timeout
                    )
            except ImportError:
                raise ImportError("请安装openai包: pip install openai")
        return self._client
    
    async def generate(self, prompt: str, system: str = None, **kwargs) -> ModelResponse:
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
            
            return ModelResponse(
                content=response.choices[0].message.content,
                model=self.model_name,
                provider=self.provider,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                } if response.usage else None
            )
            
        except Exception as e:
            logger.error(f"{self.provider}生成失败: {e}")
            return ModelResponse(
                content=f"模型调用失败: {e}",
                model=self.model_name,
                provider=self.provider
            )
    
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
            logger.error(f"{self.provider}流式生成失败: {e}")
            yield f"错误: {e}"
    
    async def list_models(self) -> List[str]:
        """获取可用模型列表"""
        try:
            client = await self._get_client()
            models = await client.models.list()
            return [model.id for model in models.data]
        except Exception as e:
            logger.error(f"获取{self.provider}模型列表失败: {e}")
            return []
    
    async def health_check(self) -> bool:
        """检查服务健康状态"""
        try:
            client = await self._get_client()
            await client.models.list()
            return True
        except:
            return False

class AnthropicAdapter(ModelAdapter):
    """Anthropic模型适配器"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._client = None
        
    def get_required_packages(self) -> List[str]:
        return ["anthropic"]
        
    async def _get_client(self):
        """获取Anthropic客户端"""
        if not self._client:
            try:
                import anthropic
                self._client = anthropic.AsyncAnthropic(
                    api_key=self.config.api_key,
                    timeout=self.config.timeout
                )
            except ImportError:
                raise ImportError("请安装anthropic包: pip install anthropic")
        return self._client
    
    async def generate(self, prompt: str, system: str = None, **kwargs) -> ModelResponse:
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
            
            return ModelResponse(
                content=response.content[0].text,
                model=self.model_name,
                provider=self.provider,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                } if response.usage else None
            )
            
        except Exception as e:
            logger.error(f"Anthropic生成失败: {e}")
            return ModelResponse(
                content=f"模型调用失败: {e}",
                model=self.model_name,
                provider=self.provider
            )
    
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

class ModelAdapterRegistry:
    """模型适配器注册表"""
    
    def __init__(self):
        self._adapters: Dict[ModelProvider, Type[ModelAdapter]] = {}
        self._register_builtin_adapters()
    
    def _register_builtin_adapters(self):
        """注册内置适配器"""
        self._adapters[ModelProvider.OLLAMA] = OllamaAdapter
        self._adapters[ModelProvider.OPENAI] = OpenAICompatibleAdapter
        self._adapters[ModelProvider.AZURE] = OpenAICompatibleAdapter
        self._adapters[ModelProvider.ANTHROPIC] = AnthropicAdapter
        self._adapters[ModelProvider.GOOGLE] = OpenAICompatibleAdapter  # Google Gemini也可以用OpenAI兼容接口
        self._adapters[ModelProvider.DEEPSEEK] = OpenAICompatibleAdapter  # DeepSeek使用OpenAI兼容接口
        self._adapters[ModelProvider.QWEN] = OpenAICompatibleAdapter  # Qwen使用OpenAI兼容接口
    
    def register_adapter(self, provider: ModelProvider, adapter_class: Type[ModelAdapter]):
        """注册新的适配器"""
        self._adapters[provider] = adapter_class
        logger.info(f"注册模型适配器: {provider.value} -> {adapter_class.__name__}")
    
    def get_adapter_class(self, provider: ModelProvider) -> Optional[Type[ModelAdapter]]:
        """获取适配器类"""
        return self._adapters.get(provider)
    
    def create_adapter(self, config: ModelConfig) -> Optional[ModelAdapter]:
        """创建适配器实例"""
        adapter_class = self.get_adapter_class(config.provider)
        if not adapter_class:
            logger.error(f"未找到适配器: {config.provider}")
            return None
        
        try:
            # 检查所需包
            adapter_instance = adapter_class(config)
            required_packages = adapter_instance.get_required_packages()
            
            for package in required_packages:
                try:
                    importlib.import_module(package)
                except ImportError:
                    logger.error(f"缺少必要的包: {package}")
                    return None
            
            return adapter_instance
            
        except Exception as e:
            logger.error(f"创建适配器失败: {e}")
            return None
    
    def list_supported_providers(self) -> List[str]:
        """列出支持的提供商"""
        return [provider.value for provider in self._adapters.keys()]

class UnifiedModelClient:
    """统一模型客户端"""
    
    def __init__(self):
        self.adapters: Dict[str, ModelAdapter] = {}
        self.default_adapter: Optional[ModelAdapter] = None
        self.registry = ModelAdapterRegistry()
        
    def add_adapter(self, name: str, adapter: ModelAdapter, is_default: bool = False):
        """添加模型适配器"""
        self.adapters[name] = adapter
        if is_default or not self.default_adapter:
            self.default_adapter = adapter
        logger.info(f"添加模型适配器: {name} ({adapter.provider})")
    
    def get_adapter(self, name: str = None) -> Optional[ModelAdapter]:
        """获取模型适配器"""
        if name:
            return self.adapters.get(name)
        return self.default_adapter
    
    async def generate(self, prompt: str, model_name: str = None, system: str = None, **kwargs) -> ModelResponse:
        """生成文本回答"""
        adapter = self.get_adapter(model_name)
        if not adapter:
            return ModelResponse(
                content=f"未找到模型适配器: {model_name}",
                model=model_name or "unknown",
                provider="unknown"
            )
        
        return await adapter.generate(prompt, system, **kwargs)
    
    async def generate_stream(self, prompt: str, model_name: str = None, system: str = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成文本"""
        adapter = self.get_adapter(model_name)
        if not adapter:
            yield f"未找到模型适配器: {model_name}"
            return
        
        async for chunk in adapter.generate_stream(prompt, system, **kwargs):
            yield chunk
    
    async def list_all_models(self) -> Dict[str, List[str]]:
        """获取所有适配器的模型列表"""
        results = {}
        for name, adapter in self.adapters.items():
            try:
                models = await adapter.list_models()
                results[name] = models
            except Exception as e:
                logger.error(f"获取{name}模型列表失败: {e}")
                results[name] = []
        return results
    
    async def health_check_all(self) -> Dict[str, bool]:
        """检查所有适配器健康状态"""
        results = {}
        for name, adapter in self.adapters.items():
            try:
                results[name] = await adapter.health_check()
            except Exception as e:
                logger.error(f"检查{name}健康状态失败: {e}")
                results[name] = False
        return results
    
    def register_custom_adapter(self, provider: ModelProvider, adapter_class: Type[ModelAdapter]):
        """注册自定义适配器"""
        self.registry.register_adapter(provider, adapter_class)
    
    def create_adapter_from_config(self, config: ModelConfig, name: str = None, is_default: bool = False) -> bool:
        """从配置创建并添加适配器"""
        adapter = self.registry.create_adapter(config)
        if adapter:
            adapter_name = name or f"{config.provider.value}_{config.model_name}"
            self.add_adapter(adapter_name, adapter, is_default)
            return True
        return False

# 全局统一客户端实例
unified_model_client = UnifiedModelClient()

# 全局注册表实例
model_adapter_registry = ModelAdapterRegistry()