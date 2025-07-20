import gradio as gr
import threading
from .qa_chain import qa_interface_stream
from .index_manager import create_uploaded_index, set_uploaded_file_content, get_uploaded_file_content
from .file_parser import parse_uploaded_file

stop_event = threading.Event()

def render_history(history, current=None):
    md = ""
    for q, a in history[:-1]:
        md += f"**我：** {q}\n\n**AI：** {a}\n\n---\n"
    # 最后一条历史（本轮）分开处理
    if history:
        q, a = history[-1]
        if current is not None:
            # 正在流式生成时，a为流式内容
            a = current
        md += f"**我：** {q}\n\n**AI：** {a}\n\n---\n"
    return md

def stop_generation():
    stop_event.set()
    return gr.update(visible=False), gr.update(visible=True)

def qa_interface_stream_with_stop(question, history):
    stop_event.clear()
    # 先把问题加入历史，AI回答为空
    history = history + [(question, "")]
    try:
        for chunk in qa_interface_stream(question):
            if stop_event.is_set():
                break
            # 只更新最后一条的AI内容
            history[-1] = (question, chunk)
            yield (render_history(history), history)
        # 最终加入历史
        history[-1] = (question, chunk)
    except Exception as e:
        history[-1] = (question, f"发生错误：{e}")
    yield (render_history(history), history)
    return (render_history(history), history)

def build_ui():
    with gr.Blocks() as demo:
        with gr.Row():
            with gr.Column(scale=1):
                question = gr.Textbox(label="请输入问题", placeholder="请输入您的问题...", elem_id="question_box")
                send_btn = gr.Button("发送", elem_id="send_btn", interactive=False, visible=True)
                stop_btn = gr.Button("停止", elem_id="stop_btn", visible=False)
                # 文件上传组件，支持pdf和docx
                file_upload = gr.File(label="上传文件（支持pdf/doc/docx）", file_types=[".pdf", ".doc", ".docx"])
                file_content = gr.Textbox(label="文件内容预览", interactive=False, lines=5)
                # 新增按钮：创建索引并优先问答
                create_index_btn = gr.Button("创建索引并优先问答", elem_id="create_index_btn")
                index_status = gr.Textbox(label="索引状态", interactive=False)
            with gr.Column(scale=2):
                answer = gr.Markdown(label="历史问答", elem_id="answer_area")
        history_state = gr.State([])

        def on_input_change(q):
            return gr.update(interactive=bool(q.strip()))

        def on_file_upload(file):
            content = parse_uploaded_file(file)
            set_uploaded_file_content(content)
            return content

        file_upload.change(
            on_file_upload,
            inputs=file_upload,
            outputs=file_content
        )

        question.change(
            on_input_change,
            inputs=question,
            outputs=send_btn
        )

        send_btn.click(
            lambda q, h: (gr.update(visible=False), gr.update(visible=True), q, h),  # 立即切换按钮
            inputs=[question, history_state],
            outputs=[send_btn, stop_btn, question, history_state]
        ).then(
            qa_interface_stream_with_stop,
            inputs=[question, history_state],
            outputs=[answer, history_state],
            queue=True
        ).then(
            lambda: (gr.update(visible=True), gr.update(visible=False)), None, [send_btn, stop_btn]
        ).then(
            lambda: "", None, question
        )

        stop_btn.click(
            stop_generation,
            inputs=None,
            outputs=[stop_btn, send_btn]
        )

        create_index_btn.click(
            lambda: create_uploaded_index(),
            inputs=None,
            outputs=index_status
        )

        demo.css = """
#answer_area {
    max-height: 90vh;
    overflow-y: auto;
    border: 1px solid #eee;
    padding: 1em;
    background: #fafbfc;
    color: #222;
    transition: background 0.2s, color 0.2s;
}
.dark #answer_area {
    border: 1px solid #444;
    background: #23272f;
    color: #eee;
}
"""
        return demo 