"""
离线评测：校验固定问题集，并按工具选择是否覆盖预期工具打分。

用法：
    python -m backend.platform.eval_runner --dry-run
    python -m backend.platform.eval_runner --live
"""
from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import BASE_DIR, TRACE_DB_PATH
from backend.platform.trace_store import _connect, init_trace_db

DEFAULT_DATASET = BASE_DIR / "eval" / "datasets" / "qa_baseline_v3.json"

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
    run_id = str(uuid.uuid4())
    passed = sum(1 for item in results if item["passed"])
    now = _utc_now()
    summary = {
        "passed": passed,
        "total": len(results),
        "accuracy": round(passed / len(results), 4) if results else 0,
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


def dry_run(dataset: Dict[str, Any]) -> List[Dict[str, Any]]:
    unknown = validate_against_registry(dataset)
    if unknown:
        raise ValueError("评测集引用了未注册工具: " + ", ".join(unknown))
    return [
        {
            "sample_id": item["id"],
            "passed": True,
            "tools_used": item["expected_tools"],
            "detail": "schema_ok",
            "output": "",
        }
        for item in dataset["samples"]
    ]


def live_run(dataset: Dict[str, Any], limit: Optional[int] = None) -> List[Dict[str, Any]]:
    from backend.agents.react_agent import ReActStudyAgent

    agent = ReActStudyAgent(verbose=False, session_id="eval")
    samples = dataset["samples"] if limit is None else dataset["samples"][:limit]
    results = []
    for item in samples:
        agent.clear_history()
        outcome = agent.react(item["input"])
        judged = score_tool_selection(item["expected_tools"], outcome.tools_used)
        results.append(
            {
                "sample_id": item["id"],
                "passed": judged["passed"],
                "tools_used": outcome.tools_used,
                "detail": json.dumps(judged, ensure_ascii=False),
                "output": outcome.final_answer,
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
    gate = check_release_gate(accuracy)
    print(
        f"[{mode}] {dataset['name']}@{dataset['version']} "
        f"{passed}/{len(results)} 通过，eval_run={run_id}"
    )
    if gate["passed"]:
        print("门禁通过（仅工具选择；忠实度等指标未检查）")
    else:
        print("门禁未通过: " + "；".join(gate["reasons"]))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
