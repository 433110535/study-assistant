"""
本机只读和少量确认接口。默认没有 API Key 时只建议绑在 127.0.0.1。

不提供流式问答，也不连接 Postgres。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException

from backend.config import TRACE_DB_PATH


def create_app(
    db_path: Optional[Path] = None,
    api_key: str = "",
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

    @app.get("/v1/review/plan", dependencies=guard)
    def review_plan(user_id: str = "student") -> dict:
        from backend.platform.review_planner import get_learning_state
        from backend.tools.review_schedule import format_morning_card

        due = get_learning_state(user_id, db_path=database)["due"]
        return {"count": len(due), "body": format_morning_card(due)}

    return app


def main() -> None:
    import uvicorn

    app = create_app(api_key=os.getenv("STUDY_API_KEY", "").strip())
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
