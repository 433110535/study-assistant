"""页面通过 ASGI 调用本机 API，不另开端口。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional


def request_json(
    method: str,
    path: str,
    *,
    db_path: Optional[Path] = None,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
) -> Any:
    from fastapi.testclient import TestClient

    from backend.api.app import create_app

    key = os.getenv("STUDY_API_KEY", "").strip() if api_key is None else api_key
    app = create_app(db_path, api_key=key)
    headers = {"X-API-Key": key} if key else {}
    with TestClient(app) as client:
        response = client.request(
            method,
            path,
            params=params,
            json=json_body,
            headers=headers,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text}")
    return response.json()


def parse_sse(payload: str) -> list:
    """读出 SSE 正文里的 data 行。空行和别的字段忽略。"""
    events = []
    for line in payload.splitlines():
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[len("data: ") :]))
    return events


def iter_chat_events(
    message: str,
    agent_factory: Optional[Callable[[], Any]] = None,
    db_path: Optional[Path] = None,
) -> Iterator[Dict[str, Any]]:
    """向 /v1/chat/stream 取事件。传入 agent_factory 时沿用那个 Agent。"""
    from fastapi.testclient import TestClient

    from backend.api.app import create_app

    key = os.getenv("STUDY_API_KEY", "").strip()
    app = create_app(db_path, api_key=key, agent_factory=agent_factory)
    headers = {"X-API-Key": key} if key else {}
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/stream",
            json={"message": message},
            headers=headers,
        )
    if response.status_code >= 400:
        raise RuntimeError(
            f"POST /v1/chat/stream -> {response.status_code}: {response.text}"
        )
    yield from parse_sse(response.text)


def grade_one_item(
    question: str,
    student: str,
    correct: str,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    return request_json(
        "POST",
        "/v1/items/grade",
        db_path=db_path,
        json_body={"question": question, "student": student, "correct": correct},
    )


def create_user_mistake(
    user_id: str,
    subject: str,
    concept: str,
    error_type: str,
    question_text: str,
    student_answer: str,
    correct_answer: str,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    return request_json(
        "POST",
        "/v1/mistakes",
        db_path=db_path,
        json_body={
            "user_id": user_id,
            "subject": subject,
            "concept": concept,
            "error_type": error_type,
            "question_text": question_text,
            "student_answer": student_answer,
            "correct_answer": correct_answer,
        },
    )


def grade_paper_text(
    text: str,
    enhanced: bool = False,
    auto_collect_mistakes: bool = False,
    user_id: str = "student",
    subject: str = "数学",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"text": text}
    if enhanced:
        body["enhanced"] = True
    if auto_collect_mistakes:
        body["auto_collect_mistakes"] = True
        body["user_id"] = user_id
        body["subject"] = subject
    return request_json(
        "POST",
        "/v1/papers/grade",
        db_path=db_path,
        json_body=body,
    )


def schedule_text(
    topics: list,
    available_hours: float = 2.0,
    include_break: bool = False,
    break_duration: int = 15,
    db_path: Optional[Path] = None,
) -> str:
    data = request_json(
        "POST",
        "/v1/schedules",
        db_path=db_path,
        json_body={
            "topics": topics,
            "available_hours": available_hours,
            "include_break": include_break,
            "break_duration": break_duration,
        },
    )
    return str(data.get("text") or "")


def plan_text(
    subject: str,
    goal: str,
    duration_days: int,
    current_level: str = "初学者",
    hours_per_day: float = 2.0,
    db_path: Optional[Path] = None,
) -> str:
    data = request_json(
        "POST",
        "/v1/plans",
        db_path=db_path,
        json_body={
            "subject": subject,
            "goal": goal,
            "duration_days": duration_days,
            "current_level": current_level,
            "hours_per_day": hours_per_day,
        },
    )
    return str(data.get("text") or "")


def questions_text(
    topic: str,
    difficulty: str = "中等",
    count: int = 3,
    question_type: str = "mixed",
    db_path: Optional[Path] = None,
) -> str:
    data = request_json(
        "POST",
        "/v1/questions",
        db_path=db_path,
        json_body={
            "topic": topic,
            "difficulty": difficulty,
            "count": count,
            "question_type": question_type,
        },
    )
    return str(data.get("text") or "")


def compare_text(
    concept1: str,
    concept2: str,
    db_path: Optional[Path] = None,
) -> str:
    data = request_json(
        "POST",
        "/v1/compare",
        db_path=db_path,
        json_body={"concept1": concept1, "concept2": concept2},
    )
    return str(data.get("text") or "")


def explain_text(
    concept: str,
    subject: str = "",
    level: str = "初学者",
    db_path: Optional[Path] = None,
) -> str:
    data = request_json(
        "POST",
        "/v1/explain",
        db_path=db_path,
        json_body={"concept": concept, "subject": subject, "level": level},
    )
    return str(data.get("text") or "")


def failure_board(db_path: Optional[Path] = None) -> Dict[str, Any]:
    return request_json("GET", "/v1/eval/latest", db_path=db_path)


def list_user_mistakes(
    user_id: str,
    status: str = "",
    db_path: Optional[Path] = None,
) -> list:
    data = request_json(
        "GET",
        "/v1/mistakes",
        db_path=db_path,
        params={"user_id": user_id, "status": status},
    )
    return data["mistakes"]


def confirm_user_mistake(mistake_id: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
    return request_json("POST", f"/v1/mistakes/{mistake_id}/confirm", db_path=db_path)


def dismiss_user_mistake(mistake_id: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
    return request_json("POST", f"/v1/mistakes/{mistake_id}/dismiss", db_path=db_path)


def due_reviews(
    user_id: str,
    now: str = "",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"user_id": user_id}
    if now:
        params["now"] = now
    return request_json("GET", "/v1/review/due", db_path=db_path, params=params)


def remember_review(
    mistake_id: str,
    quality: int,
    now: str = "",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"quality": quality}
    if now:
        body["now"] = now
    return request_json(
        "POST",
        f"/v1/mistakes/{mistake_id}/review",
        db_path=db_path,
        json_body=body,
    )


def move_review(
    mistake_id: str,
    when_text: str,
    now: str = "",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"when_text": when_text}
    if now:
        body["now"] = now
    return request_json(
        "POST",
        f"/v1/mistakes/{mistake_id}/reschedule",
        db_path=db_path,
        json_body=body,
    )


def save_review_card(
    user_id: str,
    now: str = "",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"user_id": user_id}
    if now:
        body["now"] = now
    return request_json("POST", "/v1/review/cards", db_path=db_path, json_body=body)


def list_review_cards(user_id: str, db_path: Optional[Path] = None) -> list:
    data = request_json(
        "GET",
        "/v1/review/outbox",
        db_path=db_path,
        params={"user_id": user_id},
    )
    return data["cards"]



def get_documents_api(
    user_id: str = "student",
    subject: str = "",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    params = {}
    if user_id:
        params["user_id"] = user_id
    if subject:
        params["subject"] = subject
    return request_json("GET", "/v1/documents", db_path=db_path, params=params)


def ingest_document_api(
    title: str,
    content_text: str = "",
    pdf_base64: str = "",
    subject: str = "未分类",
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    user_id: str = "student",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    return request_json(
        "POST",
        "/v1/documents",
        db_path=db_path,
        json_body={
            "title": title,
            "content_text": content_text,
            "pdf_base64": pdf_base64,
            "subject": subject,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "user_id": user_id,
        },
    )


def delete_document_api(
    doc_id: str,
    user_id: str = "student",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    return request_json(
        "DELETE",
        f"/v1/documents/{doc_id}",
        db_path=db_path,
        params={"user_id": user_id},
    )


def search_documents_api(
    query: str,
    top_k: int = 5,
    subject: str = "",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"query": query, "top_k": top_k}
    if subject:
        body["subject"] = subject
    return request_json(
        "POST",
        "/v1/documents/search",
        db_path=db_path,
        json_body=body,
    )


def ask_documents_api(
    question: str,
    top_k: int = 3,
    subject: str = "",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"question": question, "top_k": top_k}
    if subject:
        body["subject"] = subject
    return request_json(
        "POST",
        "/v1/documents/ask",
        db_path=db_path,
        json_body=body,
    )


def list_mastery_api(
    user_id: str = "student",
    db_path: Optional[Path] = None,
) -> list:
    data = request_json(
        "GET",
        "/v1/mastery",
        db_path=db_path,
        params={"user_id": user_id},
    )
    return data.get("mastery", [])
