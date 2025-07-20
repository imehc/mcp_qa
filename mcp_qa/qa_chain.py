import queue
import threading
import re
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI
from langchain.callbacks.base import BaseCallbackHandler
from .embeddings import retriever
from .index_manager import get_uploaded_retriever

OLLAMA_BASE = "http://localhost:11434/v1"
OLLAMA_MODEL = "qwen3:4b"

class GradioStreamHandler(BaseCallbackHandler):
    def __init__(self, queue):
        self.queue = queue
        self.current_text = ""

    def on_llm_new_token(self, token, **kwargs):
        self.current_text += token
        self.queue.put(self.current_text)

def split_think_answer(text):
    """
    提取<think>标签内容和主回答内容。
    返回 (answer, think_content)
    """
    think_matches = re.findall(r'<think>([\s\S]*?)</think>', text)
    think_content = '\n'.join(think_matches).strip() if think_matches else None
    # 移除<think>内容后的主回答
    answer = re.sub(r'<think>[\s\S]*?</think>', '', text).strip()
    return answer, think_content

def qa_interface_stream(question):
    q = queue.Queue()
    handler = GradioStreamHandler(q)
    # 优先用上传内容索引
    use_retriever = get_uploaded_retriever() or retriever
    llm_stream = ChatOpenAI(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE,
        api_key="ollama",
        streaming=True,
        callbacks=[handler],
    )
    qa_chain_stream = RetrievalQA.from_chain_type(
        llm=llm_stream,
        chain_type="stuff",
        retriever=use_retriever,
        input_key="question"
    )
    def run_chain():
        qa_chain_stream.invoke({"question": question})
        q.put(None)
    threading.Thread(target=run_chain).start()

    buffer = ""
    think_mode = False
    think_content = ""
    answer_content = ""
    think_done = False
    while True:
        chunk = q.get()
        if chunk is None:
            break
        buffer += chunk[len(buffer):]
        # 检查<think>标签
        if not think_done:
            start_idx = buffer.find("<think>")
            end_idx = buffer.find("</think>")
            if start_idx != -1 and not think_mode:
                think_mode = True
                think_start = start_idx + 7
                if end_idx != -1:
                    think_content = buffer[think_start:end_idx]
                    think_done = True
                    think_mode = False
                else:
                    think_content = buffer[think_start:]
            elif think_mode and end_idx == -1:
                think_content = buffer[buffer.find('<think>')+7:]
            elif think_mode and end_idx != -1:
                think_content = buffer[buffer.find('<think>')+7:end_idx]
                think_done = True
                think_mode = False
        # 主回答内容
        if think_done:
            answer_content = re.sub(r'<think>[\s\S]*?</think>', '', buffer).strip()
        # 只 yield 一段 markdown
        md = ""
        if think_content and not think_done:
            md += f"<details open><summary>思考中...</summary>\n\n{think_content.strip()}\n\n</details>\n"
        if think_done and answer_content:
            md += answer_content
        if md:
            yield md 