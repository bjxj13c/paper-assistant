"""
论文阅读与摘要生成助手 - 测试用例
"""

import os
import sys
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pdf_parser import extract_paper, chunk_text


def test_pdf_parser():
    """测试 PDF 解析功能"""
    print("=" * 50)
    print("测试 1: PDF 解析")
    print("=" * 50)

    # 创建一个简单的测试 PDF（如果没有真实论文文件）
    test_dir = Path(__file__).parent.parent / "tests"
    test_dir.mkdir(exist_ok=True)

    # 如果有命令行参数，使用它作为 PDF 路径
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        print("请提供 PDF 论文文件路径: python tests/__init__.py <pdf_path>")
        return

    try:
        paper = extract_paper(pdf_path)
        print(f"  标题: {paper.title}")
        print(f"  作者: {paper.authors}")
        print(f"  章节数: {len(paper.sections)}")
        print(f"  总字数: {len(paper.full_text)}")
        print(f"  章节列表: {[s.title for s in paper.sections]}")
        print("  PDF 解析测试通过!")
    except Exception as e:
        print(f"  PDF 解析失败: {e}")
        import traceback
        traceback.print_exc()


def test_chunk_text():
    """测试文本分块功能"""
    print("\n" + "=" * 50)
    print("测试 2: 文本分块")
    print("=" * 50)

    long_text = "段落A\n\n" * 500
    chunks = chunk_text(long_text, max_chars=2000)
    print(f"  原文本长度: {len(long_text)}")
    print(f"  分块数量: {len(chunks)}")
    print(f"  每块最大长度: {max(len(c) for c in chunks)}")
    assert all(len(c) <= 2100 for c in chunks), "分块大小超出预期"
    print("  文本分块测试通过!")


def test_paper_agent():
    """测试 AI Agent 配置（不调用 API）"""
    print("\n" + "=" * 50)
    print("测试 3: AI Agent 配置检查")
    print("=" * 50)

    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))

    if not has_anthropic and not has_openai:
        print("  警告: 未设置 API Key 环境变量")
        print("  - ANTHROPIC_API_KEY (用于 Claude API)")
        print("  - OPENAI_API_KEY (用于 OpenAI API)")
        print("  设置方法: export ANTHROPIC_API_KEY=your_key")
        print("  跳过 API 调用测试...")
        return

    try:
        from src.agent import PaperAgent
        agent = PaperAgent()
        print(f"  API 类型: {agent.api_type}")
        print(f"  AI Agent 初始化成功!")

        # 测试简单的摘要生成
        test_text = """
        本文提出了一种基于深度学习的新型文本分类方法。
        通过在三个基准数据集上的实验，我们的方法相比现有方法准确率提升了 5%。
        主要创新点包括：1) 改进的注意力机制；2) 多粒度特征融合。
        """
        print("  测试摘要生成...")
        summary = agent.generate_summary(test_text, detail_level="brief")
        print(f"  摘要结果: {summary[:200]}...")
        print("  AI Agent 测试通过!")

    except ImportError as e:
        print(f"  依赖缺失: {e}")
        print("  请运行: pip install anthropic 或 pip install openai")
    except Exception as e:
        print(f"  AI Agent 测试失败: {e}")


if __name__ == "__main__":
    test_pdf_parser()
    test_chunk_text()
    test_paper_agent()
    print("\n" + "=" * 50)
    print("所有测试完成!")
