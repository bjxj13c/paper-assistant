"""
论文阅读与摘要生成助手 - 入口脚本

用法:
    python run.py analyze paper.pdf
    python run.py summarize paper.pdf --detail brief
    python run.py keywords paper.pdf
    python run.py ask paper.pdf -q "这篇论文用的什么方法？"
    python run.py bilingual paper.pdf
"""

import sys
import io

# Windows 终端 UTF-8 编码修复
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from src.cli import main

if __name__ == "__main__":
    main()
