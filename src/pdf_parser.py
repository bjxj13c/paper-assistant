"""
论文解析模块 - 支持 PDF 和 Word（.docx）文件
"""

import re
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class PaperSection:
    """论文章节"""
    title: str
    content: str
    start_page: int = 0


@dataclass
class Paper:
    """论文数据结构"""
    file_path: str
    title: str = ""
    authors: str = ""
    abstract: str = ""
    sections: list = field(default_factory=list)
    references: str = ""
    full_text: str = ""
    metadata: dict = field(default_factory=dict)

    def get_section_titles(self):
        return [s.title for s in self.sections]

    def to_text(self, max_len: int = None):
        """将论文转为完整文本（供 AI 处理）"""
        parts = [f"标题: {self.title}", f"作者: {self.authors}"]
        if self.abstract:
            parts.append(f"摘要: {self.abstract}")
        for s in self.sections:
            parts.append(f"\n## {s.title}\n{s.content}")
        text = "\n".join(parts)
        if max_len and len(text) > max_len:
            text = text[:max_len] + "\n...(内容已截断)"
        return text


def extract_paper(file_path: str) -> Paper:
    """
    从 PDF 或 Word (.docx) 文件中提取论文内容和结构。
    自动根据文件扩展名选择解析方式。
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _extract_from_docx(file_path)
    elif suffix == ".pdf":
        return _extract_from_pdf(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {suffix}，请使用 PDF 或 DOCX 文件")


def _extract_from_docx(file_path: str) -> Paper:
    """从 Word 文档提取文本。"""
    from docx import Document

    path = Path(file_path)
    doc = Document(file_path)
    paper = Paper(file_path=str(path.absolute()))

    # 提取标题（文档内置属性）
    props = doc.core_properties
    if props.title:
        paper.title = props.title
    if props.author:
        paper.authors = props.author

    # 提取所有段落文本
    full_text_parts = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            # 根据字体大小判断标题
            if para.style and "Heading" in para.style.name:
                full_text_parts.append(f"\n{text}")
            else:
                full_text_parts.append(text)

    full_text = "\n".join(full_text_parts)
    paper.full_text = full_text

    # 分析论文结构
    _analyze_structure(paper, full_text)

    return paper


def _extract_from_pdf(file_path: str) -> Paper:
    """从 PDF 文件提取文本。"""
    import fitz  # PyMuPDF

    path = Path(file_path)
    doc = fitz.open(file_path)
    paper = Paper(file_path=str(path.absolute()))

    # 提取元数据
    meta = doc.metadata
    paper.metadata = {k: v for k, v in meta.items() if v}
    if meta.get("title"):
        paper.title = meta["title"]
    if meta.get("author"):
        paper.authors = meta["author"]

    # 按页提取文本
    full_pages = []
    for page in doc:
        text = page.get_text("text")
        full_pages.append(text)

    full_text = "\n\n".join(full_pages)
    paper.full_text = full_text

    # 分析论文结构
    _analyze_structure(paper, full_text)

    doc.close()
    return paper


def _analyze_structure(paper: Paper, text: str):
    """
    分析论文结构：识别标题、作者、摘要、各章节、参考文献。
    """
    lines = text.strip().split("\n")

    # 常见章节标题模式（中英文）
    section_patterns = [
        # 英文
        r"^(abstract|ABSTRACT|Abstract)\s*$",
        r"^(introduction|INTRODUCTION|Introduction)\s*$",
        r"^(related\s*work|RELATED\s*WORK|Related\s*Work)\s*$",
        r"^(method|methodology|METHOD|METHODOLOGY|Method|Methodology)\s*$",
        r"^(experiment|EXPERIMENT|Experiment|experiments|EXPERIMENTS)\s*$",
        r"^(result|RESULT|Result|results|RESULTS|Results)\s*$",
        r"^(discussion|DISCUSSION|Discussion)\s*$",
        r"^(conclusion|CONCLUSION|Conclusion)\s*$",
        r"^(reference|REFERENCE|Reference|references|REFERENCES|References)\s*$",
        # 中文
        r"^(摘要|ABSTRACT|摘\s*要)\s*$",
        r"^(引言|绪论|前言|研究背景|问题背景)\s*$",
        r"^(相关工作|文献综述|国内外研究现状)\s*$",
        r"^(方法|研究方法|方法论|技术方案|模型设计|系统设计)\s*$",
        r"^(实验|实验设计|实证研究|案例分析)\s*$",
        r"^(结果|实验结果|实验结果与分析|分析结果)\s*$",
        r"^(讨论|分析讨论|综合讨论)\s*$",
        r"^(结论|总结|结论与展望|总结与展望)\s*$",
        r"^(参考文献|参考资料|REFERENCES|参考)\s*$",
    ]

    # 数字编号章节：1. Introduction, 2.1 方法, 一、引言 等
    numbered_section = re.compile(
        r"^(\d+(\.\d+)*\s+|第[一二三四五六七八九十\d]+[章节部分]\s*|[一二三四五六七八九十]+[、.．]\s*)"
    )

    current_section = "引言"
    current_content = []
    found_abstract = False
    found_references = False
    reference_text = []

    # 尝试提取标题（前几行中的大字体文本通常为标题）
    if not paper.title:
        for i, line in enumerate(lines[:20]):
            line = line.strip()
            if len(line) > 5 and len(line) < 200 and not line.startswith(("http", "doi", "©", "All rights")):
                paper.title = line
                break

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            if current_content:
                current_content.append("")
            continue

        # 检查是否是章节标题
        is_section = False
        for pattern in section_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                is_section = True
                break
        if not is_section and numbered_section.match(line):
            is_section = True

        if is_section:
            # 保存上一节
            content = "\n".join(current_content).strip()
            if current_section.lower() in ("reference", "references", "参考文献", "参考资料"):
                reference_text.append(content)
                found_references = True
            elif content:
                paper.sections.append(PaperSection(title=current_section, content=content))

            current_section = line
            current_content = []

            # 识别摘要节（单独存储）
            section_lower = current_section.lower()
            if section_lower in ("abstract", "abstract", "摘要"):
                found_abstract = True
        else:
            if found_references:
                reference_text.append(line)
            else:
                current_content.append(line)

    # 保存最后一节
    content = "\n".join(current_content).strip()
    if found_references and reference_text:
        paper.references = "\n".join(reference_text)
    elif content:
        section_lower = current_section.lower()
        if section_lower in ("reference", "references", "参考文献", "参考资料"):
            paper.references = content
        else:
            paper.sections.append(PaperSection(title=current_section, content=content))

    # 尝试识别摘要（未找到独立摘要节时，从开头或第一节提取）
    if not found_abstract:
        intro_text = ""
        for s in paper.sections:
            if any(kw in s.title.lower() for kw in ("abstract", "abstract", "摘要", "引言", "introduction")):
                intro_text = s.content
                break
        if intro_text:
            # 取前 1000 字符作为摘要候选
            paper.abstract = intro_text[:1000]
        elif paper.sections:
            paper.abstract = paper.sections[0].content[:1000]


def chunk_text(text: str, max_chars: int = 8000) -> list:
    """将长文本切分为多个块，每块不超过 max_chars 字符。"""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            current = para

    if current:
        chunks.append(current)
    return chunks
