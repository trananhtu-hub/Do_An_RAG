from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..retrieval.types import RetrievedChunk


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
    """Gộp chunk theo mục cha và cắt vừa ngân sách token ước tính."""
    blocks: list[ContextBlock] = []
    seen: dict[str, int] = {}
    for chunk in chunks:
        key = chunk.parent_id or chunk.child_id
        if key in seen:
            index = seen[key]
            existing = blocks[index]
            blocks[index] = ContextBlock(
                index=existing.index,
                document=existing.document,
                section=existing.section,
                heading=existing.heading,
                content=existing.content,
                chunk_ids=(*existing.chunk_ids, chunk.child_id),
            )
            continue
        content = _truncate(chunk.content.strip(), max_block_chars)
        if not content:
            continue
        seen[key] = len(blocks)
        blocks.append(
            ContextBlock(
                index=len(blocks) + 1,
                document=document_name(chunk),
                section=section_name(chunk),
                heading=chunk.heading,
                content=content,
                chunk_ids=(chunk.child_id,),
            )
        )

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

    text = "\n\n".join(_render(block) for block in kept)
    return BuiltContext(
        text=text,
        blocks=tuple(kept),
        estimated_tokens=int(used / chars_per_token),
        dropped_blocks=dropped,
    )


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
