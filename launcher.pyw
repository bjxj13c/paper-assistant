"""
论文分析助手 - 桌面启动器（双击运行，无需终端）
==============================================
Windows: 直接双击此文件即可启动应用
"""

import sys
import os
import io

# pythonw 无控制台时，重定向输出到日志文件
try:
    sys.stdout.write("")
except Exception:
    _log = open(PROJECT_DIR / "startup.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = _log
    sys.stderr = _log

from pathlib import Path

# 切换到项目目录
PROJECT_DIR = Path(__file__).parent
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))

# 日志文件
LOG_FILE = PROJECT_DIR / "startup.log"

def log(msg):
    """写入启动日志。"""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass

log("=" * 40)
log("启动中...")

# 清理旧实例的端口占用（不是杀进程，而是让 app.py 自行处理端口）
log("环境就绪")

try:
    from app import main
    log("导入成功，启动主程序...")
    main()
    log("程序正常退出")
except ImportError as e:
    log(f"导入错误: {e}")
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "论文分析助手 - 启动失败",
        f"缺少依赖库，请先安装：\n\n"
        f"pip install -r requirements.txt\n\n"
        f"错误: {e}"
    )
    sys.exit(1)
except SystemExit:
    log("程序退出")
except Exception as e:
    import traceback
    log(f"启动错误: {e}\n{traceback.format_exc()}")
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "论文分析助手 - 启动失败",
        f"启动时发生错误:\n\n{str(e)[:300]}\n\n"
        f"详情见: startup.log\n\n"
        f"请确认已安装依赖: pip install -r requirements.txt"
    )
    sys.exit(1)
