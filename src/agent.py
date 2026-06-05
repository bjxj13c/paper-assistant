"""
AI 智能体核心逻辑 - 论文分析、摘要生成、研究问题整理

支持国内 AI 服务：DeepSeek（推荐）、智谱GLM、通义千问、月之暗面 Moonshot
"""

import json
import os
from dataclasses import dataclass, field

import config


@dataclass
class AnalysisResult:
    """论文分析结果"""
    title: str = ""
    abstract: str = ""
    keywords: list = field(default_factory=list)
    research_questions: list = field(default_factory=list)
    methodology: str = ""
    contributions: list = field(default_factory=list)
    strengths: list = field(default_factory=list)
    limitations: list = field(default_factory=list)
    reading_notes: str = ""
    raw_output: str = ""


class PaperAgent:
    """
    论文分析智能体，自动适配国内 AI API（DeepSeek / 智谱 / 通义千问 等）。
    """

    def __init__(self, api_key: str = None, provider: str = None, model: str = None, base_url: str = None):
        self.sdk_type = config.AI_SDK_TYPE
        self.model = model or config.AI_MODEL
        self.client = None
        self._custom_api_key = api_key
        self._custom_provider = provider
        self._custom_base_url = base_url
        if provider:
            provider_info = config.PROVIDER_CONFIG.get(provider, {})
            self.sdk_type = provider_info.get("sdk_type", "openai")
            if not model:
                self.model = provider_info.get("default_model", config.AI_MODEL)
            if not base_url:
                self._custom_base_url = provider_info.get("base_url", config.AI_API_BASE)
        self._init_client()

    def _init_client(self):
        """根据 provider 初始化对应的客户端。"""
        api_key = self._custom_api_key or config.AI_API_KEY
        base_url = self._custom_base_url or config.AI_API_BASE

        if not api_key:
            provider_info = config.PROVIDER_CONFIG.get(self._custom_provider or config.AI_PROVIDER, {})
            env_name = provider_info.get("api_key_env", "UNKNOWN")
            raise RuntimeError(
                f"未找到 API Key。请在设置页面填入 API Key。\n"
                f"环境变量: {env_name}\n"
                f"当前 provider: {self._custom_provider or config.AI_PROVIDER}\n"
                f"支持的 provider: deepseek / zhipu / qwen / moonshot / openai / anthropic"
            )

        if self.sdk_type == "anthropic":
            import anthropic
            self.client = anthropic.Anthropic(
                api_key=api_key,
                base_url=base_url,
            )
        else:
            import openai
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url,
            )

    def _call_llm(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        """调用大模型，自动处理两种 SDK 格式。"""
        if self.sdk_type == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
        else:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content

    # ========== 核心分析功能 ==========

    def generate_summary(self, paper_text: str, detail_level: str = "detailed") -> str:
        """生成论文摘要。detail_level: brief / detailed / structured"""
        prompts = {
            "brief": "请用3-5句话总结这篇论文的核心内容，包括研究问题、方法和主要发现。",
            "detailed": (
                "请对这篇论文进行全面总结，包括：\n"
                "1. 研究背景与问题\n"
                "2. 研究方法/技术方案\n"
                "3. 主要实验与发现\n"
                "4. 结论与贡献\n"
                "约500-800字。"
            ),
            "structured": (
                "请以 JSON 格式输出论文的结构化摘要：\n"
                '{"background": "背景", "problem": "问题", '
                '"method": "方法", "findings": "发现", '
                '"conclusion": "结论"}'
            ),
        }
        system_prompt = (
            "你是一位资深学术研究助手，擅长阅读和分析学术论文。"
            "请仔细阅读论文内容，给出准确、专业的分析。"
            "如果是英文论文，请用中文回复。"
        )
        user_prompt = f"{prompts.get(detail_level, prompts['detailed'])}\n\n论文内容：\n{paper_text}"
        return self._call_llm(system_prompt, user_prompt)

    def extract_keywords(self, paper_text: str, count: int = 8) -> list:
        """提取论文关键词。"""
        system_prompt = "你是一位学术研究助手。请以 JSON 数组格式输出关键词。"
        user_prompt = (
            f"请从以下论文中提取 {count} 个最核心的关键词，"
            f"以 JSON 数组格式输出，如: "
            f'["关键词1", "关键词2", ...]\n\n'
            f"论文内容：\n{paper_text}"
        )
        response = self._call_llm(system_prompt, user_prompt)
        return self._parse_json_array(response, count)

    def identify_research_questions(self, paper_text: str) -> list:
        """识别论文的研究问题。"""
        system_prompt = "你是一位学术研究助手。请以 JSON 数组格式输出研究问题。"
        user_prompt = (
            "请识别这篇论文的核心研究问题，以 JSON 数组格式输出。\n\n"
            f"论文内容：\n{paper_text}"
        )
        response = self._call_llm(system_prompt, user_prompt)
        return self._parse_json_array(response)

    def analyze_methodology(self, paper_text: str) -> str:
        """分析论文的研究方法。"""
        system_prompt = "你是一位学术研究助手，擅长分析研究方法。"
        user_prompt = (
            "请分析这篇论文的研究方法/技术方案，包括：\n"
            "1. 使用的算法/模型/框架\n"
            "2. 数据来源与处理方式\n"
            "3. 实验设计与评估指标\n"
            "4. 创新点\n\n"
            f"论文内容：\n{paper_text}"
        )
        return self._call_llm(system_prompt, user_prompt)

    def generate_structured_report(self, paper_text: str) -> AnalysisResult:
        """生成完整的论文分析报告（一次性完成所有分析）。"""
        system_prompt = (
            "你是一位资深学术研究助手。请对论文进行全面深入的分析。"
            "请严格以 JSON 格式输出，不要包含 JSON 之外的任何文字。\n"
            "{\n"
            '  "title": "论文标题",\n'
            '  "abstract": "200-300字论文摘要",\n'
            '  "keywords": ["关键词1", "关键词2", ...],\n'
            '  "research_questions": ["研究问题1", ...],\n'
            '  "methodology": "研究方法概述（200字）",\n'
            '  "contributions": ["贡献1", ...],\n'
            '  "strengths": ["优点1", ...],\n'
            '  "limitations": ["局限性1", ...],\n'
            '  "reading_notes": "阅读建议（100字）"\n'
            "}"
        )
        user_prompt = f"请分析以下论文：\n{paper_text}"
        response = self._call_llm(system_prompt, user_prompt, max_tokens=8192)
        return self._parse_report(response)

    def answer_question(self, paper_text: str, question: str) -> str:
        """回答用户关于论文的问题。"""
        system_prompt = (
            "你是一位学术研究助手。请基于论文内容回答用户问题。"
            "回答要准确有依据，如论文无相关信息请如实说明。"
            "请引用论文中具体段落或数据支持回答。"
        )
        user_prompt = f"论文内容：\n{paper_text}\n\n用户问题：{question}"
        return self._call_llm(system_prompt, user_prompt)

    def generate_bilingual_abstract(self, paper_text: str) -> str:
        """生成中英双语摘要。"""
        system_prompt = (
            "你是一位学术翻译与研究助手。"
            "请生成中英双语摘要，英文150-200词，中文200-300字。"
            "格式：先英文，后中文。"
        )
        user_prompt = f"论文内容：\n{paper_text}"
        return self._call_llm(system_prompt, user_prompt)

    # ========== 辅助方法 ==========

    @staticmethod
    def _parse_json_array(response: str, max_items: int = None) -> list:
        """从 AI 响应中解析 JSON 数组。"""
        try:
            # 尝试直接解析
            data = json.loads(response)
            if isinstance(data, list):
                return data[:max_items] if max_items else data
        except json.JSONDecodeError:
            pass
        # 从文本中提取 JSON 数组
        import re
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                if isinstance(data, list):
                    return data[:max_items] if max_items else data
            except json.JSONDecodeError:
                pass
        # 提取引号内的字符串
        found = re.findall(r'"([^"]+)"', response)
        if found:
            return found[:max_items] if max_items else found
        return []

    @staticmethod
    def _parse_report(raw: str) -> AnalysisResult:
        """解析 AI 返回的 JSON 报告。"""
        result = AnalysisResult(raw_output=raw)
        try:
            json_start = raw.find("{")
            json_end = raw.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(raw[json_start:json_end])
                result.title = data.get("title", "")
                result.abstract = data.get("abstract", "")
                result.keywords = data.get("keywords", [])
                result.research_questions = data.get("research_questions", [])
                result.methodology = data.get("methodology", "")
                result.contributions = data.get("contributions", [])
                result.strengths = data.get("strengths", [])
                result.limitations = data.get("limitations", [])
                result.reading_notes = data.get("reading_notes", "")
        except (json.JSONDecodeError, KeyError):
            pass
        return result
