"""
论文分析助手 - 独立桌面应用
双击运行，原生桌面窗口体验。
"""

import argparse
import sys
import os
import threading
import time
import logging
from pathlib import Path
from datetime import datetime

# 项目根目录
if getattr(sys, 'frozen', False):
    ROOT_DIR = Path(sys._MEIPASS)
else:
    ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

_LOG_FILE = ROOT_DIR / "startup.log"

def log(msg: str):
    """同时写入日志文件和终端（如果可用）。"""
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        print(line)
    except Exception:
        pass

log("论文分析助手 v2.1 启动")

# 静默日志
logging.getLogger("werkzeug").setLevel(logging.ERROR)
logging.getLogger("waitress").setLevel(logging.WARNING)

# 全局控制
_flask_port = 0

def get_free_port(default=5200):
    """获取可用端口。"""
    import socket
    for port in [default, 5201, 5202, 5203, 5204, 5205, 0]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    return 5200

def run_flask(port: int):
    """后台启动服务器（优先 waitress）。"""
    from server import app
    try:
        import waitress
        waitress.serve(app, host="127.0.0.1", port=port, _quiet=True, threads=6)
    except ImportError:
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

def wait_for_server(port: int, timeout: int = 30) -> bool:
    """等待服务器就绪。"""
    import requests
    for _ in range(timeout * 2):
        try:
            if requests.get(f"http://127.0.0.1:{port}", timeout=0.5).status_code == 200:
                return True
        except Exception:
            time.sleep(0.5)
    return False

def check_webview_available() -> bool:
    """检查 PyWebView 桌面模式是否可用。"""
    try:
        from webview.platforms.edgechromium import EdgeChrome
        return True
    except Exception:
        pass
    try:
        from webview.platforms.winforms import WinForms
        return True
    except Exception:
        pass
    return False

def launch_desktop(port: int):
    """PyWebView 原生桌面窗口。"""
    import webview
    webview.create_window(
        title="论文分析助手",
        url=f"http://127.0.0.1:{port}",
        width=1100, height=750,
        min_size=(820, 560),
        text_select=True,
    )
    webview.start(private_mode=False, storage_path=str(ROOT_DIR / ".webview_cache"))

def launch_browser(port: int):
    """浏览器模式。"""
    import webbrowser
    webbrowser.open(f"http://127.0.0.1:{port}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    global _flask_port

    # 检测已有实例
    import requests as req
    for check_port in [5200, 5201, 5202]:
        try:
            if req.get(f"http://127.0.0.1:{check_port}/api/settings", timeout=0.8).status_code == 200:
                log(f"检测到已有实例 (端口 {check_port})，连接中...")
                if args.browser or not check_webview_available():
                    launch_browser(check_port)
                else:
                    launch_desktop(check_port)
                return
        except Exception:
            continue

    # 获取端口并启动
    _flask_port = args.port if args.port > 0 else get_free_port(5200)
    log(f"端口: {_flask_port}, 启动服务...")

    threading.Thread(target=run_flask, args=(_flask_port,), daemon=True).start()

    if not wait_for_server(_flask_port):
        log("ERROR: 服务启动超时")
        sys.exit(1)

    log("服务就绪")

    if args.browser or not check_webview_available():
        log("启动浏览器模式")
        launch_browser(_flask_port)
    else:
        log("启动桌面窗口")
        launch_desktop(_flask_port)

    log("应用退出")

if __name__ == "__main__":
    main()
