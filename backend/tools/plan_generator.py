"""
学习计划生成工具
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from backend.llm_helper import get_llm


# 延迟加载 LLM 实例
_llm_instance = None


def _get_llm():
    """获取或创建 LLM 实例（单例模式）"""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = get_llm(temperature=0.7)
    return _llm_instance


def generate_study_plan(
    subject: str,
    goal: str,
    duration_days: int,
    current_level: str = "初学者",
    hours_per_day: float = 2.0,
    llm=None
) -> str:
    """
    生成学习计划

    Args:
        subject: 学科/主题
        goal: 学习目标
        duration_days: 学习天数
        current_level: 当前水平
        hours_per_day: 每天学习小时数

    Returns:
        学习计划
    """
    total_hours = duration_days * hours_per_day

    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一位专业的学习规划师。

请根据以下信息生成一个详细的学习计划：
- 总学习时长：约 {total_hours} 小时
- 要 realistic，不要安排太满
- 循序渐进，从基础到进阶
- 包含理论和实践
- 设置检查点（milestone）

输出格式：
# {subject} 学习计划

## 学习目标
{goal}

## 整体安排
- 总时长：{total_hours} 小时
- 学习周期：{duration_days} 天
- 每日投入：{hours_per_day} 小时
- 当前水平：{current_level}

## 分阶段计划

### 第一阶段：基础夯实（第 1-{phase1_days} 天）
- 学习内容：
  - Day 1-3: ...
  - Day 4-7: ...
- 阶段目标：...

### 第二阶段：核心突破（第 {phase1_days_plus_1}-{phase2_days} 天）
...

### 第三阶段：综合应用（第 {phase2_days_plus_1}-{duration_days} 天）
...

## 检查点（Checkpoints）
- 第7天：应该掌握...
- 第14天：应该能够...
- 第{duration_days}天：完成目标...

## 学习建议
- 推荐资源：...
- 学习方法：...
- 注意事项：..."""),
        ("human", "学科：{subject}\n目标：{goal}\n当前水平：{current_level}\n学习天数：{duration_days}天\n每天投入：{hours_per_day}小时")
    ])

    _llm = llm or _get_llm()
    chain = prompt | _llm

    try:
        response = chain.invoke({
            "subject": subject,
            "goal": goal,
            "duration_days": duration_days,
            "total_hours": total_hours,
            "hours_per_day": hours_per_day,
            "current_level": current_level,
            "phase1_days": duration_days // 3,
            "phase1_days_plus_1": duration_days // 3 + 1,
            "phase2_days": duration_days * 2 // 3,
            "phase2_days_plus_1": duration_days * 2 // 3 + 1
        })
        return response.content
    except Exception as e:
        return f"生成计划失败: {str(e)}"


def create_daily_schedule(
    topics: List[str],
    available_hours: float = 2.0,
    include_break: bool = True,
    break_duration: int = 15
) -> str:
    """
    创建每日学习时间表

    Args:
        topics: 要学习的主题列表
        available_hours: 可用小时数
        include_break: 是否包含休息时间
        break_duration: 休息时长（分钟）

    Returns:
        时间表
    """
    total_minutes = int(available_hours * 60)

    # 如果包含休息，计算所有休息时间
    if include_break:
        break_count = len(topics) - 1  # 每个主题后都有休息（除了最后一个）
        total_break_minutes = break_count * break_duration
        study_minutes = total_minutes - total_break_minutes
    else:
        study_minutes = total_minutes

    # 计算每个主题的时间
    minutes_per_topic = max(study_minutes // len(topics), 20)  # 至少20分钟

    schedule = []
    current_time = datetime.strptime("09:00", "%H:%M")

    for i, topic in enumerate(topics):
        end_time = current_time + timedelta(minutes=minutes_per_topic)

        schedule.append({
            "time": f"{current_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}",
            "topic": topic,
            "duration": f"{minutes_per_topic}分钟"
        })

        # 更新当前时间到下一个主题开始时间
        current_time = end_time

        # 添加休息（除了最后一个）
        if include_break and i < len(topics) - 1:
            current_time = current_time + timedelta(minutes=break_duration)
            schedule.append({
                "time": f"{current_time.strftime('%H:%M')} - {(current_time + timedelta(minutes=break_duration)).strftime('%H:%M')}",
                "topic": "休息",
                "duration": f"{break_duration}分钟"
            })
            current_time = current_time + timedelta(minutes=break_duration)  # 休息后继续

    # 格式化输出
    result = "##今日学习时间表\n\n"

    for item in schedule:
        result += f"### {item['time']} | {item['topic']}\n"
        result += f"时长：{item['duration']}\n\n"

    return result


def generate_milestone_checklist(
    subject: str,
    duration_days: int
) -> List[Dict[str, str]]:
    """
    生成里程碑检查清单

    Args:
        subject: 学科
        duration_days: 总天数

    Returns:
        里程碑列表
    """
    milestones = []

    # 根据天数生成不同数量的里程碑
    if duration_days <= 7:
        milestones_count = 2
    elif duration_days <= 30:
        milestones_count = 4
    else:
        milestones_count = 6

    interval = duration_days // milestones_count

    for i in range(1, milestones_count + 1):
        day = i * interval
        milestones.append({
            "day": f"第{day}天",
            "checkpoint": f"第{day}天检查点",
            "criteria": f"应该掌握的技能和知识点（第{day}天）"
        })

    return milestones


# 测试
if __name__ == "__main__":
    # 测试学习计划生成
    plan = generate_study_plan(
        subject="Python编程",
        goal="能够独立完成一个小项目",
        duration_days=30,
        current_level="零基础",
        hours_per_day=2
    )
    print(plan)
    print()

    # 测试每日时间表
    schedule = create_daily_schedule(
        topics=["变量和数据类型", "条件语句", "循环结构", "函数定义"],
        available_hours=2.0
    )
    print(schedule)
