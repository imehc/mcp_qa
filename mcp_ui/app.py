"""
MCP UI主应用文件
整合所有功能模块，提供统一的交互界面
"""

import asyncio
import time
from pathlib import Path
from typing import List, Dict, Any
import chainlit as cl
from chainlit.types import AskFileResponse
import aiofiles

from .clients import mcp_client, ollama_client
from .config import UIConfig, SystemPrompts
from .handlers import command_registry
from .utils import get_logger, ui_logger

logger = get_logger(__name__)

@cl.on_chat_start
async def on_chat_start():
    """聊天开始时的初始化"""
    
    logger.info("用户开始新的聊天会话")
    
    # 初始化用户会话
    cl.user_session.set("conversation_history", [])
    cl.user_session.set("knowledge_base", {})
    cl.user_session.set("current_model", UIConfig.DEFAULT_MODEL)
    
    # 检查服务状态
    mcp_healthy = await mcp_client.health_check()
    ollama_healthy = await ollama_client.health_check()
    
    if not mcp_healthy:
        await cl.Message(content="⚠️ MCP服务器连接失败，部分功能可能不可用").send()
        logger.warning("MCP服务器连接失败")
    
    if not ollama_healthy:
        await cl.Message(content="⚠️ Ollama服务连接失败，AI功能可能不可用").send()
        logger.warning("Ollama服务连接失败")
    
    # 获取可用模型并让用户选择
    if ollama_healthy:
        models = await ollama_client.list_models()
        if models:
            model_options = [cl.SelectOption(value=model, label=model) for model in models]
            selected_model = await cl.AskSelectMessage(
                content="🤖 请选择要使用的本地模型：",
                options=model_options,
                timeout=30
            ).send()
            if selected_model:
                cl.user_session.set("current_model", selected_model["value"])
                logger.info(f"用户选择模型: {selected_model['value']}")
    
    # 发送欢迎消息
    welcome_msg = """# 🤖 智能知识库助手

欢迎使用基于MCP的智能知识库系统！

## 🚀 功能特性
- 📁 **文档解析**: 支持PDF、Word、Excel、PPT、Markdown等格式
- 🔍 **语义搜索**: 基于向量相似度的智能搜索
- 🧠 **本地模型**: 集成Ollama本地大语言模型
- 📊 **过程可视化**: 实时展示思考和处理过程
- 🛠️ **MCP工具**: 强大的模块化工具集

## 🎯 使用方式
1. **上传文档**: 点击上传按钮添加文档到知识库
2. **构建索引**: 使用 `/build` 命令构建文档索引
3. **智能问答**: 直接提问，系统会自动搜索相关内容并回答
4. **工具调用**: 使用 `/help` 查看所有可用命令

开始对话吧！ 🎉"""
    
    await cl.Message(content=welcome_msg).send()
    ui_logger.log_user_action("chat_start")

@cl.on_message
async def on_message(message: cl.Message):
    """处理用户消息"""
    
    user_input = message.content.strip()
    ui_logger.log_user_action("send_message", {"length": len(user_input)})
    
    # 处理命令
    if user_input.startswith("/"):
        await handle_command(user_input)
        return
    
    # 处理普通问答
    await handle_qa(user_input)

async def handle_command(command_text: str):
    """处理命令输入"""
    
    parts = command_text.strip().split()
    if not parts:
        return
    
    command = parts[0][1:].lower()  # 移除 '/' 前缀
    args = parts[1:]
    
    # 获取命令处理器
    handler = command_registry.get_handler(command)
    
    if handler:
        logger.info(f"执行命令: {command} {args}")
        try:
            await handler.execute(args)
        except Exception as e:
            error_msg = f"❌ 命令执行失败: {str(e)}"
            await cl.Message(content=error_msg).send()
            ui_logger.log_error(e, f"执行命令失败: {command}")
    else:
        # 未知命令
        available_commands = command_registry.list_commands()
        error_msg = f"❌ 未知命令: `{command}`\n\n💡 可用命令: {', '.join([f'`/{cmd}`' for cmd in available_commands])}\n\n使用 `/help` 查看详细帮助。"
        await cl.Message(content=error_msg).send()

async def handle_qa(question: str):
    """处理问答请求"""
    
    logger.info(f"处理问答请求: {question[:100]}...")
    
    # 显示思考过程
    thinking_msg = cl.Message(content="🤔 正在思考...")
    await thinking_msg.send()
    
    start_time = time.time()
    
    try:
        # 1. 搜索相关文档
        await thinking_msg.update(content="🔍 正在搜索相关文档...")
        search_result = await mcp_client.search_documents(question, top_k=UIConfig.DEFAULT_SEARCH_K)
        
        # 2. 构建上下文
        context = ""
        context_sources = []
        
        if search_result.get("results"):
            await thinking_msg.update(content="📚 正在分析搜索结果...")
            for doc in search_result["results"]:
                title = doc.get('title', '未知文档')
                content = doc.get('content', '')
                score = doc.get('score', 0)
                
                context += f"文档: {title}\n内容: {content}\n相关性: {score:.3f}\n\n"
                context_sources.append({
                    "title": title,
                    "score": score,
                    "content": content[:200] + "..." if len(content) > 200 else content
                })
        
        # 3. 生成回答
        await thinking_msg.update(content="🧠 正在生成回答...")
        
        current_model = cl.user_session.get("current_model", UIConfig.DEFAULT_MODEL)
        
        # 构建提示词
        user_prompt = f"""问题: {question}

检索到的相关文档:
{context if context else "未找到相关文档"}

请基于上述文档内容回答问题。如果文档中没有相关信息，请明确说明。"""
        
        # 调用本地模型
        model_start_time = time.time()
        response = await ollama_client.generate(
            model=current_model,
            prompt=user_prompt,
            system=SystemPrompts.QA_SYSTEM_PROMPT,
            temperature=UIConfig.TEMPERATURE,
            max_tokens=UIConfig.MAX_TOKENS
        )
        model_duration = time.time() - model_start_time
        
        # 记录模型调用
        ui_logger.log_model_call(
            model=current_model,
            prompt_length=len(user_prompt),
            response_length=len(response),
            duration=model_duration
        )
        
        # 4. 构建最终回答
        total_duration = time.time() - start_time
        
        final_content = f"## 💡 回答\n\n{response}"
        
        # 添加参考文档信息
        if context_sources:
            final_content += "\n\n## 📚 参考文档\n\n"
            for i, source in enumerate(context_sources, 1):
                final_content += f"**{i}. {source['title']}** (相似度: {source['score']:.3f})\n"
                final_content += f"{source['content']}\n\n"
        
        # 添加统计信息
        final_content += f"\n---\n⏱️ 总用时: {total_duration:.2f}秒 | 🤖 模型: {current_model}"
        
        await thinking_msg.update(content=final_content)
        
        # 更新对话历史
        history = cl.user_session.get("conversation_history", [])
        history.append({
            "question": question,
            "answer": response,
            "sources": context_sources,
            "timestamp": time.time(),
            "model": current_model,
            "duration": total_duration
        })
        cl.user_session.set("conversation_history", history)
        
        logger.info(f"问答完成，用时: {total_duration:.2f}秒")
        
    except Exception as e:
        error_msg = f"❌ 处理问答时发生错误: {str(e)}"
        await thinking_msg.update(content=error_msg)
        ui_logger.log_error(e, "处理问答时发生异常")

@cl.on_file_upload
async def on_file_upload(files: List[AskFileResponse]):
    """处理文件上传"""
    
    logger.info(f"用户上传了 {len(files)} 个文件")
    ui_logger.log_user_action("upload_files", {"count": len(files)})
    
    uploaded_files = []
    failed_files = []
    
    # 确保上传目录存在
    upload_dir = Path(UIConfig.UPLOAD_DIR)
    upload_dir.mkdir(exist_ok=True)
    
    for file in files:
        try:
            # 检查文件大小
            if len(file.content) > UIConfig.MAX_FILE_SIZE:
                failed_files.append(f"{file.name} (文件过大)")
                continue
            
            # 检查文件扩展名
            file_ext = Path(file.name).suffix.lower()
            if file_ext not in UIConfig.ALLOWED_EXTENSIONS:
                failed_files.append(f"{file.name} (格式不支持)")    
                continue
            
            # 保存文件
            file_path = upload_dir / file.name
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(file.content)
            
            uploaded_files.append(file.name)
            ui_logger.log_file_operation("upload", str(file_path), True)
            
            # 自动解析文档
            parse_result = await mcp_client.parse_document(str(file_path))
            if "error" not in parse_result:
                logger.info(f"文档上传并解析成功: {file.name}")
            else:
                logger.warning(f"文档上传成功但解析失败: {file.name}, 错误: {parse_result['error']}")
                
        except Exception as e:
            failed_files.append(f"{file.name} (处理失败)")
            ui_logger.log_error(e, f"上传文件失败: {file.name}")
    
    # 发送结果消息
    if uploaded_files:
        msg = f"✅ **上传成功** ({len(uploaded_files)} 个文件):\n"
        for name in uploaded_files:
            msg += f"- 📄 {name}\n"
        
        if failed_files:
            msg += f"\n❌ **上传失败** ({len(failed_files)} 个文件):\n"
            for name in failed_files:
                msg += f"- ❌ {name}\n"
        
        msg += f"\n💡 **建议**: 执行 `/build` 命令构建搜索索引以启用智能问答功能。"
        
    else:
        msg = f"❌ 所有文件上传失败:\n"
        for name in failed_files:
            msg += f"- ❌ {name}\n"
        
        msg += f"\n💡 **提示**: 支持的格式包括 {', '.join(UIConfig.ALLOWED_EXTENSIONS)}"
    
    await cl.Message(content=msg).send()

def create_app():
    """创建应用实例"""
    logger.info("创建MCP UI应用")
    
    # 验证配置
    config_validation = UIConfig.validate_config()
    if not config_validation["valid"]:
        logger.error("配置验证失败:")
        for issue in config_validation["issues"]:
            logger.error(f"  - {issue}")
        raise ValueError("配置验证失败")
    
    logger.info("MCP UI应用创建完成")
    return True