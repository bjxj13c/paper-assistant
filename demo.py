"""
演示脚本 - 展示论文分析助手的基本功能（不含 API 调用）

用法:
    python demo.py <pdf_path>
"""

import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.pdf_parser import extract_paper, chunk_text

console = Console()


def demo(pdf_path: str):
    console.print(Panel.fit(
        "[bold blue]论文阅读与摘要生成助手 - 演示模式[/bold blue]",
        border_style="blue"
    ))
    console.print(f"[dim]文件: {pdf_path}[/dim]\n")

    # 1. 解析 PDF
    console.print("[bold]Step 1: PDF 解析[/bold]")
    paper = extract_paper(pdf_path)

    # 基本信息
    table = Table(title="论文基本信息")
    table.add_column("属性", style="cyan")
    table.add_column("内容", style="green")
    table.add_row("标题", paper.title or "(未识别)")
    table.add_row("作者", paper.authors or "(未识别)")
    table.add_row("总字符数", str(len(paper.full_text)))
    table.add_row("章节数", str(len(paper.sections)))
    console.print(table)

    # 章节结构
    if paper.sections:
        console.print("\n[bold]Step 2: 章节识别[/bold]")
        for i, section in enumerate(paper.sections, 1):
            preview = section.content[:80].replace("\n", " ")
            console.print(f"  [{i}] [cyan]{section.title}[/cyan]: {preview}...")

    # 摘要
    if paper.abstract:
        console.print(f"\n[bold]Step 3: 原始摘要[/bold]")
        console.print(Panel(
            paper.abstract[:500],
            title="论文摘要",
            border_style="green"
        ))

    # 文本分块
    console.print("\n[bold]Step 4: 文本分块（用于 AI 处理）[/bold]")
    chunks = chunk_text(paper.full_text, max_chars=8000)
    console.print(f"  文本已分为 {len(chunks)} 个块，每块最多 8000 字符")
    console.print(f"  每块大小: {', '.join(str(len(c)) for c in chunks)}")

    # 统计信息
    console.print("\n[bold]Step 5: 统计信息[/bold]")
    ref_len = len(paper.references)
    console.print(f"  参考文献长度: {ref_len} 字符")
    console.print(f"  平均每章长度: {sum(len(s.content) for s in paper.sections) // max(len(paper.sections), 1)} 字符")

    console.print("\n[bold green]演示完成！[/bold green]")
    console.print("\n[dim]提示: 设置 API Key 后运行 python run.py analyze 进行 AI 分析[/dim]")
    console.print("[dim]  export ANTHROPIC_API_KEY=your_key[/dim]")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print("[red]请提供 PDF 文件路径: python demo.py <pdf_path>[/red]")
        sys.exit(1)
    demo(sys.argv[1])
