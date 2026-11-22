from __future__ import annotations

from uuid import uuid4

import pytest
from app.api.deps import get_current_user, get_runtime
from app.core.auth import AuthUser
from app.main import create_app
from fastapi.testclient import TestClient
from session_support import USER_A, USER_B, build_service


@pytest.fixture
def env():
    service = build_service()
    app = create_app()
    holder = {"user": AuthUser(id=USER_A, email="a@example.com")}
    app.dependency_overrides[get_current_user] = lambda: holder["user"]
    app.dependency_overrides[get_runtime] = lambda: service
    with TestClient(app) as client:
        yield client, holder, service
    service.close()


def test_session_crud_flow(env) -> None:
    client, _, _ = env
    created = client.post("/sessions", json={"title": "Phiên S3"})
    assert created.status_code == 201
    session = created.json()
    assert session["title"] == "Phiên S3"
    assert session["message_count"] == 0

    listed = client.get("/sessions")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == session["id"]

    renamed = client.patch(f"/sessions/{session['id']}", json={"title": "  S3 cơ bản  "})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "S3 cơ bản"

    messages = client.get(f"/sessions/{session['id']}/messages")
    assert messages.status_code == 200
    assert messages.json() == {"items": [], "total": 0}

    deleted = client.delete(f"/sessions/{session['id']}")
    assert deleted.status_code == 204
    assert client.get("/sessions").json()["total"] == 0


def test_chat_without_token_returns_401() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/sessions")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "missing_token"


def test_cross_user_access_is_denied(env) -> None:
    client, holder, _ = env
    session = client.post("/sessions", json={"title": "Riêng tư"}).json()

    holder["user"] = AuthUser(id=USER_B, email="b@example.com")
    assert client.get("/sessions").json()["total"] == 0
    assert client.get(f"/sessions/{session['id']}/messages").status_code == 404
    assert client.patch(f"/sessions/{session['id']}", json={"title": "x"}).status_code == 404
    assert client.delete(f"/sessions/{session['id']}").status_code == 404

    holder["user"] = AuthUser(id=USER_A, email="a@example.com")
    assert client.get("/sessions").json()["total"] == 1


def test_invalid_session_id_returns_400(env) -> None:
    client, _, _ = env
    response = client.get("/sessions/khong-phai-uuid/messages")
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_session_id"


def test_delete_all_sessions_only_affects_current_user(env) -> None:
    client, holder, service = env
    client.post("/sessions", json={"title": "A1"})
    client.post("/sessions", json={"title": "A2"})
    holder["user"] = AuthUser(id=USER_B, email="b@example.com")
    client.post("/sessions", json={"title": "B1"})
    holder["user"] = AuthUser(id=USER_A, email="a@example.com")

    response = client.delete("/sessions")
    assert response.status_code == 200
    assert response.json()["deleted"] == 2
    assert service.count_sessions(USER_A) == 0
    assert service.count_sessions(USER_B) == 1


def test_chat_creates_session_and_returns_compatible_payload(env) -> None:
    client, _, service = env
    response = client.post("/chat", json={"question": "S3 Standard phù hợp dữ liệu nào?"})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"].startswith("S3 Standard")
    assert body["session_id"]
    assert body["rewritten_query"] == "S3 Standard phù hợp dữ liệu nào?"
    assert body["replayed"] is False
    assert body["provider"] == "fake"

    unknown = client.post(
        "/chat", json={"session_id": str(uuid4()), "question": "S3 Standard là gì?"}
    )
    assert unknown.status_code == 404
    assert unknown.json()["detail"]["code"] == "session_not_found"
    assert service.count_sessions(USER_A) == 1
