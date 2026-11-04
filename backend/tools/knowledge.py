"""
知识点讲解工具
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from backend.llm_helper import get_llm, text_content


# 延迟加载 LLM 实例
_llm_instance = None


def _get_llm():
    """获取或创建 LLM 实例（单例模式）"""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = get_llm(temperature=0.7)
    return _llm_instance


def explain_concept(
    concept: str,
    subject: str = "",
    level: str = "初学者",
    use_examples: bool = True,
    llm=None
) -> str:
    """
    讲解一个概念

    Args:
        concept: 要讲解的概念
        subject: 学科（如"数学"、"编程"等）
        level: 学习者水平（初学者/中级/高级）
        use_examples: 是否使用例子
        llm: 外部传入的LLM实例（可选）

    Returns:
        讲解内容
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一位擅长讲解概念的导师。

你的任务是：
1. 用简单易懂的语言解释概念
2. 使用生活中的类比
3. 提供具体的例子
4. 分步骤讲解

输出格式：
## 概念定义
[简单定义]

## 核心要点
- 要点1
- 要点2
- 要点3

## 生活类比
[用一个生活中的例子类比]

## 举例说明
[具体例子]

## 总结
[一句话总结]
"""),
        ("human", "请帮我讲解：{concept}\n学科：{subject}\n水平：{level}")
    ])

    _llm = llm or _get_llm()
    chain = prompt | _llm

    try:
        response = chain.invoke({
            "concept": concept,
            "subject": subject if subject else "通用",
            "level": level
        })
        return text_content(response.content)
    except Exception as e:
        return f"讲解失败: {str(e)}"


def break_down_concept(concept: str, llm=None) -> List[str]:
    """
    将复杂概念分解为多个子概念

    Args:
        concept: 要分解的概念
        llm: 外部传入的LLM实例（可选）

    Returns:
        子概念列表
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一位教育专家，擅长将复杂概念分解。

请将给定的概念分解为3-5个子概念或相关知识。
每个子概念应该简洁明了。

只返回子概念列表，每行一个，格式：
1. 子概念1
2. 子概念2
..."""),
        ("human", "请分解概念：{concept}")
    ])

    _llm = llm or _get_llm()
    chain = prompt | _llm

    try:
        response = chain.invoke({"concept": concept})
        lines = text_content(response.content).split("\n")
        return [line.strip().lstrip("0123456789.- ") for line in lines if line.strip()]
    except Exception as e:
        return [f"分解失败: {str(e)}"]


def compare_concepts(concept1: str, concept2: str, llm=None) -> str:
    """
    比较两个概念的异同

    Args:
        concept1: 概念1
        concept2: 概念2
        llm: 外部传入的LLM实例（可选）

    Returns:
        比较结果
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一位教育专家，擅长对比概念。

请比较两个概念的异同。

输出格式：
## 相同点
- 相同点1
- 相同点2

## 不同点
| 维度 | {concept1} | {concept2} |
|------|-----------|-----------|
| 维度1 | 特点 | 特点 |
| 维度2 | 特点 | 特点 |

## 使用场景
- {concept1} 适合：...
- {concept2} 适合：..."""),
        ("human", "请比较：{concept1} 和 {concept2}")
    ])

    _llm = llm or _get_llm()
    chain = prompt | _llm

    try:
        response = chain.invoke({"concept1": concept1, "concept2": concept2})
        return text_content(response.content)
    except Exception as e:
        return f"比较失败: {str(e)}"


# 测试
if __name__ == "__main__":
    # 测试讲解
    result = explain_concept("递归", "编程", "初学者")
    print(result)
    print()

    # 测试分解
    sub_concepts = break_down_concept("机器学习")
    print("子概念：")
    for sc in sub_concepts:
        print(f"  - {sc}")
    print()

    # 测试比较
    comparison = compare_concepts("列表", "元组")
    print(comparison)
