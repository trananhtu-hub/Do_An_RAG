from __future__ import annotations

import queue
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from .types import SessionStoreError

APPLICATION_NAME = "rag-chatbot-sessions"


class ConnectionPool:
    """Pool kết nối PostgreSQL tối giản, không phụ thuộc thư viện ngoài.

    Mỗi kết nối mới tới Supabase mất ~300 ms; giữ kết nối ấm giúp TTFT không
    bị cộng thêm độ trễ bắt tay TCP/TLS ở mỗi lượt hỏi.
    """

    def __init__(
        self,
        dsn: str,
        *,
        max_size: int = 8,
        connect_timeout: int = 10,
        acquire_timeout: float = 15.0,
    ) -> None:
        if not dsn.strip():
            raise ValueError("Thiếu DSN cho ConnectionPool")
        self._dsn = dsn
        self._max_size = max(1, max_size)
        self._connect_timeout = connect_timeout
        self._acquire_timeout = acquire_timeout
        self._idle: queue.LifoQueue[psycopg.Connection] = queue.LifoQueue()
        self._slots = threading.BoundedSemaphore(self._max_size)
        self._closed = False
        self._lock = threading.Lock()

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        conn = self._acquire()
        try:
            yield conn
        except psycopg.Error as exc:
            self._discard(conn)
            raise SessionStoreError(f"Lỗi PostgreSQL: {type(exc).__name__}") from exc
        except BaseException:
            self._discard(conn)
            raise
        else:
            self._release(conn)

    def _acquire(self) -> psycopg.Connection:
        if self._closed:
            raise SessionStoreError("ConnectionPool đã đóng")
        if not self._slots.acquire(timeout=self._acquire_timeout):
            raise SessionStoreError("Hết kết nối sẵn có trong pool")
        try:
            conn = self._idle.get_nowait()
        except queue.Empty:
            conn = None
        if conn is not None and not conn.closed:
            return conn
        if conn is not None:
            conn.close()
        try:
            return psycopg.connect(
                self._dsn,
                autocommit=True,
                connect_timeout=self._connect_timeout,
                application_name=APPLICATION_NAME,
            )
        except psycopg.Error as exc:
            self._slots.release()
            raise SessionStoreError(f"Không kết nối được PostgreSQL: {type(exc).__name__}") from exc

    def _release(self, conn: psycopg.Connection) -> None:
        try:
            if self._closed or conn.closed:
                conn.close()
            else:
                self._idle.put(conn)
        finally:
            self._slots.release()

    def _discard(self, conn: psycopg.Connection) -> None:
        try:
            if not conn.closed:
                conn.close()
        finally:
            self._slots.release()

    def close(self) -> None:
        with self._lock:
            self._closed = True
        while True:
            try:
                conn = self._idle.get_nowait()
            except queue.Empty:
                break
            try:
                conn.close()
            except Exception:  # noqa: BLE001 - đóng best-effort
                pass


_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def get_pool(dsn: str | None = None) -> ConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                if dsn is None:
                    from app.core.config import get_settings

                    dsn = get_settings().database_url
                _pool = ConnectionPool(dsn or "")
    return _pool


def reset_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
        _pool = None
