"""
论文阅读与摘要生成助手 - 配置管理

国内 AI API 配置（推荐 DeepSeek，性价比最高）：
    export AI_PROVIDER=deepseek
    export DEEPSEEK_API_KEY=your_key

    或
    export AI_PROVIDER=zhipu
    export ZHIPU_API_KEY=your_key
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# 项目根目录
ROOT_DIR = Path(__file__).parent

# ========== AI Provider 选择 ==========
# 支持的 provider: deepseek, zhipu, qwen, moonshot, openai, anthropic
AI_PROVIDER = os.environ.get("AI_PROVIDER", "deepseek")

# 各 Provider 的预置配置
PROVIDER_CONFIG = {
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "sdk_type": "openai",   # 使用 OpenAI 兼容 SDK
    },
    "zhipu": {
        "api_key_env": "ZHIPU_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-plus",
        "sdk_type": "openai",
    },
    "qwen": {
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "sdk_type": "openai",
    },
    "moonshot": {
        "api_key_env": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "sdk_type": "openai",
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "sdk_type": "openai",
    },
    "anthropic": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com",
        "default_model": "claude-sonnet-4-6",
        "sdk_type": "anthropic",
    },
}

# 获取当前 Provider 配置
_current = PROVIDER_CONFIG.get(AI_PROVIDER, PROVIDER_CONFIG["deepseek"])
AI_API_KEY = os.environ.get(_current["api_key_env"], "")
AI_API_BASE = _current["base_url"]
AI_MODEL = os.environ.get("AI_MODEL", _current["default_model"])
AI_SDK_TYPE = _current["sdk_type"]

# ========== 飞书配置 ==========
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_DOC_FOLDER = os.environ.get("FEISHU_DOC_FOLDER", "")
FEISHU_BOT_WEBHOOK = os.environ.get("FEISHU_BOT_WEBHOOK", "")

# ========== 输出配置 ==========
OUTPUT_DIR = ROOT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
