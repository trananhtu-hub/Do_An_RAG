from __future__ import annotations

import threading
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import AuthError, AuthUser, get_verifier
from app.services.sessions.postgres import PostgresSessionRepository
from app.services.sessions.types import SessionRepository

_bearer = HTTPBearer(auto_error=False, description="JWT của Supabase Auth")


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise api_error(401, "missing_token", "Cần đăng nhập để sử dụng tính năng này.") from None
    try:
        return get_verifier().verify(credentials.credentials)
    except AuthError as exc:
        if exc.status_code == 401:
            raise api_error(401, "invalid_token", str(exc)) from exc
        raise api_error(503, "auth_unavailable", str(exc)) from exc


_repository: SessionRepository | None = None
_repository_lock = threading.Lock()


def get_session_repository() -> SessionRepository:
    global _repository
    if _repository is None:
        with _repository_lock:
            if _repository is None:
                _repository = PostgresSessionRepository()
    return _repository


def set_session_repository(repository: SessionRepository | None) -> None:
    global _repository
    with _repository_lock:
        _repository = repository


def get_runtime() -> Any:
    """Dịch vụ chat đầy đủ, khởi tạo muộn để /health không kéo theo mô hình nặng."""
    from app.services.chat import get_chat_service

    return get_chat_service()
