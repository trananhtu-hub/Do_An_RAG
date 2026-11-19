from __future__ import annotations

from ingestion.chunking import (
    build_chunks,
    document_uuid,
    question_uuid,
    summarize_chunks,
)
from ingestion.loaders import ExtractedTable
from ingestion.sections import build_sections

PARAGRAPH = (
    "Amazon VPC cung cấp mạng riêng ảo, kiểm soát định tuyến và bảo mật " "kết nối giữa các vùng. "
)
THEORY_TEXT = (
    "Mục 1.1: Tổng quan Amazon VPC và thành phần cốt lõi\n"
    "Lĩnh vực: Thiết kế kiến trúc an toàn\n"
    "Giải thích tổng quan\n" + PARAGRAPH * 30
)
QUESTION_TEXT = (
    "Câu 1: Chọn dịch vụ lưu trữ bền vững\n"
    "Lĩnh vực: Thiết kế kiến trúc kiên cường\n"
    "Giải thích tổng quan\n"
    "Amazon S3 Standard lưu trữ dữ liệu trên nhiều vùng sẵn sàng. "
    "Đáp án đúng là: Amazon S3 Standard. "
    'Tùy chọn có nội dung "EBS gp2" là không chính xác vì chỉ gắn một máy chủ. '
    'Tùy chọn có nội dung "Instance Store" là không chính xác vì mất dữ liệu khi dừng. '
    'Tùy chọn có nội dung "EFS One Zone" là không chính xác vì chỉ một vùng. '
)


def test_chunk_cha_con_dung_kich_thuoc_va_lien_ket(document_factory):
    document = document_factory(THEORY_TEXT)
    chunks = build_chunks(document, build_sections(document))
    parents = [chunk for chunk in chunks if chunk.content_type == "parent"]
    children = [chunk for chunk in chunks if chunk.content_type == "child"]
    assert parents and children
    for parent in parents:
        assert 800 <= parent.token_count <= 1320
    for child in children:
        assert 300 <= child.token_count <= 500
        assert child.parent_id in {parent.chunk_id for parent in parents}
        assert child.parent_id != child.chunk_id
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.content.strip() for chunk in chunks)
    assert all(chunk.metadata["document"] == "data/raw/test.pdf" for chunk in chunks)
    assert all(chunk.metadata["page"] == 1 for chunk in chunks)
    assert any("Mục 1.1" in chunk.metadata["sections"] for chunk in children)
    assert summarize_chunks(chunks)["children"] == len(children)


def test_chunk_on_dinh_giua_hai_lan_chay(document_factory):
    document = document_factory(THEORY_TEXT)
    sections = build_sections(document)
    first = build_chunks(document, sections)
    second = build_chunks(document, sections)
    assert [(chunk.chunk_id, chunk.chunk_index, chunk.content_checksum) for chunk in first] == [
        (chunk.chunk_id, chunk.chunk_index, chunk.content_checksum) for chunk in second
    ]
    assert len({chunk.chunk_id for chunk in first}) == len(first)


def test_chunk_cau_hoi_giu_metadata_nguon(document_factory):
    document = document_factory(QUESTION_TEXT)
    chunks = build_chunks(document, build_sections(document))
    parents = [chunk for chunk in chunks if chunk.content_type == "parent"]
    assert len(parents) == 1
    parent = parents[0]
    assert parent.content.startswith("Câu 1: Chọn dịch vụ lưu trữ bền vững")
    assert parent.metadata["question_number"] == 1
    assert parent.metadata["domain"] == "Resilient"
    assert parent.metadata["kind"] == "question"
    children = [chunk for chunk in chunks if chunk.content_type == "child"]
    assert all(child.parent_id == parent.chunk_id for child in children)


def test_bang_duoc_luu_thanh_chunk_rieng(document_factory):
    table = ExtractedTable(
        page=3,
        index=1,
        rows=[["Lớp lưu trữ", "Độ bền"], ["S3 Standard", "11 số 9"], ["S3 One Zone-IA", "11 số 9"]],
    )
    document = document_factory(THEORY_TEXT, tables=[table])
    chunks = build_chunks(document, build_sections(document))
    table_chunks = [chunk for chunk in chunks if chunk.content_type == "table"]
    assert len(table_chunks) == 1
    chunk = table_chunks[0]
    assert chunk.parent_id is None
    assert chunk.metadata["type"] == "table"
    assert chunk.metadata["page"] == 3
    assert chunk.metadata["rows"] == 3
    assert chunk.metadata["cols"] == 2
    assert chunk.content.startswith("| Lớp lưu trữ | Độ bền |")
    assert "| S3 Standard | 11 số 9 |" in chunk.content


def test_id_tat_dinh():
    assert document_uuid("data/raw/a.pdf") == document_uuid("data/raw/a.pdf")
    assert document_uuid("data/raw/a.pdf") != document_uuid("data/raw/b.pdf")
    assert question_uuid("data/raw/a.pdf", 1) == question_uuid("data/raw/a.pdf", 1)
    assert question_uuid("data/raw/a.pdf", 1) != question_uuid("data/raw/a.pdf", 2)
