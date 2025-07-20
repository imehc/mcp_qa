import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
from mcp_qa.ui import build_ui

def main():
    demo = build_ui()
    demo.launch()

if __name__ == "__main__":
    main()
