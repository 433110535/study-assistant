"""页面通过 ASGI 调用本机 API，不另开端口。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional


def request_json(
    method: str,
    path: str,
    *,
    db_path: Optional[Path] = None,
    params: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
) -> Any:
    from fastapi.testclient import TestClient

    from backend.api.app import create_app

    key = os.getenv("STUDY_API_KEY", "").strip() if api_key is None else api_key
    app = create_app(db_path, api_key=key)
    headers = {"X-API-Key": key} if key else {}
    with TestClient(app) as client:
        response = client.request(method, path, params=params, headers=headers)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text}")
    return response.json()


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
