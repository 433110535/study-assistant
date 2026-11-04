# 项目代码地图（最通俗版）

---

## 一、记住这个核心比喻

把整个项目想成一个**公司**：
- **老板（用户）** 发需求
- **前台（app.py）** 接待，转给秘书
- **秘书（react_agent.py）** 接需求、思考、安排
- **秘书手上的工具箱（react_tools.py）** 各种工具
- **工具实际实现（tools/ 目录）** 干活的代码
- **秘书的电脑（llm_helper.py）** 连接 AI 大模型
- **资料室（knowledge/ 目录）** 知识库
- **秘书的笔记本（react_models.py）** 记录每一步数据

---

## 二、文件清单（按功能分组）

### 第一组：前门（用户看到的）

#### `frontend/app.py` —— 网页主应用
**作用**：用户看到的整个网站。
- 写了 6 个页面：在线问答、知识库、思维链可视化、知识讲解、学习计划、练习出题
- 用 Streamlit 写的，纯 Python，不写 HTML
- 接收用户输入 → 转给后端 Agent → 显示 AI 回答

**关联**：调用 `backend/agents/react_agent.py` 的 ReActStudyAgent

---

### 第二组：大脑（AI 智能体）

#### `backend/agents/base_agent.py` —— 基础 Agent 类
**作用**：所有 Agent 的"爸爸"。
- 提供：连接 LLM、管对话历史、组装消息列表
- 儿子继承它就不用重复写这些

**关联**：被 `react_agent.py` 继承

#### `backend/agents/react_agent.py` —— ReAct Agent（核心大脑）
**作用**：整个项目最重要的文件。
- 实现 ReAct 循环：思考→调工具→看结果→再思考...
- 把工具绑给 LLM，让 LLM 自己决定调不调工具
- 每一步用 yield 输出事件，前端能实时显示

**关联**：
- 继承 `base_agent.py`
- 用 `react_tools.py` 的工具
- 输出 `react_models.py` 定义的事件

#### `backend/agents/react_models.py` —— 数据格式定义
**作用**：定义 ReAct 每一步的数据长什么样。
- ReActEvent（单个事件：思考/调工具/结果/最终回答）
- ReActResult（整轮对话的结果）

**关联**：被 `react_agent.py` 和 `app.py` 使用

#### `backend/agents/react_tools.py` —— 工具说明书 + 执行器
**作用**：两件事：
1. 定义"工具说明书"（Schema）—— 给 AI 看的 JSON
2. 定义"执行器"（Executor）—— AI 决定调了，实际执行

**关联**：
- 给 `react_agent.py` 提供工具
- 调用 `tools/` 目录里的实际工具函数

---

### 第三组：手（实际工具能力）

#### `backend/tools/knowledge.py` —— 概念讲解工具
**作用**：按"定义/类比/例子"模板讲解概念。
- 函数：`explain_concept()`、`break_down_concept()`、`compare_concepts()`

**关联**：被 `react_tools.py` 调用

#### `backend/tools/plan_generator.py` —— 学习计划工具
**作用**：生成分阶段学习计划。
- 函数：`generate_study_plan()`、`create_daily_schedule()`

**关联**：被 `react_tools.py` 调用

#### `backend/tools/question_generator.py` —— 出题工具
**作用**：生成练习题（含答案和解析）。
- 函数：`generate_questions()`、`check_answer()`

**关联**：被 `react_tools.py` 调用

---

### 第四组：基础设施（连接 AI + 知识库）

#### `backend/llm_helper.py` —— LLM 实例创建
**作用**：创建通义千问的连接。
- 函数：`get_llm()` 全局只创建一次（单例）
- 用 LangChain 的 ChatOpenAI 类调通义千问

**关联**：被所有需要调 AI 的地方使用（base_agent、tools/）

#### `backend/config.py` —— 配置读取
**作用**：从 .env 读 API Key、模型名等配置。
- 提供 `validate_config()`、`get_api_key()` 等函数

**关联**：被 `llm_helper.py` 和 `base_agent.py` 使用

---

### 第五组：资料室（知识库）

#### `backend/knowledge/knowledge_base_faiss.py` —— 知识库管理
**作用**：知识库的总入口。
- `add_pdf()` —— 添加 PDF
- `search()` —— 搜索相关内容

**关联**：组合下面三个文件

#### `backend/knowledge/pdf_loader.py` —— PDF 读取
**作用**：用 PyPDF2 提取 PDF 文字。
- 函数：`extract_text_from_pdf()`、`clean_text()`

**关联**：被 `knowledge_base_faiss.py` 调用

#### `backend/knowledge/embedding.py` —— 文字转向量
**作用**：把文字变成 768 维向量。
- 函数：`get_embeddings_batch()`、`text_split_by_token()`

**关联**：被 `knowledge_base_faiss.py` 调用

#### `backend/knowledge/vector_store_faiss.py` —— FAISS 向量存储
**作用**：用 FAISS 库存向量、搜向量。
- 类：FAISSVectorStore
- `add()` 添加、`search()` 搜索

**关联**：被 `knowledge_base_faiss.py` 调用

---

## 三、调用关系图（从用户操作到 AI 回答）

```
[用户在浏览器输入"什么是递归"]
        │
        ▼
┌─────────────────────────────────┐
│ frontend/app.py                  │
│ 接收输入，调 agent.react_stream() │
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│ backend/agents/react_agent.py    │
│ 循环开始：                       │
│ 1. 组装消息                      │
│ 2. 发给 LLM                      │
│ 3. LLM 说要调 explain_concept   │
└─────────────────────────────────┘
        │
        ├──────────────────────┐
        ▼                      ▼
┌─────────────────┐    ┌──────────────────────┐
│ llm_helper.py   │    │ react_tools.py       │
│ 提供 LLM 连接   │    │ 找到 explain_concept │
└─────────────────┘    │ 执行器               │
                       └──────────────────────┘
                               │
                               ▼
                       ┌──────────────────────┐
                       │ tools/knowledge.py   │
                       │ explain_concept()    │
                       │ 实际干活             │
                       └──────────────────────┘
                               │
                               ▼ （工具结果返回给 LLM）
┌─────────────────────────────────┐
│ backend/agents/react_agent.py    │
│ 把结果塞回消息 → 再问 LLM       │
│ LLM 觉得够了 → 返回最终回答     │
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│ frontend/app.py                  │
│ 显示最终回答给用户               │
└─────────────────────────────────┘
```

---

## 四、一次 PDF 上传的调用链

```
[用户上传 Python.pdf]
        │
        ▼
frontend/app.py → FAISSKnowledgeBase.add_pdf()
        │
        ▼
knowledge_base_faiss.py 协调三步：
        │
        ├─→ pdf_loader.py 提取文字
        │
        ├─→ embedding.py 切段 + 转向量
        │
        └─→ vector_store_faiss.py 存入 FAISS
```

---

## 五、一次 RAG 问答的调用链

```
[用户问"PDF 里讲了什么"]
        │
        ▼
react_agent.py → LLM 决定调 rag_search 工具
        │
        ▼
react_tools.py → _execute_rag_search()
        │
        ▼
agent._kb.search()  ← 这里的 _kb 是 FAISSKnowledgeBase
        │
        ▼
knowledge_base_faiss.py
        │
        ├─→ embedding.py 把问题转向量
        │
        └─→ vector_store_faiss.py 在 FAISS 里搜
        │
        ▼
返回 top 3 相关段落 → 塞回给 LLM → LLM 基于内容回答
```

---

## 六、文件关系一表速查

| 文件 | 是干什么的 | 调用了谁 | 被谁调用 |
|------|------------|----------|----------|
| `frontend/app.py` | 网站主页 | react_agent, knowledge_base_faiss | 用户 |
| `agents/base_agent.py` | Agent 基类 | llm_helper, config | react_agent |
| `agents/react_agent.py` | ReAct 大脑 | base_agent, react_tools, knowledge_base | app.py |
| `agents/react_models.py` | 数据模型 | - | react_agent, app.py |
| `agents/react_tools.py` | 工具分发 | tools/* | react_agent |
| `tools/knowledge.py` | 概念讲解 | llm_helper | react_tools |
| `tools/plan_generator.py` | 学习计划 | llm_helper | react_tools |
| `tools/question_generator.py` | 出题 | llm_helper | react_tools |
| `llm_helper.py` | LLM 连接 | config | 所有需要 AI 的地方 |
| `config.py` | 配置读取 | .env | llm_helper, base_agent |
| `knowledge/knowledge_base_faiss.py` | 知识库总管 | pdf_loader, embedding, vector_store | app.py, react_tools |
| `knowledge/pdf_loader.py` | PDF 提取 | PyPDF2 | knowledge_base_faiss |
| `knowledge/embedding.py` | 文字转向量 | sentence-transformers | knowledge_base_faiss |
| `knowledge/vector_store_faiss.py` | FAISS 存储 | faiss | knowledge_base_faiss |

---

## 七、最重要的一句话记忆法

**只要记住这五个东西的关系，整个项目就通了**：

```
app.py（门面）
  → react_agent.py（大脑，做 ReAct 循环）
      → react_tools.py（工具说明书 + 分发）
          → tools/knowledge.py 等（实际干活）
          → knowledge/* （RAG 知识库）
              → llm_helper.py（连 AI）
```

底层所有需要 AI 的地方都通过 `llm_helper.py` 连通义千问。

---

**就这些。看懂这五个组、五张图，今晚答辩稳了。**
