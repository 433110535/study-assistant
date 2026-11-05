"""
答案忠实度：一句一句看回答有没有原样出现在检索片段里。

不足 4 个字的碎片不记分。没有可记分的句子时返回 applicable=False，
调用方不要把这种情况算成 0 分。这里不调用模型。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_CLAIM_SPLIT = re.compile(r"[。！？!?；;\n]+")
_MIN_CLAIM_CHARS = 4


def score_faithfulness(answer: str, contexts: Optional[List[str]] = None) -> Dict[str, Any]:
    claims = _claims(answer)
    if not claims:
        return {"applicable": False, "score": None, "grounded": 0, "claims": 0}

    blob = _compact("".join(contexts or []))
    grounded = sum(1 for claim in claims if claim in blob)
    return {
        "applicable": True,
        "score": grounded / len(claims),
        "grounded": grounded,
        "claims": len(claims),
    }


def _claims(answer: str) -> List[str]:
    claims = []
    for piece in _CLAIM_SPLIT.split(answer or ""):
        compact = _compact(piece)
        if len(compact) >= _MIN_CLAIM_CHARS:
            claims.append(compact)
    return claims


def _compact(text: str) -> str:
    return "".join((text or "").split())

# =======================================================
# 黄金校准基准集与裁判校准套件 (Judge Calibration Benchmark)
# =======================================================

GOLDEN_CALIBRATION_SAMPLES: List[Dict[str, Any]] = [
    {
        "id": "faithful_1",
        "context": ["牛顿第一定律指出，一切物体在不受外力作用时，总保持静止或匀速直线运动状态。"],
        "answer": "牛顿第一定律指出，一切物体在不受外力作用时，总保持静止或匀速直线运动状态。",
        "expected_faithful": True,
        "type": "exact_faithful",
    },
    {
        "id": "faithful_2",
        "context": ["光年是长度单位，指光在真空中一年时间内传播的距离。光在真空中传播的速度大约是每秒30万千米。"],
        "answer": "光年是长度单位，指光在真空中一年时间内传播的距离。",
        "expected_faithful": True,
        "type": "subset_faithful",
    },
    {
        "id": "hallucination_1",
        "context": ["太阳系八大行星中，水星离太阳最近，海王星离太阳最远。木星是体积最大的行星。"],
        "answer": "冥王星是太阳系中最大的行星，表面覆盖着厚达数千公里的液态金属氢海洋。",
        "expected_faithful": False,
        "type": "hallucination_unsupported",
    },
    {
        "id": "contradiction_1",
        "context": ["真空中所有电磁波的传播速度都完全相同，等于光速c。"],
        "answer": "在真空中，红外线的传播速度明显大于紫外线的传播速度。",
        "expected_faithful": False,
        "type": "contradiction_tampered",
    },
    {
        "id": "irrelevant_1",
        "context": ["水在标准大气压下的沸点是100摄氏度。冰的熔点是0摄氏度。"],
        "answer": "我不知道这个问题的答案，今天的天气真是不错。",
        "expected_faithful": False,
        "type": "irrelevant_evasion",
    },
]


def calibrate_faithfulness_judge(
    judge_fn: Optional[Any] = None,
    samples: Optional[List[Dict[str, Any]]] = None,
    threshold: float = 0.8,
) -> Dict[str, Any]:
    """对规则裁判或 LLM 裁判进行黄金校准测试，输出准确率与混淆指标。"""
    test_samples = samples or GOLDEN_CALIBRATION_SAMPLES
    results = []
    tp = tn = fp = fn = 0

    for item in test_samples:
        ans = item["answer"]
        ctx = item["context"]
        expected = item["expected_faithful"]
        if judge_fn is not None:
            pred = bool(judge_fn(ans, ctx))
        else:
            scored = score_faithfulness(ans, ctx)
            score = scored.get("score")
            pred = bool(score is not None and score >= threshold)

        is_correct = (pred == expected)
        if pred and expected:
            tp += 1
        elif not pred and not expected:
            tn += 1
        elif pred and not expected:
            fp += 1
        else:
            fn += 1

        results.append({
            "id": item["id"],
            "type": item["type"],
            "expected": expected,
            "predicted": pred,
            "correct": is_correct,
        })

    total = len(test_samples)
    accuracy = (tp + tn) / total if total > 0 else 0.0
    return {
        "total": total,
        "accuracy": accuracy,
        "passed": accuracy >= 0.8,
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "breakdown": results,
    }
