"""
对照标准答案判分、错因归类、同结构变式。

不调用大模型。没有标准答案时返回 ungraded，不编造分数。
变式替换题干里的数字，或预先列出的人名和常见物品。文字变式不重复原题。没有可替换的部分就拒绝，不调用模型。
"""
from __future__ import annotations

import ast
import hashlib
import math
import re
import unicodedata
from typing import Any, Dict, List, Optional

ERROR_CONCEPT = "概念不清"
ERROR_CALC = "计算失误"
ERROR_READING = "审题错误"
ERROR_OTHER = "其他"

_NUM_RE = re.compile(r"(?<![0-9.])(-?\d+(?:\.\d+)?)(?![0-9.])")
_NAMES = ("小明", "小红", "小华", "小李", "小王", "小张")
_OBJECTS = ("苹果", "香蕉", "橘子", "梨")
_SURFACE_GROUPS = (_NAMES, _OBJECTS)
_SURFACE_WORDS = tuple(
    sorted((word for group in _SURFACE_GROUPS for word in group), key=len, reverse=True)
)
_FACTORS = (2.0, 0.5, 10.0, 0.1, 100.0, 0.01)
_ARITH_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd)


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "")
    value = value.strip().lower()
    value = re.sub(r"\s+", "", value)
    return value.strip("。．.!！?？；;，,、")


def _to_number(text: str) -> Optional[float]:
    norm = _normalize(text)
    if not norm:
        return None
    if norm.endswith("%"):
        base = _to_number(norm[:-1])
        return None if base is None else base / 100.0
    if re.fullmatch(r"-?\d+/-?\d+", norm):
        left, right = norm.split("/")
        denominator = float(right)
        if denominator == 0:
            return None
        return float(left) / denominator
    if re.fullmatch(r"-?\d+(?:\.\d+)?", norm):
        return float(norm)
    return None


def _close(left: float, right: float) -> bool:
    scale = max(abs(left), abs(right), 1.0)
    return abs(left - right) <= 1e-6 * scale


def _accepted_answers(correct_answer: str) -> List[str]:
    parts = re.split(r"\|\||\n", correct_answer or "")
    return [part.strip() for part in parts if part.strip()]


def grade_item(
    question_text: str,
    student_answer: str,
    correct_answer: str = "",
) -> Dict[str, Any]:
    """对照标准答案打分。correct_answer 可用 || 分隔多个可接受答案。"""
    question = (question_text or "").strip()
    student = (student_answer or "").strip()
    accepted = _accepted_answers(correct_answer)
    if not question:
        return {"status": "ungraded", "score": None, "reason": "没有题干，不能判分"}
    if not accepted:
        return {
            "status": "ungraded",
            "score": None,
            "reason": "没有标准答案，不能判分",
        }
    if not student:
        return {"status": "incorrect", "score": 0, "reason": "未作答"}

    student_norm = _normalize(student)
    student_num = _to_number(student)
    for answer in accepted:
        if student_norm == _normalize(answer):
            return {"status": "correct", "score": 1, "reason": "与标准答案一致"}
        answer_num = _to_number(answer)
        if student_num is not None and answer_num is not None and _close(student_num, answer_num):
            return {"status": "correct", "score": 1, "reason": "数值与标准答案一致"}
    return {"status": "incorrect", "score": 0, "reason": "与标准答案不一致"}


def _numbers_in(text: str) -> List[float]:
    found = []
    for match in _NUM_RE.finditer(text or ""):
        try:
            found.append(float(match.group(1)))
        except ValueError:
            continue
    return found


def _is_calc_slip(question: str, student: str, correct: str) -> bool:
    student_num = _to_number(student)
    correct_num = _to_number(correct)
    if student_num is None or correct_num is None:
        return False
    if _close(student_num, -correct_num) and not _close(correct_num, 0):
        return True
    if float(student_num).is_integer() and float(correct_num).is_integer():
        if abs(student_num - correct_num) == 1:
            return True
    if _close(correct_num, 0):
        return False
    ratio = student_num / correct_num
    return any(_close(ratio, factor) for factor in _FACTORS)


def _copied_stem_number(question: str, student: str, correct: str) -> bool:
    student_num = _to_number(student)
    correct_num = _to_number(correct)
    if student_num is None:
        return False
    if correct_num is not None and _close(student_num, correct_num):
        return False
    return any(_close(student_num, value) for value in _numbers_in(question))


def diagnose_error(
    question_text: str,
    student_answer: str,
    correct_answer: str = "",
) -> Dict[str, Any]:
    """在判分结果上归类错因。判对时不编造错因。"""
    graded = grade_item(question_text, student_answer, correct_answer)
    if graded["status"] == "ungraded":
        return {
            "error_type": ERROR_OTHER,
            "summary": graded["reason"],
            "grade": graded,
        }
    if graded["status"] == "correct":
        return {"error_type": "", "summary": "回答正确，不需要归因", "grade": graded}

    student = (student_answer or "").strip()
    accepted = _accepted_answers(correct_answer)
    primary = accepted[0] if accepted else ""
    if not student:
        error_type = ERROR_READING
        summary = "没有写下答案，先看清题目在问什么。"
    elif _copied_stem_number(question_text, student, primary):
        error_type = ERROR_READING
        summary = "答案直接用了题干里的数字，先确认题目问的是哪一个量。"
    elif (
        len(_normalize(student)) >= 6
        and _normalize(student) in _normalize(question_text)
        and _normalize(student) != _normalize(primary)
    ):
        error_type = ERROR_READING
        summary = "答案更像从题干里抄了一段，先重新读问题。"
    elif _is_calc_slip(question_text, student, primary):
        error_type = ERROR_CALC
        summary = "结果和标准答案差在运算上，例如符号、进位或乘除了 10。"
    else:
        error_type = ERROR_CONCEPT
        summary = "答案和标准答案不是同一类结果，先回到这个考点的定义。"
    return {"error_type": error_type, "summary": summary, "grade": graded}


def _eval_arith(expr: str) -> Optional[float]:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None

    def walk(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = walk(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, _ARITH_OPS):
            left = walk(node.left)
            right = walk(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise ZeroDivisionError
                return left / right
            if isinstance(node.op, ast.FloorDiv):
                if right == 0:
                    raise ZeroDivisionError
                return left // right
            if isinstance(node.op, ast.Mod):
                if right == 0:
                    raise ZeroDivisionError
                return left % right
            if abs(right) > 6:
                raise ValueError("指数过大")
            return left ** right
        raise ValueError("不是纯算术式")

    try:
        return walk(tree)
    except (ValueError, ZeroDivisionError, TypeError):
        return None


def _expression_in(question: str) -> str:
    text = unicodedata.normalize("NFKC", question or "").strip()
    text = re.sub(r"^(计算|求值)\s*[:：]?\s*", "", text)
    text = text.strip("。．.？?")
    compact = re.sub(r"\s+", "", text)
    if re.fullmatch(r"[0-9+\-*/().]+", compact):
        return compact
    return ""


def _shift_number(raw: str, salt: int) -> str:
    value = float(raw)
    delta = (salt % 4) + 1
    updated = value + delta if value >= 0 else value - delta
    if updated == value:
        updated = value + 1
    if value != 0 and updated == 0:
        updated = value + delta + 1
    if "." in raw:
        text = f"{updated:.4f}".rstrip("0").rstrip(".")
        return text or "0"
    return str(int(updated)) if float(updated).is_integer() else str(updated)


def _surface_spans(question: str) -> List[tuple]:
    """从左到右找出不重叠的人名或物品。先匹配更长的词。"""
    spans = []
    index = 0
    while index < len(question):
        matched = None
        for word in _SURFACE_WORDS:
            if question.startswith(word, index):
                matched = (index, index + len(word), word)
                break
        if matched is None:
            index += 1
            continue
        spans.append(matched)
        index = matched[1]
    return spans


def _rotate_surface(word: str, steps: int) -> str:
    for group in _SURFACE_GROUPS:
        if word in group:
            return group[(group.index(word) + steps) % len(group)]
    return word


def _surface_cycle(spans: List[tuple]) -> int:
    """各组词表长度的最小公倍数。再转这么多步会回到原词。"""
    cycle = 1
    for _, _, word in spans:
        for group in _SURFACE_GROUPS:
            if word in group:
                cycle = math.lcm(cycle, len(group))
                break
    return cycle


def _render_rotated(question: str, spans: List[tuple], steps: int) -> str:
    pieces = []
    cursor = 0
    for start, end, word in spans:
        pieces.append(question[cursor:start])
        pieces.append(_rotate_surface(word, steps))
        cursor = end
    pieces.append(question[cursor:])
    return "".join(pieces)


def _swap_surface(question: str, count: int) -> Dict[str, Any]:
    spans = _surface_spans(question)
    if not spans:
        return {
            "status": "unsupported",
            "items": [],
            "reason": "题干里没有可替换的数字、人名或常见物品，不能生成同结构变式",
        }
    items = []
    seen = {question}
    # 步数对词表长度取余会绕回原词。凑不满 count 时少返回，不把原题塞回去。
    for steps in range(1, _surface_cycle(spans)):
        if len(items) >= count:
            break
        stem = _render_rotated(question, spans, steps)
        if stem in seen:
            continue
        seen.add(stem)
        items.append({"stem": stem, "answer": None})
    if not items:
        return {
            "status": "unsupported",
            "items": [],
            "reason": "题干里没有可替换的数字、人名或常见物品，不能生成同结构变式",
        }
    return {"status": "ready", "items": items, "reason": ""}


def make_variants(question_text: str, count: int = 3) -> Dict[str, Any]:
    """替换数字，或预先列出的人名和物品。没有可替换部分则拒绝编造。

    文字变式不重复原题，彼此也不重复。词表不够时少返回几条。
    """
    question = (question_text or "").strip()
    try:
        total = int(count)
    except (TypeError, ValueError):
        total = 3
    total = min(5, max(1, total))
    matches = list(_NUM_RE.finditer(question))
    if not question or not matches:
        if not question:
            return {
                "status": "unsupported",
                "items": [],
                "reason": "题干里没有可替换的数字、人名或常见物品，不能生成同结构变式",
            }
        return _swap_surface(question, total)

    digest = hashlib.sha256(question.encode("utf-8")).digest()
    items = []
    for index in range(total):
        pieces = []
        cursor = 0
        for nth, match in enumerate(matches):
            pieces.append(question[cursor:match.start()])
            salt = digest[nth % len(digest)] + index * 3 + nth
            pieces.append(_shift_number(match.group(1), salt))
            cursor = match.end()
        pieces.append(question[cursor:])
        stem = "".join(pieces)
        expr = _expression_in(stem)
        answer = _eval_arith(expr) if expr else None
        items.append({"stem": stem, "answer": answer})
    return {"status": "ready", "items": items, "reason": ""}


def format_grade(result: Dict[str, Any]) -> str:
    score = "无" if result.get("score") is None else str(result["score"])
    lines = [
        f"状态: {result.get('status')}",
        f"得分: {score}",
        f"说明: {result.get('reason') or ''}",
    ]
    if result.get("status") == "incorrect":
        lines.append("下一步：调用 diagnose_error。用户要求记入错题本时再调用 save_mistake。")
    if result.get("status") == "ungraded":
        lines.append("不要告诉用户这道题已经判对或判错。")
    return "\n".join(lines)


def format_diagnosis(result: Dict[str, Any]) -> str:
    error_type = result.get("error_type") or "无"
    return f"错因: {error_type}\n说明: {result.get('summary') or ''}"


def format_variants(result: Dict[str, Any]) -> str:
    if result.get("status") != "ready":
        return f"状态: unsupported\n说明: {result.get('reason') or '不能生成变式'}\n不要编造同结构题目。"
    lines = ["状态: ready", "变式题不附答案。请让学生先做。"]
    for index, item in enumerate(result.get("items") or [], start=1):
        lines.append(f"变式 {index}: {item['stem']}")
    return "\n".join(lines)
