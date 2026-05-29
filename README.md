# 论文阅读与摘要生成助手

AI 驱动的论文学术分析工具。上传 PDF 论文，自动生成结构化分析报告（摘要、关键词、研究方法、优缺点、阅读建议），输出 Markdown + Word 文档，支持飞书机器人自动回复。

## 快速开始

### 1. 安装依赖

```bash
cd paper-assistant
pip install -r requirements.txt
```

### 2. 配置 AI API Key

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 AI API Key（推荐 DeepSeek，便宜且速度快）：

```
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-你的Key
```

### 3. 命令行使用

```bash
# 完整分析一篇论文（生成 Markdown + Word 报告）
python run.py analyze paper.pdf

# 快速生成摘要
python run.py summarize paper.pdf --detail brief

# 提取关键词
python run.py keywords paper.pdf

# 论文问答
python run.py ask paper.pdf -q "这篇论文用了什么方法？"

# 中英双语摘要
python run.py bilingual paper.pdf

# JSON 格式输出
python run.py analyze paper.pdf --output json
```

报告保存在 `output/` 目录下，同时生成 `.md` 和 `.docx` 两种格式。

## 飞书机器人（可选）

把论文 PDF 发给飞书机器人，自动分析并回复 Word 报告。

### 机器人配置步骤

#### 1. 创建飞书应用

打开 [飞书开发者后台](https://open.feishu.cn)，点击 **创建企业自建应用**，名称填 `论文分析助手`。

#### 2. 获取凭证

应用详情页 → **凭证与基础信息** → 复制 `App ID` 和 `App Secret`，填入 `.env`：

```
FEISHU_APP_ID=cli_xxxx
FEISHU_APP_SECRET=xxxx
```

#### 3. 开启机器人

左侧 **应用功能** → **机器人** → 打开开关。

#### 4. 配置事件订阅

左侧 **事件订阅** → 打开开关：
- 添加事件 `im.message.receive_v1`（接收消息）
- 请求方式选 **使用长连接**
- 保存

#### 5. 添加权限

左侧 **权限管理** → 搜索并添加以下权限：

| 权限 | 用途 |
|------|------|
| `im:message.p2p_msg:readonly` | 接收用户消息 |
| `im:message:send_as_bot` | 回复消息 |
| `im:resource` | 下载消息中的文件 |
| `docx:document` | 创建飞书文档 |

批量授权后审批通过。

#### 6. 发布应用

左侧 **应用发布** → **创建版本**（填 `1.0.0`）→ **发布**。

#### 7. 配置 lark-cli

```bash
lark-cli config init --app-id 你的AppID --app-secret-stdin --brand feishu
```

#### 8. 启动机器人

```bash
# 持续监听模式
python run.py bot

# 单次调试模式（处理一条消息后退出）
python run.py bot --once
```

#### 9. 使用

打开飞书，搜索 **论文分析助手**，发送 PDF 论文文件，机器人会自动回复：
1. 快速摘要
2. Word 详细报告（.docx 文件）
3. 结果汇总（标题、关键词、方法）

## 支持 AI 服务商

| 服务商 | 环境变量 | 说明 |
|--------|----------|------|
| DeepSeek | `DEEPSEEK_API_KEY` | 推荐，性价比最高 |
| 智谱 GLM | `ZHIPU_API_KEY` | 国产大模型 |
| 通义千问 | `DASHSCOPE_API_KEY` | 阿里云 |
| Moonshot | `MOONSHOT_API_KEY` | 月之暗面 |
| OpenAI | `OPENAI_API_KEY` | GPT-4o |
| Anthropic | `ANTHROPIC_API_KEY` | Claude |

设置 `AI_PROVIDER` 选择服务商（默认 deepseek）。

## 项目结构

```
paper-assistant/
├── .env.example          # 配置模板
├── .gitignore
├── README.md
├── requirements.txt
├── run.py                # 入口：python run.py [analyze|summarize|keywords|ask|bilingual|bot]
├── config.py             # 配置管理（自动加载 .env）
├── bot.py                # 飞书机器人核心逻辑
├── src/
│   ├── agent.py          # AI 分析引擎
│   ├── pdf_parser.py     # PDF/DOCX 解析
│   ├── feishu.py         # 飞书文档 + Word 导出
│   └── cli.py            # CLI 命令行界面
├── tests/
│   └── test_basic.py     # 基础测试
└── output/               # 分析报告输出目录
```

## 技术架构

```
用户输入 PDF
    ↓
[PDF 解析] PyMuPDF 提取文本 → 识别章节结构
    ↓
[AI 分析] DeepSeek/GPT/... → 摘要/关键词/研究问题/方法论/优缺点
    ↓
[结果输出] → 终端 Rich 展示
          → Markdown 文件
          → Word (.docx) 文件
          → 飞书机器人自动回复
```
