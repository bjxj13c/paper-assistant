"""
论文分析助手 - 独立桌面应用
============================
双击运行，原生桌面窗口体验。
"""

import argparse
import sys
import os
import io
import threading
import time
import logging
import atexit
from pathlib import Path

# pythonw 无控制台时，重定向输出到日志文件
try:
    sys.stdout.write("")
except Exception:
    _log = open(ROOT_DIR / "startup.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = _log
    sys.stderr = _log

# 项目根目录
if getattr(sys, 'frozen', False):
    ROOT_DIR = Path(sys._MEIPASS)
else:
    ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

# 全局控制
_flask_port = 0
_shutdown_event = threading.Event()
_lock_file = ROOT_DIR / ".app.lock"

# 日志静默
logging.getLogger("werkzeug").setLevel(logging.ERROR)
logging.getLogger("waitress").setLevel(logging.WARNING)


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
    """后台线程启动服务器（优先 waitress，回退 Flask）。"""
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
        if _shutdown_event.is_set():
            return False
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


def acquire_single_instance() -> bool:
    """单实例锁：防止重复启动。如果端口已有实例则直接连接。"""
    import requests
    try:
        r = requests.get("http://127.0.0.1:5200/api/settings", timeout=0.8)
        if r.status_code == 200:
            return False  # 已有实例
    except Exception:
        pass
    return True


def launch_desktop(port: int, icon_path: str = None):
    """PyWebView 原生桌面窗口。"""
    import webview
    url = f"http://127.0.0.1:{port}"

    window = webview.create_window(
        title="论文分析助手",
        url=url,
        width=1100,
        height=750,
        min_size=(820, 560),
        text_select=True,
        easy_drag=False,
    )
    webview.start(private_mode=False, storage_path=str(ROOT_DIR / ".webview_cache"))


def launch_browser(port: int):
    """浏览器模式。"""
    import webbrowser
    webbrowser.open(f"http://127.0.0.1:{port}")
    try:
        while not _shutdown_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def main():
    parser = argparse.ArgumentParser(description="论文分析助手")
    parser.add_argument("--browser", action="store_true", help="浏览器模式")
    parser.add_argument("--port", type=int, default=0, help="指定端口")
    args = parser.parse_args()

    global _flask_port

    # 检查是否已有实例在运行
    if not acquire_single_instance():
        print("检测到应用已在运行，连接中...")
        if args.browser or not check_webview_available():
            launch_browser(5100)
        else:
            launch_desktop(5100)
        return

    # 获取端口
    _flask_port = args.port if args.port > 0 else get_free_port(5100)

    # 图标
    icon_path = str(ROOT_DIR / "icon.ico")
    if not os.path.exists(icon_path):
        icon_path = None

    # 启动后台服务
    print(f"论文分析助手 v2.1 | 端口: {_flask_port} | 启动中...")
    flask_thread = threading.Thread(target=run_flask, args=(_flask_port,), daemon=True)
    flask_thread.start()

    if not wait_for_server(_flask_port):
        print("服务启动超时！")
        sys.exit(1)

    # 桌面窗口 / 浏览器
    if args.browser or not check_webview_available():
        launch_browser(_flask_port)
    else:
        launch_desktop(_flask_port, icon_path)

    # 清理
    _lock_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
