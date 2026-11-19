from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from ..config import PROJECT_ROOT
from ..normalize import normalize_text
from .tables import ExtractedTable, extract_tables_from_page


@dataclass(frozen=True)
class PdfPage:
    number: int
    text: str


@dataclass
class PdfDocument:
    path: Path
    source_key: str
    title: str
    checksum: str
    pages: list[PdfPage]
    tables: list[ExtractedTable] = field(default_factory=list)
    image_count: int = 0

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def empty_pages(self) -> list[int]:
        return [page.number for page in self.pages if not page.text.strip()]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_key_for(path: Path, project_root: Path = PROJECT_ROOT) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return resolved.name


def is_external_test(path: Path) -> bool:
    return any(part.lower() == "external_test" for part in path.parts)


def iter_pdfs(input_dir: Path) -> list[Path]:
    paths = [
        path
        for path in sorted(input_dir.glob("*.pdf"), key=lambda item: item.name.lower())
        if not is_external_test(path)
    ]
    return paths


def title_from_path(path: Path) -> str:
    return path.stem.replace("_", " ").strip()


def load_pdf(path: Path, project_root: Path = PROJECT_ROOT) -> PdfDocument:
    pages: list[PdfPage] = []
    tables: list[ExtractedTable] = []
    image_count = 0
    with pdfplumber.open(str(path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            raw_text = page.extract_text() or ""
            pages.append(PdfPage(number=index, text=normalize_text(raw_text)))
            tables.extend(extract_tables_from_page(page, number=index))
            image_count += len(page.images)
    return PdfDocument(
        path=path,
        source_key=source_key_for(path, project_root),
        title=title_from_path(path),
        checksum=file_sha256(path),
        pages=pages,
        tables=tables,
        image_count=image_count,
    )
