"""
论文分析助手 - Flask API 服务
提供文件上传、AI 分析、聊天对话等 API 接口
"""

import json
import os
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, send_file, session, render_template

# 确保项目根目录在 path 中
# PyInstaller 打包后资源路径处理
if getattr(sys, 'frozen', False):
    _ROOT_DIR = Path(sys._MEIPASS)
else:
    _ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(_ROOT_DIR))

import config
from src.pdf_parser import extract_paper, chunk_text
from src.agent import PaperAgent
from src.feishu import save_as_docx, build_report_markdown


def _create_agent():
    """使用本地配置创建 PaperAgent 实例。"""
    api_config = config.get_api_config()
    return PaperAgent(
        api_key=api_config.get("api_key") or None,
        provider=api_config.get("provider") or None,
        model=api_config.get("model") or None,
    )

app = Flask(
    __name__,
    template_folder=str(_ROOT_DIR / "templates"),
    static_folder=str(_ROOT_DIR / "static"),
)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "paper-assistant-secret-" + str(uuid.uuid4()))
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB 上传限制

# 会话数据存储（文件系统）
SESSION_DIR = Path(config.OUTPUT_DIR) / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)


def _get_paper_dir(session_id: str) -> Path:
    """获取会话的临时目录。"""
    d = SESSION_DIR / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_paper_data(session_id: str) -> dict | None:
    """获取会话的论文数据。"""
    data_file = _get_paper_dir(session_id) / "paper_data.json"
    if data_file.exists():
        with open(data_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_paper_data(session_id: str, data: dict):
    """保存会话的论文数据。"""
    data_file = _get_paper_dir(session_id) / "paper_data.json"
    # 不保存完整文本（太大）
    save_data = {k: v for k, v in data.items() if k != "full_text"}
    if "full_text" in data:
        text_file = _get_paper_dir(session_id) / "paper_text.txt"
        text_file.write_text(data["full_text"], encoding="utf-8")
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)


def _get_paper_full_text(session_id: str) -> str:
    """获取完整论文文本。"""
    text_file = _get_paper_dir(session_id) / "paper_text.txt"
    if text_file.exists():
        return text_file.read_text(encoding="utf-8")
    data = _get_paper_data(session_id)
    if data:
        return data.get("full_text", "")
    return ""


# ========== 页面路由 ==========

@app.route("/")
def index():
    """聊天界面主页。"""
    return render_template("index.html")


# ========== API 路由 ==========

@app.route("/api/upload", methods=["POST"])
def upload_paper():
    """上传论文文件，解析并返回论文信息。"""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "未找到上传文件"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "文件名为空"}), 400

    # 检查文件类型
    filename = file.filename.lower()
    if not (filename.endswith(".pdf") or filename.endswith(".docx")):
        return jsonify({"success": False, "error": "仅支持 PDF 和 DOCX 文件"}), 400

    # 生成会话 ID
    session_id = str(uuid.uuid4())

    # 保存上传文件
    paper_dir = _get_paper_dir(session_id)
    ext = ".pdf" if filename.endswith(".pdf") else ".docx"
    tmp_path = str(paper_dir / f"paper{ext}")

    file.save(tmp_path)

    try:
        # 解析论文
        paper = extract_paper(tmp_path)
        paper_text = paper.to_text(max_len=30000)

        # 保存数据
        data = {
            "session_id": session_id,
            "title": paper.title or Path(file.filename).stem,
            "authors": paper.authors or "未知",
            "abstract": paper.abstract[:500] if paper.abstract else "",
            "sections": paper.get_section_titles(),
            "section_count": len(paper.sections),
            "text_length": len(paper.full_text),
            "full_text": paper_text,
            "filename": file.filename,
            "upload_time": datetime.now().isoformat(),
        }
        _save_paper_data(session_id, data)

        return jsonify({
            "success": True,
            "session_id": session_id,
            "title": data["title"],
            "authors": data["authors"],
            "abstract": data["abstract"],
            "sections": data["sections"],
            "section_count": data["section_count"],
            "text_length": data["text_length"],
            "filename": data["filename"],
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"论文解析失败: {str(e)}"}), 500


@app.route("/api/analyze", methods=["POST"])
def analyze_paper():
    """对已上传的论文进行结构化分析。"""
    data = request.get_json() or {}
    session_id = data.get("session_id", "")

    paper_text = _get_paper_full_text(session_id)
    if not paper_text:
        return jsonify({"success": False, "error": "未找到论文数据，请先上传文件"}), 400

    try:
        agent = _create_agent()
        result = agent.generate_structured_report(paper_text)

        return jsonify({
            "success": True,
            "title": result.title,
            "abstract": result.abstract,
            "keywords": result.keywords,
            "research_questions": result.research_questions,
            "methodology": result.methodology,
            "contributions": result.contributions,
            "strengths": result.strengths,
            "limitations": result.limitations,
            "reading_notes": result.reading_notes,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"AI 分析失败: {str(e)}"}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    """与 AI 对话：发送消息/提问，AI 基于论文回答。"""
    data = request.get_json() or {}
    session_id = data.get("session_id", "")
    message = data.get("message", "").strip()
    intent = data.get("intent", "question")  # question / summary / keywords / full_report / bilingual

    if not message and intent == "question":
        return jsonify({"success": False, "error": "消息不能为空"}), 400

    paper_text = _get_paper_full_text(session_id)
    if not paper_text:
        return jsonify({"success": False, "error": "请先上传论文文件"}), 400

    try:
        agent = _create_agent()
        paper_data = _get_paper_data(session_id) or {}

        if intent == "summary":
            # 快速摘要
            detail = data.get("detail", "brief")
            response_text = agent.generate_summary(paper_text, detail_level=detail)
            return jsonify({
                "success": True,
                "type": "summary",
                "content": response_text,
            })

        elif intent == "keywords":
            # 提取关键词
            count = data.get("count", 8)
            keywords = agent.extract_keywords(paper_text, count=count)
            return jsonify({
                "success": True,
                "type": "keywords",
                "content": keywords,
            })

        elif intent == "full_report":
            # 完整结构化报告 + 自动生成 Word 文档
            result = agent.generate_structured_report(paper_text)

            # 生成 Word 报告文件
            paper_dir = _get_paper_dir(session_id)
            safe_title = (result.title or paper_data.get("title", "analysis")).replace("/", "_").replace("\\", "_")[:50]
            docx_filename = f"论文分析_{safe_title}.docx"
            docx_path = str(paper_dir / docx_filename)
            save_as_docx(result, docx_path)
            report_size = os.path.getsize(docx_path)

            return jsonify({
                "success": True,
                "type": "full_report",
                "title": result.title,
                "abstract": result.abstract,
                "keywords": result.keywords,
                "research_questions": result.research_questions,
                "methodology": result.methodology,
                "contributions": result.contributions,
                "strengths": result.strengths,
                "limitations": result.limitations,
                "reading_notes": result.reading_notes,
                "report_url": f"/api/report-file/{session_id}",
                "report_name": docx_filename,
                "report_size": report_size,
            })

        elif intent == "bilingual":
            # 双语摘要
            response_text = agent.generate_bilingual_abstract(paper_text)
            return jsonify({
                "success": True,
                "type": "bilingual",
                "content": response_text,
            })

        elif intent == "methodology":
            # 研究方法分析
            response_text = agent.analyze_methodology(paper_text)
            return jsonify({
                "success": True,
                "type": "methodology",
                "content": response_text,
            })

        else:
            # 自由提问
            response_text = agent.answer_question(paper_text, message)
            return jsonify({
                "success": True,
                "type": "answer",
                "content": response_text,
                "question": message,
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"处理失败: {str(e)}"}), 500


@app.route("/api/download-report", methods=["POST"])
def download_report():
    """生成并下载 Word 分析报告。"""
    data = request.get_json() or {}
    session_id = data.get("session_id", "")

    paper_text = _get_paper_full_text(session_id)
    if not paper_text:
        return jsonify({"success": False, "error": "未找到论文数据"}), 400

    try:
        agent = _create_agent()
        result = agent.generate_structured_report(paper_text)

        # 保存 Word 文件
        paper_dir = _get_paper_dir(session_id)
        safe_title = (result.title or "analysis").replace("/", "_").replace("\\", "_")[:50]
        docx_path = str(paper_dir / f"{safe_title}.docx")
        save_as_docx(result, docx_path)

        return send_file(
            docx_path,
            as_attachment=True,
            download_name=f"论文分析_{safe_title}.docx",
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"报告生成失败: {str(e)}"}), 500


@app.route("/api/session-info", methods=["POST"])
def session_info():
    """获取当前会话的论文信息。"""
    data = request.get_json() or {}
    session_id = data.get("session_id", "")

    paper_data = _get_paper_data(session_id)
    if not paper_data:
        return jsonify({"success": False, "error": "未找到会话数据"}), 404

    return jsonify({
        "success": True,
        "title": paper_data.get("title", ""),
        "authors": paper_data.get("authors", ""),
        "abstract": paper_data.get("abstract", ""),
        "sections": paper_data.get("sections", []),
        "section_count": paper_data.get("section_count", 0),
        "text_length": paper_data.get("text_length", 0),
        "filename": paper_data.get("filename", ""),
    })


@app.route("/api/report-file/<session_id>")
def serve_report_file(session_id: str):
    """提供已生成的 Word 报告文件下载。"""
    paper_dir = _get_paper_dir(session_id)
    # 查找目录中的 .docx 文件
    docx_files = list(paper_dir.glob("*.docx"))
    if not docx_files:
        return jsonify({"success": False, "error": "报告文件不存在，请先生成报告"}), 404

    docx_path = str(docx_files[0])
    return send_file(
        docx_path,
        as_attachment=True,
        download_name=docx_files[0].name,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# ========== 设置管理 API ==========

@app.route("/settings")
def settings_page():
    """设置页面。"""
    return render_template("settings.html")


@app.route("/api/settings", methods=["GET"])
def get_settings():
    """获取当前 API 设置。"""
    api_config = config.get_api_config()
    local = config.load_local_config()
    return jsonify({
        "provider": api_config.get("provider", "deepseek"),
        "api_key": (api_config.get("api_key", "")[:8] + "***" + api_config.get("api_key", "")[-4:])
                    if api_config.get("api_key") else "",
        "has_api_key": bool(api_config.get("api_key")),
        "model": api_config.get("model", ""),
        "providers": list(config.PROVIDER_CONFIG.keys()),
    })


@app.route("/api/settings", methods=["POST"])
def save_settings():
    """保存 API 设置。"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "无效的请求数据"}), 400

    provider = data.get("provider", "deepseek")
    api_key = data.get("api_key", "").strip()
    model = data.get("model", "").strip()

    if not api_key:
        return jsonify({"success": False, "error": "API Key 不能为空"}), 400

    if provider not in config.PROVIDER_CONFIG:
        return jsonify({"success": False, "error": f"不支持的 Provider: {provider}"}), 400

    config.save_local_config({
        "provider": provider,
        "api_key": api_key,
        "model": model or "",
    })

    return jsonify({"success": True, "message": "设置已保存"})


@app.route("/api/settings/test", methods=["POST"])
def test_connection():
    """测试 API 连接是否正常。"""
    data = request.get_json()
    provider = data.get("provider", "deepseek")
    api_key = data.get("api_key", "").strip()
    model = data.get("model", "").strip()

    if not api_key:
        return jsonify({"success": False, "error": "请先填入 API Key"})

    try:
        agent = PaperAgent(
            api_key=api_key,
            provider=provider,
            model=model or None,
        )
        response = agent._call_llm(
            system_prompt="你是一个有用的助手。",
            user_prompt="请回复：连接成功！",
            max_tokens=50,
        )
        return jsonify({"success": True, "message": response.strip()})
    except Exception as e:
        return jsonify({"success": False, "error": f"连接失败: {str(e)}"})


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5100)
