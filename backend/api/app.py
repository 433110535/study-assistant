"""
本机接口。默认没有 API Key 时只建议绑在 127.0.0.1。

问答流式接口会调用 Agent。测试可以传入 agent_factory，避免请求模型。
不连接 Postgres。
"""
from __future__ import annotations

import hmac
import json
import os
import secrets
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional

from datetime import datetime

from fastapi import Body, Cookie, Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from backend.config import TRACE_DB_PATH
from backend.platform.auth_store import (
    init_auth_db,
    create_web_session,
    get_web_session,
    revoke_web_session,
)
from backend.platform.chat_store import init_chat_db
from backend.platform.code_attempt_store import init_code_attempt_db
from backend.platform.domain_store import (
    init_domain_db,
    add_document_record,
    list_document_records,
    delete_document_record,
    sync_legacy_documents,
    upsert_mastery,
    list_mastery,
    log_write_audit,
)


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
    paper_fn: Optional[Callable[..., Dict[str, Any]]] = None,
    kb_factory: Optional[Callable[[], Any]] = None,
    rag_ask_fn: Optional[Callable[..., str]] = None,
    auth_mode: Optional[str] = None,
    ocr_fn: Optional[Callable[..., str]] = None,
) -> FastAPI:
    database = Path(db_path) if db_path is not None else TRACE_DB_PATH
    init_domain_db(database)

    current_auth_mode = (auth_mode if auth_mode is not None else os.getenv("AUTH_MODE", "local")).strip().lower()

    app = FastAPI(title="学习助手", version="0.1.0")

    cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    dist_dir = Path("web_UI/dist")
    if dist_dir.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/app", StaticFiles(directory=str(dist_dir), html=True), name="web_ui")

    failed_login_attempts: Dict[str, list[float]] = {}
    _rate_limit_lock = threading.Lock()

    def _check_rate_limit(client_id: str) -> None:
        now = time.time()
        with _rate_limit_lock:
            recent = [t for t in failed_login_attempts.get(client_id, []) if now - t < 60.0]
            failed_login_attempts[client_id] = recent
            if len(recent) >= 5:
                raise HTTPException(status_code=429, detail="尝试次数过多，请稍后再试")

    def _record_failure(client_id: str) -> None:
        with _rate_limit_lock:
            failed_login_attempts.setdefault(client_id, []).append(time.time())

    def _clear_failure(client_id: str) -> None:
        with _rate_limit_lock:
            failed_login_attempts.pop(client_id, None)

    def require_key(
        request: Request,
        x_api_key: str = Header(default=""),
        study_session: Optional[str] = Cookie(default=None),
    ) -> Dict[str, Any]:
        if api_key and x_api_key:
            if hmac.compare_digest(x_api_key, api_key):
                return {"user_id": "student", "auth_type": "api_key"}
            raise HTTPException(status_code=401, detail="需要 X-API-Key")

        token = study_session
        if not token:
            auth_hdr = request.headers.get("Authorization", "")
            if auth_hdr.startswith("Bearer "):
                token = auth_hdr[7:].strip()
        if token:
            sess = get_web_session(token, db_path=database)
            if sess:
                return {"user_id": sess["user_id"], "auth_type": "session"}

        if api_key:
            raise HTTPException(status_code=401, detail="需要 X-API-Key")
        if current_auth_mode == "password":
            raise HTTPException(status_code=401, detail="未登录")

        return {"user_id": "student", "auth_type": "local"}

    guard = [Depends(require_key)]

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/v1/auth/login")
    def login(request: Request, payload: dict = Body(...)) -> Response:
        client_id = request.client.host if request.client else "local"
        _check_rate_limit(client_id)
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "").strip()
        expected_user = os.getenv("APP_USERNAME", "student").strip() or "student"
        expected_pass = os.getenv("APP_PASSWORD", "study2026").strip()
        if not username or not password or not expected_pass or not (
            hmac.compare_digest(username, expected_user) and hmac.compare_digest(password, expected_pass)
        ):
            _record_failure(client_id)
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        _clear_failure(client_id)
        token = secrets.token_urlsafe(32)
        sess = create_web_session(username, token, db_path=database)
        resp = JSONResponse(content={"user_id": username, "expires_at": sess["expires_at"], "token": token})
        resp.set_cookie(
            key="study_session",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 7,
        )
        return resp


    @app.post("/v1/auth/logout")
    def logout(request: Request, study_session: Optional[str] = Cookie(default=None)) -> Response:
        token = study_session
        if not token:
            auth_hdr = request.headers.get("Authorization", "")
            if auth_hdr.startswith("Bearer "):
                token = auth_hdr[7:].strip()
        if token:
            revoke_web_session(token, db_path=database)
        resp = Response(status_code=204)
        resp.delete_cookie(key="study_session")
        return resp

    @app.get("/v1/auth/me")
    def auth_me(user: Dict[str, Any] = Depends(require_key)) -> dict:
        if current_auth_mode == "local":
            return {"user_id": user.get("user_id", "student"), "mode": "local"}
        return {"user_id": user.get("user_id", "student"), "mode": current_auth_mode}

    @app.get("/v1/sessions")
    def list_sessions_route(
        user_id: str = "student",
        limit: int = 50,
        offset: int = 0,
        current_user: Dict[str, Any] = Depends(require_key),
    ) -> dict:
        from backend.platform.chat_store import list_sessions_summary

        effective_user = current_user["user_id"] if current_user.get("auth_type") == "session" else (user_id or "student")
        return list_sessions_summary(
            user_id=effective_user,
            limit=limit,
            offset=offset,
            db_path=database,
        )

    @app.get("/v1/sessions/{session_id}/messages")
    def get_session_messages_route(
        session_id: str,
        current_user: Dict[str, Any] = Depends(require_key),
    ) -> dict:
        from backend.platform.chat_store import get_session, load_session_messages_detailed

        sess = get_session(session_id, db_path=database)
        if sess is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        if current_user.get("auth_type") == "session" and sess.get("user_id") != current_user.get("user_id"):
            raise HTTPException(status_code=404, detail="会话不存在")
        messages = load_session_messages_detailed(session_id, db_path=database)
        return {"session_id": session_id, "messages": messages}

    @app.post("/v1/sessions")
    def create_session_route(
        payload: dict = Body(default={}),
        current_user: Dict[str, Any] = Depends(require_key),
    ) -> dict:
        from backend.platform.chat_store import start_session

        if current_user.get("auth_type") == "session":
            user_id = current_user.get("user_id", "student")
        else:
            user_id = str(payload.get("user_id") or "student").strip() or "student"
        title = str(payload.get("title") or "新对话").strip() or "新对话"
        session_id = start_session(user_id=user_id, title=title, db_path=database)
        return {"session_id": session_id}

    @app.post("/v1/vision/ocr")
    async def vision_ocr_route(
        file: UploadFile = File(...),
        focus: str = Form(default="全部"),
        current_user: Dict[str, Any] = Depends(require_key),
    ) -> dict:
        filename = file.filename or ""
        suffix = Path(filename).suffix.lower() if filename else ""
        allowed_exts = {".jpg", ".jpeg", ".png", ".webp"}
        allowed_mimes = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
        content_type = (file.content_type or "").lower()

        if suffix:
            if suffix not in allowed_exts:
                raise HTTPException(status_code=400, detail="不支持的图片格式，仅支持 JPEG/PNG/WebP")
        else:
            if content_type not in allowed_mimes:
                raise HTTPException(status_code=400, detail="不支持的图片格式，仅支持 JPEG/PNG/WebP")

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="上传图片为空")
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="图片大小超过 5MB 限制")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix or ".jpg") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        t0 = time.perf_counter()
        try:
            reader = ocr_fn
            if reader is None:
                from backend.tools.vision import read_image

                reader = read_image
            text = reader(tmp_path, focus=focus)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"视觉模型调用失败: {e}")
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        if not isinstance(text, str):
            text = str(text)

        if text.startswith("未配置 DASHSCOPE_API_KEY"):
            raise HTTPException(status_code=503, detail=text)
        if text.startswith("图片不存在或不可读"):
            raise HTTPException(status_code=400, detail=text)
        if text.startswith("读取图片失败") or text.startswith("图片预处理失败"):
            raise HTTPException(status_code=400, detail=text)
        if text.startswith("视觉模型调用失败") or text.startswith("视觉模型返回错误"):
            raise HTTPException(status_code=502, detail=text)
        if text.startswith("未能从模型响应中解析识别文本"):
            raise HTTPException(status_code=502, detail=text)

        return {
            "text": text,
            "model": os.getenv("VISION_MODEL", "qwen-vl-max"),
            "elapsed_ms": elapsed_ms,
        }

    @app.post("/v1/code/run")
    def run_code_route(
        payload: dict = Body(...),
        current_user: Dict[str, Any] = Depends(require_key),
    ) -> dict:
        code = str(payload.get("code") or "")
        if len(code.encode("utf-8")) > 50 * 1024 or len(code) > 50 * 1024:
            raise HTTPException(status_code=400, detail="代码长度超过 50KB 限制")
        tests = str(payload.get("tests") or "")
        if len(tests.encode("utf-8")) > 50 * 1024 or len(tests) > 50 * 1024:
            raise HTTPException(status_code=400, detail="测试代码长度超过 50KB 限制")
        raw_timeout = payload.get("timeout_s", 2.0)
        try:
            timeout_s = float(raw_timeout)
        except (TypeError, ValueError):
            timeout_s = 2.0
        from backend.platform.code_attempt_store import new_thread_id, append_attempt
        from backend.tools.code_sandbox import run_student_code

        thread_id = str(payload.get("thread_id") or "").strip() or new_thread_id()
        if current_user.get("auth_type") == "session":
            user_id = current_user.get("user_id", "student")
        else:
            user_id = str(payload.get("user_id") or "student").strip() or "student"

        result = run_student_code(code, tests=tests, timeout_s=timeout_s)
        append_attempt(
            user_id=user_id,
            thread_id=thread_id,
            code=code,
            tests=tests,
            result=result,
            db_path=database,
        )

        status = result.get("status") or "error"
        stderr = result.get("stderr") or ""
        if not stderr and status != "passed":
            stderr = result.get("exception_message") or ""

        return {
            "status": status,
            "stdout": result.get("stdout") or "",
            "stderr": stderr,
            "exit_code": 0 if status == "passed" else 1,
            "duration_ms": int(result.get("latency_ms") or 0),
            "timed_out": bool(status == "timeout"),
            "thread_id": thread_id,
        }

    @app.post("/v1/code/hint")
    def code_hint_route(
        payload: dict = Body(...),
        current_user: Dict[str, Any] = Depends(require_key),
    ) -> dict:
        raw_level = payload.get("level", 1)
        try:
            level = int(raw_level)
        except (TypeError, ValueError):
            level = 1
        observation = str(payload.get("observation") or "")
        from backend.tools.code_sandbox import hint_for_level

        hint = hint_for_level(level=level, observation=observation)
        return {"hint": hint}

    @app.get("/v1/code/attempts")
    def code_attempts_route(
        thread_id: str = "",
        user_id: str = "student",
        limit: int = 50,
        current_user: Dict[str, Any] = Depends(require_key),
    ) -> dict:
        from backend.platform.code_attempt_store import list_attempts, latest_thread

        effective_user = current_user["user_id"] if current_user.get("auth_type") == "session" else (user_id or "student")
        clamped_limit = max(0, min(int(limit), 200))
        tid = thread_id.strip() if thread_id else (latest_thread(effective_user, db_path=database) or "")
        attempts = list_attempts(user_id=effective_user, thread_id=tid, limit=clamped_limit, db_path=database) if tid else []
        return {"thread_id": tid, "attempts": attempts}

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

    @app.post("/v1/mistakes", dependencies=guard)
    def create_mistake(payload: dict = Body(...)) -> dict:
        from backend.platform.mistake_store import create_pending

        user_id = str(payload.get("user_id") or "student").strip() or "student"
        mistake_id = create_pending(
            user_id,
            subject=str(payload.get("subject") or "").strip() or "未填写",
            concept=str(payload.get("concept") or "").strip() or "未命名考点",
            error_type=str(payload.get("error_type") or "").strip() or "其他",
            question_text=str(payload.get("question_text") or ""),
            student_answer=str(payload.get("student_answer") or ""),
            correct_answer=str(payload.get("correct_answer") or ""),
            db_path=database,
        )
        return {"id": mistake_id, "status": "pending"}

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

    @app.post("/v1/papers/grade", dependencies=guard)
    def grade_paper_route(payload: dict = Body(...)) -> dict:
        text = str(payload.get("text") or "")
        if not text.strip():
            raise HTTPException(status_code=400, detail="text 不能为空")
        enhanced = bool(payload.get("enhanced", False))
        auto_collect = bool(payload.get("auto_collect_mistakes", False))
        user_id = str(payload.get("user_id") or "student").strip() or "student"
        subject = str(payload.get("subject") or "数学").strip() or "数学"

        fn = paper_fn
        if fn is None:
            from backend.tools.grading import grade_paper

            fn = grade_paper
        import inspect

        sig = inspect.signature(fn)
        if "enhanced" in sig.parameters:
            result = fn(text, enhanced=enhanced)
        else:
            result = fn(text)

        if not auto_collect:
            return result

        from backend.platform.domain_store import upsert_mastery
        from backend.platform.mistake_store import create_pending
        from backend.tools.grading import diagnose_error

        collected_ids = []
        for item in result.get("items", []):
            st = item.get("status")
            concept = item.get("concept") or "综合考点"
            delta = 0.1 if st == "correct" else (-0.15 if st in ("incorrect", "partial") else 0.0)
            upsert_mastery(concept=concept, is_correct=(st == 'correct'), user_id=user_id, db_path=database)

            if st in ("incorrect", "partial"):
                q_text = str(item.get("question") or "")
                s_ans = str(item.get("student_answer") or "")
                c_ans = str(item.get("correct_answer") or "")
                diag = diagnose_error(q_text, s_ans, c_ans)
                c_name = diag.get("concept") or concept
                e_type = diag.get("error_type") or "理解错误"
                m_id = create_pending(
                    user_id=user_id,
                    subject=subject,
                    concept=c_name,
                    error_type=e_type,
                    question_text=q_text,
                    student_answer=s_ans,
                    correct_answer=c_ans,
                    db_path=database,
                )
                collected_ids.append(m_id)

        resp = dict(result)
        resp["collected_mistake_ids"] = collected_ids
        resp["collected_count"] = len(collected_ids)
        return resp

    @app.post("/v1/items/grade", dependencies=guard)
    def grade_one(payload: dict = Body(...)) -> dict:
        from backend.tools.grading import diagnose_error, grade_item, make_variants

        question = str(payload.get("question") or "")
        student = str(payload.get("student") or "")
        correct = str(payload.get("correct") or "")
        graded = grade_item(question, student, correct)
        if graded["status"] != "incorrect":
            return {"graded": graded, "diagnosed": None, "variants": None}
        return {
            "graded": graded,
            "diagnosed": diagnose_error(question, student, correct),
            "variants": make_variants(question, 3),
        }


    def get_kb() -> Any:
        if kb_factory is not None:
            return kb_factory()
        try:
            from backend.knowledge.knowledge_base_faiss import FAISSKnowledgeBase
            return FAISSKnowledgeBase()
        except Exception:
            return None

    @app.get("/v1/documents", dependencies=guard)
    def get_documents_route(user_id: str = "student", subject: str = "") -> dict:
        sync_legacy_documents(database)
        docs = list_document_records(user_id=user_id or None, subject=subject or None, db_path=database)
        kb = get_kb()
        stats = kb.get_stats() if kb and hasattr(kb, "get_stats") else {}
        return {
            "documents": docs,
            "total_documents": len(docs),
            "total_chunks": sum(int(d.get("chunks", 0)) for d in docs),
            "stats": stats,
            "index_version": "faiss_v1",
        }

    @app.post("/v1/documents", dependencies=guard)
    def create_document(payload: dict = Body(...)) -> dict:
        title = str(payload.get("title") or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="title 不能为空")
        subject = str(payload.get("subject") or "未分类").strip() or "未分类"
        user_id = str(payload.get("user_id") or "student").strip() or "student"
        content_text = str(payload.get("content_text") or "")
        pdf_base64 = str(payload.get("pdf_base64") or "")
        chunk_size = int(payload.get("chunk_size", 500))
        chunk_overlap = int(payload.get("chunk_overlap", 50))
        doc_id = str(payload.get("doc_id") or title.replace(" ", "_")).strip()

        kb = get_kb()
        chunks = 0
        if pdf_base64 and kb is not None:
            import base64
            import tempfile
            raw = base64.b64decode(pdf_base64)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(raw)
                tmp_path = tmp.name
            try:
                ok = kb.add_pdf(
                    tmp_path,
                    doc_id=doc_id,
                    title=title,
                    subject=subject,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                if not ok:
                    raise HTTPException(status_code=500, detail="PDF 处理失败")
                doc_rec = getattr(kb, "doc_info", {}).get(doc_id, {})
                chunks = doc_rec.get("chunk_count", 0)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        elif content_text and kb is not None:
            ok = kb.add_text(
                content_text,
                doc_id=doc_id,
                title=title,
                subject=subject,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            if not ok:
                raise HTTPException(status_code=500, detail="文本处理失败")
            doc_rec = getattr(kb, "doc_info", {}).get(doc_id, {})
            chunks = doc_rec.get("chunk_count", 0)
        else:
            chunks = int(payload.get("chunks", 0))

        add_document_record(
            doc_id=doc_id,
            title=title,
            path="",
            subject=subject,
            chunks=chunks,
            user_id=user_id,
            db_path=database,
        )
        trace_id = log_write_audit(
            "kb_add_document",
            {"doc_id": doc_id, "title": title, "subject": subject, "chunks": chunks},
            user_id=user_id,
            db_path=database,
        )
        return {"doc_id": doc_id, "title": title, "chunks": chunks, "trace_id": trace_id}

    @app.delete("/v1/documents/{doc_id}", dependencies=guard)
    def remove_document(doc_id: str, user_id: str = "student") -> dict:
        kb = get_kb()
        if kb is not None and hasattr(kb, "delete_document"):
            kb.delete_document(doc_id)
        delete_document_record(doc_id, user_id=user_id, db_path=database)
        trace_id = log_write_audit(
            "kb_delete_document",
            {"doc_id": doc_id},
            user_id=user_id,
            db_path=database,
        )
        return {"deleted": True, "doc_id": doc_id, "trace_id": trace_id}

    @app.post("/v1/documents/search", dependencies=guard)
    def search_documents_route(payload: dict = Body(...)) -> dict:
        query = str(payload.get("query") or "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="query 不能为空")
        top_k = int(payload.get("top_k", 5))
        subject = payload.get("subject")
        kb = get_kb()
        results = kb.search(query, top_k=top_k, subject=subject) if kb and hasattr(kb, "search") else []
        return {"results": results, "count": len(results)}

    @app.post("/v1/documents/ask", dependencies=guard)
    def ask_documents_route(payload: dict = Body(...)) -> dict:
        question = str(payload.get("question") or "").strip()
        if not question:
            raise HTTPException(status_code=400, detail="question 不能为空")
        top_k = int(payload.get("top_k", 3))
        subject = payload.get("subject")
        kb = get_kb()
        results = kb.search(question, top_k=top_k, subject=subject) if kb and hasattr(kb, "search") else []
        if rag_ask_fn is not None:
            answer = rag_ask_fn(question, results)
        else:
            if results:
                context = "\n\n".join([
                    f"【资料{i+1}】(来源: {r.get('metadata', {}).get('title', '未知')})\n{r.get('content', '')}"
                    for i, r in enumerate(results)
                ])
            else:
                context = "未找到相关资料。"
            try:
                from backend.llm_helper import get_llm
                from langchain_core.prompts import ChatPromptTemplate
                llm = get_llm(temperature=0.7)
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "你是一个学习助手。请根据以下参考资料回答用户的问题。如果资料中没有相关信息，请如实说明，并结合自己的知识简要回答。\n\n参考资料：\n{context}"),
                    ("user", "{question}"),
                ])
                chain = prompt | llm
                resp = chain.invoke({"context": context, "question": question})
                answer = resp.content if hasattr(resp, "content") else str(resp)
            except Exception as e:
                answer = f"AI回答生成失败: {e}"

        sources = [r.get("metadata", {}).get("title", "未知") for r in results]
        trace_id = log_write_audit(
            "rag_ask",
            {"question": question, "sources_count": len(sources)},
            user_id="student",
            db_path=database,
        )
        return {"answer": answer, "sources": sources, "results": results, "trace_id": trace_id}

    @app.get("/v1/mastery", dependencies=guard)
    def mastery_route(user_id: str = "student") -> dict:
        return {"mastery": list_mastery(user_id, db_path=database)}

    @app.post("/v1/database/backup", dependencies=guard)
    def db_backup_route(payload: dict = Body(default={})) -> dict:
        from backend.platform.db_backup import backup_database, count_database_records

        dest_str = str(payload.get("dest") or "").strip()
        dest_path = Path(dest_str) if dest_str else None
        saved_path = backup_database(database, dest_path)
        counts = count_database_records(saved_path)
        return {"backup_path": str(saved_path), "records": counts}

    @app.post("/v1/database/restore", dependencies=guard)
    def db_restore_route(payload: dict = Body(...)) -> dict:
        from backend.platform.db_backup import count_database_records, restore_database

        backup_str = str(payload.get("backup_path") or "").strip()
        if not backup_str:
            raise HTTPException(status_code=400, detail="backup_path 不能为空")
        backup_path = Path(backup_str)
        if not backup_path.is_file():
            raise HTTPException(status_code=404, detail="备份文件不存在")
        restore_database(backup_path, database)
        counts = count_database_records(database)
        return {"restored": True, "records": counts}

    return app


def main() -> None:
    import uvicorn

    app = create_app(api_key=os.getenv("STUDY_API_KEY", "").strip())
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
