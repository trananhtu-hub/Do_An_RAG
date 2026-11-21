from __future__ import annotations

import threading
from collections.abc import Sequence
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .types import ChunkRecord

_VECTOR_SEARCH = """
select
    c.id::text as child_id,
    c.parent_id::text as parent_id,
    c.content,
    c.token_count,
    p.token_count as parent_token_count,
    c.metadata,
    coalesce(d.source_key, c.metadata->>'document') as document,
    1 - (c.embedding <=> %s::vector) as score
from public.chunks c
join public.documents d on d.id = c.document_id
left join public.chunks p on p.id = c.parent_id
where c.content_type = 'child'
  and c.embedding is not null
  and 1 - (c.embedding <=> %s::vector) >= %s
order by c.embedding <=> %s::vector
limit %s
"""

_LEXICAL_SEARCH = """
with parsed as (
    select to_tsquery('simple', public.unaccent(%s)) as query
)
select
    c.id::text as child_id,
    c.parent_id::text as parent_id,
    c.content,
    c.token_count,
    p.token_count as parent_token_count,
    c.metadata,
    coalesce(d.source_key, c.metadata->>'document') as document,
    ts_rank(c.search_vector_unaccented, parsed.query) as score
from public.chunks c
join public.documents d on d.id = c.document_id
left join public.chunks p on p.id = c.parent_id
cross join parsed
where c.content_type = 'child'
  and c.search_vector_unaccented @@ parsed.query
order by score desc, c.id
limit %s
"""


def _trigram_query(term_count: int) -> str:
    # Lọc bằng ILIKE để tận dụng chỉ mục GIN trigram; chỉ chấm điểm trên dòng khớp.
    matched = " + ".join(
        "(case when c.search_text ilike %s then 1 else 0 end)" for _ in range(term_count)
    )
    filters = " or ".join("c.search_text ilike %s" for _ in range(term_count))
    return f"""
select
    c.id::text as child_id,
    c.parent_id::text as parent_id,
    c.content,
    c.token_count,
    p.token_count as parent_token_count,
    c.metadata,
    coalesce(d.source_key, c.metadata->>'document') as document,
    ({matched})::float / %s as score
from public.chunks c
join public.documents d on d.id = c.document_id
left join public.chunks p on p.id = c.parent_id
where c.content_type = 'child'
  and ({filters})
order by score desc, c.id
limit %s
"""


def _like_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(f"{value:.7g}" for value in values) + "]"


def _to_record(row: dict[str, Any]) -> ChunkRecord:
    metadata = row.get("metadata") or {}
    page = metadata.get("page")
    return ChunkRecord(
        child_id=row["child_id"],
        parent_id=row["parent_id"],
        content=row["content"],
        parent_content=None,
        document=row["document"] or metadata.get("document") or "",
        section=metadata.get("section"),
        heading=metadata.get("heading"),
        page=int(page) if isinstance(page, int | float | str) and str(page).isdigit() else None,
        token_count=row.get("token_count"),
        parent_token_count=row.get("parent_token_count"),
        metadata=metadata,
    )


class PgChunkStore:
    """Truy vấn chunk trên Supabase PostgreSQL; mỗi luồng dùng một kết nối."""

    def __init__(self, database_url: str, *, ef_search: int = 100) -> None:
        if not database_url:
            raise ValueError("Thiếu DATABASE_URL để truy vấn kho tri thức")
        if ef_search <= 0:
            raise ValueError("ef_search phải lớn hơn 0")
        self._database_url = database_url
        self._ef_search = int(ef_search)
        self._local = threading.local()
        self._connections: list[psycopg.Connection[Any]] = []
        self._lock = threading.Lock()

    def _connection(self) -> psycopg.Connection[Any]:
        connection = getattr(self._local, "connection", None)
        if connection is None or connection.closed:
            connection = psycopg.connect(
                self._database_url, row_factory=dict_row, connect_timeout=20
            )
            with connection.cursor() as cursor:
                cursor.execute(f"set hnsw.ef_search = {self._ef_search:d}")
            connection.commit()
            self._local.connection = connection
            with self._lock:
                self._connections.append(connection)
        return connection

    def close(self) -> None:
        with self._lock:
            connections, self._connections = self._connections, []
        for connection in connections:
            try:
                connection.close()
            except Exception:  # pragma: no cover - đóng kết nối hỏng không quan trọng
                pass
        self._local = threading.local()

    def vector_search(
        self, vector: Sequence[float], limit: int, threshold: float
    ) -> list[ChunkRecord]:
        literal = vector_literal(vector)
        with self._connection().cursor() as cursor:
            cursor.execute(_VECTOR_SEARCH, (literal, literal, threshold, literal, limit))
            rows = cursor.fetchall()
        records = [_to_record(row) for row in rows]
        for record, row in zip(records, rows, strict=True):
            record.vector_score = float(row["score"])
        return records

    def lexical_search(self, tsquery: str, limit: int) -> list[ChunkRecord]:
        with self._connection().cursor() as cursor:
            cursor.execute(_LEXICAL_SEARCH, (tsquery, limit))
            rows = cursor.fetchall()
        records = [_to_record(row) for row in rows]
        for record, row in zip(records, rows, strict=True):
            record.lexical_score = float(row["score"])
        return records

    def trigram_search(
        self, terms: Sequence[str], limit: int, min_matched_terms: int
    ) -> list[ChunkRecord]:
        if not terms:
            return []
        patterns = [_like_pattern(term) for term in terms]
        sql = _trigram_query(len(patterns))
        # Lấy dư rồi lọc ngưỡng trong Python để không lặp biểu thức khớp trong SQL.
        params = [*patterns, len(patterns), *patterns, limit * 2]
        with self._connection().cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        records = [_to_record(row) for row in rows]
        kept: list[ChunkRecord] = []
        for record, row in zip(records, rows, strict=True):
            score = float(row["score"])
            if score * len(patterns) < min_matched_terms:
                continue
            record.trigram_score = score
            kept.append(record)
            if len(kept) >= limit:
                break
        return kept

    def fetch_parents(self, parent_ids: Sequence[str]) -> dict[str, str]:
        if not parent_ids:
            return {}
        with self._connection().cursor() as cursor:
            cursor.execute(
                "select id::text as parent_id, content from public.chunks "
                "where id = any(%s::uuid[])",
                (list(dict.fromkeys(parent_ids)),),
            )
            return {row["parent_id"]: row["content"] for row in cursor.fetchall()}

    def healthcheck(self) -> dict[str, int]:
        with self._connection().cursor() as cursor:
            cursor.execute(
                "select count(*) as chunks, "
                "(select count(*) from public.chunks where content_type = 'child') as children "
                "from public.chunks"
            )
            row = cursor.fetchone()
        return {"chunks": int(row["chunks"]), "children": int(row["children"])}
