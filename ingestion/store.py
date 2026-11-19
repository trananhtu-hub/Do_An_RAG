from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .chunking import Chunk, document_uuid, question_uuid
from .config import EMBEDDING_DIM, EMBEDDING_MODEL
from .embeddings import vector_literal
from .loaders import PdfDocument
from .questions import ExtractedQuestion

DOCUMENT_INSERT = """
insert into public.documents (
    id, source_key, title, source_url, source_type, version,
    page_count, checksum, language, metadata, updated_at
) values (%s, %s, %s, null, 'pdf', %s, %s, %s, %s, %s, now())
"""

CHUNK_INSERT = """
insert into public.chunks (
    id, document_id, parent_id, chunk_index, content, embedding,
    metadata, token_count, content_type, checksum, embedding_model
) values (%s, %s, %s, %s, %s, %s::vector, %s, %s, %s, %s, %s)
"""

QUESTION_INSERT = """
insert into public.questions (
    id, document_id, external_id, question_number, question, options,
    correct_answer, explanation, domain, source, metadata, topic,
    source_page, page_end, language, checksum
) values (
    %s, %s, %s, %s, %s, %s::jsonb,
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s
)
"""


@dataclass
class StoredDocument:
    id: str
    source_key: str
    checksum: str | None
    page_count: int | None
    metadata: dict[str, Any] = field(default_factory=dict)
    chunk_count: int = 0
    parent_count: int = 0
    child_count: int = 0
    null_embeddings: int = 0
    question_count: int = 0


class Store:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._conn: psycopg.Connection[Any] | None = None

    def __enter__(self) -> Store:
        self.connect()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def connect(self) -> None:
        if self._conn is None:
            self._conn = psycopg.connect(self._database_url, row_factory=dict_row)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def connection(self) -> psycopg.Connection[Any]:
        if self._conn is None:
            raise RuntimeError("Chưa kết nối cơ sở dữ liệu")
        return self._conn

    def ensure_indexes(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "create index if not exists chunks_embedding_hnsw_idx "
                "on public.chunks using hnsw (embedding vector_cosine_ops)"
            )
            cursor.execute(
                "create index if not exists chunks_search_vector_idx "
                "on public.chunks using gin (search_vector)"
            )
        self.connection.commit()

    def existing_documents(self) -> dict[str, StoredDocument]:
        query = """
        select
            d.id::text as id,
            d.source_key,
            d.checksum,
            d.page_count,
            d.metadata,
            (select count(*) from public.chunks c where c.document_id = d.id) as chunk_count,
            (select count(*) from public.chunks c
                where c.document_id = d.id and c.content_type = 'parent') as parent_count,
            (select count(*) from public.chunks c
                where c.document_id = d.id and c.content_type = 'child') as child_count,
            (select count(*) from public.chunks c
                where c.document_id = d.id and c.embedding is null) as null_embeddings,
            (select count(*) from public.questions q where q.document_id = d.id) as question_count
        from public.documents d
        where d.source_key is not null
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
        return {
            row["source_key"]: StoredDocument(
                id=row["id"],
                source_key=row["source_key"],
                checksum=row["checksum"],
                page_count=row["page_count"],
                metadata=row["metadata"] or {},
                chunk_count=int(row["chunk_count"]),
                parent_count=int(row["parent_count"]),
                child_count=int(row["child_count"]),
                null_embeddings=int(row["null_embeddings"]),
                question_count=int(row["question_count"]),
            )
            for row in rows
        }

    def replace_document(
        self,
        *,
        document: PdfDocument,
        chunks: Sequence[Chunk],
        questions: Sequence[ExtractedQuestion],
        embeddings: Mapping[str, Sequence[float]],
        metadata: dict[str, Any],
        version: str,
    ) -> None:
        if not chunks:
            raise ValueError(f"Tài liệu {document.source_key} không có chunk nào")
        missing = [chunk.chunk_id for chunk in chunks if chunk.chunk_id not in embeddings]
        if missing:
            raise ValueError(f"Thiếu embedding cho {len(missing)} chunk của {document.source_key}")
        document_id = document_uuid(document.source_key, version)
        parent_rows = [chunk for chunk in chunks if chunk.content_type == "parent"]
        child_rows = [chunk for chunk in chunks if chunk.content_type == "child"]
        other_rows = [chunk for chunk in chunks if chunk.content_type not in {"parent", "child"}]

        # Đóng transaction ẩn do các lệnh select trước đó mở; nếu không, khối dưới
        # chỉ là savepoint và dữ liệu sẽ bị rollback khi đóng kết nối.
        self.connection.commit()
        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "delete from public.documents where source_key = %s",
                    (document.source_key,),
                )
                cursor.execute(
                    DOCUMENT_INSERT,
                    (
                        document_id,
                        document.source_key,
                        document.title,
                        version,
                        document.page_count,
                        document.checksum,
                        metadata.get("language", "vi"),
                        Jsonb(metadata),
                    ),
                )
                chunk_params = [
                    (
                        chunk.chunk_id,
                        document_id,
                        chunk.parent_id,
                        chunk.chunk_index,
                        chunk.content,
                        vector_literal(embeddings[chunk.chunk_id]),
                        Jsonb(chunk.metadata),
                        chunk.token_count,
                        chunk.content_type,
                        chunk.content_checksum,
                        EMBEDDING_MODEL,
                    )
                    for chunk in (*parent_rows, *child_rows, *other_rows)
                ]
                cursor.executemany(CHUNK_INSERT, chunk_params)
                question_params = [
                    (
                        question_uuid(document.source_key, question.number, version),
                        document_id,
                        question.external_id,
                        question.number,
                        question.question,
                        Jsonb(question.options),
                        question.correct_answer,
                        question.explanation,
                        question.domain,
                        document.title,
                        Jsonb(question.metadata),
                        question.topic,
                        question.source_page,
                        question.page_end,
                        question.language,
                        question.checksum,
                    )
                    for question in questions
                ]
                if question_params:
                    cursor.executemany(QUESTION_INSERT, question_params)

    def database_stats(self) -> dict[str, Any]:
        query = """
        select
            (select count(*) from public.documents) as documents,
            (select coalesce(sum(page_count), 0) from public.documents) as pages,
            (select count(*) from public.chunks) as chunks,
            (select count(*) from public.chunks where content_type = 'parent') as parents,
            (select count(*) from public.chunks where content_type = 'child') as children,
            (select count(*) from public.questions) as questions
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            totals = cursor.fetchone()
            cursor.execute(
                "select domain, count(*) as total from public.questions "
                "group by domain order by domain"
            )
            domains = {row["domain"] or "unknown": int(row["total"]) for row in cursor.fetchall()}
        return {
            "documents": int(totals["documents"]),
            "pages": int(totals["pages"]),
            "chunks": int(totals["chunks"]),
            "parents": int(totals["parents"]),
            "children": int(totals["children"]),
            "questions": int(totals["questions"]),
            "domains": domains,
        }

    def integrity_report(self) -> dict[str, int]:
        query = """
        select
            (select count(*) from public.chunks
                where content is null or btrim(content) = '') as empty_chunks,
            (select count(*) from public.chunks
                where embedding is null) as null_embeddings,
            (select count(*) from public.chunks
                where embedding is not null
                  and vector_dims(embedding) <> %s) as wrong_dimensions,
            (select count(*) from public.chunks c
                left join public.chunks p on p.id = c.parent_id
                where c.content_type = 'child'
                  and (c.parent_id is null or p.id is null
                       or p.content_type <> 'parent'
                       or p.document_id <> c.document_id)) as children_without_parent,
            (select count(*) from public.chunks
                where token_count is null or token_count <= 0) as missing_token_counts,
            (select count(*) from public.chunks
                where checksum is null or checksum = '') as missing_checksums,
            (select count(*) from (
                select document_id, chunk_index from public.chunks
                group by document_id, chunk_index having count(*) > 1
            ) as duplicates) as duplicate_chunk_indexes
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query, (EMBEDDING_DIM,))
            row = cursor.fetchone()
        return {key: int(value) for key, value in row.items()}
