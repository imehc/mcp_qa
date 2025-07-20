import fitz  # pymupdf
from unstructured.partition.docx import partition_docx

def parse_uploaded_file(file):
    """
    解析上传的文件，支持pdf、doc、docx。
    返回解析后的文本内容。
    """
    if file is None:
        return ""
    if file.name.endswith(".pdf"):
        doc = fitz.open(file.name)
        text = "\n".join(page.get_text() for page in doc)
        return text
    elif file.name.endswith(".docx") or file.name.endswith(".doc"):
        try:
            elements = partition_docx(filename=file.name)
            text = "\n".join([el.text for el in elements if hasattr(el, 'text')])
            return text
        except Exception as e:
            return f"Word文件解析失败：{e}。如为doc格式请尝试另存为docx后再上传。"
    else:
        return "仅支持pdf、doc、docx文件" 