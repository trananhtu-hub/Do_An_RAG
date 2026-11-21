from __future__ import annotations

import json

from ingestion.questions import extract_questions, load_answer_overrides
from ingestion.sections import build_sections

QUESTION_TEXT = """Câu 1: Thiết kế lưu trữ bền vững cho ứng dụng
Lĩnh vực: Thiết kế kiến trúc kiên cường
Giải thích tổng quan
Amazon S3 cung cấp độ bền dữ liệu rất cao và sao chép nhiều vùng.
Đáp án đúng là: S3 Standard.
Tùy chọn có nội dung "S3 One Zone-IA" là không chính xác vì chỉ lưu một vùng.
Tùy chọn có nội dung "EBS gp2" là không chính xác vì chỉ gắn một máy chủ.
Tùy chọn có nội dung "Instance Store" là không chính xác vì mất dữ liệu khi dừng.
Tài liệu tham khảo
https://docs.aws.amazon.com/s3/
Câu 2: Chọn dịch vụ tính toán
Lĩnh vực: Thiết kế kiến trúc hiệu năng cao
Giải thích tổng quan
Amazon EC2 phù hợp cho tải cần kiểm soát máy chủ.
Đáp án đúng là: Amazon EC2
"""


def test_sections_nhan_dien_cau_va_lay_tieu_de_day_du(document_factory):
    document = document_factory(QUESTION_TEXT)
    sections = build_sections(document)
    assert [section.label for section in sections] == ["Câu 1", "Câu 2"]
    assert sections[0].heading == "Câu 1: Thiết kế lưu trữ bền vững cho ứng dụng"
    assert sections[0].domain_raw == "Thiết kế kiến trúc kiên cường"
    assert sections[0].page_start == 1
    assert sections[0].page_end == 1


def test_extract_questions_du_truong_va_domain_chuan_hoa(document_factory):
    document = document_factory(QUESTION_TEXT)
    questions = extract_questions(document, build_sections(document))
    assert len(questions) == 2
    first = questions[0]
    assert first.external_id == "aws-saa-q0001"
    assert first.question == "Thiết kế lưu trữ bền vững cho ứng dụng"
    assert first.correct_answer == "S3 Standard"
    assert first.options[0]["label"] == "A"
    assert first.options[0]["is_correct"] is True
    assert first.domain == "Resilient"
    assert first.source_page == 1
    assert first.language == "vi"
    assert len(first.checksum) == 64
    assert first.metadata["answer_source"] == "vi_colon"

    second = questions[1]
    assert second.domain == "High-Performing"
    assert second.number == 2


def test_dap_an_bo_sung_dien_khi_trich_xuat_that_bai(document_factory):
    text = (
        "Câu 3: Chủ đề chưa có đáp án\n"
        "Lĩnh vực: Thiết kế kiến trúc bảo mật\n"
        "Giải thích tổng quan\n"
        "Nội dung mô tả dịch vụ phù hợp.\n"
    )
    document = document_factory(text)
    questions = extract_questions(
        document,
        build_sections(document),
        {
            3: {
                "correct_answer": "Amazon Kinesis",
                "basis": "explicit",
                "note": "Giải thích nêu trực tiếp.",
            }
        },
    )
    assert questions[0].correct_answer == "Amazon Kinesis"
    assert questions[0].options[0]["is_correct"] is True
    assert questions[0].options[0]["text"] == "Amazon Kinesis"
    assert questions[0].metadata["answer_source"] == "manual_review"
    assert questions[0].metadata["answer_override_basis"] == "explicit"
    assert questions[0].metadata["answer_override_note"] == "Giải thích nêu trực tiếp."
    assert "missing_correct_answer" not in questions[0].metadata["warnings"]


def test_dap_an_bo_sung_khong_ghi_de_dap_an_da_trich(document_factory):
    document = document_factory(QUESTION_TEXT)
    questions = extract_questions(
        document,
        build_sections(document),
        {1: {"correct_answer": "Đáp án khác", "basis": "explicit", "note": ""}},
    )
    assert questions[0].correct_answer == "S3 Standard"
    assert questions[0].metadata["answer_source"] == "vi_colon"
    assert "answer_override_note" not in questions[0].metadata


def test_load_answer_overrides_doc_tep_va_bo_qua_tep_khong_ton_tai(tmp_path):
    path = tmp_path / "overrides.json"
    path.write_text(
        json.dumps(
            {"a.pdf": {"5": {"correct_answer": "X", "basis": "explicit", "note": "n"}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    data = load_answer_overrides(path)
    assert data["a.pdf"][5]["correct_answer"] == "X"
    assert load_answer_overrides(tmp_path / "khong-ton-tai.json") == {}


def test_tieu_de_bi_ngat_dong_duoc_noi_lai(document_factory):
    text = (
        "Câu 7: Thiết kế hệ thống có khả năng chịu lỗi\n"
        "và tự động mở rộng theo lưu lượng\n"
        "Lĩnh vực: Thiết kế kiến trúc linh hoạt\n"
        "Giải thích tổng quan\n"
        "Nội dung giải thích.\n"
    )
    document = document_factory(text)
    sections = build_sections(document)
    assert sections[0].title == (
        "Thiết kế hệ thống có khả năng chịu lỗi và tự động mở rộng theo lưu lượng"
    )
    assert sections[0].body.startswith("Lĩnh vực:")
