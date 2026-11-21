from __future__ import annotations

from app.services.generation.citations import check_citations
from app.services.generation.context import build_context
from app.services.generation.types import AnswerPayload, Citation, ReasoningStep
from conftest import make_chunk

QUOTE = "S3 Standard được thiết kế cho dữ liệu truy cập thường xuyên"


def _payload(answer: str, citations: list[Citation] | None = None) -> AnswerPayload:
    return AnswerPayload(
        answer=answer,
        reasoning_steps=[ReasoningStep(noi_dung="bước")],
        citations=citations or [],
        confidence=0.9,
    )


def _context_and_chunks():
    chunk = make_chunk()
    return build_context([chunk]), [chunk]


def test_valid_citation_matches() -> None:
    context, chunks = _context_and_chunks()
    payload = _payload(
        "S3 Standard phù hợp dữ liệu truy cập thường xuyên [S3 Storage Classes – S3 Standard].",
        [Citation(source="S3 Storage Classes – S3 Standard", quote=QUOTE)],
    )
    report = check_citations(payload, context.blocks, chunks)
    assert report.ok
    assert report.citation_validity == 1.0
    assert report.quote_grounding == 1.0


def test_wrong_section_is_flagged() -> None:
    context, chunks = _context_and_chunks()
    payload = _payload("Nội dung [S3 Storage Classes – S3 Glacier Deep Archive].")
    report = check_citations(payload, context.blocks, chunks)
    assert not report.ok
    assert report.citation_validity == 0.0
    assert "không tìm thấy" in report.unmatched[0].reason


def test_missing_dash_is_flagged() -> None:
    context, chunks = _context_and_chunks()
    payload = _payload("Nội dung [S3 Storage Classes tr. 12].")
    report = check_citations(payload, context.blocks, chunks)
    assert not report.ok
    assert "thiếu mục" in report.unmatched[0].reason


def test_source_key_stem_is_accepted() -> None:
    context, chunks = _context_and_chunks()
    payload = _payload("Nội dung [S3_Storage_Classes – S3 Standard].")
    report = check_citations(payload, context.blocks, chunks)
    assert report.ok


def test_fabricated_quote_is_flagged() -> None:
    context, chunks = _context_and_chunks()
    payload = _payload(
        "Nội dung [S3 Storage Classes – S3 Standard].",
        [
            Citation(
                source="S3 Storage Classes – S3 Standard", quote="S3 Standard miễn phí hoàn toàn"
            )
        ],
    )
    report = check_citations(payload, context.blocks, chunks)
    assert report.quote_grounding < 1.0
    assert any("quote" in issue.reason for issue in report.unmatched)


def test_declared_source_not_in_context_is_flagged() -> None:
    context, chunks = _context_and_chunks()
    payload = _payload(
        "Nội dung [S3 Storage Classes – S3 Standard].",
        [Citation(source="Amazon Bedrock – Models", quote=QUOTE)],
    )
    report = check_citations(payload, context.blocks, chunks)
    assert any("citations" in issue.reason for issue in report.unmatched)


def test_section_with_muc_prefix_matches() -> None:
    chunk = make_chunk(section="Mục 1.2", content="S3 Standard cho dữ liệu nóng.")
    context = build_context([chunk])
    for cited in ("S3 Storage Classes – Mục 1.2", "S3 Storage Classes – 1.2"):
        report = check_citations(_payload(f"Nội dung [{cited}]."), context.blocks, [chunk])
        assert report.ok, cited


def test_section_label_inside_parent_content_matches() -> None:
    chunk = make_chunk(
        section="Mục 1.2",
        content="Mục 1.6: IAM database authentication hỗ trợ token 15 phút.",
    )
    context = build_context([chunk])
    payload = _payload("Token có hiệu lực 15 phút [S3 Storage Classes – Mục 1.6].")
    report = check_citations(payload, context.blocks, [chunk])
    assert report.ok, report.unmatched


def test_comma_separated_sections_are_all_checked() -> None:
    chunk = make_chunk(
        section="Mục 1.4",
        content="Mục 1.4: Standard-IA đa AZ. Mục 1.5: One Zone-IA một AZ.",
    )
    context = build_context([chunk])
    good = _payload("Nội dung [S3 Storage Classes – Mục 1.4, Mục 1.5].")
    assert check_citations(good, context.blocks, [chunk]).ok

    bad = _payload("Nội dung [S3 Storage Classes – Mục 1.4, Mục 9.9].")
    report = check_citations(bad, context.blocks, [chunk])
    assert not report.ok
    assert "1.4, Mục 9.9" in report.unmatched[0].citation


def test_no_citations_has_full_validity() -> None:
    context, chunks = _context_and_chunks()
    report = check_citations(_payload("Không trích dẫn."), context.blocks, chunks)
    assert report.citation_validity == 1.0
    assert report.ok
