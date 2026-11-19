from __future__ import annotations

from dataclasses import dataclass

from ..normalize import normalize_text


@dataclass
class ExtractedTable:
    page: int
    index: int
    rows: list[list[str]]

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def col_count(self) -> int:
        return max((len(row) for row in self.rows), default=0)

    def to_markdown(self) -> str:
        return table_to_markdown(self.rows)

    def to_metadata(self) -> dict[str, int | str]:
        return {
            "type": "table",
            "page": self.page,
            "table_index": self.index,
            "rows": self.row_count,
            "cols": self.col_count,
        }


def _clean_cell(value: object) -> str:
    if value is None:
        return ""
    return normalize_text(str(value)).replace("\n", " ").strip()


def table_to_markdown(rows: list[list[str]]) -> str:
    cleaned = [[_clean_cell(cell) for cell in row] for row in rows]
    cleaned = [row for row in cleaned if any(cell for cell in row)]
    if not cleaned:
        return ""
    width = max(len(row) for row in cleaned)
    padded = [row + [""] * (width - len(row)) for row in cleaned]
    header = padded[0]
    body = padded[1:]
    lines = [
        "| " + " | ".join(cell.replace("|", "\\|") for cell in header) + " |",
        "| " + " | ".join("---" for _ in range(width)) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |")
    return "\n".join(lines)


def table_from_rows(
    rows: list[list[object]] | None, page: int, index: int
) -> ExtractedTable | None:
    if not rows:
        return None
    cleaned = [[_clean_cell(cell) for cell in row] for row in rows]
    cleaned = [row for row in cleaned if any(cell for cell in row)]
    if not cleaned:
        return None
    return ExtractedTable(page=page, index=index, rows=cleaned)


def extract_tables_from_page(page: object, number: int) -> list[ExtractedTable]:
    extracted = []
    for index, rows in enumerate(page.extract_tables() or [], start=1):
        table = table_from_rows(rows, page=number, index=index)
        if table is not None:
            extracted.append(table)
    return extracted
