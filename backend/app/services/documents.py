from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.core.config import REPO_ROOT

from .sessions.pool import ConnectionPool, get_pool


class DocumentNotFound(LookupError):
    """Không có tài liệu hoặc tệp nguồn không còn trên đĩa."""


class DocumentService:
    def __init__(self, pool: ConnectionPool | None = None) -> None:
        self._pool = pool

    def _connection_pool(self) -> ConnectionPool:
        return self._pool if self._pool is not None else get_pool()

    def list_documents(self) -> list[dict[str, Any]]:
        with self._connection_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    select id, title, source_key, page_count
                    from public.documents
                    order by title
                    """
                )
                return [dict(row) for row in cur.fetchall()]

    def resolve_file(self, document_id: UUID) -> tuple[Path, str]:
        with self._connection_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "select title, source_key from public.documents where id = %s",
                    (document_id,),
                )
                row = cur.fetchone()
        if row is None or not row["source_key"]:
            raise DocumentNotFound("Không tìm thấy tài liệu.")
        path = Path(row["source_key"])
        if not path.is_absolute():
            path = REPO_ROOT / path
        path = path.resolve()
        data_root = (REPO_ROOT / "data").resolve()
        # Chỉ phục vụ PDF nằm trong data/ để không lộ tệp ngoài kho tài liệu.
        if not path.is_relative_to(data_root) or path.suffix.lower() != ".pdf":
            raise DocumentNotFound("Tệp tài liệu không hợp lệ.")
        if not path.is_file():
            raise DocumentNotFound("Tệp tài liệu không còn trên máy chủ.")
        return path, row["title"]
