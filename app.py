import json
import time
from mcp import ClientSession
from mcp.types import TextContent, ImageContent
import os
from aiohttp import ClientSession
import chainlit as cl
from openai import AsyncOpenAI
import traceback
from dotenv import load_dotenv

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
        self.tool_called = False  # Track if a tool was called in the last turn

    async def _cleanup_streams(self):
        """清理所有活动流的辅助方法"""
        for stream in self.active_streams:
            try:
                await stream.aclose()
            except Exception:
                pass
        self.active_streams = []

    # 请用这个修改后的完整函数替换您文件中的旧版本
    async def process_response_stream(self, response_stream, tools, temperature=0):
        """
        处理响应流以处理思考过程和函数调用。
        """
        function_arguments = ""
        function_name = ""
        tool_call_id = ""
        is_collecting_function_args = False
        collected_messages = []
        # Reset tool_called status for the current stream processing
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
                            thought_for = round(time.time() - self.thinking_start_time)
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
                            mcp_tools = cl.user_session.get("mcp_tools", {})
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
                                    # Add collected content before tool call
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
                            if response_stream in self.active_streams:
                                self.active_streams.remove(response_stream)
                                await response_stream.close()

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
                        mcp_tools = cl.user_session.get("mcp_tools", {})
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

                        if response_stream in self.active_streams:
                            self.active_streams.remove(response_stream)
                            await response_stream.close()

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
                    if response_stream in self.active_streams:
                        self.active_streams.remove(response_stream)
                # --- 修改结束 ---

        except GeneratorExit:
            if response_stream in self.active_streams:
                self.active_streams.remove(response_stream)
                await response_stream.aclose()
        except Exception as e:
            print(f"process_response_stream中的错误: {e}")
            traceback.print_exc()
            if response_stream in self.active_streams:
                self.active_streams.remove(response_stream)

    async def generate_response(self, tools, temperature=0):
        """
        Generates a single response from the LLM.
        It yields tokens for the response and updates the internal state (e.g., self.tool_called).
        The while loop for sequential calls is now handled in on_message.
        """
        print(f"Messages sent to API: {self.messages}")

        response_stream = await self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=tools,
            parallel_tool_calls=False,
            stream=True,
            temperature=temperature,
        )

        try:
            # Stream and process this single response.
            # self.process_response_stream will update self.messages and self.tool_called
            async for token in self.process_response_stream(
                response_stream, tools, temperature
            ):
                yield token
        except GeneratorExit:
            # Ensure cleanup if the client disconnects during generation
            await self._cleanup_streams()
            return


def flatten(xss):
    return [x for xs in xss for x in xs]


@cl.on_mcp_connect
async def on_mcp(connection, session: ClientSession):
    result = await session.list_tools()
    tools = [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.inputSchema,
        }
        for t in result.tools
    ]

    mcp_tools = cl.user_session.get("mcp_tools", {})
    mcp_tools[connection.name] = tools
    cl.user_session.set("mcp_tools", mcp_tools)


@cl.step(type="tool")
async def call_tool(mcp_name, function_name, function_args):
    try:
        resp_items = []
        print(f"函数名: {function_name} 函数参数: {function_args}")
        mcp_session, _ = cl.context.session.mcp_sessions.get(mcp_name)
        func_response = await mcp_session.call_tool(function_name, function_args)
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
        traceback.print_exc()
        resp_items.append({"type": "text", "text": str(e)})
    return json.dumps(resp_items)


@cl.on_chat_start
async def start_chat():
    # We no longer set messages or system_prompt here as the client is created per message
    cl.user_session.set("mcp_tools", {})
    cl.user_session.set("messages", [])


# --- COMPLETELY REWRITTEN METHOD ---
@cl.on_message
async def on_message(message: cl.Message):
    mcp_tools = cl.user_session.get("mcp_tools", {})
    tools = flatten([tools for _, tools in mcp_tools.items()])
    tools = [{"type": "function", "function": tool} for tool in tools]

    # Create a single client instance for the duration of the turn
    client = ChatClient()
    # Restore the full conversation history
    client.messages = cl.user_session.get("messages", [])

    # Append the new user message to the history
    client.messages.append({"role": "user", "content": message.content})

    # This loop handles the conversation turn. It will run once for the initial
    # response, and if a tool is called, it will run again to generate the
    # final response after the tool result.
    while True:
        # Create a new, empty message for each step of the assistant's response.
        msg = cl.Message(content="")

        # Stream the assistant's response into the new message.
        # The generate_response method now only handles one API call at a time.
        async for text_chunk in client.generate_response(tools=tools):
            await msg.stream_token(text_chunk)

        # Send the completed message. If it's empty (e.g., only a tool call),
        # it won't be displayed.
        if msg.content:
            await msg.send()

        # Check the flag on the client instance. If no tool was called,
        # the assistant's turn is complete, and we can exit the loop.
        if not client.tool_called:
            break
        # If a tool was called, the loop will continue.
        # client.messages has already been updated with the tool call and result,
        # so the next iteration will generate a response based on that.

    # Persist the final, updated message history to the user session.
    cl.user_session.set("messages", client.messages)
