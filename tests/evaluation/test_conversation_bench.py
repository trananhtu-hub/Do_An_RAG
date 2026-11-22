from __future__ import annotations

from pathlib import Path

from evaluation.conversation_bench import (
    _citation_document_ok,
    _criteria_for_turn,
    auto_checks,
    load_scenarios,
)


def _scenario(code: str):
    return next(scenario for scenario in load_scenarios() if scenario.code == code)


def test_kb08_turn2_khong_doi_ca_hai_tai_lieu() -> None:
    """Hồi quy KB-08 lượt 2: Căn cứ chỉ ghi mục, không được đòi cả S3 lẫn IAM."""
    scenario = _scenario("KB-08")
    turn = scenario.turns[1]
    assert _citation_document_ok(scenario, turn, ["S3 Storage Classes – Mục 1.10 (tr. 7–8)"])
    assert _citation_document_ok(scenario, turn, ["S3 Storage Classes – Mục 1.10", "IAM – Mục 1.6"])
    assert not _citation_document_ok(scenario, turn, ["IAM – Mục 1.6 (tr. 5)"])
    assert not _citation_document_ok(scenario, turn, ["S3 Storage Classes – Mục 1.1"])


def test_kb08_turn2_auto_check_trich_dan_dat_voi_chi_s3() -> None:
    scenario = _scenario("KB-08")
    turn = scenario.turns[1]
    record = {
        "answer": "Tối thiểu 180 ngày; thời gian khôi phục 12–48 giờ.",
        "rewritten_query": "Nên chuyển log S3 sang Glacier Deep Archive sau bao lâu?",
        "citations": [
            {
                "source": "S3 Storage Classes – Mục 1.10 (tr. 7–8)",
                "quote": "Glacier Deep Archive",
            }
        ],
    }
    checks = auto_checks(scenario, turn, record, _sources(record))
    citation = next(check for check in checks if check[0] == "trích dẫn đúng tài liệu/mục")
    assert citation[1], citation[2]


def test_kb01_turn2_doi_du_hai_tai_lieu() -> None:
    scenario = _scenario("KB-01")
    turn = scenario.turns[1]
    assert _citation_document_ok(
        scenario, turn, ["S3 Storage Classes – Mục 1.1", "EC2 Tinh toan – Mục 1.4"]
    )
    assert not _citation_document_ok(scenario, turn, ["S3 Storage Classes – Mục 1.1"])


def test_kb08_luot1_khong_nhan_tieu_chi_iam() -> None:
    scenario = _scenario("KB-08")
    criteria = _criteria_for_turn(scenario, scenario.turns[0])
    assert not any("IAM" in item for item in criteria)


def test_kb08_luot3_nhan_tieu_chi_iam_va_doi_chu_de() -> None:
    scenario = _scenario("KB-08")
    criteria = _criteria_for_turn(scenario, scenario.turns[2])
    assert any("IAM" in item for item in criteria)
    assert any("đổi chủ đề" in item.casefold() for item in criteria)
    assert not any(item.startswith("Lượt 4") for item in criteria)


def _sources(record: dict) -> list[str]:
    return [citation["source"] for citation in record.get("citations", [])]


def test_dev_scenarios_parse_du_ma_dv() -> None:
    scenarios = load_scenarios(Path("inputs/conversations_dev.md"))
    expected = [f"DV-{index:02d}" for index in range(1, 11)]
    assert [scenario.code for scenario in scenarios] == expected
    assert all(len(scenario.turns) == 4 for scenario in scenarios)
