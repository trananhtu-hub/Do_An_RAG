from __future__ import annotations

import re
from dataclasses import dataclass, field

from .loaders import PdfDocument
from .normalize import flatten_text

SECTION_RE = re.compile(r"^(?P<kind>Câu|Mục)\s+(?P<number>\d+(?:\.\d+){0,3})\s*:\s*(?P<title>.*)$")
DOMAIN_LINE_RE = re.compile(r"^Lĩnh\s+vực\s*:\s*(?P<value>.+)$", re.IGNORECASE)
EXPLANATION_MARKER = "giải thích tổng quan"
TITLE_CONTINUATION_LIMIT = 3


@dataclass
class Section:
    kind: str
    label: str
    number: int | None
    heading: str
    title: str
    body: str
    domain_raw: str | None
    page_start: int
    page_end: int
    lines: list[tuple[int, str]] = field(default_factory=list)

    @property
    def text(self) -> str:
        return f"{self.heading}\n{self.body}".strip()

    @property
    def page_label(self) -> str:
        if self.page_start == self.page_end:
            return f"tr.{self.page_start}"
        return f"tr.{self.page_start}-{self.page_end}"


def document_lines(document: PdfDocument) -> list[tuple[int, str]]:
    lines = []
    for page in document.pages:
        for line in page.text.split("\n"):
            stripped = line.strip()
            if stripped:
                lines.append((page.number, stripped))
    return lines


def _looks_like_title_stop(line: str) -> bool:
    lowered = line.lower()
    if DOMAIN_LINE_RE.match(line) or lowered.startswith(EXPLANATION_MARKER):
        return True
    if line.startswith(("•", "-", "*")):
        return True
    if line.endswith(".") and len(line) > 40:
        return True
    return False


def _extract_title(raw_title: str, following: list[str]) -> tuple[str, int]:
    parts = [raw_title.strip()]
    consumed = 0
    for line in following[:TITLE_CONTINUATION_LIMIT]:
        if _looks_like_title_stop(line):
            break
        parts.append(line)
        consumed += 1
    return flatten_text(" ".join(part for part in parts if part)), consumed


def _extract_domain(lines: list[str]) -> str | None:
    for line in lines:
        match = DOMAIN_LINE_RE.match(line)
        if match:
            return flatten_text(match.group("value"))
    return None


def build_sections(document: PdfDocument) -> list[Section]:
    lines = document_lines(document)
    starts = [index for index, (_, line) in enumerate(lines) if SECTION_RE.match(line)]
    sections: list[Section] = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        block = lines[start:end]
        heading_page, heading_line = block[0]
        match = SECTION_RE.match(heading_line)
        if match is None:
            continue
        body_lines = [line for _, line in block[1:]]
        title, consumed = _extract_title(match.group("title"), body_lines)
        remaining_lines = body_lines[consumed:]
        kind = "question" if match.group("kind") == "Câu" else "section"
        raw_number = match.group("number")
        number = int(raw_number) if kind == "question" and "." not in raw_number else None
        sections.append(
            Section(
                kind=kind,
                label=f"{match.group('kind')} {match.group('number')}",
                number=number,
                heading=f"{match.group('kind')} {match.group('number')}: {title}",
                title=title,
                body="\n".join(remaining_lines),
                domain_raw=_extract_domain(body_lines),
                page_start=heading_page,
                page_end=block[-1][0],
                lines=block,
            )
        )
    return sections


def preamble_text(document: PdfDocument) -> str:
    lines = document_lines(document)
    first = len(lines)
    for index, (_, line) in enumerate(lines):
        if SECTION_RE.match(line):
            first = index
            break
    return "\n".join(line for _, line in lines[:first]).strip()
