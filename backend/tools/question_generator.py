"""
习题生成和答案检查工具
"""
from typing import List, Dict, Optional

from langchain_core.prompts import ChatPromptTemplate

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from backend.llm_helper import get_llm, text_content


# 延迟加载 LLM 实例
_llm_instance = None


def _get_llm():
    """获取或创建 LLM 实例（单例模式）"""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = get_llm(temperature=0.7)
    return _llm_instance


def generate_questions(
    topic: str,
    difficulty: str = "中等",
    count: int = 3,
    question_type: str = "mixed",
    llm=None
) -> str:
    """
    生成练习题

    Args:
        topic: 题目主题
        difficulty: 难度（简单/中等/困难）
        count: 题目数量
        question_type: 题型（choice/填空/编程/mixed）

    Returns:
        生成的题目
    """
    difficulty_map = {
        "简单": "基础概念和简单应用",
        "中等": "需要一定思考和综合运用",
        "困难": "需要深入理解和复杂推理"
    }

    type_instruction = {
        "choice": "选择题（每题4个选项）",
        "填空": "填空题",
        "编程": "编程题",
        "mixed": "混合题型（选择题和简答题）"
    }

    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一位出题专家，擅长生成教学练习题。

请根据主题生成 {count} 道 {difficulty} 级别的练习题。

要求：
1. 题目要有教学意义，能帮助理解概念
2. 难度符合 {difficulty} 的标准：{difficulty_desc}
3. 提供【参考答案】和【解析】
4. 题型：{type_desc}

输出格式：
## 练习题（{topic}）

### 题目 1
**题目内容**

【参考答案】
...

【解析】
...

---

### 题目 2
..."""),
        ("human", "{topic}")
    ])

    _llm = llm or _get_llm()
    chain = prompt | _llm

    try:
        response = chain.invoke({
            "topic": topic,
            "difficulty": difficulty,
            "difficulty_desc": difficulty_map.get(difficulty, ""),
            "count": count,
            "type_desc": type_instruction.get(question_type, type_instruction["mixed"])
        })
        return text_content(response.content)
    except Exception as e:
        return f"生成题目失败: {str(e)}"


def check_answer(
    question: str,
    user_answer: str,
    question_type: str = "general",
    llm=None
) -> str:
    """
    检查答案并给出反馈

    Args:
        question: 题目
        user_answer: 用户答案
        question_type: 题型

    Returns:
        评价反馈
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一位耐心的老师，负责批改作业。

请检查学生的答案，并给出详细的反馈。

评价原则：
1. 鼓励为主，即使错了也要肯定其努力
2. 指出错误所在，并解释为什么错了
3. 给出正确答案和详细解析
4. 提供改进建议

输出格式：
## 答案评价

### 正确性
[正确/部分正确/错误]

### 反馈
[具体的反馈意见]

### 详细解析
[详细解释正确答案]

### 建议改进
[学习建议]
"""),
        ("human", "题目：{question}\n学生答案：{user_answer}")
    ])

    _llm = llm or _get_llm()
    chain = prompt | _llm

    try:
        response = chain.invoke({"question": question, "user_answer": user_answer})
        return text_content(response.content)
    except Exception as e:
        return f"检查答案失败: {str(e)}"


# 测试
if __name__ == "__main__":
    # 测试生成题目
    questions = generate_questions("Python列表", "中等", 2)
    print(questions)
    print()

    # 测试答案检查
    feedback = check_answer(
        "Python中用什么关键字定义函数？",
        "用 def 关键字"
    )
    print(feedback)
