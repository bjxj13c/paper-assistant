"""
论文阅读与摘要生成助手 - 配置管理

支持从本地 JSON 配置文件加载设置（GUI 模式），
也兼容环境变量方式（CLI 模式）。
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# 项目根目录（兼容 PyInstaller 打包）
if getattr(sys, 'frozen', False):
    ROOT_DIR = Path(sys._MEIPASS)
else:
    ROOT_DIR = Path(__file__).parent

# 本地配置文件路径（API Key 存储）
# PyInstaller 打包后优先用 exe 同目录（便携版），受限时用 AppData
if getattr(sys, 'frozen', False):
    _EXE_DIR = Path(sys.executable).parent
    LOCAL_CONFIG_PATH = _EXE_DIR / "local_config.json"
    # 测试可写性
    try:
        LOCAL_CONFIG_PATH.touch()
    except (PermissionError, OSError):
        import tempfile
        _appdata = Path(os.environ.get("APPDATA", tempfile.gettempdir()))
        _cfg_dir = _appdata / "PaperAssistant"
        _cfg_dir.mkdir(parents=True, exist_ok=True)
        LOCAL_CONFIG_PATH = _cfg_dir / "local_config.json"
else:
    LOCAL_CONFIG_PATH = ROOT_DIR / "local_config.json"


def load_local_config() -> dict:
    """从本地 JSON 配置文件加载设置。"""
    if LOCAL_CONFIG_PATH.exists():
        try:
            with open(LOCAL_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_local_config(data: dict):
    """保存设置到本地 JSON 配置文件。"""
    with open(LOCAL_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_api_config() -> dict:
    """
    获取 API 配置，优先级：本地配置 > 环境变量。
    返回: {"provider": "...", "api_key": "...", "model": "..."}
    """
    local = load_local_config()
    provider = local.get("provider") or os.environ.get("AI_PROVIDER", "deepseek")
    api_key = local.get("api_key") or ""
    model = local.get("model") or os.environ.get("AI_MODEL", "")

    # 如果没有本地 api_key，尝试从环境变量获取
    if not api_key:
        provider_config = PROVIDER_CONFIG.get(provider, PROVIDER_CONFIG["deepseek"])
        env_name = provider_config.get("api_key_env", "")
        api_key = os.environ.get(env_name, "")

    # 如果没有指定 model，使用 provider 默认值
    if not model:
        provider_config = PROVIDER_CONFIG.get(provider, PROVIDER_CONFIG["deepseek"])
        model = provider_config.get("default_model", "")

    return {"provider": provider, "api_key": api_key, "model": model}

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
# PyInstaller 打包后，使用用户 AppData 目录（避免 Program Files 权限问题）
if getattr(sys, 'frozen', False):
    _EXE_DIR = Path(sys.executable).parent
    # 优先用 exe 同目录（便携版），失败则用 AppData
    OUTPUT_DIR = _EXE_DIR / "output"
    try:
        OUTPUT_DIR.mkdir(exist_ok=True)
        # 测试是否可写
        _test = OUTPUT_DIR / ".write_test"
        _test.touch()
        _test.unlink()
    except (PermissionError, OSError):
        # Program Files 等受限目录 → 回退到 AppData
        import tempfile
        _appdata = Path(os.environ.get("APPDATA", tempfile.gettempdir()))
        OUTPUT_DIR = _appdata / "PaperAssistant" / "output"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
else:
    OUTPUT_DIR = ROOT_DIR / "output"
    OUTPUT_DIR.mkdir(exist_ok=True)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
