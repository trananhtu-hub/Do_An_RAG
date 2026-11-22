from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path

from ..retrieval.types import RetrievedChunk

_SECTION_HEADING = re.compile(r"(?m)^[ \t]*Mục[ \t]+(\d+(?:\.\d+)*)[ \t]*[:.\-–][ \t]*(.*?)[ \t]*$")
_GENERIC_SECTIONS = frozenset({"", "Toàn văn"})


@dataclass(frozen=True)
class ContextBlock:
    index: int
    document: str
    section: str
    heading: str | None
    content: str
    chunk_ids: tuple[str, ...]

    @property
    def label(self) -> str:
        return f"{self.document} – {self.section}"


@dataclass(frozen=True)
class BuiltContext:
    text: str
    blocks: tuple[ContextBlock, ...]
    estimated_tokens: int
    dropped_blocks: int

    @property
    def is_empty(self) -> bool:
        return not self.blocks


def build_context(
    chunks: list[RetrievedChunk] | tuple[RetrievedChunk, ...],
    *,
    max_context_tokens: int = 8000,
    chars_per_token: float = 3.5,
    max_block_chars: int = 6000,
) -> BuiltContext:
    """Tách nội dung theo tiêu đề mục để nhãn trích dẫn khớp nội dung thật.

    Chunk con có thể vắt qua ranh giới mục, còn chunk cha có thể gộp nhiều mục.
    Nếu giữ nguyên nhãn của chunk, mô hình sẽ trích sai mục; tách theo dòng
    "Mục N:" trong nội dung khắc phục lệch nhãn mà không đổi truy xuất.
    """
    blocks = _collect_blocks(chunks, max_block_chars)
    budget_chars = int(max_context_tokens * chars_per_token)
    kept: list[ContextBlock] = []
    used = 0
    for block in blocks:
        cost = _block_chars(block)
        if kept and used + cost > budget_chars:
            break
        kept.append(block)
        used += cost
    dropped = len(blocks) - len(kept)
    kept = [replace(block, index=index) for index, block in enumerate(kept, start=1)]

    text = "\n\n".join(_render(block) for block in kept)
    return BuiltContext(
        text=text,
        blocks=tuple(kept),
        estimated_tokens=int(used / chars_per_token),
        dropped_blocks=dropped,
    )


@dataclass(frozen=True)
class _Segment:
    document: str
    section: str
    heading: str | None
    content: str
    chunk_id: str


def _collect_blocks(
    chunks: list[RetrievedChunk] | tuple[RetrievedChunk, ...],
    max_block_chars: int,
) -> list[ContextBlock]:
    blocks: list[ContextBlock] = []
    positions: dict[tuple[str, ...], list[int]] = {}
    for chunk in chunks:
        for segment in _chunk_segments(chunk):
            content = _truncate(segment.content, max_block_chars)
            if not content:
                continue
            if segment.section in _GENERIC_SECTIONS:
                key: tuple[str, ...] = (segment.document, segment.section, segment.chunk_id)
            else:
                key = (segment.document, segment.section)
            bucket = positions.setdefault(key, [])
            for index in reversed(bucket):
                existing = blocks[index]
                if _within(content, existing.content):
                    blocks[index] = replace(
                        existing, chunk_ids=_union(existing.chunk_ids, segment.chunk_id)
                    )
                    break
                if _within(existing.content, content):
                    blocks[index] = replace(
                        existing,
                        heading=segment.heading or existing.heading,
                        content=content,
                        chunk_ids=_union(existing.chunk_ids, segment.chunk_id),
                    )
                    break
            else:
                bucket.append(len(blocks))
                blocks.append(
                    ContextBlock(
                        index=0,
                        document=segment.document,
                        section=segment.section,
                        heading=segment.heading,
                        content=content,
                        chunk_ids=(segment.chunk_id,),
                    )
                )
    return blocks


def _chunk_segments(chunk: RetrievedChunk) -> list[_Segment]:
    document = document_name(chunk)
    fallback_section = section_name(chunk)
    content = chunk.content.strip()
    segments: list[_Segment] = []
    if content:
        segments.extend(
            _split_segments(document, fallback_section, chunk.heading, content, chunk.child_id)
        )
    child = (chunk.child_content or "").strip()
    if child and child != content and not _within(child, content):
        # Chunk cha có thể không chứa trọn nội dung con (chunk con vắt qua mục);
        # giữ thêm nội dung con để không mất dữ kiện chỉ có trong chunk con.
        segments.extend(
            _split_segments(document, fallback_section, chunk.heading, child, chunk.child_id)
        )
    return segments


def _split_segments(
    document: str,
    fallback_section: str,
    fallback_heading: str | None,
    content: str,
    chunk_id: str,
) -> list[_Segment]:
    matches = list(_SECTION_HEADING.finditer(content))
    if not matches:
        return [_Segment(document, fallback_section, fallback_heading, content, chunk_id)]
    segments: list[_Segment] = []
    preamble = content[: matches[0].start()].strip()
    if preamble:
        segments.append(_Segment(document, fallback_section, fallback_heading, preamble, chunk_id))
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(content)
        body = content[match.start() : end].strip()
        if not body:
            continue
        segments.append(
            _Segment(
                document,
                f"Mục {match.group(1)}",
                match.group(2).strip() or None,
                body,
                chunk_id,
            )
        )
    return segments


def _within(inner: str, outer: str) -> bool:
    if not inner or not outer:
        return False
    return _collapse(inner) in _collapse(outer)


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _union(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    return values if value in values else (*values, value)


def document_name(chunk: RetrievedChunk) -> str:
    if chunk.document_title:
        return chunk.document_title.strip()
    source = Path(chunk.document).stem
    return source.replace("_", " ").strip() or chunk.document


def section_name(chunk: RetrievedChunk) -> str:
    if chunk.section and chunk.section.strip():
        return chunk.section.strip()
    if chunk.heading and chunk.heading.strip():
        return chunk.heading.strip()
    return "Toàn văn"


def _render(block: ContextBlock) -> str:
    return (
        f"[ĐOẠN {block.index}]\n"
        f"Tài liệu: {block.document}\n"
        f"Mục: {block.section}\n"
        f"Nội dung:\n{block.content}"
    )


def _block_chars(block: ContextBlock) -> int:
    return len(block.content) + len(block.document) + len(block.section) + 60


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    pivot = cut.rfind("\n")
    if pivot > limit * 0.6:
        cut = cut[:pivot]
    return cut.rstrip() + " […]"
