# 智能学习助手 - 完整知识手册（从零开始）

> 本文档涵盖：项目介绍、技术栈、环境搭建、文件结构、每个代码文件详解、智能体搭建流程模板、核心概念讲解。面向零基础读者。

---

# 第一部分：项目介绍

## 1.1 这个项目是什么

一个 **AI 学习助手网站**，学生可以在上面：
- 和 AI 聊天，问学习问题
- 上传 PDF 学习资料，AI 帮你检索相关内容
- 让 AI 帮你制定学习计划、讲解概念、出练习题
- 看到 AI 的完整思考过程（思维链可视化）

## 1.2 和普通 ChatGPT 有什么区别

| 普通 ChatGPT | 本项目 |
|---|---|
| 直接回答 | 先思考→决定调工具→执行→再回答 |
| 没有知识库 | 有本地知识库（PDF上传） |
| 答案凭记忆 | RAG 检索让答案有依据 |
| 单一对话 | 多个功能页面 |
| 看不到推理 | 思维链全程可视化 |

---

# 第二部分：技术栈详解

## 2.1 用到的所有技术

### 编程语言
- **Python 3.12** — 整个项目都用 Python 写

### 大模型相关
- **通义千问 qwen-max** — 阿里云的大模型，通过 API 调用
- **DashScope** — 阿里云的 AI 平台，提供 OpenAI 兼容接口
- **LangChain** — LLM 应用开发框架（管理消息、Prompt、工具）

### 知识库相关
- **FAISS** — Facebook 开源的向量搜索库
- **sentence-transformers** — 文本转向量的模型库
- **shibing624/text2vec-base-chinese** — 中文文本向量模型

### 前端
- **Streamlit** — Python 的 Web 框架

### 其他
- **PyPDF2** — 读 PDF 文件
- **python-dotenv** — 读取 .env 配置文件
- **pydantic** — 数据模型定义和校验

## 2.2 每个技术为什么选它

| 技术 | 为什么选 |
|------|---------|
| 通义千问 | 国内访问稳定，免费额度够用，支持 function calling |
| LangChain | 行业标准，文档全，工具调用封装好 |
| FAISS | 免费离线，比 Pinecone 等云服务省事 |
| Streamlit | 不用写 HTML/CSS/JS，纯 Python 搭网站 |
| sentence-transformers | 免费，中文模型效果好，API 简单 |

## 2.3 关键概念解释

### 什么是 LLM（大语言模型）
就是 ChatGPT、通义千问这种 AI。输入文字，输出文字。本质是预测"下一个字应该是什么"。

### 什么是 API
应用程序接口。你的代码通过 HTTP 请求调通义千问的服务，发问题过去，它把回答发回来。

### 什么是 Token
AI 处理文字的最小单位。一个汉字大约 1-2 个 token。按 token 计费。

---

# 第三部分：环境搭建（从零开始）

## 3.1 准备工作

### 必须安装的软件
1. **Python 3.12+** — 去 python.org 下载
2. **VS Code** 或 PyCharm — 写代码的编辑器
3. **Git** — 版本管理（可选）

### 必须申请的账号
1. **阿里云账号** — 为了用通义千问
2. **DashScope API Key** — 去 https://dashscope.console.aliyun.com/ 申请

## 3.2 创建项目目录

```bash
mkdir 智能体
cd 智能体
```

## 3.3 创建虚拟环境

虚拟环境 = 一个独立的 Python 环境，装的包不会影响系统。

```bash
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate   # Mac/Linux
```

激活后命令行前面会有 `(venv)` 字样。

## 3.4 安装依赖

创建 `requirements.txt`：

```
streamlit>=1.30
langchain-core>=0.1
langchain-openai>=0.1
langchain-community>=0.1
python-dotenv
faiss-cpu
sentence-transformers
PyPDF2
pydantic
```

安装：
```bash
pip install -r requirements.txt
```

## 3.5 配置 API Key

创建 `.env` 文件：
```
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_PROVIDER=qwen
LLM_MODEL=qwen-max
```

**注意**：`.env` 文件不能上传到 GitHub，里面有密码。`.gitignore` 里要加上 `.env`。

## 3.6 目录结构

最终目录长这样：

```
智能体/
├── backend/                    后端代码
│   ├── __init__.py
│   ├── config.py               配置读取
│   ├── llm_helper.py           LLM 实例创建
│   ├── agents/                 AI 智能体
│   │   ├── __init__.py
│   │   ├── base_agent.py       基础 Agent
│   │   ├── react_agent.py      ReAct Agent（核心）
│   │   ├── react_models.py     数据模型
│   │   └── react_tools.py      工具定义
│   ├── tools/                  具体工具
│   │   ├── __init__.py
│   │   ├── knowledge.py        概念讲解
│   │   ├── plan_generator.py   学习计划
│   │   ├── question_generator.py 出题
│   │   └── rag_tool.py         知识库检索
│   └── knowledge/              知识库
│       ├── __init__.py
│       ├── embedding.py        文字转向量
│       ├── pdf_loader.py       PDF 读取
│       ├── vector_store_faiss.py FAISS 向量存储
│       └── knowledge_base_faiss.py 知识库管理
├── frontend/                   前端代码
│   └── app.py                  Streamlit 主应用
├── data/                       数据目录（运行时生成）
│   └── faiss_index/            FAISS 索引文件
├── .env                        API Key 配置
├── .env.example                配置示例
├── requirements.txt            依赖列表
├── start.bat                   Windows 启动脚本
└── README.md                   项目说明
```

---

# 第四部分：每个文件详解

## 4.1 `backend/config.py` — 配置管理

**作用**：读取 `.env` 文件，给其他文件提供 API Key 等配置。

```python
import os
from dotenv import load_dotenv

load_dotenv()  # 把 .env 文件里的变量加载到环境变量

def get_config():
    """获取配置"""
    return {
        "api_key": os.getenv("DASHSCOPE_API_KEY"),
        "model": os.getenv("LLM_MODEL", "qwen-max"),
    }

def validate_config():
    """校验配置是否完整"""
    config = get_config()
    if not config["api_key"]:
        return False, "请配置 DASHSCOPE_API_KEY"
    return True, "配置正常"
```

**为什么需要这个文件**：不让 API Key 硬编码在代码里，安全性好。

## 4.2 `backend/llm_helper.py` — LLM 创建

**作用**：创建 LLM 实例（连接通义千问的客户端）。整个项目共用一个。

```python
from langchain_openai import ChatOpenAI
from backend.config import get_config

_llm_instance = None

def get_llm(temperature=0.7):
    """获取 LLM 实例（单例模式）"""
    global _llm_instance
    if _llm_instance is None:
        config = get_config()
        _llm_instance = ChatOpenAI(
            model=config["model"],
            temperature=temperature,
            api_key=config["api_key"],
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
    return _llm_instance
```

**关键点**：
- **单例模式**：整个项目只创建一个 LLM 实例，节省资源
- **ChatOpenAI**：LangChain 的类，用来和 OpenAI 格式的 API 通信
- **base_url**：通义千问的 OpenAI 兼容接口地址

**为什么用 ChatOpenAI 调通义千问？** 因为通义千问提供了 OpenAI 兼容接口，API 格式一样，可以用同一个客户端库。

## 4.3 `backend/agents/base_agent.py` — Agent 基类

**作用**：所有 Agent 的"爸爸"，提供公共功能（连 LLM、管对话历史）。

```python
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from backend.llm_helper import get_llm

class BaseAgent:
    def __init__(self, verbose=False, **kwargs):
        self.llm = get_llm()              # 拿到 LLM 连接
        self.verbose = verbose             # 是否打印调试信息
        self.conversation_history = []     # 对话历史

    def get_system_prompt(self):
        """子类重写：返回系统提示词"""
        return "你是一个AI助手"

    def _build_messages(self, user_input):
        """组装消息列表发给 LLM"""
        messages = [SystemMessage(content=self.get_system_prompt())]
        messages.extend(self.conversation_history)
        messages.append(HumanMessage(content=user_input))
        return messages
```

**核心概念**：

### 系统提示词（System Prompt）
告诉 AI "你是谁、该怎么做"。比如"你叫 Jesse，是学习助手"。

### 消息类型
LangChain 用不同类区分消息：
- `SystemMessage` — 系统指令
- `HumanMessage` — 用户说的话
- `AIMessage` — AI 回复的话
- `ToolMessage` — 工具返回的结果

### 对话历史（Conversation History）
让 AI 记住之前聊了什么。每轮对话存到这里。

### 为什么写基类
不管是简单 Agent 还是 ReAct Agent，都需要"连 LLM"和"管历史"。写成基类，子类复用。

## 4.4 `backend/agents/react_models.py` — 数据模型

**作用**：定义 ReAct 循环中每一步的数据格式。

```python
from enum import Enum
from typing import Dict, Any, List
from pydantic import BaseModel

class ReActEventType(str, Enum):
    THINKING = "thinking"          # AI 在思考
    TOOL_CALL = "tool_call"        # AI 决定调工具
    TOOL_RESULT = "tool_result"    # 工具返回了结果
    FINAL_ANSWER = "final_answer"  # 最终回答
    ERROR = "error"                # 出错了

class ReActEvent(BaseModel):
    event_type: ReActEventType
    content: str = ""
    tool_name: str = ""
    tool_args: Dict[str, Any] = {}
    tool_result: str = ""
    iteration: int = 0

class ReActResult(BaseModel):
    user_input: str = ""
    final_answer: str = ""
    steps: List = []
    total_iterations: int = 0
    tools_used: List[str] = []
    success: bool = True
```

**为什么需要数据模型**：让前端知道"AI 现在在干什么"，按固定格式显示。

**什么是 Pydantic**：Python 数据校验库。比普通 class 多类型检查。

## 4.5 `backend/agents/react_tools.py` — 工具定义

**作用**：定义"AI 能用的工具说明书"和"工具的实际执行代码"。

### 第一部分：工具 Schema（给 AI 看的）

```python
def get_tool_schemas():
    return [
        {
            "type": "function",
            "function": {
                "name": "explain_concept",
                "description": "详细讲解一个学习概念，适合用户想理解某个知识点时使用",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "concept": {
                            "type": "string",
                            "description": "要讲解的概念名称"
                        },
                        "subject": {
                            "type": "string",
                            "description": "所属学科"
                        },
                        "level": {
                            "type": "string",
                            "description": "学习者水平：初学者/中级/高级",
                            "default": "初学者"
                        }
                    },
                    "required": ["concept"]
                }
            }
        },
        # ... 其他3个工具类似
    ]
```

**关键点**：
- AI 靠 `description` 判断什么时候用这个工具
- `parameters` 告诉 AI 这个工具需要什么参数
- 这是 OpenAI Function Calling 的标准格式

### 第二部分：工具执行器

```python
TOOL_EXECUTORS = {
    "rag_search": _execute_rag_search,
    "explain_concept": _execute_explain_concept,
    "generate_study_plan": _execute_study_plan,
    "generate_questions": _execute_questions,
}

def _execute_explain_concept(agent, concept, subject="", level="初学者"):
    """执行 explain_concept 工具"""
    from backend.tools.knowledge import explain_concept
    return explain_concept(concept, subject=subject, level=level, llm=agent.llm)

def execute_tool(agent, tool_name, tool_args):
    """根据工具名找到函数并执行"""
    executor = TOOL_EXECUTORS.get(tool_name)
    if not executor:
        return f"未知工具: {tool_name}"
    return executor(agent, **tool_args)
```

**为什么分两部分**：
- Schema 是给 AI 看的（JSON），AI 根据描述决定要不要调
- 执行器是你写的 Python 函数，AI 决定调了之后真正执行

## 4.6 `backend/agents/react_agent.py` — ReAct 核心（最重要！）

**作用**：ReAct 循环。整个系统的大脑。

```python
from backend.agents.base_agent import BaseAgent
from backend.agents.react_tools import get_tool_schemas, execute_tool
from backend.agents.react_models import ReActEvent, ReActEventType
from langchain_core.messages import ToolMessage

REACT_SYSTEM_PROMPT = """你叫 Jesse，是一个智能学习助手。
你可以使用工具来更好地帮助用户。根据用户的问题，判断是否需要调用工具。
不需要工具时直接回答即可。"""

class ReActStudyAgent(BaseAgent):
    def __init__(self, max_iterations=5, **kwargs):
        super().__init__(**kwargs)

        # ★ 把工具绑定到 LLM
        self.tool_schemas = get_tool_schemas()
        self.llm_with_tools = self.llm.bind_tools(self.tool_schemas)
        # bind_tools 的作用：每次调 LLM 时自动把工具定义塞进请求

        self._kb = None  # 知识库（后面初始化）

    def get_system_prompt(self):
        return REACT_SYSTEM_PROMPT

    def react_stream(self, user_input):
        """
        ★★★ ReAct 核心循环 ★★★

        流程：
        1. 组装消息
        2. 发给 LLM
        3. LLM 调工具了吗？
           - 没 → 最终回答，结束
           - 调了 → 执行工具 → 结果塞回去 → 回到2
        4. 最多循环 max_iterations 次
        """
        messages = self._build_messages(user_input)

        for iteration in range(1, self.max_iterations + 1):

            # ① 报告：AI 在思考
            yield ReActEvent(
                event_type=ReActEventType.THINKING,
                content="Jesse正在思考...",
                iteration=iteration
            )

            # ② 发给 LLM，让它决定
            response = self.llm_with_tools.invoke(messages)
            messages.append(response)

            # ③ 检查：调工具了吗？
            if not response.tool_calls:
                # 没调 → 直接给了回答
                yield ReActEvent(
                    event_type=ReActEventType.FINAL_ANSWER,
                    content=response.content
                )
                return

            # ④ 调了工具，逐个执行
            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]

                yield ReActEvent(
                    event_type=ReActEventType.TOOL_CALL,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    iteration=iteration
                )

                # 执行工具
                result = execute_tool(self, tool_name, tool_args)

                yield ReActEvent(
                    event_type=ReActEventType.TOOL_RESULT,
                    tool_name=tool_name,
                    tool_result=result,
                    content=result[:200],
                    iteration=iteration
                )

                # 把工具结果塞回消息列表
                messages.append(ToolMessage(
                    content=result,
                    tool_call_id=tc.get("id", "")
                ))

            # ⑤ 回到循环开头，把更新后的消息再发给 LLM

        # 超过最大轮次，强制回答
        response = self.llm.invoke(messages)
        yield ReActEvent(
            event_type=ReActEventType.FINAL_ANSWER,
            content=response.content
        )
```

**几个关键概念**：

### bind_tools 做了什么
把工具定义绑到 LLM 实例。之后每次 invoke，工具定义自动跟着一起发给 AI。

### response.tool_calls
AI 的回答里如果调了工具，这个字段就是 `[{name, args, id}]`。没调就是空列表。

### ToolMessage
工具执行完，结果要用 `ToolMessage` 包一下塞回消息列表，LLM 才知道"这是之前那个工具的结果"。`tool_call_id` 用来和之前的工具调用对应。

### yield 是什么
Python 生成器语法。每次 yield 一个事件，前端立即收到并显示。不用等整个过程跑完。

### max_iterations = 5
最多循环 5 次。简单问题 0-1 次，复杂问题 2-3 次，超过 5 次基本说明 AI 在反复犹豫。

## 4.7 `backend/tools/knowledge.py` — 概念讲解工具

**作用**：讲解概念。本质是一个带模板的 Prompt。

```python
from langchain_core.prompts import ChatPromptTemplate
from backend.llm_helper import get_llm

def explain_concept(concept, subject="", level="初学者", use_examples=True, llm=None):
    """讲解一个概念"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一位擅长讲解概念的导师。
请按以下格式输出：
## 概念定义
## 核心要点
## 生活类比
## 举例说明
## 总结
"""),
        ("human", "请帮我讲解：{concept}\n学科：{subject}\n水平：{level}")
    ])

    _llm = llm or get_llm()
    chain = prompt | _llm  # LangChain 管道

    response = chain.invoke({
        "concept": concept,
        "subject": subject or "通用",
        "level": level
    })
    return response.content
```

**为什么用 PromptTemplate**：每次调用只是概念名不同，模板一样。用模板可以复用。

**`prompt | _llm` 是什么**：LangChain 管道操作符。左边输出接到右边输入。

**`llm=None` 参数干嘛的**：ReAct Agent 会把自己的 LLM 实例传进来（`llm=agent.llm`），复用连接。

## 4.8 `backend/tools/plan_generator.py` — 学习计划工具

和 knowledge.py 一样的模式，只是 Prompt 模板不同（生成分阶段计划）。不展开。

## 4.9 `backend/tools/question_generator.py` — 出题工具

同上，Prompt 模板生成题目+答案+解析。

## 4.10 `backend/tools/rag_tool.py` — 知识库检索工具

**作用**：从知识库搜相关内容（不调 LLM，直接查数据库）。

```python
def rag_search(query, knowledge_base, top_k=3):
    """从知识库检索"""
    if not knowledge_base:
        return "知识库未初始化"

    results = knowledge_base.search(query, top_k=top_k)

    if not results:
        return "未找到相关内容"

    output = ""
    for i, doc in enumerate(results, 1):
        output += f"\n--- 相关内容 {i} ---\n"
        output += doc["content"] + "\n"
    return output
```

**和其他工具的区别**：这个不调 LLM，直接查 FAISS 向量库。

**top_k 是什么**：返回最相似的前 K 条结果。top_k=3 就是返回 3 条最相关的。

## 4.11 `backend/knowledge/embedding.py` — 文字转向量

**作用**：把文字变成向量（一串数字），用于相似度搜索。

```python
from sentence_transformers import SentenceTransformer

_model = None

def get_embedding_model():
    """加载向量模型（全局只一次）"""
    global _model
    if _model is None:
        _model = SentenceTransformer("shibing624/text2vec-base-chinese")
    return _model

def get_embeddings_batch(texts):
    """把一批文字转成向量"""
    model = get_embedding_model()
    return model.encode(texts)

def text_split_by_token(text, chunk_size=500):
    """把长文本切成小段"""
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunks.append(text[i:i+chunk_size])
    return chunks
```

**文字是怎么变成向量的（具体过程）**：

以 `"什么是递归"` 为例：

**第1步：分词**
```
"什么是递归" → ["什么", "是", "递归"]
```

模型词典里每个词有编号：`"递归" → 2391`

**第2步：查词嵌入表**
模型内部有一个 768 列的大表，每个编号对应一行 768 个数字：
```
"什么" → [0.12, -0.34, 0.56, ..., 0.78]  768个数字
"是"   → [0.03, 0.91, -0.22, ..., 0.15]  768个数字
"递归" → [-0.45, 0.67, 0.33, ..., -0.89] 768个数字
```

这行数字是模型**训练阶段**学出来的。

**第3步：Transformer 编码**
让每个词去看其他词（自注意力机制），加上下文信息：
```
"什么" 看到 "递归" → 知道在问概念
"递归" 看到 "什么" → 知道自己被询问
```

经过 6-12 层处理，每个词向量从"孤立词义"变成"带上下文的词义"。

**第4步：池化**
3 个 768 维向量取平均，合成 1 个 768 维向量。这就是最终结果。

**为什么是 768 维**：模型设计决定的。维度越高越精确，计算越慢。768 是中文模型的常用值。

## 4.12 `backend/knowledge/pdf_loader.py` — PDF 读取

```python
from PyPDF2 import PdfReader

def extract_text_from_pdf(file_path):
    """从 PDF 提取文字"""
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

def clean_text(text):
    """清理文本"""
    import re
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
```

## 4.13 `backend/knowledge/vector_store_faiss.py` — FAISS 向量存储

**作用**：用 FAISS 存向量，提供搜索功能。

```python
import faiss
import numpy as np

class FAISSVectorStore:
    def __init__(self, dimension=768):
        self.index = faiss.IndexFlatIP(dimension)
        # IndexFlatIP = 内积相似度
        self.texts = []

    def add(self, texts, embeddings):
        """添加文本和向量"""
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized = embeddings / norms  # 归一化
        self.index.add(normalized.astype('float32'))
        self.texts.extend(texts)

    def search(self, query_embedding, top_k=3):
        """搜索最相似的 top_k 条"""
        query = query_embedding / np.linalg.norm(query_embedding)
        scores, indices = self.index.search(
            query.reshape(1, -1).astype('float32'), top_k
        )
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0:
                results.append({
                    "content": self.texts[idx],
                    "score": float(score)
                })
        return results
```

**什么是 FAISS**：Facebook 开源的向量搜索库。给一个向量，能在百万级数据里秒搜最相似的。

**为什么要归一化**：归一化后内积等价于余弦相似度，值在 -1 到 1 之间，1 表示完全一样。

## 4.14 `backend/knowledge/knowledge_base_faiss.py` — 知识库管理

**作用**：把上面三个模块（embedding、pdf_loader、vector_store）串起来。

```python
class FAISSKnowledgeBase:
    def __init__(self):
        self.vector_store = FAISSVectorStore()
        self.documents = {}

    def add_pdf(self, file_path, subject="未分类"):
        # 1. 读 PDF
        text = extract_text_from_pdf(file_path)
        text = clean_text(text)

        # 2. 切段
        chunks = text_split_by_token(text, chunk_size=500)

        # 3. 转向量
        embeddings = get_embeddings_batch(chunks)

        # 4. 存入 FAISS
        self.vector_store.add(chunks, embeddings)

        # 5. 记录信息
        self.documents[file_path] = {
            "subject": subject,
            "chunks": len(chunks)
        }

    def search(self, query, top_k=3):
        # 1. 问题转向量
        query_embedding = get_embeddings_batch([query])[0]
        # 2. 在 FAISS 里搜
        return self.vector_store.search(query_embedding, top_k)
```

**知识库完整流程**：
```
PDF → 提取文字 → 切段 → 每段转向量 → 存 FAISS
提问 → 问题转向量 → 在 FAISS 里找最近的 → 返回相关段落
```

## 4.15 `frontend/app.py` — 前端主应用

**最大的文件**，所有页面都在这里。核心结构：

```python
import streamlit as st
from backend.agents.react_agent import ReActStudyAgent
from backend.agents.react_models import ReActEventType

# 页面配置
st.set_page_config(page_title="智能学习助手", layout="wide")

# 初始化
def init_session_state():
    """Streamlit 每次交互都重跑整个脚本，状态要存 session_state"""
    if "agent" not in st.session_state:
        st.session_state.agent = ReActStudyAgent(verbose=False)
    if "messages" not in st.session_state:
        st.session_state.messages = []

init_session_state()

# 侧边栏导航
page = st.sidebar.selectbox("选择功能", [
    "在线问答", "知识库", "思维链可视化", "知识讲解", "学习计划", "练习出题"
])

# 页面路由
if page == "在线问答":
    render_qa()
elif page == "知识库":
    render_kb()
# ...
```

### render_qa() 在线问答页面

```python
def render_qa():
    st.title("在线问答")

    # 显示历史对话
    for msg in st.session_state.messages:
        # ...

    # 输入框
    with st.form("chat_form"):
        user_input = st.text_input("输入问题")
        submitted = st.form_submit_button("发送")

        if submitted and user_input:
            # ★ 调用 ReAct 循环
            for event in st.session_state.agent.react_stream(user_input):
                if event.event_type == ReActEventType.THINKING:
                    st.info(f"思考中: {event.content}")
                elif event.event_type == ReActEventType.TOOL_CALL:
                    st.info(f"调用工具: {event.tool_name}")
                elif event.event_type == ReActEventType.FINAL_ANSWER:
                    st.session_state.messages.append(
                        {"role": "assistant", "content": event.content}
                    )
                    st.markdown(event.content)

            st.rerun()
```

**关键概念**：

### st.session_state
Streamlit 每次用户点击按钮，整个脚本都重跑一遍。变量要存到 `session_state` 才不丢。

### st.form
表单组件。用户输入文字后点"发送"才触发，不会每敲一个字就刷新。

### st.rerun()
手动触发页面刷新。

## 4.16 启动脚本

### start.bat
```bat
@echo off
chcp 65001 >nul
title 智能学习助手
streamlit run frontend/app.py
pause
```

双击启动。`chcp 65001` 是设置控制台编码为 UTF-8，防止中文乱码。

### start_online.bat
```bat
@echo off
chcp 65001 >nul
cpolar http 8501
pause
```

双击启动内网穿透（需要先装 cpolar）。

---

# 第五部分：智能体搭建流程模板

## 5.1 通用搭建流程（适用于任何 ReAct Agent）

```
Step 1: 明确需求
    → 我的 Agent 要解决什么问题？
    → 需要哪些能力（工具）？

Step 2: 准备 LLM
    → 选模型（通义千问/GPT/Claude）
    → 申请 API Key
    → 写 llm_helper.py

Step 3: 写基类
    → 继承 BaseAgent
    → 实现对话历史管理
    → 定义系统提示词

Step 4: 写工具
    → 每个工具一个 Prompt 模板
    → 每个工具有明确的输入输出
    → 工具要能独立测试

Step 5: 写工具 Schema
    → JSON 格式描述工具
    → description 要写清楚什么时候用
    → parameters 要列出参数和类型

Step 6: 写 ReAct 循环
    → 绑定工具
    → 实现循环逻辑
    → 设置 max_iterations
    → 用 yield 流式输出

Step 7: 接前端
    → 调 react_stream
    → 根据事件类型显示不同 UI

Step 8: 加知识库（可选）
    → 写 embedding/pdf_loader/vector_store
    → 把知识库注入 Agent
    → 写 rag_search 工具

Step 9: 测试和优化
    → 测试各种问题
    → 调整系统提示词
    → 调整工具描述
```

## 5.2 决策模板：什么时候用什么

| 需求 | 用什么 |
|------|--------|
| 简单问答 | 直接调 LLM，不用工具 |
| 需要查资料 | 加 RAG 工具 |
| 需要多步推理 | 用 ReAct 循环 |
| 需要结构化输出 | 用 PromptTemplate |
| 需要记忆 | 加 conversation_history |
| 需要外部 API | 写新工具，包成 function |

## 5.3 系统提示词模板

```
你叫 [名字]，是一个 [角色]。

你可以使用以下工具来帮助用户：
- [工具1]：[什么时候用]
- [工具2]：[什么时候用]

工作原则：
1. 根据用户问题判断是否需要工具
2. 不需要工具时直接回答
3. 需要工具时调用合适的工具
4. 工具返回结果后，整理成用户友好的回答

回答风格：
- [具体要求]
```

---

# 第六部分：核心概念深度讲解

## 6.1 ReAct 是什么

ReAct = **Re**asoning（推理）+ **Act**ing（行动）

让 AI "边想边做"：

```
第1步（思考）：用户问"列表推导式是什么"
              → AI 想：这是概念讲解需求，应该用 explain_concept 工具

第2步（行动）：调用 explain_concept(concept="列表推导式")

第3步（观察）：工具返回详细讲解

第4步（判断）：AI 看了内容，觉得够了
              → 整理成最终回答
```

**和传统方法区别**：
- 传统：代码里写死规则（看到"解释"两个字就调工具）
- ReAct：AI 自己根据语义判断

## 6.2 Function Calling 是什么

大模型自带的"函数调用"能力。

具体做法：
1. 把工具定义（名字、描述、参数）用 JSON 格式发给大模型
2. 大模型看到问题后，有两种选择：
   - 不需要工具 → 直接返回文字
   - 需要工具 → 返回 `tool_calls: [{name, args}]`
3. 你执行工具，把结果再发给大模型
4. 大模型看到结果后再决定

```python
# 把工具定义绑到 LLM
self.llm_with_tools = self.llm.bind_tools(self.tool_schemas)

# 问大模型
response = self.llm_with_tools.invoke(messages)

# 看大模型有没有调工具
if response.tool_calls:
    # 调了
else:
    # 没调，直接回答了
```

## 6.3 RAG 是什么

RAG = Retrieval-Augmented Generation（检索增强生成）

**先搜后答**：先从知识库找相关内容，再让 AI 基于这些内容回答。

```
用户上传 PDF
    ↓
PDF 切段 → 每段转向量 → 存 FAISS

用户提问
    ↓
问题转向量
    ↓
FAISS 找最相似的段落
    ↓
找到的内容 + 问题 一起发给 AI
    ↓
AI 基于找到的内容回答（不凭空编造）
```

**为什么用 RAG**：
- AI 的知识有截止日期，最新信息不知道
- 你自己的资料 AI 当然不知道
- RAG 让 AI 临时"读"你的资料再回答

## 6.4 Embedding（向量嵌入）

把文字变成一串数字，意思相近的文字数字也相近。

```
"递归"        → [0.12, -0.34, ..., 0.78]  ← 768 个数字
"函数调用自己" → [0.11, -0.32, ..., 0.75]  ← 数字很接近
"红烧肉"      → [-0.89, 0.45, ..., -0.12] ← 数字差很远
```

**怎么算相似度**：余弦相似度。两个向量求夹角余弦，值在 -1 到 1 之间，越接近 1 越相似。

## 6.5 FAISS 工作原理

FAISS = Facebook AI Similarity Search

**暴力搜索**：新向量跟库里每个向量都算一遍相似度，排序取前 K。慢。

**FAISS 优化**：
- 把向量分桶（聚类）
- 搜索时只搜最相关的几个桶
- 用 SIMD 指令并行计算

**IndexFlatIP** 是最简单的索引类型，精确搜索（内积相似度）。

## 6.6 LangChain 是什么

一个 Python 框架，简化 LLM 应用开发。

提供：
- **消息类型**（SystemMessage/HumanMessage/AIMessage/ToolMessage）
- **PromptTemplate**（Prompt 模板）
- **ChatOpenAI**（连 OpenAI 兼容 API 的客户端）
- **bind_tools**（绑定工具）
- **管道操作符 `|`**（串接组件）

**不用 LangChain 行不行**：行，但你要自己写消息管理、API 调用、工具定义等，麻烦。

## 6.7 Harness Engineering

把裸模型包装成可用 Agent 的"外壳工程"。

| Harness 包含什么 | 你项目里对应 |
|---|---|
| 工具定义和约束 | react_tools.py 的 schema |
| Agent 行为控制 | react_agent.py 的循环 + max_iterations |
| 跨会话状态管理 | conversation_history |
| 错误处理 | try/except + 错误事件 |
| 把模型包装成 Agent | 整个 backend/agents/ |

裸 qwen-max 只是聊天模型。你加了工具、循环、知识库、状态管理 —— 这些"包装"就是 harness。

---

# 第七部分：常见问题

## Q1: 为什么用 Streamlit 不用 React/Vue？
Streamlit 是 Python 框架，不用写 HTML/CSS/JS。后端也是 Python，一个人能搞定全栈。适合比赛 Demo。

## Q2: 为什么用通义千问不用 GPT？
- 国内访问稳定
- 免费额度够用
- 支持 function calling
- 中文效果好

## Q3: 为什么用 FAISS 不用 Pinecone？
- FAISS 免费，本地跑
- Pinecone 是云服务，要付费
- FAISS 性能足够好

## Q4: max_iterations 为什么是 5？
经验值。简单问题 0-1 次，复杂问题 2-3 次，5 是余量保护，防止无限循环。

## Q5: 为什么用 sentence-transformers？
- 免费离线
- 有中文专用模型
- API 简单

## Q6: ReAct 比直接对话好在哪？
- AI 自己判断要不要用工具，比写死规则灵活
- 支持多步推理（先查→再分析→再回答）
- 工具调用过程可见，可解释性强

## Q7: 知识库为什么要切段？
- 向量搜索按"段"匹配，太长了匹配不准
- AI 上下文有限，太长塞不下
- 500 字一段是经验值

## Q8: 项目怎么扩展？
- 加新工具：在 tools/ 加 Python 函数 + react_tools.py 加 schema
- 加新页面：在 app.py 加 render_xxx 函数
- 换模型：改 .env 的 LLM_MODEL
- 加缓存：用 @st.cache_resource 装饰器

---

# 第八部分：项目运行

## 8.1 启动

```bash
cd E:\比赛项目\智能体
streamlit run frontend/app.py
```

或双击 `start.bat`。

## 8.2 访问

浏览器打开 http://localhost:8501

## 8.3 外网访问

```bash
cpolar http 8501
```

或双击 `start_online.bat`。

## 8.4 停止

在命令行窗口按 `Ctrl+C`。

---

# 第九部分：面试/答辩可能问的问题

## Q: 你们的 Agent 怎么实现工具调用的？
A: 通过 OpenAI 兼容的 Function Calling 机制。用 LangChain 的 `bind_tools` 把工具定义绑到 LLM，LLM 自己决定是否调用。调用后用 `execute_tool` 执行，结果用 `ToolMessage` 塞回消息列表。

## Q: RAG 检索的原理？
A: 用户上传 PDF 后，文本被切段，每段用 sentence-transformers 转成 768 维向量，存入 FAISS。提问时，问题也转向量，用余弦相似度在 FAISS 里找最接近的段落，作为上下文发给 LLM。

## Q: 为什么用 ReAct 不用 LangChain 自带的 AgentExecutor？
A: 自己写 ReAct 循环可以完全控制流程，方便加日志、流式输出、自定义错误处理，更适合做思维链可视化。

## Q: 你们用 Harness Engineering 了吗？
A: 用了。我们把通义千问模型包装成了学习助手 Agent，外面加了工具调用框架、ReAct 循环、知识库管道、对话历史、错误处理等"外壳"，这就是 Harness Engineering。

## Q: 项目最大的技术难点？
A: ReAct 循环的实现。要正确处理消息类型（SystemMessage/HumanMessage/AIMessage/ToolMessage），保证 LLM 能正确理解工具调用上下文。还要设计合理的 max_iterations 和系统提示词，避免 AI 无限循环。

## Q: 怎么保证 AI 回答准确？
A: 三层保障：
1. RAG 让回答基于知识库内容，减少编造
2. 工具用结构化 Prompt 模板，输出规范
3. 系统提示词约束 AI 的回答风格

---

# 附录：核心文件清单

| 文件 | 作用 | 重要程度 |
|------|------|---------|
| `backend/agents/react_agent.py` | ReAct 核心循环 | ★★★★★ |
| `backend/agents/react_tools.py` | 工具定义和执行 | ★★★★★ |
| `backend/agents/base_agent.py` | Agent 基类 | ★★★★ |
| `backend/tools/*.py` | 4 个具体工具 | ★★★★ |
| `backend/knowledge/*.py` | 知识库（RAG） | ★★★★ |
| `frontend/app.py` | 前端界面 | ★★★★ |
| `backend/llm_helper.py` | LLM 实例 | ★★★ |
| `backend/config.py` | 配置管理 | ★★ |
| `backend/agents/react_models.py` | 数据模型 | ★★★ |
| `start.bat` | 启动脚本 | ★ |

---

**文档结束**

有问题翻这份文档，基本上项目相关的都能找到答案。
