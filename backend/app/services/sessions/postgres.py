from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .pool import ConnectionPool, get_pool
from .types import MessageRecord, SessionRecord, SessionStoreError

SESSION_COLUMNS = """
    s.id, s.user_id, s.title, s.summary, s.summary_message_count,
    s.message_count, s.token_count, s.metadata, s.created_at, s.updated_at
"""

MESSAGE_COLUMNS = """
    m.id, m.session_id, m.role, m.content, m.rewritten_query, m.citations,
    m.token_count, m.request_id, m.metadata, m.created_at, m.seq
"""


class PostgresSessionRepository:
    def __init__(self, pool: ConnectionPool | None = None) -> None:
        self._pool = pool or get_pool()

    # -- phiên ---------------------------------------------------------------
    def create_session(
        self,
        user_id: UUID,
        *,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionRecord:
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                insert into public.sessions (id, user_id, title, metadata)
                values (%s, %s, %s, %s)
                returning {SESSION_COLUMNS.replace("s.", "")}
                """,
                (uuid4(), user_id, title, Jsonb(metadata or {})),
            )
            return _session(cur.fetchone())

    def list_sessions(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[SessionRecord]:
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                select {SESSION_COLUMNS}
                from public.sessions s
                where s.user_id = %s
                order by s.updated_at desc, s.created_at desc
                limit %s offset %s
                """,
                (user_id, limit, offset),
            )
            return [_session(row) for row in cur.fetchall()]

    def count_sessions(self, user_id: UUID) -> int:
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute("select count(*) from public.sessions where user_id = %s", (user_id,))
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def get_session(self, user_id: UUID, session_id: UUID) -> SessionRecord | None:
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                select {SESSION_COLUMNS}
                from public.sessions s
                where s.id = %s and s.user_id = %s
                """,
                (session_id, user_id),
            )
            row = cur.fetchone()
            return _session(row) if row else None

    def update_session(
        self, user_id: UUID, session_id: UUID, *, title: str | None
    ) -> SessionRecord | None:
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                update public.sessions s
                set title = coalesce(%s, s.title), updated_at = now()
                where s.id = %s and s.user_id = %s
                returning {SESSION_COLUMNS.replace("s.", "")}
                """,
                (title, session_id, user_id),
            )
            row = cur.fetchone()
            return _session(row) if row else None

    def delete_session(self, user_id: UUID, session_id: UUID) -> bool:
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "delete from public.sessions where id = %s and user_id = %s returning id",
                (session_id, user_id),
            )
            return cur.fetchone() is not None

    def delete_all_sessions(self, user_id: UUID) -> int:
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute("delete from public.sessions where user_id = %s returning id", (user_id,))
            return len(cur.fetchall())

    def set_summary(
        self,
        user_id: UUID,
        session_id: UUID,
        *,
        summary: str,
        summary_message_count: int,
    ) -> SessionRecord | None:
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                update public.sessions s
                set summary = %s,
                    summary_message_count = %s,
                    summary_updated_at = now(),
                    updated_at = now()
                where s.id = %s and s.user_id = %s
                returning {SESSION_COLUMNS.replace("s.", "")}
                """,
                (summary, summary_message_count, session_id, user_id),
            )
            row = cur.fetchone()
            return _session(row) if row else None

    # -- tin nhắn ------------------------------------------------------------
    def begin_turn(
        self,
        user_id: UUID,
        session_id: UUID,
        *,
        question: str,
        rewritten_query: str | None = None,
        question_tokens: int = 0,
        request_id: UUID | None = None,
        assistant_metadata: dict[str, Any] | None = None,
        set_title_if_empty: bool = True,
    ) -> tuple[MessageRecord, MessageRecord] | None:
        """Ghi câu hỏi và tin nhắn trợ lý giữ chỗ trong một transaction.

        Giữ chỗ trước giúp client gửi lại cùng request_id không tạo lượt trùng
        và cho phép lưu dở câu trả lời khi stream bị ngắt.
        """
        try:
            with self._pool.connection() as conn:
                with conn.transaction():
                    with conn.cursor(row_factory=dict_row) as cur:
                        cur.execute(
                            "select id, title from public.sessions "
                            "where id = %s and user_id = %s for update",
                            (session_id, user_id),
                        )
                        session = cur.fetchone()
                        if session is None:
                            return None
                        new_title = None
                        if set_title_if_empty and not session["title"]:
                            new_title = question.strip()[:80] or None
                        returning = (
                            "id, session_id, role, content, rewritten_query, citations, "
                            "token_count, request_id, metadata, created_at, seq"
                        )
                        cur.execute(
                            f"""
                            insert into public.messages
                                (id, session_id, role, content, rewritten_query,
                                 citations, metadata, token_count, request_id)
                            values (%s, %s, 'user', %s, %s, %s, %s, %s, null)
                            returning {returning}
                            """,
                            (
                                uuid4(),
                                session_id,
                                question,
                                rewritten_query,
                                Jsonb([]),
                                Jsonb({}),
                                max(0, question_tokens),
                            ),
                        )
                        user_message = cur.fetchone()
                        cur.execute(
                            f"""
                            insert into public.messages
                                (id, session_id, role, content, rewritten_query,
                                 citations, metadata, token_count, request_id)
                            values (%s, %s, 'assistant', '', null, %s, %s, 0, %s)
                            returning {returning}
                            """,
                            (
                                uuid4(),
                                session_id,
                                Jsonb([]),
                                Jsonb(assistant_metadata or {}),
                                request_id,
                            ),
                        )
                        assistant_message = cur.fetchone()
                        cur.execute(
                            """
                            update public.sessions
                            set message_count = message_count + 2,
                                token_count = token_count + %s,
                                updated_at = now(),
                                title = coalesce(title, %s)
                            where id = %s and user_id = %s
                            """,
                            (max(0, question_tokens), new_title, session_id, user_id),
                        )
                        return _message(user_message), _message(assistant_message)
        except SessionStoreError:
            raise
        except Exception as exc:  # noqa: BLE001 - unique request_id, khóa ngoại
            raise SessionStoreError(f"Không mở được lượt hội thoại: {type(exc).__name__}") from exc

    def add_message(
        self,
        user_id: UUID,
        session_id: UUID,
        *,
        role: str,
        content: str,
        rewritten_query: str | None = None,
        citations: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        token_count: int = 0,
        request_id: UUID | None = None,
        set_title_if_empty: bool = False,
    ) -> MessageRecord | None:
        try:
            with self._pool.connection() as conn:
                with conn.transaction():
                    with conn.cursor(row_factory=dict_row) as cur:
                        cur.execute(
                            "select id, title from public.sessions "
                            "where id = %s and user_id = %s for update",
                            (session_id, user_id),
                        )
                        session = cur.fetchone()
                        if session is None:
                            return None
                        new_title = None
                        if set_title_if_empty and not session["title"]:
                            new_title = content.strip()[:80] or None
                        cur.execute(
                            """
                            insert into public.messages
                                (id, session_id, role, content, rewritten_query,
                                 citations, metadata, token_count, request_id)
                            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            returning
                                id, session_id, role, content, rewritten_query, citations,
                                token_count, request_id, metadata, created_at, seq
                            """,
                            (
                                uuid4(),
                                session_id,
                                role,
                                content,
                                rewritten_query,
                                Jsonb(citations or []),
                                Jsonb(metadata or {}),
                                max(0, token_count),
                                request_id,
                            ),
                        )
                        message = cur.fetchone()
                        cur.execute(
                            """
                            update public.sessions
                            set message_count = message_count + 1,
                                token_count = token_count + %s,
                                updated_at = now(),
                                title = coalesce(title, %s)
                            where id = %s and user_id = %s
                            """,
                            (max(0, token_count), new_title, session_id, user_id),
                        )
                        return _message(message)
        except SessionStoreError:
            raise
        except Exception as exc:  # noqa: BLE001 - psycopg lỗi unique, khóa ngoại
            raise SessionStoreError(f"Không ghi được tin nhắn: {type(exc).__name__}") from exc

    def update_message(
        self,
        user_id: UUID,
        message_id: UUID,
        *,
        content: str | None = None,
        citations: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        token_count: int | None = None,
    ) -> MessageRecord | None:
        try:
            with self._pool.connection() as conn:
                with conn.transaction():
                    with conn.cursor(row_factory=dict_row) as cur:
                        cur.execute(
                            """
                            select m.id, m.session_id, m.token_count
                            from public.messages m
                            join public.sessions s on s.id = m.session_id
                            where m.id = %s and s.user_id = %s
                            for update of m
                            """,
                            (message_id, user_id),
                        )
                        target = cur.fetchone()
                        if target is None:
                            return None
                        cur.execute(
                            """
                            update public.messages m
                            set content = coalesce(%s, m.content),
                                citations = coalesce(%s, m.citations),
                                metadata = coalesce(%s, m.metadata),
                                token_count = coalesce(%s, m.token_count)
                            where m.id = %s
                            returning
                                m.id, m.session_id, m.role, m.content, m.rewritten_query,
                                m.citations, m.token_count, m.request_id, m.metadata,
                                m.created_at, m.seq
                            """,
                            (
                                content,
                                Jsonb(citations) if citations is not None else None,
                                Jsonb(metadata) if metadata is not None else None,
                                token_count,
                                message_id,
                            ),
                        )
                        message = cur.fetchone()
                        if token_count is not None:
                            delta = max(0, token_count) - int(target["token_count"] or 0)
                            if delta:
                                cur.execute(
                                    """
                                    update public.sessions
                                    set token_count = greatest(0, token_count + %s),
                                        updated_at = now()
                                    where id = %s
                                    """,
                                    (delta, target["session_id"]),
                                )
                        return _message(message)
        except SessionStoreError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise SessionStoreError(f"Không cập nhật được tin nhắn: {type(exc).__name__}") from exc

    def get_message_by_request(
        self, user_id: UUID, session_id: UUID, request_id: UUID
    ) -> MessageRecord | None:
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                select {MESSAGE_COLUMNS}
                from public.messages m
                join public.sessions s on s.id = m.session_id
                where m.session_id = %s and m.request_id = %s and s.user_id = %s
                """,
                (session_id, request_id, user_id),
            )
            row = cur.fetchone()
            return _message(row) if row else None

    def list_messages(
        self, user_id: UUID, session_id: UUID, *, limit: int = 200, offset: int = 0
    ) -> list[MessageRecord]:
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                select {MESSAGE_COLUMNS}
                from public.messages m
                join public.sessions s on s.id = m.session_id
                where m.session_id = %s and s.user_id = %s
                order by m.seq asc
                limit %s offset %s
                """,
                (session_id, user_id, limit, offset),
            )
            return [_message(row) for row in cur.fetchall()]

    def recent_messages(self, user_id: UUID, session_id: UUID, limit: int) -> list[MessageRecord]:
        if limit <= 0:
            return []
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                select {MESSAGE_COLUMNS}
                from public.messages m
                join public.sessions s on s.id = m.session_id
                where m.session_id = %s and s.user_id = %s
                order by m.seq desc
                limit %s
                """,
                (session_id, user_id, limit),
            )
            rows = cur.fetchall()
        return [_message(row) for row in reversed(rows)]


def _session(row: dict[str, Any]) -> SessionRecord:
    return SessionRecord(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        summary=row["summary"],
        summary_message_count=int(row["summary_message_count"] or 0),
        message_count=int(row["message_count"] or 0),
        token_count=int(row["token_count"] or 0),
        metadata=dict(row["metadata"] or {}),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _message(row: dict[str, Any]) -> MessageRecord:
    return MessageRecord(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        rewritten_query=row["rewritten_query"],
        citations=list(row["citations"] or []),
        token_count=int(row["token_count"] or 0),
        request_id=row["request_id"],
        metadata=dict(row["metadata"] or {}),
        created_at=row["created_at"],
        seq=int(row["seq"] or 0),
    )
