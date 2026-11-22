from __future__ import annotations

import asyncio
import json
import threading

from app.api.sse import format_sse, sse_event_stream
from app.services.chat import StreamEvent


def test_format_sse_uses_event_id_and_unicode() -> None:
    frame = format_sse(
        StreamEvent("token", {"text": "Xin chào\nDòng thứ hai"}),
        event_id=7,
    )
    assert frame.startswith("id: 7\nevent: token\ndata: ")
    assert frame.endswith("\n\n")
    lines = frame.strip().split("\n")
    assert len(lines) == 3
    assert json.loads(lines[2][len("data: ") :]) == {"text": "Xin chào\nDòng thứ hai"}
    assert "Xin chào" in lines[2]


def test_format_sse_parses_back_to_json() -> None:
    frame = format_sse(StreamEvent("done", {"status": "complete", "n": 1}))
    event_line = next(line for line in frame.split("\n") if line.startswith("event: "))
    data_lines = [line[6:] for line in frame.split("\n") if line.startswith("data: ")]
    assert event_line == "event: done"
    assert json.loads("\n".join(data_lines)) == {"status": "complete", "n": 1}


async def _never_disconnected() -> bool:
    return False


def test_events_are_flushed_before_producer_finishes() -> None:
    gate = threading.Event()
    closed = threading.Event()

    def events():
        try:
            yield StreamEvent("meta", {"step": 1})
            gate.wait(2.0)
            yield StreamEvent("done", {"status": "complete"})
        finally:
            closed.set()

    async def scenario():
        stream = sse_event_stream(events(), is_disconnected=_never_disconnected)
        first = await anext(stream)
        assert "event: meta" in first
        assert gate.is_set() is False, "sự kiện đầu phải được đẩy ra trước khi luồng kết thúc"
        gate.set()
        rest = [frame async for frame in stream]
        return first, rest

    _, rest = asyncio.run(scenario())
    assert any("event: done" in frame for frame in rest)
    assert closed.is_set()


def test_disconnect_stops_producer_and_emits_no_error() -> None:
    state = {"checks": 0, "closed": False}

    async def disconnected_after_first() -> bool:
        state["checks"] += 1
        return state["checks"] > 1

    def events():
        try:
            for index in range(1000):
                yield StreamEvent("token", {"text": str(index)})
        finally:
            state["closed"] = True

    async def scenario():
        return [
            frame
            async for frame in sse_event_stream(events(), is_disconnected=disconnected_after_first)
        ]

    frames = asyncio.run(scenario())
    assert len(frames) == 1
    assert "event: token" in frames[0]
    assert state["closed"] is True
    assert not any("event: error" in frame for frame in frames)


def test_producer_exception_becomes_error_event() -> None:
    def events():
        yield StreamEvent("meta", {"step": 1})
        raise RuntimeError("bùng nổ")

    async def scenario():
        return [
            frame async for frame in sse_event_stream(events(), is_disconnected=_never_disconnected)
        ]

    frames = asyncio.run(scenario())
    assert "event: meta" in frames[0]
    assert "event: error" in frames[-1]
    assert '"code":"stream_failed"' in frames[-1]
