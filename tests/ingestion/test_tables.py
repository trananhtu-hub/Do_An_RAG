from __future__ import annotations

from ingestion.loaders import table_from_rows


def test_table_markdown_giu_hang_va_cot():
    table = table_from_rows(
        [["Dịch vụ", "Vùng", "Chi phí"], ["S3", "Nhiều AZ", "Thấp"]],
        page=4,
        index=2,
    )
    assert table is not None
    assert table.row_count == 2
    assert table.col_count == 3
    assert table.to_metadata() == {
        "type": "table",
        "page": 4,
        "table_index": 2,
        "rows": 2,
        "cols": 3,
    }
    markdown = table.to_markdown()
    assert markdown.splitlines()[0] == "| Dịch vụ | Vùng | Chi phí |"
    assert markdown.splitlines()[1] == "| --- | --- | --- |"
    assert "| S3 | Nhiều AZ | Thấp |" in markdown


def test_table_bo_qua_hang_rong_va_chuan_hoa_o():
    table = table_from_rows(
        [["A", "B"], ["", ""], ["một\nhai", None]],
        page=1,
        index=1,
    )
    assert table is not None
    assert table.rows == [["A", "B"], ["một hai", ""]]
    assert table.col_count == 2


def test_table_rong_tra_ve_none():
    assert table_from_rows(None, page=1, index=1) is None
    assert table_from_rows([], page=1, index=1) is None
    assert table_from_rows([["", ""]], page=1, index=1) is None
