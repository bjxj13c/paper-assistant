"""
飞书论文分析机器人
把 PDF 论文发给机器人，自动分析并回复飞书文档链接。

用法:
    python bot.py              # 启动机器人，持续监听
    python bot.py --once       # 处理一条消息后退出（调试用）
"""

import json
import os
import subprocess
import sys
import time
import tempfile
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import config
from src.pdf_parser import extract_paper
from src.agent import PaperAgent

# ========== Token 管理 ==========

def get_tenant_token() -> str:
    """获取 tenant_access_token。"""
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": config.FEISHU_APP_ID, "app_secret": config.FEISHU_APP_SECRET},
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json().get("tenant_access_token", "")
    raise RuntimeError(f"获取飞书 Token 失败: {resp.text}")


def _get_raw_message(token: str, message_id: str) -> dict:
    """通过 API 获取原始消息内容，提取 file_key 等信息。"""
    resp = requests.get(
        f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"[Bot] 获取消息失败: {resp.text}")
        return {}
    data = resp.json()
    if data.get("code") != 0:
        print(f"[Bot] API 错误: {data}")
        return {}
    items = data.get("data", {}).get("items", [])
    if not items:
        return {}
    msg = items[0]
    body = msg.get("body", {}).get("content", "{}")
    try:
        return json.loads(body) if isinstance(body, str) else body
    except json.JSONDecodeError:
        return {}


def upload_and_send_file(token: str, chat_id: str, reply_msg_id: str, file_path: str, file_name: str = ""):
    """上传文件到飞书，并作为回复发送。"""
    file_size = os.path.getsize(file_path)
    display_name = file_name or os.path.basename(file_path)

    # 1. 上传文件
    with open(file_path, "rb") as f:
        resp = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (display_name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"file_type": "doc", "file_name": display_name},
            timeout=60,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"上传失败: {resp.text}")
    file_key = resp.json().get("data", {}).get("file_key", "")
    if not file_key:
        raise RuntimeError(f"未获取到 file_key: {resp.json()}")

    # 2. 通过回复发送文件
    content = json.dumps({"file_key": file_key, "file_name": display_name})
    body = {
        "msg_type": "file",
        "content": content,
    }
    resp2 = requests.post(
        f"https://open.feishu.cn/open-apis/im/v1/messages/{reply_msg_id}/reply",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=30,
    )
    if resp2.status_code != 200:
        print(f"[Bot] 发送文件失败: {resp2.text}")


def download_file(token: str, message_id: str, file_key: str, save_path: str) -> str:
    """从飞书消息中下载文件。"""
    resp = requests.get(
        f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{file_key}",
        params={"type": "file"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    if resp.status_code == 200:
        with open(save_path, "wb") as f:
            f.write(resp.content)
        return save_path
    raise RuntimeError(f"文件下载失败: {resp.text}")


def send_message(token: str, chat_id: str, msg_id: str, text: str):
    """回复消息。"""
    body = {
        "msg_type": "text",
        "content": json.dumps({"text": text}),
    }
    resp = requests.post(
        f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/reply",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"[Bot] 回复失败: {resp.text}")
    return resp.json()


# ========== 事件处理 ==========

def handle_message(event: dict):
    """处理一条飞书消息。"""
    msg_id = event.get("message_id") or event.get("id", "")
    chat_id = event.get("chat_id", "")
    sender_id = event.get("sender_id", "")
    msg_type = event.get("message_type", "")

    print(f"\n[Bot] 收到消息: msg_id={msg_id}, type={msg_type}, sender={sender_id}")

    # 获取 token
    token = get_tenant_token()

    # 非文件消息 -> 提示用法
    if msg_type != "file":
        send_message(token, chat_id, msg_id,
            "请直接发送 PDF 论文文件给我，我会自动分析并生成报告。\n"
            "支持的功能：摘要生成、关键词提取、研究方法分析、优缺点评估、阅读建议等。"
        )
        return

    # 文件消息：通过 API 获取原始内容（lark-cli 会预渲染 content 为文本）
    raw_content = _get_raw_message(token, msg_id)
    if not raw_content:
        send_message(token, chat_id, msg_id, "无法读取文件信息，请重试。")
        return

    file_name = raw_content.get("file_name", "unknown.pdf")
    file_key = raw_content.get("file_key", "")
    if not file_key:
        send_message(token, chat_id, msg_id, f"无法获取文件: {file_name}")
        return

    if not file_name.lower().endswith(".pdf"):
        send_message(token, chat_id, msg_id, f"抱歉，目前只支持 PDF 论文文件。你发送的是: {file_name}")
        return

    print(f"[Bot] 收到 PDF: {file_name} (key={file_key})")

    # 回复处理中
    send_message(token, chat_id, msg_id, f"收到论文《{file_name}》，正在分析中......")

    # 下载文件
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        tmp_pdf = f.name
    try:
        download_file(token, msg_id, file_key, tmp_pdf)
        print(f"[Bot] 文件已下载: {tmp_pdf}")
    except Exception as e:
        send_message(token, chat_id, msg_id, f"文件下载失败: {e}")
        return

    # 分析论文
    try:
        paper = extract_paper(tmp_pdf)
        paper_text = paper.to_text(max_len=15000)
        agent = PaperAgent()

        # 第一步：快速摘要
        print("[Bot] 生成快速摘要...")
        brief_summary = agent.generate_summary(paper_text, detail_level="brief")
        send_message(token, chat_id, msg_id, f"{brief_summary}\n\n详细报告生成中，请稍候......")

        # 第二步：完整分析
        print("[Bot] 生成完整报告...")
        result = agent.generate_structured_report(paper_text)
        print(f"[Bot] 分析完成: {result.title}")

        from src.feishu import save_as_docx

        # 生成 Word 并发送到聊天
        safe_title = (result.title or file_name).replace("/", "_").replace("\\", "_")[:50]
        docx_path = save_as_docx(result)
        docx_filename = f"论文分析_{safe_title}.docx"
        print(f"[Bot] Word 已生成: {docx_path}")
        upload_and_send_file(token, chat_id, msg_id, docx_path, docx_filename)

        # 发送结果摘要
        kw_str = "、".join(result.keywords[:5]) if result.keywords else ""
        if result.methodology:
            send_message(token, chat_id, msg_id,
                f"**论文**: {result.title}\n"
                f"**关键词**: {kw_str}\n"
                f"**方法**: {result.methodology[:200]}..."
            )

    except Exception as e:
        import traceback
        traceback.print_exc()
        send_message(token, chat_id, msg_id, f"论文分析失败: {e}")
    finally:
        try:
            os.unlink(tmp_pdf)
        except Exception:
            pass


# ========== 主循环 ==========

def run_bot(once: bool = False):
    """启动飞书机器人，持续监听消息。"""

    if not config.FEISHU_APP_ID:
        print("[Bot] 错误: 未配置 FEISHU_APP_ID，请先复制 .env.example 为 .env 并填入飞书应用凭证")
        return

    print(f"[Bot] 论文分析机器人启动中...")
    print(f"[Bot] AI Provider: {config.AI_PROVIDER} | Model: {config.AI_MODEL}")

    cmd = [
        "lark-cli", "event", "consume", "im.message.receive_v1",
        "--as", "bot",
    ]
    if once:
        cmd.extend(["--max-events", "1"])

    print(f"[Bot] {'单次调试模式' if once else '持续监听模式'}，等待消息...\n")

    proc = subprocess.Popen(
        " ".join(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        shell=True,
    )

    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                handle_message(event)
            except json.JSONDecodeError:
                print(f"[Bot] 无法解析: {line[:100]}")
            except Exception as e:
                print(f"[Bot] 处理异常: {e}")

            if once:
                break
    except KeyboardInterrupt:
        print("\n[Bot] 已停止")
    finally:
        proc.terminate()
        proc.wait()
