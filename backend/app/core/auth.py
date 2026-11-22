from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx

from app.core.config import get_settings


@dataclass(frozen=True)
class AuthUser:
    id: UUID
    email: str | None = None
    role: str = "authenticated"


class AuthError(Exception):
    def __init__(self, message: str, *, status_code: int = 401) -> None:
        super().__init__(message)
        self.status_code = status_code


def supabase_api_base(raw_url: str) -> str:
    """Bỏ hậu tố /rest/v1 nếu người dùng dán nguyên URL REST vào .env."""
    url = (raw_url or "").strip().rstrip("/")
    if not url:
        return ""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


class SupabaseTokenVerifier:
    def __init__(
        self,
        base_url: str,
        anon_key: str,
        *,
        cache_ttl_seconds: float = 60.0,
        timeout_seconds: float = 8.0,
        max_cache_entries: int = 1024,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = supabase_api_base(base_url)
        self._anon_key = anon_key.strip()
        self._cache_ttl = cache_ttl_seconds
        self._timeout = timeout_seconds
        self._max_cache = max_cache_entries
        self._cache: dict[str, tuple[float, AuthUser]] = {}
        self._lock = threading.Lock()
        self._client = httpx.Client(transport=transport)
        if not self._base_url or not self._anon_key:
            raise AuthError("Chưa cấu hình SUPABASE_URL và SUPABASE_ANON_KEY", status_code=503)

    def close(self) -> None:
        self._client.close()

    def verify(self, token: str) -> AuthUser:
        token = token.strip()
        if not token:
            raise AuthError("Token rỗng")
        cache_key = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None and cached[0] > now:
                return cached[1]

        try:
            response = self._client.get(
                f"{self._base_url}/auth/v1/user",
                headers={"apikey": self._anon_key, "authorization": f"Bearer {token}"},
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise AuthError(
                f"Không kết nối được Supabase Auth: {type(exc).__name__}",
                status_code=503,
            ) from exc

        if response.status_code in (401, 403):
            with self._lock:
                self._cache.pop(cache_key, None)
            raise AuthError("Token đăng nhập không hợp lệ hoặc đã hết hạn", status_code=401)
        if response.status_code != 200:
            raise AuthError(
                f"Supabase Auth trả HTTP {response.status_code}",
                status_code=503,
            )
        try:
            data: Any = response.json()
        except ValueError as exc:
            raise AuthError("Supabase Auth trả dữ liệu không hợp lệ", status_code=503) from exc
        if not isinstance(data, dict):
            raise AuthError("Supabase Auth trả dữ liệu không hợp lệ", status_code=503)
        raw_id = data.get("id")
        try:
            user_id = UUID(str(raw_id))
        except (TypeError, ValueError) as exc:
            raise AuthError("Token không chứa mã người dùng hợp lệ", status_code=401) from exc
        if data.get("aud") not in (None, "authenticated") and data.get("role") != "authenticated":
            raise AuthError("Token không dành cho người dùng đã đăng nhập", status_code=401)
        user = AuthUser(
            id=user_id,
            email=data.get("email"),
            role=str(data.get("role") or "authenticated"),
        )
        with self._lock:
            if len(self._cache) >= self._max_cache:
                self._prune(now)
            self._cache[cache_key] = (now + self._cache_ttl, user)
        return user

    def _prune(self, now: float) -> None:
        expired = [key for key, (expires, _) in self._cache.items() if expires <= now]
        for key in expired:
            self._cache.pop(key, None)
        if len(self._cache) >= self._max_cache:
            self._cache.clear()


_verifier: SupabaseTokenVerifier | None = None
_verifier_lock = threading.Lock()


def get_verifier() -> SupabaseTokenVerifier:
    global _verifier
    if _verifier is None:
        with _verifier_lock:
            if _verifier is None:
                settings = get_settings()
                _verifier = SupabaseTokenVerifier(
                    settings.supabase_url,
                    settings.supabase_anon_key,
                )
    return _verifier


def reset_verifier() -> None:
    global _verifier
    with _verifier_lock:
        if _verifier is not None:
            _verifier.close()
        _verifier = None
