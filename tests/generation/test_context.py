from __future__ import annotations

from app.services.generation.context import build_context, document_name, section_name
from conftest import make_chunk


def test_renders_labels_and_content() -> None:
    context = build_context([make_chunk()])
    assert "[ĐOẠN 1]" in context.text
    assert "Tài liệu: S3 Storage Classes" in context.text
    assert "Mục: S3 Standard" in context.text
    assert context.estimated_tokens > 0
    assert not context.is_empty


def test_deduplicates_same_parent() -> None:
    first = make_chunk("c1", parent_id="p1", rank=1)
    second = make_chunk("c2", parent_id="p1", rank=2)
    context = build_context([first, second])
    assert len(context.blocks) == 1
    assert context.blocks[0].chunk_ids == ("c1", "c2")


def test_document_name_falls_back_to_stem() -> None:
    chunk = make_chunk(document_title=None)
    assert document_name(chunk) == "S3 Storage Classes"


def test_section_falls_back_to_heading() -> None:
    chunk = make_chunk(section=None, heading="Tổng quan")
    assert section_name(chunk) == "Tổng quan"


def test_budget_drops_blocks_beyond_limit() -> None:
    chunks = [make_chunk(f"c{i}", parent_id=f"p{i}", content="x" * 5000, rank=i) for i in range(5)]
    context = build_context(chunks, max_context_tokens=1000, chars_per_token=3.5)
    assert context.dropped_blocks > 0
    assert len(context.blocks) < len(chunks)
    assert "ĐOẠN" in context.text


def test_empty_input() -> None:
    context = build_context([])
    assert context.is_empty
    assert context.text == ""


def test_long_block_is_truncated() -> None:
    chunk = make_chunk(content="a" * 20_000)
    context = build_context([chunk], max_block_chars=1000)
    assert len(context.blocks[0].content) <= 1010
    assert "[…]" in context.blocks[0].content
