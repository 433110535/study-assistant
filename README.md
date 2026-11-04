# 智能学习助手 · Study Assistant

> 面向自主学习场景的 AI 学习代理：把教材、练习、错题和复习计划连成一条闭环，而不是只回答一次问题。

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.41+-FF4B4B?logo=streamlit&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C)
![Qwen](https://img.shields.io/badge/LLM-Qwen--Max-615CED)
![License](https://img.shields.io/badge/License-MIT-green)

**仓库地址：** [https://github.com/433110535/study-assistant](https://github.com/433110535/study-assistant)

---

## 目录

- [为什么做这个项目](#为什么做这个项目)
- [核心能力](#核心能力)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [设计与工程原则](#设计与工程原则)
- [质量与评测](#质量与评测)
- [路线图](#路线图)
- [参与与反馈](#参与与反馈)
- [许可](#许可)

---

## 为什么做这个项目

通用聊天机器人能讲知识，但它不知道三件关键的事：

1. **你手上是什么教材**——回答往往脱离你正在学的资料。
2. **你错在哪里**——没有错题记录，就无法针对性补强。
3. **你学到哪一步**——没有学习档案，计划与复习只能靠感觉。

本项目把 **RAG 检索、工具调用、运行 trace、学习记录与评测** 放在同一条链路上：

```text
上传教材 → 检索依据 → 讲解/出题 → （规划）批改 → 错题归因 → 到期复习
```

目标不是做一个“什么都能聊”的机器人，而是一个能持续跟进、可被验证的学习代理。详细设计见 [`说明/功能扩展设想.md`](说明/功能扩展设想.md)。

---

## 核心能力

### 已实现

- **ReAct 多步问答**：模型自主选择工具，流式输出，思维链可展开查看。
- **个人知识库**：PDF → 切分 → 向量化 → FAISS 检索，回答带来源与相似度。
- **学习工具集**：概念讲解、对比、学习计划、日程、出题与批改（部分页面为直接函数调用）。
- **拍照识题（初版）**：问答页上传题目图片 → Agent 调用 `read_image`（DashScope VL）→ 可选 RAG → 分步讲解；支持发送前修正识别文本；图片仅存本地 `data/uploads/`。
- **工具注册表**：`ToolSpec` 元数据（超时、副作用、成本提示）。
- **运行 trace（SQLite）**：每次问答 run 与 tool_call 写入 `data/app.db`，为评测与中台打地基。

### 规划中

- 拍照批改闭环（判分、错题本、变式题、复习提醒）
- 代码执行助教（沙箱 + 测试用例）
- 主动复习推送（独立 Worker + SM-2）
- 数据中台 / 评测中台（数据集版本、离线 runner、发布门禁）

---

## 系统架构

```mermaid
flowchart LR
    U[用户] --> UI[Streamlit 工作台]
    UI --> A[ReAct Agent]
    A -->|Function Calling| T[工具注册层]
    T --> R[RAG 检索]
    T --> V[read_image · VL]
    T --> P[讲解 / 计划 / 出题]
    R --> D[(PDF · FAISS)]
    A --> LLM[Qwen / DashScope]
    A --> S[(SQLite trace)]
    S --> E[评测 · 回归 · 规划]
```

一次带图片的问答路径：

```text
上传图片 → 消息含本地路径
  → read_image 识题
  → rag_search（按需）
  → 分步讲解 + 变式题
  → trace 落库
```

---

## 技术栈

| 类别 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.11+ | 后端与前端同语言 |
| 界面 | Streamlit | 多页面工作台 |
| Agent | LangChain + 自研 ReAct | 流式与工具可视化 |
| 大模型 | Qwen-Max（DashScope） | Function Calling |
| 视觉 | Qwen-VL（`VISION_MODEL`） | 题目识图 |
| 向量检索 | FAISS + DashScope Embedding | 本地索引 |
| 持久化 | SQLite（`data/app.db`） | run / tool_call trace |
| 评测 | 规划中（Ragas / promptfoo） | 离线门禁 |

---

## 快速开始

```bash
git clone https://github.com/433110535/study-assistant.git
cd study-assistant

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
# source venv/bin/activate

pip install -r requirements.txt
```

配置环境变量：

```bash
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env
```

在 `.env` 中填入 DashScope API Key（文本与识图共用）：

```dotenv
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_MODEL=qwen-max
VISION_MODEL=qwen-vl-max
```

启动：

```bash
python start.py
# 或
streamlit run frontend/app.py
```

浏览器访问 `http://localhost:8501`。在 **在线问答** 页可上传题目图片进行识题讲解。

### 测试（不调用 LLM）

```bash
python -m unittest discover -s tests -v
```

---

## 项目结构

```text
study-assistant/
├── backend/
│   ├── agents/          # ReAct、工具注册表、事件模型
│   ├── tools/             # 讲解、计划、出题、vision.py
│   ├── knowledge/         # PDF、FAISS
│   ├── platform/          # trace_store（SQLite）
│   ├── config.py
│   └── llm_helper.py
├── frontend/
│   └── app.py             # Streamlit 工作台
├── tests/
├── data/                  # 索引、上传、app.db（默认不入库）
├── 说明/                  # 功能扩展设想等
├── requirements.txt
└── README.md
```

---

## 设计与工程原则

1. **Agent 决策，而非关键词匹配**  
2. **工具是一等公民**：超时、错误字符串返回、trace 记录  
3. **写操作需确认**（后续日历、消息、错题本）  
4. **回答可追溯**：RAG 带来源；run 可落库  
5. **评测先于大规模功能堆叠**  
6. **不堆假功能页**：新能力必须新增真实动作轴  

---

## 质量与评测

目标值（随评测中台逐步启用）：

| 维度 | 指标 | 目标 |
|---|---|---|
| 检索 | hit@3 | ≥ 0.85 |
| 生成 | 忠实度 | ≥ 0.85 |
| Agent | 工具选择准确率 | ≥ 90% |
| 工程 | trace 覆盖率 | 100% |

---

## 路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| P0 | 开源仓库、README、架构文档 | 已完成 |
| P1 | 工具注册表、SQLite trace、拍照识题初版 | **进行中** |
| P2 | 错题本 + 拍照批改闭环 | 规划中 |
| P3 | 代码执行助教 | 规划中 |
| P4 | 主动复习与推送 | 规划中 |
| P5 | 评测 runner、门禁、FastAPI 服务化 | 规划中 |

---

## 参与与反馈

欢迎 Issue / PR。较大改动请先对照 `说明/功能扩展设想.md` 讨论优先级。

---

## 许可

MIT License（如需正式 LICENSE 文件可在 Issue 中提出）。
