"""
离线评测：校验固定问题集，并按工具选择是否覆盖预期工具打分。

用法：
    python -m backend.platform.eval_runner --dry-run
    python -m backend.platform.eval_runner --live
"""
from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import BASE_DIR, TRACE_DB_PATH
from backend.platform.trace_store import _connect, init_trace_db

DEFAULT_DATASET = BASE_DIR / "eval" / "datasets" / "qa_baseline_v5.json"

# 未传入的指标保持未检查。忠实度只用调用方给出的分数，不在这里调用模型。
GATE_MIN_ACCURACY = 0.90
GATE_MIN_FAITHFULNESS = 0.85
GATE_MAX_DROP = 0.03


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_dataset(path: Optional[Path] = None) -> Dict[str, Any]:
    dataset_path = Path(path or DEFAULT_DATASET)
    with dataset_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data.get("samples"), list) or not data["samples"]:
        raise ValueError(f"评测集为空: {dataset_path}")
    ids = [item.get("id") for item in data["samples"]]
    if len(ids) != len(set(ids)):
        raise ValueError("评测集 sample id 重复")
    for item in data["samples"]:
        if "input" not in item or "expected_tools" not in item:
            raise ValueError(f"样本缺少 input 或 expected_tools: {item.get('id')}")
        if not isinstance(item["expected_tools"], list):
            raise ValueError(f"expected_tools 必须是列表: {item.get('id')}")
        if "contexts" in item or "answer" in item:
            contexts = item.get("contexts")
            answer = item.get("answer")
            if not isinstance(contexts, list) or not contexts or not all(
                isinstance(piece, str) and piece.strip() for piece in contexts
            ):
                raise ValueError(f"检索样本缺少固定片段: {item.get('id')}")
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError(f"检索样本缺少参考回答: {item.get('id')}")
    raw = dataset_path.read_bytes()
    data["_source_path"] = str(dataset_path)
    data["_content_hash"] = hashlib.sha256(raw).hexdigest()
    return data


def score_tool_selection(expected: List[str], actual: List[str]) -> Dict[str, Any]:
    """预期工具都必须出现；允许多调用，不允许漏调用。"""
    actual_set = list(dict.fromkeys(actual or []))
    missing = [name for name in expected if name not in actual_set]
    extra = [name for name in actual_set if name not in expected]
    passed = not missing
    if not expected and actual_set:
        passed = False
        missing = []
    return {
        "passed": passed,
        "missing": missing,
        "extra": extra if expected else actual_set,
    }


def validate_against_registry(dataset: Dict[str, Any]) -> List[str]:
    import backend.agents.react_tools  # noqa: F401  触发工具注册
    from backend.agents.tool_registry import get_tool_spec

    unknown = []
    for item in dataset["samples"]:
        for name in item["expected_tools"]:
            if get_tool_spec(name) is None and name not in unknown:
                unknown.append(name)
    return unknown


def ensure_eval_tables(db_path: Optional[Path] = None) -> None:
    path = Path(db_path or TRACE_DB_PATH)
    init_trace_db(path)
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS eval_runs (
                id TEXT PRIMARY KEY,
                dataset_name TEXT,
                dataset_version TEXT,
                mode TEXT,
                status TEXT,
                sample_count INTEGER,
                passed INTEGER,
                summary_json TEXT,
                started_at TEXT,
                finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS eval_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                eval_run_id TEXT NOT NULL,
                sample_id TEXT NOT NULL,
                tools_used TEXT,
                passed INTEGER,
                detail TEXT,
                output_preview TEXT
            );
            """
        )
        conn.commit()


def save_eval_run(
    dataset: Dict[str, Any],
    mode: str,
    results: List[Dict[str, Any]],
    db_path: Optional[Path] = None,
) -> str:
    path = Path(db_path or TRACE_DB_PATH)
    ensure_eval_tables(path)
    source = dataset.get("_source_path")
    if source:
        from backend.platform.dataset_catalog import register_file

        register_file(Path(source), db_path=path)
    run_id = str(uuid.uuid4())
    passed = sum(1 for item in results if item["passed"])
    now = _utc_now()
    faithfulness = mean_faithfulness(results)
    summary = {
        "passed": passed,
        "total": len(results),
        "accuracy": round(passed / len(results), 4) if results else 0,
        "faithfulness": None if faithfulness is None else round(faithfulness, 4),
        "failure_attribution": attribute_failures(results),
    }
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO eval_runs
            (id, dataset_name, dataset_version, mode, status, sample_count,
             passed, summary_json, started_at, finished_at)
            VALUES (?, ?, ?, ?, 'ok', ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                dataset.get("name", ""),
                dataset.get("version", ""),
                mode,
                len(results),
                passed,
                json.dumps(summary, ensure_ascii=False),
                now,
                now,
            ),
        )
        for item in results:
            conn.execute(
                """
                INSERT INTO eval_results
                (eval_run_id, sample_id, tools_used, passed, detail, output_preview)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    item["sample_id"],
                    json.dumps(item.get("tools_used", []), ensure_ascii=False),
                    1 if item["passed"] else 0,
                    item.get("detail", ""),
                    (item.get("output") or "")[:500],
                ),
            )
        conn.commit()
    return run_id


def check_release_gate(
    accuracy: float,
    baseline_accuracy: Optional[float] = None,
    faithfulness: Optional[float] = None,
    baseline_faithfulness: Optional[float] = None,
) -> Dict[str, Any]:
    """工具选择必查。传入忠实度时，低于 0.85 或较基线下跌超过 3 个百分点也失败。"""
    reasons = []
    checked = ["tool_selection"]
    not_checked = ["faithfulness", "pii", "injection", "iterations", "cost"]
    if accuracy + 1e-9 < GATE_MIN_ACCURACY:
        reasons.append(
            f"工具选择准确率 {accuracy:.2%} 低于 {GATE_MIN_ACCURACY:.0%}"
        )
    if (
        baseline_accuracy is not None
        and baseline_accuracy - accuracy > GATE_MAX_DROP + 1e-9
    ):
        reasons.append(
            f"工具选择准确率 {accuracy:.2%} 比基线 {baseline_accuracy:.2%} "
            f"下降超过 {GATE_MAX_DROP:.0%}"
        )
    if faithfulness is not None:
        checked.append("faithfulness")
        not_checked.remove("faithfulness")
        if faithfulness + 1e-9 < GATE_MIN_FAITHFULNESS:
            reasons.append(
                f"忠实度 {faithfulness:.2%} 低于 {GATE_MIN_FAITHFULNESS:.0%}"
            )
        if (
            baseline_faithfulness is not None
            and baseline_faithfulness - faithfulness > GATE_MAX_DROP + 1e-9
        ):
            reasons.append(
                f"忠实度 {faithfulness:.2%} 比基线 {baseline_faithfulness:.2%} "
                f"下降超过 {GATE_MAX_DROP:.0%}"
            )
    return {
        "passed": not reasons,
        "reasons": reasons,
        "accuracy": accuracy,
        "baseline_accuracy": baseline_accuracy,
        "faithfulness": faithfulness,
        "baseline_faithfulness": baseline_faithfulness,
        "checked": checked,
        "not_checked": not_checked,
    }


def attribute_failures(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """把没通过的样本按缺失工具计数。通过的样本不计入。没有缺失列表的失败记为 other。"""
    counts: Dict[str, int] = {}
    for item in results:
        if item.get("passed"):
            continue
        missing = _missing_tools(item.get("detail"))
        if not missing:
            counts["other"] = counts.get("other", 0) + 1
            continue
        for name in missing:
            counts[name] = counts.get(name, 0) + 1
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [{"tool": name, "count": count} for name, count in ranked]


def load_failure_board(
    db_path: Optional[Path] = None,
    history: int = 8,
) -> Dict[str, Any]:
    """读取最近几次评测。最新一次带失败样本；没有记录时 latest 为 None。

    summary 里已有 failure_attribution 就直接用。旧记录没有这个字段时，
    按失败样本的 detail 重新计数。
    """
    path = Path(db_path or TRACE_DB_PATH)
    ensure_eval_tables(path)
    limit = max(1, int(history))
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT id, dataset_name, dataset_version, mode, sample_count,
                   passed, summary_json, started_at, finished_at
            FROM eval_runs
            ORDER BY started_at DESC, rowid DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        if not rows:
            return {"latest": None, "earlier": []}
        failed_rows = conn.execute(
            """
            SELECT sample_id, detail
            FROM eval_results
            WHERE eval_run_id = ? AND passed = 0
            ORDER BY id ASC
            """,
            (rows[0]["id"],),
        ).fetchall()
    latest = _board_run(rows[0], failed_rows)
    earlier = [_board_run(row, []) for row in rows[1:]]
    for item in earlier:
        item["failed_samples"] = []
    return {"latest": latest, "earlier": earlier}


def _board_run(row: Any, failed_rows: List[Any]) -> Dict[str, Any]:
    summary = _load_summary(row["summary_json"])
    failed_samples = [
        {
            "sample_id": str(item["sample_id"]),
            "missing": _missing_tools(item["detail"]),
        }
        for item in failed_rows
    ]
    attribution = _stored_attribution(summary)
    if attribution is None:
        attribution = attribute_failures(
            [{"passed": False, "detail": item["detail"]} for item in failed_rows]
        )
    sample_count = int(row["sample_count"] or 0)
    passed_count = int(row["passed"] or 0)
    accuracy = summary.get("accuracy")
    if not isinstance(accuracy, (int, float)):
        accuracy = (passed_count / sample_count) if sample_count else 0.0
    faithfulness = summary.get("faithfulness")
    if faithfulness is not None and not isinstance(faithfulness, (int, float)):
        faithfulness = None
    return {
        "id": row["id"],
        "dataset_name": row["dataset_name"] or "",
        "dataset_version": row["dataset_version"] or "",
        "mode": row["mode"] or "",
        "sample_count": sample_count,
        "passed_count": passed_count,
        "accuracy": float(accuracy),
        "faithfulness": None if faithfulness is None else float(faithfulness),
        "failure_attribution": attribution,
        "failed_samples": failed_samples,
        "started_at": row["started_at"] or "",
        "finished_at": row["finished_at"] or "",
        "gate": check_release_gate(
            float(accuracy),
            faithfulness=None if faithfulness is None else float(faithfulness),
        ),
    }


def _load_summary(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _stored_attribution(summary: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    if "failure_attribution" not in summary:
        return None
    stored = summary.get("failure_attribution")
    if not isinstance(stored, list):
        return None
    cleaned = []
    for item in stored:
        if not isinstance(item, dict) or "tool" not in item or "count" not in item:
            return None
        try:
            count = int(item["count"])
        except (TypeError, ValueError):
            return None
        cleaned.append({"tool": str(item["tool"]), "count": count})
    return cleaned


def _missing_tools(detail: Any) -> List[str]:
    parsed = detail
    if isinstance(detail, str):
        try:
            parsed = json.loads(detail)
        except json.JSONDecodeError:
            return []
    if not isinstance(parsed, dict):
        return []
    missing = parsed.get("missing")
    if not isinstance(missing, list):
        return []
    return [str(name) for name in missing if name]


def mean_faithfulness(results: List[Dict[str, Any]]) -> Optional[float]:
    """只平均这次打了分的样本。没有检索片段的题不进来。"""
    scores = [
        float(item["faithfulness"])
        for item in results
        if item.get("faithfulness_applicable") and item.get("faithfulness") is not None
    ]
    if not scores:
        return None
    return sum(scores) / len(scores)


def _faithfulness_for_sample(sample: Dict[str, Any]) -> Dict[str, Any]:
    if "contexts" not in sample and "answer" not in sample:
        return {"applicable": False, "score": None, "grounded": 0, "claims": 0}
    from backend.platform.faithfulness import score_faithfulness

    return score_faithfulness(sample.get("answer") or "", sample.get("contexts") or [])


def dry_run(dataset: Dict[str, Any]) -> List[Dict[str, Any]]:
    unknown = validate_against_registry(dataset)
    if unknown:
        raise ValueError("评测集引用了未注册工具: " + ", ".join(unknown))
    results = []
    for item in dataset["samples"]:
        scored = _faithfulness_for_sample(item)
        results.append(
            {
                "sample_id": item["id"],
                "passed": True,
                "tools_used": item["expected_tools"],
                "detail": "schema_ok",
                "output": item.get("answer") or "",
                "faithfulness": scored["score"],
                "faithfulness_applicable": scored["applicable"],
            }
        )
    return results


def passages_from_rag_result(text: str) -> List[str]:
    """从 rag_search 的返回里取出正文。没找到或检索失败时返回空列表。"""
    raw = (text or "").strip()
    if not raw or raw.startswith(("知识库未启用", "未在知识库中找到", "知识库检索失败")):
        return []
    passages = []
    for part in raw.split("【资料")[1:]:
        body = part.split("\n", 1)[1].strip() if "\n" in part else ""
        if body:
            passages.append(body)
    return passages


def score_live_answer(answer: str, rag_results: Optional[List[str]]) -> Dict[str, Any]:
    """没调用检索时不打分。调用了就把回答和当次片段比较，没有片段则按空上下文记。"""
    from backend.platform.faithfulness import score_faithfulness

    if not rag_results:
        return {"applicable": False, "score": None, "grounded": 0, "claims": 0}
    contexts: List[str] = []
    for item in rag_results:
        contexts.extend(passages_from_rag_result(item))
    return score_faithfulness(answer, contexts)


def live_run(dataset: Dict[str, Any], limit: Optional[int] = None) -> List[Dict[str, Any]]:
    from backend.agents.react_agent import ReActStudyAgent

    agent = ReActStudyAgent(verbose=False, session_id="eval")
    samples = dataset["samples"] if limit is None else dataset["samples"][:limit]
    results = []
    for item in samples:
        agent.clear_history()
        outcome = agent.react(item["input"])
        judged = score_tool_selection(item["expected_tools"], outcome.tools_used)
        scored = score_live_answer(outcome.final_answer, outcome.rag_results)
        results.append(
            {
                "sample_id": item["id"],
                "passed": judged["passed"],
                "tools_used": outcome.tools_used,
                "detail": json.dumps(judged, ensure_ascii=False),
                "output": outcome.final_answer,
                "faithfulness": scored["score"],
                "faithfulness_applicable": scored["applicable"],
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="学习助手工具选择评测")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--dry-run", action="store_true", help="只校验评测集，不调用模型")
    parser.add_argument("--live", action="store_true", help="调用 Agent 并写入 eval_runs")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条，0 表示全部")
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    if args.live:
        results = live_run(dataset, limit=args.limit or None)
        mode = "live"
    else:
        results = dry_run(dataset)
        mode = "dry-run"
    run_id = save_eval_run(dataset, mode, results)
    passed = sum(1 for item in results if item["passed"])
    accuracy = passed / len(results) if results else 0.0
    faithfulness = mean_faithfulness(results)
    gate = check_release_gate(accuracy, faithfulness=faithfulness)
    faith_text = "不适用" if faithfulness is None else f"{faithfulness:.2%}"
    print(
        f"[{mode}] {dataset['name']}@{dataset['version']} "
        f"工具选择 {passed}/{len(results)}，忠实度 {faith_text}，eval_run={run_id}"
    )
    if gate["passed"]:
        if faithfulness is None:
            print("门禁通过（仅工具选择；这次没有可打分的忠实度）")
        else:
            print(f"门禁通过（工具选择 {accuracy:.2%}，忠实度 {faithfulness:.2%}）")
    else:
        print("门禁未通过: " + "；".join(gate["reasons"]))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
