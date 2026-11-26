from __future__ import annotations

import queue
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from .types import SessionStoreError

APPLICATION_NAME = "rag-chatbot-sessions"


class ConnectionPool:
    """Pool kết nối PostgreSQL tối giản, không phụ thuộc thư viện ngoài.

    Mỗi kết nối mới tới Supabase mất ~300 ms; giữ kết nối ấm giúp TTFT không
    bị cộng thêm độ trễ bắt tay TCP/TLS ở mỗi lượt hỏi. Kết nối để lâu có thể
    bị máy chủ đóng mà client chưa biết, nên trước khi tái sử dụng sau một
    khoảng nghỉ, pool kiểm tra bằng SELECT 1 và thay kết nối hỏng.
    """

    def __init__(
        self,
        dsn: str,
        *,
        max_size: int = 8,
        connect_timeout: int = 10,
        acquire_timeout: float = 15.0,
        liveness_interval: float = 30.0,
    ) -> None:
        if not dsn.strip():
            raise ValueError("Thiếu DSN cho ConnectionPool")
        self._dsn = dsn
        self._max_size = max(1, max_size)
        self._connect_timeout = connect_timeout
        self._acquire_timeout = acquire_timeout
        self._liveness_interval = liveness_interval
        self._idle: queue.LifoQueue[tuple[psycopg.Connection, float]] = queue.LifoQueue()
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
            conn, released_at = self._idle.get_nowait()
        except queue.Empty:
            conn, released_at = None, 0.0
        if conn is not None:
            idle_for = time.monotonic() - released_at
            stale = (
                conn.closed
                or conn.broken
                or (idle_for > self._liveness_interval and not self._is_alive(conn))
            )
            if stale:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001 - đóng best-effort
                    pass
                conn = None
        if conn is not None:
            return conn
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

    @staticmethod
    def _is_alive(conn: psycopg.Connection) -> bool:
        try:
            conn.execute("SELECT 1").fetchone()
            return True
        except psycopg.Error:
            return False

    def _release(self, conn: psycopg.Connection) -> None:
        try:
            if self._closed or conn.closed:
                conn.close()
            else:
                self._idle.put((conn, time.monotonic()))
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
                conn, _ = self._idle.get_nowait()
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
