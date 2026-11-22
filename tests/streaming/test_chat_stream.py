from __future__ import annotations

import asyncio
import json
import time
from uuid import uuid4

import pytest
from app.api.deps import get_current_user, get_runtime
from app.api.sse import sse_event_stream
from app.core.auth import AuthUser
from app.main import create_app
from fastapi.testclient import TestClient
from stream_support import ANSWER, CHUNKS, USER_A, FakeStreamingGeneration, build_service


@pytest.fixture
def service():
    instance = build_service()
    yield instance
    instance.close()


def _collect(service, session_id, question: str, *, request_id=None):
    return list(service.stream(USER_A, session_id, question, request_id=request_id))


def _parse_frames(text: str) -> list[tuple[str, dict]]:
    parsed: list[tuple[str, dict]] = []
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        lines = block.split("\n")
        event = next(line[len("event: ") :] for line in lines if line.startswith("event: "))
        data_lines = [line[len("data: ") :] for line in lines if line.startswith("data: ")]
        parsed.append((event, json.loads("\n".join(data_lines))))
    return parsed


def test_stream_emits_meta_tokens_citations_done_in_order(service) -> None:
    session = service.create_session(USER_A, title="Stream")
    events = _collect(service, session.id, "S3 Standard phù hợp dữ liệu nào?")

    assert events[0].event == "meta"
    meta = events[0].data
    assert meta["session_id"] == str(session.id)
    assert meta["message_id"]
    assert meta["rewritten_query"] == "S3 Standard phù hợp dữ liệu nào?"
    assert meta["replayed"] is False

    tokens = [event.data["text"] for event in events if event.event == "token"]
    assert "".join(tokens) == ANSWER
    assert len(tokens) == len(CHUNKS)

    assert [event.event for event in events[-2:]] == ["citations", "done"]
    citations = events[-2].data
    assert citations["items"][0]["source"] == "S3 Storage Classes – S3 Standard"
    assert citations["citation_validity"] == 1.0

    done = events[-1].data
    assert done["status"] == "complete"
    assert done["ttft_ms"] == 12.5
    assert done["usage"] == {"input_tokens": 90, "output_tokens": 30}
    assert done["provider"] == "fake"
    assert done["replayed"] is False

    messages = service.list_messages(USER_A, session.id)
    assert messages[1].content == ANSWER
    assert messages[1].metadata["stream_status"] == "complete"
    assert messages[1].citations[0]["source"] == "S3 Storage Classes – S3 Standard"


def test_identical_request_id_replays_stored_answer(service) -> None:
    generation: FakeStreamingGeneration = service.generation
    session = service.create_session(USER_A)
    request_id = uuid4()
    first = _collect(service, session.id, "S3 Standard phù hợp dữ liệu nào?", request_id=request_id)
    assert first[0].data["replayed"] is False
    calls_after_first = len(generation.stream_calls)

    replay = _collect(
        service, session.id, "S3 Standard phù hợp dữ liệu nào?", request_id=request_id
    )
    assert replay[0].event == "meta"
    assert replay[0].data["replayed"] is True
    assert "".join(event.data["text"] for event in replay if event.event == "token") == ANSWER
    assert replay[-1].data["replayed"] is True
    assert len(generation.stream_calls) == calls_after_first
    assert len(service.list_messages(USER_A, session.id)) == 2


def test_model_error_mid_stream_emits_error_and_keeps_partial_answer() -> None:
    generation = FakeStreamingGeneration(fail_at_chunk=1)
    service = build_service(generation)
    try:
        session = service.create_session(USER_A)
        events = _collect(service, session.id, "S3 Standard phù hợp dữ liệu nào?")
        assert events[0].event == "meta"
        assert events[1].event == "token"
        assert events[-2].event == "error"
        assert events[-2].data["code"] == "generation_failed"
        assert events[-1].event == "done"
        assert events[-1].data["status"] == "error"

        message = service.list_messages(USER_A, session.id)[1]
        assert message.content == CHUNKS[0].strip()
        assert message.metadata["stream_status"] == "error"
    finally:
        service.close()


def test_client_disconnect_closes_stream_and_saves_partial_answer() -> None:
    generation = FakeStreamingGeneration(
        chunks=tuple(f"mẩu {i} " for i in range(50)),
        chunk_delay=0.005,
    )
    service = build_service(generation)
    try:
        session = service.create_session(USER_A)
        seen = {"tokens": 0}

        async def disconnected_after_first_token() -> bool:
            return seen["tokens"] >= 1

        async def scenario():
            frames: list[str] = []
            stream = sse_event_stream(
                service.stream(USER_A, session.id, "S3 Standard phù hợp dữ liệu nào?"),
                is_disconnected=disconnected_after_first_token,
            )
            async for frame in stream:
                frames.append(frame)
                if "\nevent: token\n" in frame:
                    seen["tokens"] += 1
            return frames

        frames = asyncio.run(scenario())
        assert "event: meta" in frames[0]
        assert any("event: token" in frame for frame in frames)
        assert not any("event: error" in frame for frame in frames)

        deadline = time.monotonic() + 5.0
        message = service.list_messages(USER_A, session.id)[1]
        while time.monotonic() < deadline:
            message = service.list_messages(USER_A, session.id)[1]
            if message.metadata.get("stream_status") == "interrupted":
                break
            time.sleep(0.02)
        assert message.metadata["stream_status"] == "interrupted"
        assert message.content.startswith("mẩu 0")
    finally:
        service.close()


@pytest.fixture
def api_env():
    service = build_service()
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id=USER_A, email="a@example.com")
    app.dependency_overrides[get_runtime] = lambda: service
    with TestClient(app) as client:
        yield client, service
    service.close()


def test_chat_stream_endpoint_returns_sse(api_env) -> None:
    client, service = api_env
    response = client.post("/chat/stream", json={"question": "S3 Standard phù hợp dữ liệu nào?"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"

    events = _parse_frames(response.text)
    names = [name for name, _ in events]
    assert names[0] == "meta"
    assert names[-2:] == ["citations", "done"]
    assert "".join(data["text"] for name, data in events if name == "token") == ANSWER
    assert events[-1][1]["status"] == "complete"

    created = client.get("/sessions").json()
    assert created["total"] == 1
    assert service.count_sessions(USER_A) == 1
