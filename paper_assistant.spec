# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置 - 论文分析助手
=====================================
打包命令:
    pyinstaller paper_assistant.spec          → 文件夹模式（推荐）
    pyinstaller --onefile paper_assistant.spec → 单文件模式

输出:
    dist/论文分析助手/论文分析助手.exe
"""

import sys
from pathlib import Path

# SPECPATH 是 PyInstaller 提供的内置变量，指向 spec 文件所在目录
ROOT = Path(SPECPATH)

# ==================== 收集数据文件 ====================
datas = []

# 模板文件 (Flask templates)
templates_dir = ROOT / "templates"
if templates_dir.exists():
    for f in templates_dir.glob("*.html"):
        datas.append((str(f), "templates"))

# 静态资源 (CSS, JS)
static_dir = ROOT / "static"
if static_dir.exists():
    for f in static_dir.rglob("*"):
        if f.is_file():
            rel = str(f.parent.relative_to(ROOT))
            datas.append((str(f), rel))

# 根目录 Python 模块 (server.py, config.py, bot.py 等)
for f in ROOT.glob("*.py"):
    if f.name != "app.py":
        datas.append((str(f), "."))

# 源码包
src_dir = ROOT / "src"
if src_dir.exists():
    for f in src_dir.glob("*.py"):
        datas.append((str(f), "src"))

# 环境变量模板
env_example = ROOT / ".env.example"
if env_example.exists():
    datas.append((str(env_example), "."))

# ==================== 隐藏导入 ====================
hiddenimports = [
    # Flask 全家桶
    "flask", "flask.app", "flask.helpers", "flask.templating", "flask.json",
    "werkzeug", "werkzeug.serving", "werkzeug.debug", "werkzeug.urls",
    "jinja2", "jinja2.ext", "jinja2.nodes",
    "itsdangerous", "markupsafe", "click",
    # PDF
    "fitz", "pymupdf",
    # DOCX
    "docx", "docx.opc", "docx.oxml", "docx.shared",
    "docx.enum.text", "docx.enum.style",
    # AI SDK
    "openai", "openai._base_client",
    "anthropic",
    # HTTP / IO
    "requests", "urllib3", "certifi", "charset_normalizer", "idna",
    "dotenv",
    # Rich (CLI 备用的终端美化)
    "rich", "rich.console", "rich.table", "rich.panel",
    "rich.markdown", "rich.progress", "rich.text",
    # 其他
    "json", "uuid", "tempfile", "threading", "webbrowser",
    "argparse", "datetime", "subprocess", "socket",
    "pathlib",
]

# Windows 平台额外
if sys.platform == "win32":
    hiddenimports += [
        "win32event", "win32api", "win32con",
        "pywintypes", "winerror",
    ]


# ==================== 打包分析 ====================
a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "tkinter.test",
        "matplotlib", "numpy", "scipy", "pandas",
        "sqlalchemy", "sqlite3",
        "test", "tests", "unittest",
        "setuptools", "pip", "wheel", "pkg_resources",
        "jupyter", "ipython", "notebook",
        "sphinx", "pytest", "coverage",
        "Cython", "numba",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# ==================== 可执行文件 ====================
# 图标
icon_path = None
for candidate in [ROOT / "icon.ico", ROOT / "static" / "icon.ico"]:
    if candidate.exists():
        icon_path = str(candidate)
        break

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PaperAssistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,              # 无命令行窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

# ==================== 输出目录 (onedir 模式) ====================
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PaperAssistant",
)
