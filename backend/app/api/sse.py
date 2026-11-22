from __future__ import annotations

import asyncio
import json
import queue
import threading
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Any

from app.services.chat import StreamEvent

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

_POLL_SECONDS = 0.02
_JOIN_TIMEOUT_SECONDS = 8.0


def format_sse(event: StreamEvent, *, event_id: int | None = None) -> str:
    """Định dạng một sự kiện SSE; mỗi sự kiện flush riêng, không buffer cả câu trả lời."""
    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event.event}")
    payload = json.dumps(event.data, ensure_ascii=False, separators=(",", ":"))
    for line in payload.split("\n"):
        lines.append(f"data: {line}")
    return "\n".join(lines) + "\n\n"


async def sse_event_stream(
    events: Iterator[StreamEvent],
    *,
    is_disconnected: Callable[[], Awaitable[bool]],
) -> AsyncIterator[str]:
    """Chạy generator đồng bộ trong luồng nền và đẩy từng sự kiện ra client.

    Khi client ngắt kết nối, cờ dừng được bật; luồng nền đóng generator ngay sau
    sự kiện kế tiếp, nhờ đó mô hình ngừng sinh và câu trả lời dở được lưu lại.
    """
    loop = asyncio.get_running_loop()
    outgoing: queue.Queue[tuple[str, Any]] = queue.Queue()
    stop = threading.Event()

    def producer() -> None:
        try:
            for event in events:
                if stop.is_set():
                    break
                outgoing.put(("event", event))
        except Exception as exc:  # noqa: BLE001 - chuyển thành sự kiện lỗi
            outgoing.put(("error", exc))
        finally:
            events.close()
            outgoing.put(("end", None))

    future = loop.run_in_executor(None, producer)
    event_id = 0
    try:
        while True:
            if await is_disconnected():
                stop.set()
                break
            try:
                kind, payload = outgoing.get_nowait()
            except queue.Empty:
                await asyncio.sleep(_POLL_SECONDS)
                continue
            if kind == "end":
                break
            if kind == "error":
                event_id += 1
                yield format_sse(
                    StreamEvent(
                        "error",
                        {
                            "code": "stream_failed",
                            "message": "Luồng trả lời gặp lỗi không mong đợi.",
                        },
                    ),
                    event_id=event_id,
                )
                break
            event_id += 1
            yield format_sse(payload, event_id=event_id)
            if payload.event == "done":
                stop.set()
                break
    finally:
        stop.set()
        try:
            await asyncio.wait_for(asyncio.shield(future), timeout=_JOIN_TIMEOUT_SECONDS)
        except (Exception, asyncio.CancelledError):
            # Client đã đi hoặc luồng nền chậm; không biến ngắt kết nối thành lỗi 500.
            pass
