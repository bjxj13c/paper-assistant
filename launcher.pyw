"""
论文分析助手 - 桌面启动器（双击运行）
"""
import sys, os
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))

try:
    from app import main
    main()
except Exception as e:
    import traceback
    err = traceback.format_exc()
    # 写入日志
    try:
        with open(PROJECT_DIR / "startup.log", "a", encoding="utf-8") as f:
            f.write(f"\n启动失败:\n{err}\n")
    except Exception:
        pass
    # 弹窗提示
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "论文分析助手 - 启动失败",
        f"{str(e)[:200]}\n\n请运行: pip install -r requirements.txt\n\n详情见: startup.log"
    )
    sys.exit(1)
