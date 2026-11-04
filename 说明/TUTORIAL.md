# 从零开始写这个智能体 - 保姆级教程

---

## 第零步：理解整体思路

你要做一个网站，用户在上面提问，AI 来回答。

但 AI 不是直接回答，而是**先判断要不要查资料/调工具，再回答**。

这就需要几层东西：

```
用户看到的界面（前端）
    ↓ 把用户问题传下去
AI 的大脑（智能体 Agent）
    ↓ 判断要不要用工具
工具箱（Tools）
    ↓ 工具可能要查资料
知识库（Knowledge Base）
    ↓ 底层需要调 AI 模型
大模型 API（通义千问 qwen-max）
```

**建造顺序**：从下往上建。先把最底层的搞通，再一层层往上加。

---

## 第一步：建文件夹 + 装依赖

### 1.1 建文件夹结构

```
智能体/
├── backend/          ← 后端代码放这里
│   ├── agents/      ← AI 大脑
│   ├── tools/       ← 工具箱
│   └── knowledge/   ← 知识库
├── frontend/         ← 前端代码放这里
└── .env              ← 存密码（API Key）
```

### 1.2 创建 Python 虚拟环境（可选）

```bash
cd E:\比赛项目\智能体
python -m venv venv
venv\Scripts\activate
```

### 1.3 安装依赖

创建 `requirements.txt`：

```
streamlit
langchain-core
langchain-openai
langchain-community
python-dotenv
faiss-cpu
sentence-transformers
PyPDF2
```

安装：
```bash
pip install -r requirements.txt
```

**每个包干嘛的**：
- `streamlit`：做网页界面的
- `langchain-core`：管理 AI 对话消息、Prompt 模板
- `langchain-openai`：用 OpenAI 格式调大模型（通义千问兼容这个格式）
- `python-dotenv`：读取 .env 文件里的密码
- `faiss-cpu`：Facebook 的向量搜索库（知识库检索用的）
- `sentence-transformers`：把文字转成向量
- `PyPDF2`：读 PDF 文件

---

## 第二步：配置 API Key

### 2.1 创建 `.env` 文件

```
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_PROVIDER=qwen
LLM_MODEL=qwen-max
```

这是你的通义千问 API 密钥，去 https://dashscope.console.aliyun.com/ 申请。

### 2.2 创建 `backend/config.py` — 读取配置

```python
import os
from dotenv import load_dotenv

load_dotenv()  # 加载 .env 文件

def get_config():
    return {
        "api_key": os.getenv("DASHSCOPE_API_KEY"),
        "model": os.getenv("LLM_MODEL", "qwen-max"),
    }

def validate_config():
    config = get_config()
    if not config["api_key"]:
        return False, "请配置 DASHSCOPE_API_KEY"
    return True, "配置正常"
```

**作用**：别的文件要 API Key 的时候，不用自己读 .env，调 `get_config()` 就行。

---

## 第三步：写 LLM 辅助模块

### 3.1 创建 `backend/llm_helper.py` — 创建 AI 实例

```python
from langchain_openai import ChatOpenAI
from backend.config import get_config

def get_llm(temperature=0.7):
    """创建一个 LLM 实例（就是连接通义千问的客户端）"""
    config = get_config()
    return ChatOpenAI(
        model=config["model"],           # 用哪个模型
        temperature=temperature,         # 0=严谨，1=有创意
        api_key=config["api_key"],       # 密钥
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        # ↑ 通义千问的 OpenAI 兼容接口地址
    )
```

**作用**：整个项目只有一个地方创建 LLM 连接，别的文件调 `get_llm()` 就能拿到一个能跟 AI 通信的对象。

**为什么用 ChatOpenAI？** 因为通义千问提供了 OpenAI 兼容接口，可以用 OpenAI 的客户端库来调通义千问，不用学新的 SDK。

---

## 第四步：写基础 Agent

### 4.1 创建 `backend/agents/base_agent.py` — 所有 Agent 的"爸爸"

```python
from langchain_core.messages import SystemMessage, HumanMessage
from backend.llm_helper import get_llm

class BaseAgent:
    def __init__(self, verbose=False, **kwargs):
        self.llm = get_llm()         # 拿到 LLM 连接
        self.verbose = verbose        # 是否打印调试信息
        self.conversation_history = []  # 对话历史

    def get_system_prompt(self):
        """子类要重写这个方法，返回系统提示词"""
        return "你是一个AI助手"

    def _build_messages(self, user_input):
        """把对话历史 + 用户输入组装成消息列表发给 LLM"""
        messages = [SystemMessage(content=self.get_system_prompt())]
        # ↑ 系统提示词：告诉 AI 它是谁、该怎么做

        messages.extend(self.conversation_history)
        # ↑ 之前的对话记录（让 AI 记住上下文）

        messages.append(HumanMessage(content=user_input))
        # ↑ 用户的新问题

        return messages
```

**什么是系统提示词？**
就是告诉 AI "你是谁、你的角色是什么"。比如"你叫 Jesse，是一个学习助手"。

**什么是 conversation_history？**
AI 需要记住之前聊了什么，才能有连贯的对话。每轮对话都存到这里。

**什么是 HumanMessage/SystemMessage？**
LangChain 用不同的类来区分消息类型：
- `SystemMessage`：系统指令（AI 的角色设定）
- `HumanMessage`：用户说的话
- `AIMessage`：AI 回复的话

**为什么要写"基类"？**
因为不管是简单 Agent 还是 ReAct Agent，都需要"连 LLM"和"管理对话历史"这些功能。写成基类，子类就不用重复写了。

---

## 第五步：写工具（Tools）

工具就是 AI 可以调用的 Python 函数。每个工具本质上就是**一个固定的 Prompt 模板**，让 AI 按特定格式输出。

### 5.1 创建 `backend/tools/knowledge.py` — 概念讲解工具

```python
from langchain_core.prompts import ChatPromptTemplate
from backend.llm_helper import get_llm

def explain_concept(concept, subject="", level="初学者", llm=None):
    """讲解一个概念"""

    # 这是一个 Prompt 模板，有两个占位符 {concept} 和 {subject}
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

    # 拿到 LLM 实例
    _llm = llm or get_llm()

    # 把 Prompt 模板和 LLM 串成一条链
    chain = prompt | _llm
    # ↑ 这是 LangChain 的管道语法，相当于：先填模板，再发给 AI

    # 执行：把 concept/subject/level 填入模板，发给 AI，拿回结果
    response = chain.invoke({
        "concept": concept,
        "subject": subject or "通用",
        "level": level
    })

    return response.content  # 返回 AI 的文字回答
```

**为什么用 `ChatPromptTemplate`？**
因为每次调用这个工具，只是概念名不同，模板是一样的。用模板可以复用。

**`prompt | _llm` 是什么意思？**
这是 LangChain 的管道操作符。`|` 左边是输入处理，右边是输出处理。相当于把模板的输出直接接给 LLM。

**`llm=None` 参数干嘛的？**
ReAct Agent 会把自己的 LLM 实例传进来（`llm=agent.llm`），这样工具和 Agent 用同一个 AI 连接。如果没传，就自己创建一个。

### 5.2 创建 `backend/tools/plan_generator.py` — 学习计划工具

```python
from langchain_core.prompts import ChatPromptTemplate
from backend.llm_helper import get_llm

def generate_study_plan(subject, goal, duration_weeks=4, llm=None):
    """生成学习计划"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是学习规划师。请生成分阶段学习计划。
输出格式：
## 第一阶段：xxx（第1-2周）
- 目标：...
- 学习内容：...
- 练习任务：...

## 第二阶段：xxx（第3-4周）
...
"""),
        ("human", "学科：{subject}\n目标：{goal}\n时长：{duration}周")
    ])

    _llm = llm or get_llm()
    chain = prompt | _llm

    response = chain.invoke({
        "subject": subject,
        "goal": goal,
        "duration": duration_weeks
    })
    return response.content
```

**和 5.1 一样的模式**：定义模板 → 创建链 → 调用 → 返回结果。只是模板内容不同。

### 5.3 创建 `backend/tools/question_generator.py` — 出题工具

```python
from langchain_core.prompts import ChatPromptTemplate
from backend.llm_helper import get_llm

def generate_questions(topic, difficulty="中等", count=3, llm=None):
    """生成练习题"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是出题专家。请生成 {count} 道题目。
每道题格式：
### 题目 X（{difficulty}难度）
**题目：** ...
**A.** ...
**B.** ...
**C.** ...
**D.** ...
**正确答案：** ...
**解析：** ...
"""),
        ("human", "主题：{topic}\n难度：{difficulty}\n数量：{count}")
    ])

    _llm = llm or get_llm()
    chain = prompt | _llm

    response = chain.invoke({
        "topic": topic,
        "difficulty": difficulty,
        "count": count
    })
    return response.content
```

### 5.4 创建 `backend/tools/rag_tool.py` — 知识库检索工具

这个和其他工具不同，它不是让 AI 生成内容，而是**从知识库里搜相关内容**。

```python
from backend.llm_helper import get_llm

def rag_search(query, knowledge_base, top_k=3):
    """从知识库检索相关内容"""
    if not knowledge_base:
        return "知识库未初始化"

    # 在 FAISS 向量库里搜索
    results = knowledge_base.search(query, top_k=top_k)

    if not results:
        return "未找到相关内容"

    # 把搜索结果拼成一段文字返回
    output = ""
    for i, doc in enumerate(results, 1):
        output += f"\n--- 相关内容 {i} ---\n"
        output += doc["content"] + "\n"

    return output
```

**和其他工具的区别**：这个不调 LLM，而是直接查数据库。

---

## 第六步：写 ReAct 数据模型

### 6.1 创建 `backend/agents/react_models.py`

```python
from enum import Enum
from typing import Dict, Any, List
from pydantic import BaseModel

# 事件类型枚举：AI 的每一步都属于其中一种
class ReActEventType(str, Enum):
    THINKING = "thinking"        # AI 在思考
    TOOL_CALL = "tool_call"      # AI 决定调工具
    TOOL_RESULT = "tool_result"  # 工具返回了结果
    FINAL_ANSWER = "final_answer" # AI 给出最终回答
    ERROR = "error"              # 出错了

# 单个事件
class ReActEvent(BaseModel):
    event_type: ReActEventType   # 事件类型
    content: str = ""            # 内容（思考内容/回答/错误信息）
    tool_name: str = ""          # 工具名（如果是工具调用）
    tool_args: Dict[str, Any] = {}  # 工具参数
    tool_result: str = ""        # 工具返回结果
    iteration: int = 0           # 第几轮

# 最终结果
class ReActResult(BaseModel):
    user_input: str = ""
    final_answer: str = ""
    steps: List = []
    total_iterations: int = 0
    tools_used: List[str] = []
    success: bool = True
```

**为什么要定义这些模型？**
因为 ReAct 循环每一步都要向前端报告"我现在在干什么"。用固定的数据模型，前端就知道怎么显示了。

**什么是 Pydantic？**
一个 Python 库，用来定义数据结构。比普通 class 多了类型检查。比如你定义 `iteration: int`，传个字符串进去就会报错。

---

## 第七步：写工具 Schema（告诉 AI 有哪些工具）

### 7.1 创建 `backend/agents/react_tools.py`

这个文件做两件事：
1. 定义工具的"说明书"（给 AI 看的）
2. 定义工具的实际执行函数

```python
# ============ 第一部分：工具说明书 ============

def get_tool_schemas():
    """返回工具定义列表（OpenAI function calling 格式）"""

    return [
        {
            "type": "function",
            "function": {
                "name": "explain_concept",              # 工具名
                "description": "详细讲解一个学习概念，适合用户想理解某个知识点时使用",
                # ↑ AI 靠这个描述判断什么时候用这个工具
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
                    "required": ["concept"]  # 必填参数
                }
            }
        },
        # ... 其他3个工具格式一样，省略
    ]


# ============ 第二部分：工具执行器 ============

# 工具名 → 执行函数 的映射表
TOOL_EXECUTORS = {
    "rag_search": _execute_rag_search,
    "explain_concept": _execute_explain_concept,
    "generate_study_plan": _execute_study_plan,
    "generate_questions": _execute_questions,
}

# 每个执行函数
def _execute_explain_concept(agent, concept, subject="", level="初学者"):
    from backend.tools.knowledge import explain_concept
    return explain_concept(concept, subject=subject, level=level, llm=agent.llm)
    # ↑ 把 agent 的 LLM 传进去，复用连接

def _execute_rag_search(agent, query, top_k=3):
    from backend.tools.rag_tool import rag_search
    return rag_search(query, agent._kb, top_k=top_k)
    # ↑ 把 agent 的知识库传进去

# ... 其他执行函数类似

# 统一入口
def execute_tool(agent, tool_name, tool_args):
    """根据工具名找到对应的函数并执行"""
    executor = TOOL_EXECUTORS.get(tool_name)
    if not executor:
        return f"未知工具: {tool_name}"
    return executor(agent, **tool_args)
```

**为什么分"说明书"和"执行器"？**
- "说明书"是给 AI 看的（JSON 格式），AI 根据描述决定要不要调
- "执行器"是你写的 Python 函数，AI 决定调了之后，真正执行代码

**为什么需要 `execute_tool` 这个统一入口？**
因为 Agent 不知道 AI 会调哪个工具。AI 返回一个工具名和参数，`execute_tool` 根据名字找到对应的函数来执行。

---

## 第八步：写 ReAct Agent（核心！）

### 8.1 创建 `backend/agents/react_agent.py`

这是整个系统最核心的文件。

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
        super().__init__(**kwargs)  # 调用 BaseAgent 的初始化

        # ★ 关键：把工具说明书绑到 LLM
        self.tool_schemas = get_tool_schemas()
        self.llm_with_tools = self.llm.bind_tools(self.tool_schemas)
        # bind_tools 做的事：每次调 LLM 时，自动把工具定义塞进 API 请求
        # 这样 LLM 就知道"我有这些工具可以用"

        # 知识库（后面会初始化）
        self._kb = None

    def get_system_prompt(self):
        return REACT_SYSTEM_PROMPT

    def react_stream(self, user_input):
        """
        ★★★ ReAct 核心循环 ★★★

        流程：
        1. 组装消息（系统提示 + 历史 + 用户问题）
        2. 发给 LLM
        3. LLM 的回答里有没有 tool_calls？
           - 没有 → 就是最终回答，结束
           - 有 → 执行工具，把结果塞回去，回到第2步
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
            messages.append(response)  # 把 AI 的回答加入历史

            # ③ 检查：AI 调工具了吗？
            if not response.tool_calls:
                # 没调工具 → AI 直接给了回答
                yield ReActEvent(
                    event_type=ReActEventType.FINAL_ANSWER,
                    content=response.content
                )
                return  # 结束！

            # ④ AI 调了工具，逐个执行
            for tc in response.tool_calls:
                tool_name = tc["name"]      # 工具名
                tool_args = tc["args"]       # 参数（AI 自动填的）

                # 报告：在调工具
                yield ReActEvent(
                    event_type=ReActEventType.TOOL_CALL,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    iteration=iteration
                )

                # 执行工具
                result = execute_tool(self, tool_name, tool_args)

                # 报告：工具结果
                yield ReActEvent(
                    event_type=ReActEventType.TOOL_RESULT,
                    tool_name=tool_name,
                    tool_result=result,
                    content=result[:200],
                    iteration=iteration
                )

                # ★ 把工具结果塞回消息列表
                # ToolMessage 是 LangChain 的特殊消息类型
                # tool_call_id 用来和之前的工具调用对应
                messages.append(ToolMessage(
                    content=result,
                    tool_call_id=tc.get("id", "")
                ))

            # ⑤ 回到循环开头，把更新后的 messages 再发给 LLM
            # LLM 看到工具结果后，决定：够了→回答，不够→继续调

        # 超过最大轮次，强制让 LLM 回答
        response = self.llm.invoke(messages)
        yield ReActEvent(
            event_type=ReActEventType.FINAL_ANSWER,
            content=response.content
        )
```

**几个关键概念**：

1. **`bind_tools`**：把工具定义绑到 LLM。之后每次 `invoke`，工具定义自动跟着一起发给 AI。

2. **`response.tool_calls`**：AI 的回答里如果调了工具，这个字段就是 `[{name: "xxx", args: {...}}]`。如果没调，就是空列表 `[]`。

3. **`ToolMessage`**：工具执行完，结果要用 `ToolMessage` 包一下塞回消息列表，LLM 才知道"这是之前那个工具的结果"。

4. **`yield`**：Python 的生成器语法。每次 `yield` 一个事件，前端就能立即收到并显示。不用等整个过程跑完。

---

## 第九步：写知识库（可选，但比赛加分）

知识库的作用：用户上传 PDF → 存起来 → 以后提问时能从 PDF 里找到相关内容。

### 9.1 `backend/knowledge/embedding.py` — 文字转向量

```python
from sentence_transformers import SentenceTransformer

_model = None

def get_embedding_model():
    """加载向量模型（全局只加载一次）"""
    global _model
    if _model is None:
        _model = SentenceTransformer("shibing624/text2vec-base-chinese")
        # ↑ 一个中文文本向量模型，把文字转成 768 维的数字向量
    return _model

def get_embeddings_batch(texts):
    """把一批文字转成向量"""
    model = get_embedding_model()
    return model.encode(texts)

def text_split_by_token(text, chunk_size=500):
    """把长文本切成小段（每段约 500 字）"""
    # 为什么切？因为向量搜索按"段"来匹配，太长了匹配不准
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunks.append(text[i:i+chunk_size])
    return chunks
```

**什么是 Embedding？**
把文字变成一串数字（向量）。意思相近的文字，数字也相近。这样就能用数学方法找"最相似的内容"。

### 9.2 `backend/knowledge/pdf_loader.py` — 读 PDF

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
    """清理文本（去乱码、多余空格）"""
    import re
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
```

### 9.3 `backend/knowledge/vector_store_faiss.py` — FAISS 向量存储

```python
import faiss
import numpy as np

class FAISSVectorStore:
    def __init__(self, dimension=768):
        # 768 是 text2vec-base-chinese 模型输出的向量维度
        self.index = faiss.IndexFlatIP(dimension)
        # ↑ IndexFlatIP = 内积相似度（向量越接近，值越大）
        self.texts = []  # 存原始文字，和向量一一对应

    def add(self, texts, embeddings):
        """添加文本和对应的向量"""
        # 归一化：让内积等价于余弦相似度
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized = embeddings / norms
        self.index.add(normalized.astype('float32'))
        self.texts.extend(texts)

    def search(self, query_embedding, top_k=3):
        """搜索最相似的 top_k 个文本"""
        # 归一化查询向量
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

### 9.4 `backend/knowledge/knowledge_base_faiss.py` — 知识库管理

```python
import os
from backend.knowledge.embedding import get_embeddings_batch, text_split_by_token
from backend.knowledge.pdf_loader import extract_text_from_pdf, clean_text
from backend.knowledge.vector_store_faiss import FAISSVectorStore

class FAISSKnowledgeBase:
    def __init__(self):
        self.vector_store = FAISSVectorStore()
        self.documents = {}  # 存文档信息

    def add_pdf(self, file_path, subject="未分类"):
        """处理并添加 PDF"""
        # 1. 读取 PDF 文字
        text = extract_text_from_pdf(file_path)
        text = clean_text(text)

        # 2. 切成小段
        chunks = text_split_by_token(text, chunk_size=500)

        # 3. 每段转成向量
        embeddings = get_embeddings_batch(chunks)

        # 4. 存入 FAISS
        self.vector_store.add(chunks, embeddings)

        # 5. 记录文档信息
        self.documents[file_path] = {
            "subject": subject,
            "chunks": len(chunks)
        }

    def search(self, query, top_k=3):
        """搜索相关内容"""
        # 1. 把问题转成向量
        query_embedding = get_embeddings_batch([query])[0]

        # 2. 在 FAISS 里搜索
        return self.vector_store.search(query_embedding, top_k)
```

**知识库完整流程**：
```
PDF → 提取文字 → 切段 → 每段转向量 → 存 FAISS
提问 → 问题转向量 → 在 FAISS 里找最近的 → 返回相关段落
```

---

## 第十步：写前端界面

### 10.1 创建 `frontend/app.py`

这是最大的文件，所有页面都在这里。

```python
import streamlit as st
from backend.agents.react_agent import ReActStudyAgent
from backend.agents.react_models import ReActEventType

# ========== 页面配置 ==========
st.set_page_config(page_title="智能学习助手", page_icon="🎓", layout="wide")

# ========== 初始化 ==========
def init_session_state():
    """Streamlit 每次交互都会重新运行整个脚本，
    所以需要把状态存到 session_state 里"""
    if "agent" not in st.session_state:
        st.session_state.agent = ReActStudyAgent(verbose=False)
        # ↑ 创建 Agent 实例
    if "messages" not in st.session_state:
        st.session_state.messages = []
        # ↑ 对话历史

init_session_state()

# ========== 侧边栏导航 ==========
page = st.sidebar.selectbox("选择功能", ["在线问答", "知识库", "思维链可视化"])

# ========== 页面路由 ==========
if page == "在线问答":
    render_qa()
elif page == "知识库":
    render_kb()
elif page == "思维链可视化":
    render_viz()

# ========== QA 页面 ==========
def render_qa():
    st.title("在线问答")

    # 显示历史对话
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f'> {msg["content"]}')
        else:
            st.markdown(msg["content"])

    # 输入框
    with st.form("chat_form"):
        user_input = st.text_input("输入问题")
        submitted = st.form_submit_button("发送")

        if submitted and user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})

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

            st.rerun()  # 刷新页面，显示新消息
```

**什么是 `st.session_state`？**
Streamlit 每次用户点击按钮，整个 Python 脚本都会从头重新运行一遍。所以变量都存在 `session_state` 里，防止丢失。

**为什么用 `st.form`？**
Streamlit 的表单组件。用户输入文字后点"发送"才触发，不会每敲一个字就刷新页面。

---

## 总结：建造顺序

```
第1步：文件夹 + 依赖         → 搭好地基
第2步：.env + config.py      → 配好密码
第3步：llm_helper.py         → 连上 AI
第4步：base_agent.py         → Agent 基类（对话管理）
第5步：tools/*.py             → 4个工具（讲解/计划/出题/检索）
第6步：react_models.py       → 数据模型
第7步：react_tools.py        → 工具 Schema + 执行器
第8步：react_agent.py        → ReAct 核心循环 ★★★
第9步：knowledge/*.py         → 知识库（PDF+向量搜索）
第10步：app.py                → 前端界面
```

**核心就是第8步**。其他都是为它服务的：
- 第3-4步：让 Agent 能跟 AI 说话
- 第5步：提供工具能力
- 第6-7步：让 AI 知道有哪些工具、怎么调用
- 第9步：给检索工具提供数据源
- 第10步：让用户能用浏览器操作
