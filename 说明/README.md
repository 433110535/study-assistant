# 智能学习助手 (Study Assistant)

一个基于 LangChain + ReAct 的智能学习助手，能够回答课程问题、讲解知识点、生成学习计划，适合教育创新/AI应用赛道。

## 核心功能

- **ReAct 智能问答**: AI 自主决定是否调用工具，多步推理回答问题
- **概念讲解**: 用通俗易懂的语言讲解复杂概念
- **学习计划**: 根据学习目标和时间自动生成学习计划
- **习题生成**: 生成不同难度的练习题
- **RAG 知识库**: 上传PDF，基于个人资料回答（FAISS 向量检索）
- **思维链可视化**: 展示 AI 的完整推理过程
- **多轮对话**: 记住学习进度，支持上下文记忆

## 技术栈

| 类别 | 技术选型 | 说明 |
|------|---------|------|
| LLM | **通义千问 qwen-max** | 通过 DashScope OpenAI 兼容 API 调用 |
| Agent | **ReAct 循环** | Reason+Act，LLM 自主决定工具调用 |
| 向量检索 | **FAISS** | Facebook 开源向量搜索库 |
| 框架 | LangChain | 消息管理、Prompt 模板、工具绑定 |
| 前端 | Streamlit | Python Web 框架，快速搭建 |

## 快速开始

```bash
cd "E:\比赛项目\智能体"
streamlit run frontend/app.py
```

访问地址: http://localhost:8501

外网分享可使用 cpolar 内网穿透：
```bash
cpolar http 8501
```

## 项目结构

```
E:\比赛项目\智能体\
├── backend/
│   ├── agents/              # Agent 核心逻辑
│   │   ├── base_agent.py        # 基础 Agent（对话历史、消息格式化）
│   │   ├── react_agent.py       # ReAct 智能体（核心循环）
│   │   ├── react_models.py      # 数据模型（事件、步骤、结果）
│   │   └── react_tools.py       # 工具 Schema + 执行器
│   ├── tools/               # 具体工具实现
│   │   ├── knowledge.py         # 概念讲解
│   │   ├── plan_generator.py    # 学习计划生成
│   │   ├── question_generator.py # 习题生成
│   │   └── rag_tool.py          # RAG 检索
│   ├── knowledge/           # 知识库
│   │   ├── knowledge_base_faiss.py  # FAISS 向量知识库
│   │   ├── vector_store_faiss.py    # FAISS 向量存储
│   │   ├── embedding.py             # 文本转向量
│   │   └── pdf_loader.py            # PDF 文件读取
│   ├── llm_helper.py        # LLM 实例创建
│   └── config.py            # 配置管理（API Key 等）
├── frontend/
│   └── app.py               # Streamlit 主应用（所有页面）
├── PROJECT_EXPLAIN.md       # 项目详解（大白话版）
├── requirements.txt         # 依赖列表
├── start.bat                # Windows 一键启动
└── start.py                 # Python 启动脚本
```

## ReAct 工作原理

```
用户提问 → [系统提示 + 工具定义 + 对话历史] 发给 LLM
         → LLM 自己决定：直接回答 or 调用工具
         → 调工具 → 执行 → 结果塞回去 → 再问 LLM
         → 没调工具 → 就是最终回答
```

可用工具：
- `rag_search` - 知识库检索
- `explain_concept` - 概念讲解
- `generate_study_plan` - 学习计划
- `generate_questions` - 出题

## 比赛亮点

1. **ReAct 推理**: AI 自主判断是否调用工具，比关键词匹配更智能
2. **Function Calling**: 利用大模型的函数调用能力实现工具选择
3. **RAG 检索增强**: 基于 FAISS 向量检索，让 AI 回答有据可依
4. **思维链可视化**: 完整展示 AI 推理过程，可解释性强
5. **企业级 UI**: 专业简洁的界面设计

## 许可

MIT License
