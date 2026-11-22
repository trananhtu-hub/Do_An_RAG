from __future__ import annotations

from dataclasses import replace

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
    chunks = [
        make_chunk(
            f"c{i}",
            parent_id=f"p{i}",
            content="x" * 5000,
            section=f"Mục 1.{i + 2}",
            rank=i,
        )
        for i in range(5)
    ]
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


def test_splits_content_at_embedded_section_headings() -> None:
    content = (
        "Mục 1.2: S3 Standard\nS3 Standard cho dữ liệu truy cập thường xuyên.\n"
        "Mục 1.3: Intelligent-Tiering\nIntelligent-Tiering tự chuyển lớp.\n"
        "Mục 1.4: S3 Standard-IA\nStandard-IA có chi phí lưu trữ thấp hơn."
    )
    chunk = replace(make_chunk(), content=content, child_content="S3 Standard cho dữ liệu")
    context = build_context([chunk])
    assert [block.section for block in context.blocks] == ["Mục 1.2", "Mục 1.3", "Mục 1.4"]
    assert "Standard-IA" in context.blocks[2].content
    assert context.blocks[2].heading == "S3 Standard-IA"


def test_keeps_child_content_missing_from_parent() -> None:
    parent = "Mục 1.2: Amazon EBS\nEBS cung cấp volume cho EC2.\nMục 1.3: Instance store"
    child = "Mục 1.4: Amazon EBS\nEBS gắn với một AZ; volume chỉ gắn được cho instance cùng AZ."
    chunk = replace(make_chunk(section="Mục 1.3"), content=parent, child_content=child)
    context = build_context([chunk])
    assert any("EBS gắn với một AZ" in block.content for block in context.blocks)
    assert any(block.section == "Mục 1.4" for block in context.blocks)


def test_merges_overlapping_sections_from_multiple_chunks() -> None:
    first = make_chunk(
        "c1",
        parent_id="p1",
        section="Mục 1.2",
        content="Mục 1.2: S3 Standard\nNội dung đầy đủ của mục 1.2.",
    )
    second = make_chunk(
        "c2",
        parent_id="p2",
        section="Mục 1.2",
        content="Mục 1.2: S3 Standard\nNội dung đầy đủ của mục 1.2.",
    )
    context = build_context([first, second])
    assert len(context.blocks) == 1
    assert context.blocks[0].chunk_ids == ("c1", "c2")
