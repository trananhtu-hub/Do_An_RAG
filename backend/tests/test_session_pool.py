from __future__ import annotations

import time

import psycopg

from app.services.sessions.pool import ConnectionPool


class FakeConnection:
    def __init__(self, *, alive: bool = True) -> None:
        self.closed = False
        self.broken = False
        self.alive = alive
        self.probes = 0

    def execute(self, sql: str) -> FakeConnection:
        self.probes += 1
        if not self.alive:
            raise psycopg.OperationalError("server closed the connection unexpectedly")
        return self

    def fetchone(self) -> tuple[int]:
        return (1,)

    def close(self) -> None:
        self.closed = True


def test_thay_ket_noi_cu_da_chet(monkeypatch) -> None:
    pool = ConnectionPool("postgresql://unused", liveness_interval=0)
    stale = FakeConnection(alive=False)
    fresh = FakeConnection()
    pool._idle.put((stale, 0.0))
    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: fresh)

    conn = pool._acquire()

    assert conn is fresh
    assert stale.closed is True
    assert stale.probes == 1


def test_tai_su_dung_ket_noi_am_khong_kiem_tra(monkeypatch) -> None:
    pool = ConnectionPool("postgresql://unused", liveness_interval=3600)
    warm = FakeConnection()
    pool._idle.put((warm, time.monotonic()))

    def fail_connect(*args, **kwargs):
        raise AssertionError("không được tạo kết nối mới")

    monkeypatch.setattr(psycopg, "connect", fail_connect)

    assert pool._acquire() is warm
    assert warm.probes == 0


def test_thay_ket_noi_da_dong_ma_khong_can_kiem_tra(monkeypatch) -> None:
    pool = ConnectionPool("postgresql://unused", liveness_interval=3600)
    closed = FakeConnection()
    closed.closed = True
    fresh = FakeConnection()
    pool._idle.put((closed, time.monotonic()))
    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: fresh)

    assert pool._acquire() is fresh
    assert closed.probes == 0
