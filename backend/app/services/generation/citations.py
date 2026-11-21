from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from ..retrieval.types import RetrievedChunk
from .context import ContextBlock
from .types import AnswerPayload, CitationIssue, CitationReport

_BRACKET = re.compile(r"\[(?!\()[^\[\]\n]{2,200}\](?!\()")
_DASH = re.compile(r"\s*[–—]\s*|\s+-\s+")
_PREFIX = re.compile(r"^(?:mục|section|chương|phần)\s+", re.IGNORECASE)
_NORM_PREFIX = re.compile(r"^(?:muc|section|chuong|phan)\s+")
_PAGE = re.compile(r"[,\s]*(?:tr\.|trang|p\.)\s*\d+\s*$", re.IGNORECASE)
_SECTION_IN_TEXT = re.compile(r"\bmục\s+([0-9]+(?:\.[0-9]+)*)", re.IGNORECASE)
_NON_WORD = re.compile(r"[^0-9a-zà-ỹ\s]")
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class CitationTarget:
    title: str
    section: str
    aliases: frozenset[str]
    sections: frozenset[str]


def build_targets(
    blocks: tuple[ContextBlock, ...],
    chunks: list[RetrievedChunk] | tuple[RetrievedChunk, ...] = (),
) -> tuple[CitationTarget, ...]:
    targets: list[CitationTarget] = []
    for block in blocks:
        aliases = {_normalize(block.document), _normalize(Path(block.document).stem)}
        sections = {_norm_section(block.section)}
        if block.heading:
            sections.add(_norm_section(block.heading))
        # Chunk cha gộp nhiều mục con; nhãn mục xuất hiện trong nội dung cũng là căn cứ hợp lệ.
        sections.update(_normalize(number) for number in _SECTION_IN_TEXT.findall(block.content))
        targets.append(
            CitationTarget(
                title=block.document,
                section=block.section,
                aliases=frozenset(alias for alias in aliases if alias),
                sections=frozenset(section for section in sections if section),
            )
        )
    for chunk in chunks:
        aliases = {
            _normalize(Path(chunk.document).stem),
            _normalize(chunk.document),
            _normalize(chunk.document.replace("_", " ")),
        }
        if chunk.document_title:
            aliases.add(_normalize(chunk.document_title))
        sections = {
            _norm_section(value)
            for value in (chunk.section, chunk.heading)
            if value and value.strip()
        }
        sections.update(_normalize(number) for number in _SECTION_IN_TEXT.findall(chunk.content))
        targets.append(
            CitationTarget(
                title=chunk.document_title or Path(chunk.document).stem,
                section=chunk.section or chunk.heading or "",
                aliases=frozenset(alias for alias in aliases if alias),
                sections=frozenset(sections),
            )
        )
    return tuple(targets)


def check_citations(
    payload: AnswerPayload,
    blocks: tuple[ContextBlock, ...],
    chunks: list[RetrievedChunk] | tuple[RetrievedChunk, ...] = (),
) -> CitationReport:
    targets = build_targets(blocks, chunks)
    inline = tuple(match.group(0)[1:-1].strip() for match in _BRACKET.finditer(payload.answer))
    matched: list[str] = []
    issues: list[CitationIssue] = []
    for citation in inline:
        reason = _citation_issue(citation, targets)
        if reason is None:
            matched.append(citation)
        else:
            issues.append(CitationIssue(citation=citation, reason=reason))

    for citation in payload.citations:
        if _citation_issue(citation.source, targets) is not None:
            issues.append(
                CitationIssue(
                    citation=citation.source,
                    reason="nguồn khai báo trong trường citations không khớp ngữ cảnh",
                )
            )

    haystack = _normalize(" ".join(block.content for block in blocks))
    checked = 0
    found = 0
    for citation in payload.citations:
        quote = _normalize(citation.quote)
        if len(quote) < 12:
            if quote:
                checked += 1
                found += 1
            continue
        checked += 1
        if quote in haystack:
            found += 1
        elif _starts_with_quote(quote, haystack):
            found += 1
        else:
            issues.append(
                CitationIssue(
                    citation=citation.source,
                    reason="quote không xuất hiện nguyên văn trong ngữ cảnh",
                )
            )

    return CitationReport(
        inline_citations=inline,
        matched=tuple(matched),
        unmatched=tuple(issues),
        quotes_checked=checked,
        quotes_found=found,
    )


def _starts_with_quote(quote: str, haystack: str) -> bool:
    """Chấp nhận quote bị mô hình cắt bớt ở cuối nhưng đầu khớp nguyên văn."""
    head = quote[: max(40, int(len(quote) * 0.8))]
    return len(head) >= 40 and head in haystack


def _citation_issue(citation: str, targets: tuple[CitationTarget, ...]) -> str | None:
    parts = _DASH.split(citation.strip(), maxsplit=1)
    if len(parts) != 2:
        return "thiếu mục sau dấu '–' theo định dạng [tài liệu – mục Y]"
    document_raw = _PREFIX.sub("", parts[0].strip()).strip()
    sections_raw = [
        _PREFIX.sub("", piece.strip()).strip()
        for piece in re.split(r"[,;]", _PAGE.sub("", parts[1]))
        if piece.strip()
    ]
    document = _normalize(document_raw)
    if not document:
        return "thiếu tên tài liệu"
    if not sections_raw:
        return "thiếu tên mục"
    for section_raw in sections_raw:
        section = _norm_section(section_raw)
        if not section:
            return "thiếu tên mục"
        matched = any(
            _document_matches(document, target) and _section_matches(section, target)
            for target in targets
        )
        if not matched:
            return (
                "không tìm thấy tài liệu/mục này trong ngữ cảnh đã cấp: "
                f"{document_raw} – {section_raw}"
            )
    return None


def _document_matches(document: str, target: CitationTarget) -> bool:
    for alias in target.aliases:
        if document == alias:
            return True
        if len(document) >= 6 and len(alias) >= 6:
            if document in alias or alias in document:
                return True
    return False


def _section_matches(section: str, target: CitationTarget) -> bool:
    for alias in target.sections:
        if section == alias:
            return True
        if len(section) >= 4 and len(alias) >= 4:
            if section in alias or alias in section:
                return True
    return False


def _norm_section(text: str) -> str:
    return _NORM_PREFIX.sub("", _normalize(text))


def _normalize(text: str) -> str:
    text = _PAGE.sub("", text.strip())
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    text = text.casefold()
    text = _NON_WORD.sub(" ", text)
    return _SPACE.sub(" ", text).strip()
