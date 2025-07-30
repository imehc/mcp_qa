import json
import time
from mcp.types import TextContent, ImageContent
import os
import chainlit as cl
from openai import AsyncOpenAI
import traceback
from dotenv import load_dotenv
from typing import AsyncGenerator

load_dotenv()

SYSTEM_PROMPT = "you are a helpful assistant."


class ChatClient:
    def __init__(self) -> None:
        self.model = os.getenv("MODEL", "deepseek-r1")
        self.client = AsyncOpenAI(
            api_key=os.getenv("API_KEY", ""),
            base_url=os.getenv(
                "BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
            ),
        )
        self.messages = []
        self.system_prompt = SYSTEM_PROMPT
        self.active_streams = []  # 跟踪活动的响应流
        self.thinking_start_time = None  # 跟踪思考开始时间
        self.tool_called = False  # 跟踪上一轮是否调用了工具

    async def _cleanup_streams(self):
        """清理所有活动流的辅助方法"""
        cleanup_tasks = []
        for stream in self.active_streams[:]:  # 创建一个副本以避免在迭代期间进行修改
            try:
                if hasattr(stream, 'aclose'):
                    cleanup_tasks.append(stream.aclose())
                elif hasattr(stream, 'close'):
                    cleanup_tasks.append(stream.close())
            except Exception:
                pass  # 忽略单个清理错误
        
        # 超时等待所有清理任务
        if cleanup_tasks:
            try:
                import asyncio
                await asyncio.wait_for(
                    asyncio.gather(*cleanup_tasks, return_exceptions=True),
                    timeout=2.0
                )
            except asyncio.TimeoutError:
                pass  # 忽略超时
            except Exception:
                pass  # 忽略其它错误
        
        self.active_streams.clear()

    async def process_response_stream(
        self, response_stream, tools, temperature=0
    ) -> AsyncGenerator[str, None]:
        """
        处理响应流以处理思考过程和函数调用。
        """
        function_arguments = ""
        function_name = ""
        tool_call_id = ""
        is_collecting_function_args = False
        collected_messages = []
        # 重置当前流处理的工具调用状态
        self.tool_called = False
        thinking_content_exists = False

        # 如需要，添加到活动流中以便清理
        self.active_streams.append(response_stream)

        try:
            # 首先，通过检查第一个数据块来判断是否存在思考内容
            first_chunk = None
            async for chunk in response_stream:
                first_chunk = chunk
                if chunk.choices == []:
                    continue
                delta = chunk.choices[0].delta
                reasoning_content = getattr(delta, "reasoning_content", None)
                if reasoning_content is not None:
                    thinking_content_exists = True
                    self.thinking_start_time = time.time()
                break

            # 如果存在思考内容则处理思考过程 (这部分代码保持不变)
            if thinking_content_exists and first_chunk is not None:
                # 使用异步上下文管理器正确处理步骤
                async with cl.Step(name="Thinking") as thinking_step:
                    # 处理第一个数据块的推理内容
                    delta = first_chunk.choices[0].delta
                    reasoning_content = getattr(delta, "reasoning_content", None)
                    if reasoning_content is not None:
                        await thinking_step.stream_token(reasoning_content)

                    # 继续处理思考内容
                    thinking_finished = False
                    async for chunk in response_stream:
                        if chunk.choices == []:
                            continue
                        delta = chunk.choices[0].delta
                        reasoning_content = getattr(delta, "reasoning_content", None)

                        if reasoning_content is not None:
                            await thinking_step.stream_token(reasoning_content)
                        else:
                            # 思考完成，更新步骤名称和时间
                            thought_for = round(
                                time.time() - (self.thinking_start_time or 0)
                            )
                            thinking_step.name = f"已思考{thought_for}秒"
                            await thinking_step.update()

                            # 处理此数据块的常规内容（如果有）
                            if delta.content:
                                collected_messages.append(delta.content)
                                yield delta.content

                            # 检查工具调用
                            if delta.tool_calls:
                                if len(delta.tool_calls) > 0:
                                    tool_call = delta.tool_calls[0]
                                    if tool_call.function.name:
                                        function_name = tool_call.function.name
                                        tool_call_id = tool_call.id
                                    if tool_call.function.arguments:
                                        function_arguments += (
                                            tool_call.function.arguments
                                        )
                                        is_collecting_function_args = True

                            thinking_finished = True
                            break

                # 在思考之后继续处理常规内容和工具调用的流
                if thinking_finished:
                    async for part in response_stream:
                        if part.choices == []:
                            continue
                        delta = part.choices[0].delta
                        finish_reason = part.choices[0].finish_reason

                        # 处理助手内容
                        if delta.content:
                            collected_messages.append(delta.content)
                            yield delta.content

                        # 处理工具调用
                        if delta.tool_calls:
                            if len(delta.tool_calls) > 0:
                                tool_call = delta.tool_calls[0]

                                # 获取函数名称
                                if tool_call.function.name:
                                    function_name = tool_call.function.name
                                    tool_call_id = tool_call.id

                                # 处理函数参数增量
                                if tool_call.function.arguments:
                                    function_arguments += tool_call.function.arguments
                                    is_collecting_function_args = True

                        # 工具调用处理的其余部分...
                        if (
                            finish_reason == "tool_calls"
                            and is_collecting_function_args
                        ):
                            # 处理当前工具调用
                            print(
                                f"函数名: {function_name} 函数参数: {function_arguments}"
                            )
                            function_args = json.loads(function_arguments)
                            mcp_tools = cl.user_session.get("mcp_tools", {}) or {}
                            mcp_name = None
                            for connection_name, session_tools in mcp_tools.items():
                                if any(
                                    tool.get("name") == function_name
                                    for tool in session_tools
                                ):
                                    mcp_name = connection_name
                                    break

                            # 添加带有工具调用的助手消息
                            self.messages.append(
                                {
                                    "role": "assistant",
                                    "tool_calls": [
                                        {
                                            "id": tool_call_id,
                                            "function": {
                                                "name": function_name,
                                                "arguments": function_arguments,
                                            },
                                            "type": "function",
                                        }
                                    ],
                                    # 添加工具调用前收集的内容
                                    "content": "".join(
                                        [
                                            msg
                                            for msg in collected_messages
                                            if msg is not None
                                        ]
                                    )
                                    or None,
                                }
                            )

                            # 在开始新流之前安全关闭当前流
                            try:
                                if response_stream in self.active_streams:
                                    self.active_streams.remove(response_stream)
                                if hasattr(response_stream, 'aclose'):
                                    await response_stream.aclose()
                            except Exception:
                                pass  # 忽略清理错误

                            # 调用工具并将响应添加到消息中
                            func_response = await call_tool(
                                mcp_name, function_name, function_args
                            )
                            print(f"函数响应: {json.loads(func_response)}")
                            self.messages.append(
                                {
                                    "tool_call_id": tool_call_id,
                                    "role": "tool",
                                    "name": function_name,
                                    "content": json.loads(func_response),
                                }
                            )

                            # 设置工具已调用标志
                            self.tool_called = True
                            break

                        # 检查是否已到达助手响应的结尾
                        if finish_reason == "stop":
                            # 如果有内容则添加最终助手消息
                            if collected_messages:
                                final_content = "".join(
                                    [
                                        msg
                                        for msg in collected_messages
                                        if msg is not None
                                    ]
                                )
                                if final_content.strip():
                                    self.messages.append(
                                        {"role": "assistant", "content": final_content}
                                    )

                            # 正常完成后从活动流中移除
                            if response_stream in self.active_streams:
                                self.active_streams.remove(response_stream)
                            break
            else:
                # --- 修改开始 ---
                # 没有思考内容，像以前一样正常处理
                # 修复：我们将首先循环以累积所有数据，然后在循环之后处理工具调用。

                # 创建一个可以统一处理第一个块和剩余流的迭代器
                async def combined_stream():
                    if first_chunk is not None:
                        yield first_chunk
                    async for part in response_stream:
                        yield part

                final_finish_reason = None

                # 循环遍历整个流以累积数据
                async for part in combined_stream():
                    if not part.choices:
                        continue

                    delta = part.choices[0].delta
                    finish_reason = part.choices[0].finish_reason

                    # 流式传输内容
                    if delta.content:
                        collected_messages.append(delta.content)
                        yield delta.content

                    # 累积工具调用信息
                    if delta.tool_calls:
                        is_collecting_function_args = True
                        tool_call = delta.tool_calls[0]
                        if tool_call.id:
                            tool_call_id = tool_call.id
                        if tool_call.function.name:
                            function_name = tool_call.function.name
                        if tool_call.function.arguments:
                            function_arguments += tool_call.function.arguments

                    # 如果我们得到完成原因，就保存它并退出循环
                    if finish_reason:
                        final_finish_reason = finish_reason
                        break

                # 在循环结束后，我们拥有了所有信息，现在可以安全地处理它
                if final_finish_reason == "tool_calls" and is_collecting_function_args:
                    print(f"函数名: {function_name} 函数参数: {function_arguments}")

                    try:
                        function_args = json.loads(function_arguments)
                        mcp_tools = cl.user_session.get("mcp_tools", {}) or {}
                        mcp_name = next(
                            (
                                name
                                for name, tools in mcp_tools.items()
                                if any(t.get("name") == function_name for t in tools)
                            ),
                            None,
                        )

                        self.messages.append(
                            {
                                "role": "assistant",
                                "content": "".join(
                                    [
                                        msg
                                        for msg in collected_messages
                                        if msg is not None
                                    ]
                                )
                                or None,
                                "tool_calls": [
                                    {
                                        "id": tool_call_id,
                                        "function": {
                                            "name": function_name,
                                            "arguments": function_arguments,
                                        },
                                        "type": "function",
                                    }
                                ],
                            }
                        )

                        try:
                            if response_stream in self.active_streams:
                                self.active_streams.remove(response_stream)
                            if hasattr(response_stream, 'aclose'):
                                await response_stream.aclose()
                        except Exception:
                            pass  # 忽略清理错误

                        func_response = await call_tool(
                            mcp_name, function_name, function_args
                        )
                        print(f"函数响应: {json.loads(func_response)}")
                        self.messages.append(
                            {
                                "tool_call_id": tool_call_id,
                                "role": "tool",
                                "name": function_name,
                                "content": json.loads(func_response),
                            }
                        )
                        self.tool_called = True

                    except json.JSONDecodeError as e:
                        print(f"JSON解码错误: {e}. 无效的参数: '{function_arguments}'")
                        # 添加一条错误消息到历史记录中
                        if collected_messages:
                            self.messages.append(
                                {
                                    "role": "assistant",
                                    "content": "".join(collected_messages),
                                }
                            )

                elif final_finish_reason == "stop":
                    if collected_messages:
                        final_content = "".join(
                            [msg for msg in collected_messages if msg is not None]
                        )
                        if final_content.strip():
                            self.messages.append(
                                {"role": "assistant", "content": final_content}
                            )
                    try:
                        if response_stream in self.active_streams:
                            self.active_streams.remove(response_stream)
                    except Exception:
                        pass  # 忽略清理错误
        except GeneratorExit:
            # 正确处理生成器清理
            try:
                if response_stream in self.active_streams:
                    self.active_streams.remove(response_stream)
                    if hasattr(response_stream, 'aclose'):
                        await response_stream.aclose()
            except Exception:
                pass  # 忽略清理错误
            raise 
        except Exception as e:
            print(f"process_response_stream中的错误: {e}")
            traceback.print_exc()
            try:
                if response_stream in self.active_streams:
                    self.active_streams.remove(response_stream)
                    if hasattr(response_stream, 'aclose'):
                        await response_stream.aclose()
            except Exception:
                pass  # 忽略清理错误

    async def generate_response(self, tools, temperature=0):
        """
        从LLM生成单个响应。
        它为响应生成令牌并更新内部状态（例如，self.tool_called）。
        现在在on_message中处理顺序调用的while循环。
        """
        print(f"发送给API的消息: {self.messages}")

        # 仅在有工具可用时包含tools参数
        api_params = {
            "model": self.model,
            "messages": self.messages,
            "parallel_tool_calls": False,
            "stream": True,
            "temperature": temperature,
        }

        if tools:  # 仅当列表不为空时添加工具
            api_params["tools"] = tools

        response_stream = await self.client.chat.completions.create(**api_params)

        try:
            # 流式传输并处理此单个响应。
            # self.process_response_stream将更新self.messages和self.tool_called
            async for token in self.process_response_stream(
                response_stream, tools, temperature
            ):
                yield token
        except GeneratorExit:
            # 确保GeneratorExit进行适当清理
            await self._cleanup_streams()
            raise 


def flatten(xss):
    return [x for xs in xss for x in xs]


@cl.on_mcp_connect
def on_mcp(connection, session) -> None:
    import asyncio

    asyncio.create_task(on_mcp_async(connection, session))


async def on_mcp_async(connection, session) -> None:
    result = await session.list_tools()
    tools = [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.inputSchema,
        }
        for t in result.tools
    ]

    mcp_tools = cl.user_session.get("mcp_tools", {}) or {}
    mcp_tools[connection.name] = tools
    cl.user_session.set("mcp_tools", mcp_tools)


@cl.step(type="tool")
async def call_tool(mcp_name, function_name, function_args):
    resp_items = []  # 在开始时初始化resp_items
    try:
        print(f"函数名: {function_name} 函数参数: {function_args}")
        mcp_session_data = cl.context.session.mcp_sessions.get(mcp_name)  # type: ignore
        if mcp_session_data is None:
            raise ValueError(f"未找到MCP会话: {mcp_name}")

        mcp_session, _ = mcp_session_data
        
        # 增加MCP工具调用超时时间
        import asyncio
        try:
            func_response = await asyncio.wait_for(
                mcp_session.call_tool(function_name, function_args),
                timeout=30.0  # 30超时
            )
        except asyncio.TimeoutError:
            print("调用mcp工具超时")
            resp_items.append({"type": "text", "text": "工具调用超时，请重试"})
            return json.dumps(resp_items)
            
        for item in func_response.content:
            if isinstance(item, TextContent):
                resp_items.append({"type": "text", "text": item.text})
            elif isinstance(item, ImageContent):
                resp_items.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{item.mimeType};base64,{item.data}",
                        },
                    }
                )
            else:
                raise ValueError(f"不支持的内容类型: {type(item)}")

    except Exception as e:
        print(f"调用mcp工具报错: {e}")
        traceback.print_exc()
        resp_items.append({"type": "text", "text": f"工具调用失败: {str(e)}"})
    return json.dumps(resp_items)


@cl.on_chat_start
async def start_chat():
    # 我们不再在此处设置messages或system_prompt，因为客户端是按消息创建的
    cl.user_session.set("mcp_tools", {})
    cl.user_session.set("messages", [])


@cl.on_message
async def on_message(message: cl.Message):
    mcp_tools = cl.user_session.get("mcp_tools", {}) or {}
    tools = flatten([tools for _, tools in mcp_tools.items()])
    tools = [{"type": "function", "function": tool} for tool in tools]

    # 为本轮对话持续时间创建单个客户端实例
    client = ChatClient()
    # 恢复完整的对话历史
    client.messages = cl.user_session.get("messages", []) or []

    # 将新的用户消息追加到历史记录中
    client.messages.append({"role": "user", "content": message.content})

    # 此循环处理对话轮次。它将为初始响应运行一次，
    # 如果调用了工具，它将再次运行以在工具结果后生成最终响应。
    while True:
        # 为助手响应的每个步骤创建一个新的空消息。
        msg = cl.Message(content="")

        # 将助手的响应流式传输到新消息中。
        # generate_response方法现在一次只处理一个API调用。
        async for text_chunk in client.generate_response(tools=tools):
            await msg.stream_token(text_chunk)

        # 发送已完成的消息。如果它是空的（例如，只有工具调用），
        # 它将不会被显示。
        if msg.content:
            await msg.send()

        # 检查客户端实例上的标志。如果没有调用工具，
        # 助手的轮次就完成了，我们可以退出循环。
        if not client.tool_called:
            break
        # 如果调用了工具，循环将继续。
        # client.messages已经用工具调用和结果更新了，
        # 所以下一次迭代将基于此生成响应。

    # 将最终更新的消息历史保存到用户会话中。
    cl.user_session.set("messages", client.messages)
