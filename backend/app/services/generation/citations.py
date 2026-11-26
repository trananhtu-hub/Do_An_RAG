from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


def inline_citation_sources(answer: str) -> list[str]:
    """Chuỗi trích dẫn dạng [Nguồn – Mục] trong câu trả lời, giữ thứ tự xuất hiện."""
    seen: set[str] = set()
    sources: list[str] = []
    for match in _BRACKET.finditer(answer):
        value = match.group(0)[1:-1].strip()
        if value and value not in seen:
            seen.add(value)
            sources.append(value)
    return sources


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


@dataclass(frozen=True)
class _EnrichmentCandidate:
    document: str
    document_title: str
    section: str
    page: int | None
    aliases: frozenset[str]
    sections: frozenset[str]


def enrich_citations(
    payload: AnswerPayload,
    blocks: tuple[ContextBlock, ...],
    chunks: list[RetrievedChunk] | tuple[RetrievedChunk, ...] = (),
) -> list[dict[str, Any]]:
    """Bổ sung tài liệu, mục và trang cho từng trích dẫn để UI mở đúng chỗ.

    Mô hình chỉ trả về chuỗi ``[tài liệu – mục]``; các trường còn lại được đối
    chiếu với ngữ cảnh đã truy xuất. Trích dẫn không khớp vẫn giữ nguyên chuỗi
    gốc để người dùng thấy thay vì bị ẩn đi.
    """
    candidates = _enrichment_candidates(blocks, chunks)
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for citation in payload.citations:
        source = citation.source.strip()
        if not source or source in seen:
            continue
        seen.add(source)
        entries.append(_enrich_entry(source, citation.quote, candidates))
    # Câu trả lời có thể nhắc trích dẫn dạng inline mà không khai lại ở trường
    # citations; vẫn hiện chip để người dùng lần được tới tài liệu.
    for source in inline_citation_sources(payload.answer):
        if source in seen:
            continue
        seen.add(source)
        entries.append(_enrich_entry(source, "", candidates))
    return entries


def _enrich_entry(
    source: str,
    quote: str,
    candidates: tuple[_EnrichmentCandidate, ...],
) -> dict[str, Any]:
    parsed = _parse_citation(source)
    match: _EnrichmentCandidate | None = None
    if parsed is not None:
        document, sections = parsed
        match = _match_candidate(document, sections, candidates)
    return {
        "source": source,
        "quote": quote,
        "document": match.document if match else None,
        "document_title": match.document_title if match else None,
        "section": match.section if match else None,
        "page": match.page if match else None,
    }


def _parse_citation(source: str) -> tuple[str, list[str]] | None:
    parts = _DASH.split(source.strip(), maxsplit=1)
    if len(parts) != 2:
        return None
    document = _normalize(_PREFIX.sub("", parts[0].strip()).strip())
    if not document:
        return None
    sections = [
        _norm_section(_PREFIX.sub("", piece.strip()).strip())
        for piece in re.split(r"[,;]", _PAGE.sub("", parts[1]))
        if piece.strip()
    ]
    sections = [section for section in sections if section]
    return (document, sections) if sections else None


def _match_candidate(
    document: str,
    sections: list[str],
    candidates: tuple[_EnrichmentCandidate, ...],
) -> _EnrichmentCandidate | None:
    scored: list[tuple[int, int, _EnrichmentCandidate]] = []
    for index, candidate in enumerate(candidates):
        if not _document_matches(document, candidate):
            continue
        section_match = any(_section_matches(section, candidate) for section in sections)
        if not section_match:
            continue
        score = 0 if candidate.page is not None else 1
        scored.append((score, index, candidate))
    if scored:
        scored.sort(key=lambda item: (item[0], item[1]))
        return scored[0][2]
    # Không khớp mục nhưng khớp tài liệu: vẫn mở được tài liệu, chỉ thiếu số trang.
    for candidate in candidates:
        if _document_matches(document, candidate) and candidate.page is not None:
            return candidate
    return None


def _enrichment_candidates(
    blocks: tuple[ContextBlock, ...],
    chunks: list[RetrievedChunk] | tuple[RetrievedChunk, ...],
) -> tuple[_EnrichmentCandidate, ...]:
    by_id = {chunk.child_id: chunk for chunk in chunks}
    candidates: list[_EnrichmentCandidate] = []
    for chunk in chunks:
        aliases = {
            _normalize(chunk.document),
            _normalize(chunk.document.replace("_", " ")),
            _normalize(Path(chunk.document).stem),
        }
        title = chunk.document_title or Path(chunk.document).stem
        aliases.add(_normalize(title))
        sections = {
            _norm_section(value)
            for value in (chunk.section, chunk.heading)
            if value and value.strip()
        }
        sections.update(_normalize(number) for number in _SECTION_IN_TEXT.findall(chunk.content))
        candidates.append(
            _EnrichmentCandidate(
                document=chunk.document,
                document_title=title,
                section=chunk.section or chunk.heading or "",
                page=chunk.page,
                aliases=frozenset(alias for alias in aliases if alias),
                sections=frozenset(section for section in sections if section),
            )
        )
    for block in blocks:
        link = next((by_id[chunk_id] for chunk_id in block.chunk_ids if chunk_id in by_id), None)
        title = block.document if link is None else link.document_title or block.document
        aliases = {
            _normalize(block.document),
            _normalize(block.document.replace("_", " ")),
            _normalize(Path(block.document).stem),
            _normalize(title),
        }
        sections = {_norm_section(block.section)}
        if block.heading:
            sections.add(_norm_section(block.heading))
        sections.update(_normalize(number) for number in _SECTION_IN_TEXT.findall(block.content))
        candidates.append(
            _EnrichmentCandidate(
                document=block.document,
                document_title=title,
                section=block.section,
                page=link.page if link is not None else None,
                aliases=frozenset(alias for alias in aliases if alias),
                sections=frozenset(section for section in sections if section),
            )
        )
    return tuple(candidates)


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
