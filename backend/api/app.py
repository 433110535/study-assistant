"""
本机接口。默认没有 API Key 时只建议绑在 127.0.0.1。

问答流式接口会调用 Agent。测试可以传入 agent_factory，避免请求模型。
不连接 Postgres。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from datetime import datetime

from fastapi import Body, Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse

from backend.config import TRACE_DB_PATH


def _break_minutes(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    minutes = int(value)
    if minutes < 5 or minutes > 30:
        return None
    return minutes


def _plan_days(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    days = int(value)
    if days < 7 or days > 90:
        return None
    return days


def _plan_hours(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    hours = float(value)
    if hours < 0.5 or hours > 8:
        return None
    return hours


def _question_count(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    count = int(value)
    if count < 1 or count > 10:
        return None
    return count


def _parse_now(value: str):
    text = (value or "").strip()
    if not text:
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def encode_sse(event: Any) -> str:
    """把一条 ReAct 事件写成一行 SSE。"""
    if hasattr(event, "model_dump"):
        data = event.model_dump(mode="json")
    else:
        data = dict(event)
    return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"


def iter_chat_sse(agent: Any, message: str) -> Iterator[str]:
    for event in agent.react_stream(message):
        yield encode_sse(event)


def create_app(
    db_path: Optional[Path] = None,
    api_key: str = "",
    agent_factory: Optional[Callable[[], Any]] = None,
    explain_fn: Optional[Callable[..., str]] = None,
    compare_fn: Optional[Callable[..., str]] = None,
    questions_fn: Optional[Callable[..., str]] = None,
    plan_fn: Optional[Callable[..., str]] = None,
    schedule_fn: Optional[Callable[..., str]] = None,
) -> FastAPI:
    database = Path(db_path) if db_path is not None else TRACE_DB_PATH
    app = FastAPI(title="学习助手", version="0.1.0")

    def require_key(x_api_key: str = Header(default="")) -> None:
        if api_key and x_api_key != api_key:
            raise HTTPException(status_code=401, detail="需要 X-API-Key")

    guard = [Depends(require_key)]

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/v1/tools", dependencies=guard)
    def tools() -> dict:
        import backend.agents.react_tools  # noqa: F401
        from backend.agents.tool_registry import get_all_specs

        rows = [
            {
                "name": spec.name,
                "side_effects": spec.side_effects,
                "requires_approval": spec.requires_approval,
                "timeout_s": spec.timeout_s,
                "retries": spec.retries,
                "cost_hint": spec.cost_hint,
            }
            for spec in get_all_specs()
        ]
        return {"tools": rows}

    @app.get("/v1/traces/{trace_id}", dependencies=guard)
    def trace(trace_id: str) -> dict:
        from backend.platform.trace_store import get_trace

        found = get_trace(trace_id, db_path=database)
        if found is None:
            raise HTTPException(status_code=404, detail="没有这次运行")
        return found

    @app.get("/v1/datasets", dependencies=guard)
    def datasets() -> dict:
        from backend.platform.dataset_catalog import list_versions

        return {"versions": list_versions(db_path=database)}

    @app.get("/v1/eval/latest", dependencies=guard)
    def latest_eval() -> dict:
        from backend.platform.eval_runner import load_failure_board

        return load_failure_board(database)

    @app.get("/v1/mistakes", dependencies=guard)
    def mistakes(user_id: str = "student", status: str = "") -> dict:
        from backend.platform.mistake_store import list_mistakes

        rows = list_mistakes(user_id, status=status or None, db_path=database)
        return {"mistakes": rows}

    @app.post("/v1/mistakes/{mistake_id}/confirm", dependencies=guard)
    def confirm(mistake_id: str) -> dict:
        from backend.platform.mistake_store import confirm_mistake

        if not confirm_mistake(mistake_id, db_path=database):
            raise HTTPException(status_code=404, detail="没有可确认的待确认错题")
        return {"id": mistake_id, "status": "confirmed"}

    @app.post("/v1/mistakes/{mistake_id}/dismiss", dependencies=guard)
    def dismiss(mistake_id: str) -> dict:
        from backend.platform.mistake_store import dismiss_mistake

        if not dismiss_mistake(mistake_id, db_path=database):
            raise HTTPException(status_code=404, detail="没有可丢弃的待确认错题")
        return {"id": mistake_id, "status": "dismissed"}

    @app.get("/v1/review/due", dependencies=guard)
    def review_due(user_id: str = "student", now: str = "") -> dict:
        from backend.platform.review_planner import get_learning_state

        due = get_learning_state(user_id, now=_parse_now(now), db_path=database)["due"]
        return {"due": due}

    @app.post("/v1/mistakes/{mistake_id}/review", dependencies=guard)
    def mark_review(mistake_id: str, payload: dict = Body(...)) -> dict:
        from backend.platform.review_planner import record_review

        quality = payload.get("quality")
        if not isinstance(quality, int) or quality < 0 or quality > 5:
            raise HTTPException(status_code=400, detail="quality 必须是 0 到 5 的整数")
        saved = record_review(
            mistake_id,
            quality,
            reviewed_at=_parse_now(str(payload.get("now") or "")),
            db_path=database,
        )
        if not saved:
            raise HTTPException(status_code=404, detail="没有可记回忆的已确认错题")
        return saved

    @app.post("/v1/mistakes/{mistake_id}/reschedule", dependencies=guard)
    def move_review(mistake_id: str, payload: dict = Body(...)) -> dict:
        from backend.platform.review_planner import reschedule

        when_text = str(payload.get("when_text") or "")
        if not reschedule(
            mistake_id,
            when_text,
            now=_parse_now(str(payload.get("now") or "")),
            db_path=database,
        ):
            raise HTTPException(status_code=404, detail="没有可改期的已确认错题")
        return {"id": mistake_id, "when_text": when_text}

    @app.post("/v1/review/cards", dependencies=guard)
    def save_card(payload: dict = Body(...)) -> dict:
        from backend.platform.review_planner import run_review_push

        user_id = str(payload.get("user_id") or "student")
        return run_review_push(
            user_id,
            now=_parse_now(str(payload.get("now") or "")),
            db_path=database,
        )

    @app.get("/v1/review/outbox", dependencies=guard)
    def outbox(user_id: str = "student") -> dict:
        from backend.platform.review_planner import list_outbox

        return {"cards": list_outbox(user_id, db_path=database)}

    @app.get("/v1/review/plan", dependencies=guard)
    def review_plan(user_id: str = "student") -> dict:
        from backend.platform.review_planner import get_learning_state
        from backend.tools.review_schedule import format_morning_card

        due = get_learning_state(user_id, db_path=database)["due"]
        return {"count": len(due), "body": format_morning_card(due)}

    def new_agent() -> Any:
        if agent_factory is not None:
            return agent_factory()
        from backend.agents.react_agent import ReActStudyAgent

        return ReActStudyAgent(verbose=False, session_id="api")

    @app.post("/v1/chat/stream", dependencies=guard)
    def chat_stream(payload: dict = Body(...)) -> StreamingResponse:
        message = str(payload.get("message") or "").strip()
        if not message:
            raise HTTPException(status_code=400, detail="message 不能为空")
        agent = new_agent()
        return StreamingResponse(
            iter_chat_sse(agent, message),
            media_type="text/event-stream",
        )

    @app.post("/v1/explain", dependencies=guard)
    def explain(payload: dict = Body(...)) -> dict:
        concept = str(payload.get("concept") or "").strip()
        if not concept:
            raise HTTPException(status_code=400, detail="concept 不能为空")
        subject = str(payload.get("subject") or "")
        level = str(payload.get("level") or "初学者")
        fn = explain_fn
        if fn is None:
            from backend.tools.knowledge import explain_concept

            fn = explain_concept
        return {"text": fn(concept, subject, level)}

    @app.post("/v1/compare", dependencies=guard)
    def compare(payload: dict = Body(...)) -> dict:
        left = str(payload.get("concept1") or "").strip()
        right = str(payload.get("concept2") or "").strip()
        if not left or not right:
            raise HTTPException(status_code=400, detail="需要两个概念")
        fn = compare_fn
        if fn is None:
            from backend.tools.knowledge import compare_concepts

            fn = compare_concepts
        return {"text": fn(left, right)}

    @app.post("/v1/questions", dependencies=guard)
    def questions(payload: dict = Body(...)) -> dict:
        topic = str(payload.get("topic") or "").strip()
        count = _question_count(payload.get("count", 3))
        if not topic:
            raise HTTPException(status_code=400, detail="topic 不能为空")
        if count is None:
            raise HTTPException(status_code=400, detail="count 必须是 1 到 10 的整数")
        difficulty = str(payload.get("difficulty") or "中等")
        question_type = str(payload.get("question_type") or "mixed")
        fn = questions_fn
        if fn is None:
            from backend.tools.question_generator import generate_questions

            fn = generate_questions
        return {"text": fn(topic, difficulty, count, question_type)}

    @app.post("/v1/plans", dependencies=guard)
    def plans(payload: dict = Body(...)) -> dict:
        subject = str(payload.get("subject") or "").strip()
        goal = str(payload.get("goal") or "").strip()
        days = _plan_days(payload.get("duration_days", 30))
        hours = _plan_hours(payload.get("hours_per_day", 2))
        if not subject or not goal:
            raise HTTPException(status_code=400, detail="subject 和 goal 不能为空")
        if days is None or hours is None:
            raise HTTPException(status_code=400, detail="学习天数须为 7 到 90，每日时长须为 0.5 到 8 小时")
        level = str(payload.get("current_level") or "初学者")
        fn = plan_fn
        if fn is None:
            from backend.tools.plan_generator import generate_study_plan

            fn = generate_study_plan
        return {"text": fn(subject, goal, days, level, hours)}

    @app.post("/v1/schedules", dependencies=guard)
    def schedules(payload: dict = Body(...)) -> dict:
        raw_topics = payload.get("topics")
        if not isinstance(raw_topics, list):
            raise HTTPException(status_code=400, detail="topics 必须是非空列表")
        topics = [str(item).strip() for item in raw_topics if str(item).strip()]
        hours = _plan_hours(payload.get("available_hours", 2))
        include_break = payload.get("include_break", False)
        if not isinstance(include_break, bool):
            raise HTTPException(status_code=400, detail="include_break 必须是布尔值")
        break_duration = _break_minutes(payload.get("break_duration", 15))
        if not topics:
            raise HTTPException(status_code=400, detail="至少要有一个学习主题")
        if hours is None or break_duration is None:
            raise HTTPException(status_code=400, detail="可用时长须为 0.5 到 8 小时，休息须为 5 到 30 分钟")
        fn = schedule_fn
        if fn is None:
            from backend.tools.plan_generator import create_daily_schedule

            fn = create_daily_schedule
        return {"text": fn(topics, hours, include_break, break_duration)}

    return app


def main() -> None:
    import uvicorn

    app = create_app(api_key=os.getenv("STUDY_API_KEY", "").strip())
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
