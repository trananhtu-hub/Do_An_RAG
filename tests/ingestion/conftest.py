from __future__ import annotations

from pathlib import Path

import pytest

from ingestion.loaders import PdfDocument, PdfPage


def make_document(
    text: str,
    *,
    source_key: str = "data/raw/test.pdf",
    title: str = "Tài liệu thử",
    tables: list | None = None,
) -> PdfDocument:
    return PdfDocument(
        path=Path(source_key),
        source_key=source_key,
        title=title,
        checksum="checksum-test",
        pages=[PdfPage(number=1, text=text)],
        tables=tables or [],
    )


@pytest.fixture
def document_factory():
    return make_document
