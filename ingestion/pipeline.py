from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .chunking import (
    Chunk,
    build_chunks,
    document_role,
    document_role_from_key,
    summarize_chunks,
)
from .config import (
    DEFAULT_EMBED_CACHE_PATH,
    DEFAULT_INPUT,
    DEFAULT_STATS_PATH,
    DEFAULT_VERSION,
    EXPECTED_QUESTIONS,
    PIPELINE_VERSION,
    Settings,
)
from .embeddings import EmbeddingClient, EmbeddingQuotaError
from .loaders import (
    PdfDocument,
    file_sha256,
    is_external_test,
    iter_pdfs,
    load_pdf,
    source_key_for,
)
from .questions import ExtractedQuestion, extract_questions
from .sections import build_sections
from .store import Store, StoredDocument


def log_event(event: str, **fields: Any) -> None:
    payload = {
        "time": datetime.now(UTC).isoformat(timespec="seconds"),
        "event": event,
        **fields,
    }
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _safe_error(exc: BaseException, settings: Settings) -> str:
    text = f"{type(exc).__name__}: {exc}"
    secrets = [settings.database_url, settings.gemini_api_key, *settings.gemini_api_keys]
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text[:500]


def _cache_key(checksum: str, settings: Settings) -> str:
    return f"{settings.embedding_model}:{settings.embedding_dim}:{checksum}"


def _load_embed_cache(path: Path) -> dict[str, list[float]]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    cache: dict[str, list[float]] = {}
    for key, values in raw.items():
        if not isinstance(values, list):
            continue
        try:
            cache[str(key)] = [float(value) for value in values]
        except (TypeError, ValueError):
            continue
    return cache


def _save_embed_cache(path: Path, cache: dict[str, list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache), encoding="utf-8")
    tmp.replace(path)


@dataclass
class ParsedDocument:
    document: PdfDocument
    chunks: list[Chunk]
    questions: list[ExtractedQuestion]
    metadata: dict[str, Any]
    parse_seconds: float


@dataclass
class RunRecord:
    source_key: str
    title: str
    role: str
    pages: int
    chunks: int
    parents: int
    children: int
    tables: int
    questions: int
    status: str
    seconds: float
    checksum: str = ""
    error_pages: list[int] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_key": self.source_key,
            "title": self.title,
            "role": self.role,
            "pages": self.pages,
            "chunks": self.chunks,
            "parents": self.parents,
            "children": self.children,
            "tables": self.tables,
            "questions": self.questions,
            "status": self.status,
            "seconds": round(self.seconds, 3),
            "checksum": self.checksum[:16],
            "error_pages": self.error_pages,
            "error": self.error,
        }


def _document_metadata(
    document: PdfDocument,
    chunks: Sequence[Chunk],
    questions: Sequence[ExtractedQuestion],
    version: str,
) -> dict[str, Any]:
    summary = summarize_chunks(list(chunks))
    return {
        "source_key": document.source_key,
        "document_title": document.title,
        "document_role": document_role(document),
        "source_type": "pdf",
        "version": version,
        "pipeline_version": PIPELINE_VERSION,
        "checksum": document.checksum,
        "page_count": document.page_count,
        "empty_pages": document.empty_pages,
        "table_count": len(document.tables),
        "image_count": document.image_count,
        "chunk_count": len(chunks),
        "parent_count": summary["parents"],
        "child_count": summary["children"],
        "question_count": len(questions),
        "language": "vi",
    }


def _is_current(
    stored: StoredDocument | None,
    checksum: str,
    force: bool,
) -> bool:
    if force or stored is None or stored.checksum != checksum:
        return False
    metadata = stored.metadata or {}
    if metadata.get("pipeline_version") != PIPELINE_VERSION:
        return False
    if stored.chunk_count <= 0 or stored.null_embeddings > 0:
        return False
    expected_questions = metadata.get("question_count")
    return expected_questions == stored.question_count


def _parse_document(path: Path, version: str) -> ParsedDocument:
    started = time.perf_counter()
    document = load_pdf(path)
    sections = build_sections(document)
    chunks = build_chunks(document, sections, version)
    questions = extract_questions(document, sections)
    metadata = _document_metadata(document, chunks, questions, version)
    return ParsedDocument(
        document=document,
        chunks=chunks,
        questions=questions,
        metadata=metadata,
        parse_seconds=time.perf_counter() - started,
    )


def _skipped_record(stored: StoredDocument, role: str, checksum: str) -> RunRecord:
    metadata = stored.metadata or {}
    return RunRecord(
        source_key=stored.source_key,
        title=str(metadata.get("document_title", stored.source_key)),
        role=role,
        pages=int(stored.page_count or metadata.get("page_count") or 0),
        chunks=stored.chunk_count,
        parents=stored.parent_count,
        children=stored.child_count,
        tables=int(metadata.get("table_count", 0)),
        questions=stored.question_count,
        status="skipped",
        seconds=0.0,
        checksum=checksum,
        error_pages=list(metadata.get("empty_pages", [])),
    )


def _domain_shares(distribution: dict[str, int]) -> dict[str, float]:
    total = sum(distribution.values())
    if total == 0:
        return {}
    return {
        domain: round(count * 100.0 / total, 2) for domain, count in sorted(distribution.items())
    }


def _input_paths(path: Path) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() != ".pdf":
            raise RuntimeError(f"Tệp đầu vào không phải PDF: {path}")
        if is_external_test(path):
            raise RuntimeError("Không được đưa tệp trong data/external_test vào kho tri thức")
        return [path]
    if path.is_dir():
        return iter_pdfs(path)
    raise RuntimeError(f"Không tìm thấy đường dẫn đầu vào: {path}")


def _write_stats(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_ingestion(
    *,
    input_dir: Path,
    stats_path: Path,
    embed_cache_path: Path,
    version: str,
    force: bool,
    settings: Settings,
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    started = time.perf_counter()
    records: list[RunRecord] = []
    failures = 0

    with Store(settings.database_url) as store:
        store.ensure_indexes()
        existing = store.existing_documents()
        paths = _input_paths(input_dir)
        log_event(
            "scan",
            input=str(input_dir),
            documents=len(paths),
            force=force,
            existing=len(existing),
        )
        if not paths:
            raise RuntimeError(f"Không tìm thấy tệp PDF nào trong {input_dir}")

        to_process: list[tuple[Path, str]] = []
        skipped: list[RunRecord] = []
        for path in paths:
            source_key = source_key_for(path)
            checksum = file_sha256(path)
            stored = existing.get(source_key)
            if _is_current(stored, checksum, force):
                assert stored is not None
                skipped.append(
                    _skipped_record(stored, document_role_from_key(source_key), checksum)
                )
                log_event("skip", document=source_key, reason="unchanged")
            else:
                to_process.append((path, checksum))

        parsed: list[ParsedDocument] = []
        for path, checksum in to_process:
            source_key = source_key_for(path)
            try:
                item = _parse_document(path, version)
                parsed.append(item)
                log_event(
                    "parse",
                    document=source_key,
                    pages=item.document.page_count,
                    chunks=len(item.chunks),
                    questions=len(item.questions),
                    tables=len(item.document.tables),
                    seconds=round(item.parse_seconds, 2),
                )
            except Exception as exc:
                failures += 1
                records.append(
                    RunRecord(
                        source_key=source_key,
                        title=path.stem,
                        role=document_role_from_key(source_key),
                        pages=0,
                        chunks=0,
                        parents=0,
                        children=0,
                        tables=0,
                        questions=0,
                        status="failed",
                        seconds=0.0,
                        checksum=checksum,
                        error=_safe_error(exc, settings),
                    )
                )
                log_event(
                    "parse_failed",
                    document=source_key,
                    error=_safe_error(exc, settings),
                )

        vectors: dict[str, list[float]] = {}
        embedding_seconds = 0.0
        batches = 0
        retries = 0
        resumed = 0
        all_chunks = [chunk for item in parsed for chunk in item.chunks]
        if all_chunks:
            cache = _load_embed_cache(embed_cache_path)
            cached = {
                chunk.chunk_id: cache[_cache_key(chunk.content_checksum, settings)]
                for chunk in all_chunks
                if _cache_key(chunk.content_checksum, settings) in cache
            }
            missing = [chunk for chunk in all_chunks if chunk.chunk_id not in cached]
            resumed = len(cached)
            vectors.update(cached)
            log_event(
                "embed_start",
                chunks=len(all_chunks),
                cached=resumed,
                missing=len(missing),
                keys=len(settings.gemini_api_keys),
            )
            if missing:
                embed_started = time.perf_counter()
                milestone = 0

                def report_progress(done: int, total_count: int) -> None:
                    nonlocal milestone
                    if done >= milestone + 200 or done == total_count:
                        milestone = done
                        log_event("embed_progress", done=done, total=total_count)

                def checkpoint(done: int, batch_vectors: list[list[float]]) -> None:
                    start = done - len(batch_vectors)
                    for offset, vector in enumerate(batch_vectors):
                        chunk = missing[start + offset]
                        cache[_cache_key(chunk.content_checksum, settings)] = vector
                        vectors[chunk.chunk_id] = vector
                    _save_embed_cache(embed_cache_path, cache)

                try:
                    with EmbeddingClient(
                        settings.gemini_api_keys,
                        model=settings.embedding_model,
                        dimensions=settings.embedding_dim,
                        batch_size=settings.embedding_batch_size,
                    ) as client:
                        result = client.embed_texts(
                            [chunk.content for chunk in missing],
                            progress=report_progress,
                            checkpoint=checkpoint,
                        )
                except EmbeddingQuotaError as exc:
                    log_event(
                        "quota_exhausted",
                        embedded_in_run=exc.done,
                        remaining=exc.total - exc.done,
                        cached=len(vectors),
                        chunks=len(all_chunks),
                        cache=str(embed_cache_path),
                        message=str(exc),
                    )
                    raise
                embedding_seconds = time.perf_counter() - embed_started
                batches = result.batches
                retries = result.retries
            log_event(
                "embed_done",
                vectors=len(vectors),
                batches=batches,
                retries=retries,
                seconds=round(embedding_seconds, 2),
            )

        for item in parsed:
            source_key = item.document.source_key
            write_started = time.perf_counter()
            try:
                document_vectors = {
                    chunk.chunk_id: vectors[chunk.chunk_id] for chunk in item.chunks
                }
                store.replace_document(
                    document=item.document,
                    chunks=item.chunks,
                    questions=item.questions,
                    embeddings=document_vectors,
                    metadata=item.metadata,
                    version=version,
                )
                summary = summarize_chunks(item.chunks)
                records.append(
                    RunRecord(
                        source_key=source_key,
                        title=item.document.title,
                        role=document_role(item.document),
                        pages=item.document.page_count,
                        chunks=len(item.chunks),
                        parents=summary["parents"],
                        children=summary["children"],
                        tables=len(item.document.tables),
                        questions=len(item.questions),
                        status="ingested",
                        seconds=item.parse_seconds + (time.perf_counter() - write_started),
                        checksum=item.document.checksum,
                        error_pages=item.document.empty_pages,
                    )
                )
                log_event(
                    "write",
                    document=source_key,
                    chunks=len(item.chunks),
                    questions=len(item.questions),
                )
            except Exception as exc:
                failures += 1
                records.append(
                    RunRecord(
                        source_key=source_key,
                        title=item.document.title,
                        role=document_role(item.document),
                        pages=item.document.page_count,
                        chunks=len(item.chunks),
                        parents=0,
                        children=0,
                        tables=len(item.document.tables),
                        questions=len(item.questions),
                        status="failed",
                        seconds=item.parse_seconds,
                        checksum=item.document.checksum,
                        error=_safe_error(exc, settings),
                    )
                )
                log_event(
                    "write_failed",
                    document=source_key,
                    error=_safe_error(exc, settings),
                )

        records.extend(skipped)
        records.sort(key=lambda record: record.source_key)
        database = store.database_stats()
        integrity = store.integrity_report()
        domain_shares = _domain_shares(database["domains"])
        question_coverage = (
            round(database["questions"] * 100.0 / EXPECTED_QUESTIONS, 2)
            if EXPECTED_QUESTIONS
            else 0.0
        )
        duration = time.perf_counter() - started

    stats = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "duration_seconds": round(duration, 2),
        "pipeline_version": PIPELINE_VERSION,
        "version": version,
        "force": force,
        "input": str(input_dir),
        "run": {
            "documents_seen": len(records),
            "ingested": sum(1 for record in records if record.status == "ingested"),
            "skipped": sum(1 for record in records if record.status == "skipped"),
            "failed": sum(1 for record in records if record.status == "failed"),
            "chunks_written": sum(
                record.chunks for record in records if record.status == "ingested"
            ),
            "questions_written": sum(
                record.questions for record in records if record.status == "ingested"
            ),
            "embeddings": len(vectors),
            "embedding_batches": batches,
            "embedding_resumed": resumed,
            "embedding_retries": retries,
            "embedding_seconds": round(embedding_seconds, 2),
        },
        "database": database,
        "domain_shares_percent": domain_shares,
        "question_coverage_percent": question_coverage,
        "expected_questions": EXPECTED_QUESTIONS,
        "integrity": integrity,
        "documents": [record.to_dict() for record in records],
    }
    _write_stats(stats_path, stats)
    log_event(
        "summary",
        ingested=stats["run"]["ingested"],
        skipped=stats["run"]["skipped"],
        failed=stats["run"]["failed"],
        chunks=database["chunks"],
        questions=database["questions"],
        seconds=round(duration, 2),
        stats=str(stats_path),
    )

    bad_integrity = any(value != 0 for value in integrity.values())
    if failures or bad_integrity:
        raise IngestionFailed("Nạp dữ liệu có lỗi; xem chi tiết trong tệp thống kê")
    return stats


class IngestionFailed(RuntimeError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Nạp PDF AWS SAA-C03 vào Supabase (pdfplumber + Gemini embeddings)"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--stats-path", type=Path, default=DEFAULT_STATS_PATH)
    parser.add_argument("--embed-cache", type=Path, default=DEFAULT_EMBED_CACHE_PATH)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Nạp lại toàn bộ, bỏ qua kiểm tra checksum",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = Settings.from_env()
    except RuntimeError as exc:
        log_event("config_error", error=str(exc))
        return 2
    log_event(
        "start",
        input=str(args.input),
        version=args.version,
        force=args.force,
        pipeline_version=PIPELINE_VERSION,
    )
    try:
        run_ingestion(
            input_dir=args.input,
            stats_path=args.stats_path,
            embed_cache_path=args.embed_cache,
            version=args.version,
            force=args.force,
            settings=settings,
        )
    except IngestionFailed as exc:
        log_event("failed", error=str(exc))
        return 1
    except EmbeddingQuotaError:
        return 3
    except Exception as exc:
        log_event("error", error=_safe_error(exc, settings))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
