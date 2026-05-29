"""
论文阅读与摘要生成助手 - CLI 命令行界面
"""

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn

from .pdf_parser import extract_paper
from .agent import PaperAgent
from . import feishu as _feishu

console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="论文阅读与摘要生成助手")
def main():
    """论文阅读与摘要生成助手 - AI 驱动的论文学术分析工具

    支持 PDF 论文的自动解析、摘要生成、关键词提取、
    研究问题整理等功能，结果可保存至飞书文档或本地文件。
    """
    pass


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option("-o", "--output", help="输出格式: text/json/report", default="report")
@click.option("--feishu/--no-feishu", default=True, help="是否同步到飞书")
@click.option("--notify/--no-notify", default=False, help="是否发送飞书机器人通知")
@click.option("--local/--no-local", default=True, help="是否保存到本地")
def analyze(pdf_path, output, feishu, notify, local):
    """分析一篇 PDF 论文，生成完整分析报告。

    PDF_PATH: 论文 PDF 文件路径
    """
    console.print(Panel.fit(
        "[bold blue]论文阅读与摘要生成助手[/bold blue]",
        border_style="blue"
    ))

    # 1. 解析 PDF
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("正在解析 PDF 文件...", total=None)
        try:
            paper = extract_paper(pdf_path)
        except Exception as e:
            console.print(f"[red]解析失败: {e}[/red]")
            sys.exit(1)

    console.print(f"[green]解析完成[/green] - 标题: {paper.title or '(未识别)'}")
    console.print(f"  章节: {', '.join(paper.get_section_titles()) if paper.sections else '(未识别)'}")

    # 2. 构建输入文本
    paper_text = paper.to_text(max_len=15000)

    # 3. AI 分析
    agent = PaperAgent()
    doc_url = ""
    result = None

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("AI 正在分析论文...", total=None)
        try:
            result = agent.generate_structured_report(paper_text)
            progress.update(task, description="分析完成!")
        except Exception as e:
            progress.update(task, description=f"分析失败: {e}")
            console.print(f"[red]AI 分析失败: {e}[/red]")
            console.print("[yellow]提示: 请确保已设置 API Key 环境变量[/yellow]")
            sys.exit(1)

    # 4. 输出结果
    if output == "json":
        _output_json(result)
    elif output == "report":
        _output_report(result)
    else:
        _output_text(result)

    # 5. 保存到本地
    if local and result:
        _feishu.save_to_local(result)

    # 6. 同步到飞书
    if feishu and result:
        try:
            doc_url = _feishu.create_doc(f"论文分析: {result.title}", result) or ""
        except Exception as e:
            console.print(f"[yellow]飞书同步失败: {e}[/yellow]")

    # 7. 发送通知
    if notify and result:
        summary = result.abstract if result.abstract else "分析完成"
        _feishu.send_bot_notification(
            title=result.title or paper.title or "论文",
            summary=summary[:200],
            doc_url=doc_url,
        )

    console.print("\n[bold green]分析完成![/bold green]")
    if doc_url:
        console.print(f"[blue]飞书文档: {doc_url}[/blue]")


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option("--detail", "-d", type=click.Choice(["brief", "detailed", "structured"]),
              default="detailed", help="摘要详细程度")
def summarize(pdf_path, detail):
    """快速生成论文摘要（不生成完整报告）。

    PDF_PATH: 论文 PDF 文件路径
    """
    paper = extract_paper(pdf_path)
    paper_text = paper.to_text(max_len=12000)

    agent = PaperAgent()
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("正在生成摘要...", total=None)
        summary = agent.generate_summary(paper_text, detail_level=detail)

    console.print(Panel(Markdown(summary), title="论文摘要", border_style="green"))


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True))
def keywords(pdf_path):
    """提取论文关键词。

    PDF_PATH: 论文 PDF 文件路径
    """
    paper = extract_paper(pdf_path)
    paper_text = paper.to_text(max_len=10000)

    agent = PaperAgent()
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("正在提取关键词...", total=None)
        kw = agent.extract_keywords(paper_text)

    table = Table(title="关键词提取结果")
    table.add_column("序号", style="cyan", width=6)
    table.add_column("关键词", style="green")
    for i, k in enumerate(kw, 1):
        table.add_row(str(i), k)
    console.print(table)


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option("--question", "-q", prompt="请输入你对论文的问题", help="关于论文的问题")
def ask(pdf_path, question):
    """向 AI 提问关于某篇论文的问题。

    PDF_PATH: 论文 PDF 文件路径
    """
    paper = extract_paper(pdf_path)
    paper_text = paper.to_text(max_len=12000)

    agent = PaperAgent()
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("AI 正在思考...", total=None)
        answer = agent.answer_question(paper_text, question)

    console.print(Panel(Markdown(answer), title=f"Q: {question}", border_style="yellow"))


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True))
def bilingual(pdf_path):
    """生成中英双语摘要。

    PDF_PATH: 论文 PDF 文件路径
    """
    paper = extract_paper(pdf_path)
    paper_text = paper.to_text(max_len=10000)

    agent = PaperAgent()
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("正在生成双语摘要...", total=None)
        result = agent.generate_bilingual_abstract(paper_text)

    console.print(Panel(Markdown(result), title="中英双语摘要", border_style="cyan"))


# ========== 输出格式化 ==========

def _output_report(result):
    """以富文本报告形式输出。"""
    console.print("\n")
    console.rule("[bold blue]论文分析报告")

    if result.title:
        console.print(f"\n[bold]论文标题:[/bold] {result.title}")

    if result.abstract:
        console.print(Panel(
            Markdown(result.abstract),
            title="[bold]摘要[/bold]",
            border_style="green"
        ))

    if result.keywords:
        kw_str = " | ".join(f"[cyan]{k}[/cyan]" for k in result.keywords)
        console.print(f"[bold]关键词:[/bold] {kw_str}")

    if result.research_questions:
        console.print("\n[bold]研究问题:[/bold]")
        for i, q in enumerate(result.research_questions, 1):
            console.print(f"  {i}. [yellow]{q}[/yellow]")

    if result.methodology:
        console.print(Panel(
            Markdown(result.methodology),
            title="[bold]研究方法[/bold]",
            border_style="blue"
        ))

    if result.contributions:
        console.print("\n[bold]主要贡献:[/bold]")
        for c in result.contributions:
            console.print(f"  [green]+[/green] {c}")

    if result.strengths:
        console.print("\n[bold]优点:[/bold]")
        for s in result.strengths:
            console.print(f"  [green]✓[/green] {s}")

    if result.limitations:
        console.print("\n[bold]局限性:[/bold]")
        for l in result.limitations:
            console.print(f"  [yellow]![/yellow] {l}")

    if result.reading_notes:
        console.print(Panel(
            Markdown(result.reading_notes),
            title="[bold]阅读建议[/bold]",
            border_style="yellow"
        ))

    console.rule()


def _output_json(result):
    """以 JSON 格式输出。"""
    data = {
        "title": result.title,
        "abstract": result.abstract,
        "keywords": result.keywords,
        "research_questions": result.research_questions,
        "methodology": result.methodology,
        "contributions": result.contributions,
        "strengths": result.strengths,
        "limitations": result.limitations,
        "reading_notes": result.reading_notes,
    }
    console.print_json(data)


def _output_text(result):
    """以纯文本格式输出。"""
    lines = [
        f"标题: {result.title}",
        f"\n摘要:\n{result.abstract}",
        f"\n关键词: {', '.join(result.keywords)}",
        f"\n研究问题:\n" + "\n".join(f"  - {q}" for q in result.research_questions),
        f"\n研究方法:\n{result.methodology}",
    ]
    console.print("\n".join(lines))


@main.command()
@click.option("--once/--no-once", default=False, help="处理一条消息后退出（调试用）")
def bot(once):
    """启动飞书机器人：把 PDF 发给机器人，自动分析并回复。"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from bot import run_bot
    run_bot(once=once)


if __name__ == "__main__":
    main()
