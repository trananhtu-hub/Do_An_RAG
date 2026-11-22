from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user, get_runtime
from app.api.sse import SSE_HEADERS, sse_event_stream
from app.core.auth import AuthUser
from app.models.chat_schemas import (
    ChatRequest,
    ChatResponse,
    DeleteAllSessionsResponse,
    MessageListResponse,
    MessageResponse,
    SessionCreateRequest,
    SessionListResponse,
    SessionResponse,
    SessionUpdateRequest,
)
from app.models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Kiểm tra tình trạng backend")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


# -- phiên hội thoại ---------------------------------------------------------
@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo phiên hội thoại mới",
)
def create_session(
    payload: SessionCreateRequest,
    user: AuthUser = Depends(get_current_user),
    service=Depends(get_runtime),
) -> SessionResponse:
    session = service.create_session(user.id, title=payload.title, metadata=payload.metadata)
    return SessionResponse.from_record(session)


@router.get("/sessions", response_model=SessionListResponse, summary="Liệt kê phiên của tôi")
def list_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: AuthUser = Depends(get_current_user),
    service=Depends(get_runtime),
) -> SessionListResponse:
    sessions = service.list_sessions(user.id, limit=limit, offset=offset)
    return SessionListResponse(
        items=[SessionResponse.from_record(session) for session in sessions],
        total=service.count_sessions(user.id),
    )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=MessageListResponse,
    summary="Đọc tin nhắn của một phiên",
)
def list_messages(
    session_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: AuthUser = Depends(get_current_user),
    service=Depends(get_runtime),
) -> MessageListResponse:
    session = service.get_session(user.id, _uuid(session_id))
    messages = service.list_messages(user.id, _uuid(session_id), limit=limit, offset=offset)
    return MessageListResponse(
        items=[MessageResponse.from_record(message) for message in messages],
        total=session.message_count,
    )


@router.patch(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    summary="Đổi tên phiên",
)
def rename_session(
    session_id: str,
    payload: SessionUpdateRequest,
    user: AuthUser = Depends(get_current_user),
    service=Depends(get_runtime),
) -> SessionResponse:
    session = service.get_session(user.id, _uuid(session_id))
    updated = service.rename_session(user.id, session.id, payload.title)
    return SessionResponse.from_record(updated or session)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa một phiên",
)
def delete_session(
    session_id: str,
    user: AuthUser = Depends(get_current_user),
    service=Depends(get_runtime),
) -> Response:
    from app.api.deps import api_error

    if not service.delete_session(user.id, _uuid(session_id)):
        raise api_error(404, "session_not_found", "Không tìm thấy phiên cần xóa.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/sessions",
    response_model=DeleteAllSessionsResponse,
    summary="Xóa toàn bộ phiên và tin nhắn của tôi",
)
def delete_all_sessions(
    user: AuthUser = Depends(get_current_user),
    service=Depends(get_runtime),
) -> DeleteAllSessionsResponse:
    return DeleteAllSessionsResponse(deleted=service.delete_all_sessions(user.id))


# -- chat --------------------------------------------------------------------
@router.post("/chat", response_model=ChatResponse, summary="Hỏi một lượt (không streaming)")
def chat(
    payload: ChatRequest,
    user: AuthUser = Depends(get_current_user),
    service=Depends(get_runtime),
) -> ChatResponse:
    session_id = payload.session_id
    if session_id is None:
        session = service.create_session(user.id, title=payload.question[:80])
        session_id = session.id
    outcome = service.answer(
        user.id,
        session_id,
        payload.question,
        request_id=payload.request_id,
    )
    message = outcome.message
    result = outcome.result
    if result is None:
        return ChatResponse(
            session_id=outcome.session_id,
            message_id=message.id if message else None,
            answer=message.content if message else "",
            citations=message.citations if message else [],
            rewritten_query=outcome.turn.rewritten,
            confidence=0.0,
            abstained=False,
            abstention_type="none",
            provider="replay",
            model="replay",
            latency_ms=0.0,
            usage={"input_tokens": 0, "output_tokens": 0},
            warnings=[],
            replayed=True,
        )
    return ChatResponse(
        session_id=outcome.session_id,
        message_id=message.id if message else None,
        answer=result.payload.answer,
        citations=[citation.model_dump() for citation in result.payload.citations],
        rewritten_query=outcome.turn.rewritten,
        confidence=result.payload.confidence,
        abstained=result.payload.abstained,
        abstention_type=result.payload.abstention_type,
        provider=result.provider,
        model=result.model,
        latency_ms=result.latency_ms,
        usage={
            "input_tokens": result.usage_input_tokens,
            "output_tokens": result.usage_output_tokens,
        },
        warnings=list(result.warnings),
    )


@router.post(
    "/chat/stream",
    summary="Hỏi một lượt và nhận câu trả lời qua SSE",
    response_class=StreamingResponse,
)
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    user: AuthUser = Depends(get_current_user),
    service=Depends(get_runtime),
) -> StreamingResponse:
    session_id = payload.session_id
    if session_id is None:
        session = await run_in_threadpool(
            service.create_session, user.id, title=payload.question[:80]
        )
        session_id = session.id
    turn = await run_in_threadpool(
        service.prepare,
        user.id,
        session_id,
        payload.question,
        request_id=payload.request_id,
    )
    events = service.stream_turn(turn)
    return StreamingResponse(
        sse_event_stream(events, is_disconnected=request.is_disconnected),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


def _uuid(value: str):
    from uuid import UUID

    try:
        return UUID(value)
    except ValueError:
        from app.api.deps import api_error

        raise api_error(400, "invalid_session_id", "Mã phiên không hợp lệ.") from None
