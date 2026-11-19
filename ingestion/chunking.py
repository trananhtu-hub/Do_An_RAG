from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from .config import (
    CHILD_MAX_TOKENS,
    CHILD_MIN_TOKENS,
    CHILD_OVERLAP_RATIO,
    DEFAULT_VERSION,
    PARENT_MAX_TOKENS,
    PARENT_MIN_TOKENS,
)
from .domains import (
    DOMAIN_CODES,
    infer_domain,
    normalize_domain,
    resolve_question_domain,
)
from .loaders import PdfDocument
from .normalize import sha256_text
from .sections import Section
from .tokens import estimate_tokens

CHILD_TARGET_TOKENS = (CHILD_MIN_TOKENS + CHILD_MAX_TOKENS) // 2
PARENT_HARD_MAX_TOKENS = int(PARENT_MAX_TOKENS * 1.1)
UNIT_MAX_TOKENS = CHILD_MAX_TOKENS - 70
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")
BULLET_PREFIXES = ("•", "-", "*", "–", "—")
UUID_NAMESPACE = uuid.NAMESPACE_URL


@dataclass(frozen=True)
class TextUnit:
    text: str
    tokens: int
    section_label: str
    heading: str
    page_start: int
    page_end: int
    is_heading: bool = False


@dataclass
class Chunk:
    chunk_id: str
    document_source: str
    parent_id: str | None
    chunk_index: int
    content: str
    token_count: int
    content_type: str
    content_checksum: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "id": self.chunk_id,
            "document_source": self.document_source,
            "parent_id": self.parent_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "token_count": self.token_count,
            "content_type": self.content_type,
            "checksum": self.content_checksum,
            "metadata": self.metadata,
        }


@dataclass
class _ParentDraft:
    kind: str
    sections: list[Section]
    units: list[TextUnit]
    domain: str | None
    domain_source: str
    domains: list[str]
    question_number: int | None
    part_index: int
    part_total: int

    @property
    def page_start(self) -> int:
        return min(unit.page_start for unit in self.units)

    @property
    def page_end(self) -> int:
        return max(unit.page_end for unit in self.units)


def document_uuid(source_key: str, version: str = DEFAULT_VERSION) -> str:
    return str(uuid.uuid5(UUID_NAMESPACE, f"aws-saa-rag:{version}:document:{source_key}"))


def question_uuid(source_key: str, number: int, version: str = DEFAULT_VERSION) -> str:
    name = f"aws-saa-rag:{version}:question:{source_key}:{number:04d}"
    return str(uuid.uuid5(UUID_NAMESPACE, name))


def _chunk_uuid(
    source_key: str,
    version: str,
    role: str,
    parent_ordinal: int,
    child_ordinal: int = 0,
) -> str:
    name = f"aws-saa-rag:{version}:{source_key}:{role}:{parent_ordinal}:{child_ordinal}"
    return str(uuid.uuid5(UUID_NAMESPACE, name))


def document_role_from_key(source_key: str) -> str:
    name = source_key.lower()
    if "question-bank" in name:
        return "question_bank"
    if "exam-guide" in name:
        return "exam_guide"
    return "supplement"


def document_role(document: PdfDocument) -> str:
    return document_role_from_key(document.source_key)


def _top_level_number(label: str) -> str:
    parts = label.split()
    return parts[-1].split(".")[0] if parts else ""


def _hard_split(text: str, max_tokens: int) -> list[str]:
    max_chars = max(1, int(max_tokens * 3))
    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    current: list[str] = []
    size = 0
    for word in text.split():
        addition = len(word) + (1 if current else 0)
        if current and size + addition > max_chars:
            pieces.append(" ".join(current))
            current = [word]
            size = len(word)
        else:
            current.append(word)
            size += addition
    if current:
        pieces.append(" ".join(current))
    return pieces or [text]


def _split_text_units(text: str, max_tokens: int) -> list[str]:
    pieces: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(BULLET_PREFIXES) and estimate_tokens(line) <= max_tokens:
            pieces.append(line)
            continue
        for sentence in SENTENCE_BOUNDARY_RE.split(line):
            sentence = sentence.strip()
            if not sentence:
                continue
            if estimate_tokens(sentence) > max_tokens:
                pieces.extend(_hard_split(sentence, max_tokens))
            else:
                pieces.append(sentence)
    return pieces


def _section_units(section: Section, max_tokens: int = UNIT_MAX_TOKENS) -> list[TextUnit]:
    units: list[TextUnit] = []
    heading = section.heading.strip()
    if heading:
        units.append(
            TextUnit(
                text=heading,
                tokens=estimate_tokens(heading),
                section_label=section.label,
                heading=heading,
                page_start=section.page_start,
                page_end=section.page_start,
                is_heading=True,
            )
        )
    for piece in _split_text_units(section.body, max_tokens=max_tokens):
        units.append(
            TextUnit(
                text=piece,
                tokens=estimate_tokens(piece),
                section_label=section.label,
                heading=heading,
                page_start=section.page_start,
                page_end=section.page_end,
            )
        )
    if not units:
        fallback = section.title or section.label
        units.append(
            TextUnit(
                text=fallback,
                tokens=estimate_tokens(fallback),
                section_label=section.label,
                heading=heading or fallback,
                page_start=section.page_start,
                page_end=section.page_end,
                is_heading=True,
            )
        )
    return units


def _join_units(units: list[TextUnit]) -> str:
    return "\n".join(unit.text for unit in units if unit.text.strip()).strip()


def _range_tokens(units: list[TextUnit], start: int, end: int) -> int:
    return sum(unit.tokens for unit in units[start:end])


def _window_prefix(units: list[TextUnit], start: int) -> list[TextUnit]:
    if start <= 0 or units[start].is_heading or not units[start].heading:
        return []
    return [
        TextUnit(
            text=units[start].heading,
            tokens=estimate_tokens(units[start].heading),
            section_label=units[start].section_label,
            heading=units[start].heading,
            page_start=units[start].page_start,
            page_end=units[start].page_start,
            is_heading=True,
        )
    ]


def _pack_ranges(
    units: list[TextUnit],
    target_tokens: int,
    max_tokens: int,
    floor_tokens: int,
) -> list[tuple[int, int]]:
    if not units:
        return []
    ranges: list[list[int]] = []
    start = 0
    while start < len(units):
        end = start
        tokens = 0
        while end < len(units):
            unit_tokens = units[end].tokens
            if tokens and tokens + unit_tokens > max_tokens:
                break
            tokens += unit_tokens
            end += 1
            if tokens >= target_tokens:
                break
        if end == start:
            end += 1
        ranges.append([start, end])
        start = end

    if len(ranges) >= 2:
        previous, last = ranges[-2], ranges[-1]
        last_tokens = _range_tokens(units, last[0], last[1])
        if last_tokens < floor_tokens:
            combined = _range_tokens(units, previous[0], last[1])
            if combined <= max_tokens:
                previous[1] = last[1]
                ranges.pop()
            elif last[0] > previous[0]:
                while last_tokens < floor_tokens and previous[1] - previous[0] > 1:
                    moved = units[previous[1] - 1].tokens
                    if _range_tokens(units, previous[0], previous[1] - 1) < floor_tokens:
                        break
                    if last_tokens + moved > max_tokens:
                        break
                    previous[1] -= 1
                    last[0] -= 1
                    last_tokens += moved
    return [(start, end) for start, end in ranges]


def _parent_part_ranges(
    units: list[TextUnit],
    total: int,
    heading_tokens: int = 0,
) -> list[tuple[int, int]]:
    if total + heading_tokens <= PARENT_HARD_MAX_TOKENS:
        return [(0, len(units))]
    max_tokens = max(1, PARENT_MAX_TOKENS - heading_tokens)
    floor_tokens = max(1, PARENT_MIN_TOKENS - heading_tokens)
    count = max(1, math.ceil(total / max_tokens))
    while count > 1 and total / count < floor_tokens:
        count -= 1
    if count == 1 and total + heading_tokens > PARENT_HARD_MAX_TOKENS:
        count = 2
    target = max(1, math.ceil(total / count))
    return _pack_ranges(
        units,
        target_tokens=target,
        max_tokens=max_tokens,
        floor_tokens=floor_tokens,
    )


def _question_drafts(document: PdfDocument, sections: list[Section]) -> list[_ParentDraft]:
    drafts: list[_ParentDraft] = []
    for section in sections:
        if section.number is None:
            continue
        units = _section_units(section)
        total = sum(unit.tokens for unit in units)
        heading_units = [unit for unit in units if unit.is_heading][:1]
        body_units = units[len(heading_units) :]
        body_total = total - sum(unit.tokens for unit in heading_units)
        heading_tokens = sum(unit.tokens for unit in heading_units)
        ranges = (
            _parent_part_ranges(body_units, body_total, heading_tokens) if body_units else [(0, 0)]
        )
        domain, domain_source = resolve_question_domain(section.number, section.domain_raw)
        if domain is None:
            domain = infer_domain(section.text)
            domain_source = "inferred" if domain else "missing"
        for part_index, (start, end) in enumerate(ranges, start=1):
            part_units = heading_units + body_units[start:end]
            drafts.append(
                _ParentDraft(
                    kind="question",
                    sections=[section],
                    units=part_units,
                    domain=domain,
                    domain_source=domain_source,
                    domains=[domain] if domain else [],
                    question_number=section.number,
                    part_index=part_index,
                    part_total=len(ranges),
                )
            )
    return drafts


def _chapter_groups(document: PdfDocument, sections: list[Section]) -> list[list[Section]]:
    if document_role(document) != "exam_guide":
        return [sections] if sections else []
    groups: list[list[Section]] = []
    current: list[Section] = []
    current_top = ""
    for section in sections:
        top = _top_level_number(section.label)
        if current and top != current_top:
            groups.append(current)
            current = []
        current.append(section)
        current_top = top
    if current:
        groups.append(current)
    return groups


def _balanced_ranges(
    units: list[TextUnit],
    max_tokens: int = PARENT_MAX_TOKENS,
    min_tokens: int = PARENT_MIN_TOKENS,
    hard_max_tokens: int = PARENT_HARD_MAX_TOKENS,
) -> list[tuple[int, int]]:
    total = sum(unit.tokens for unit in units)
    if total <= max_tokens:
        return [(0, len(units))]
    count = max(1, math.ceil(total / max_tokens))
    while count > 1 and total / count < min_tokens:
        count -= 1
    if count == 1 and total > hard_max_tokens:
        count = 2
    target = max(1, math.ceil(total / count))
    return _pack_ranges(
        units,
        target_tokens=target,
        max_tokens=max_tokens,
        floor_tokens=min_tokens,
    )


def _domains_for_sections(document: PdfDocument, sections: list[Section]) -> tuple[list[str], str]:
    explicit: list[str] = []
    for section in sections:
        code = normalize_domain(section.domain_raw)
        if code and code not in explicit:
            explicit.append(code)
    if explicit:
        return explicit, "explicit"
    if document_role(document) == "exam_guide":
        top = _top_level_number(sections[0].label)
        if top in {"1", "2", "3", "4"}:
            return [DOMAIN_CODES[int(top) - 1]], "exam_guide_section"
    text = " ".join(section.text for section in sections)
    inferred = infer_domain(text)
    return ([inferred] if inferred else []), ("inferred" if inferred else "missing")


def _theory_drafts(document: PdfDocument, sections: list[Section]) -> list[_ParentDraft]:
    drafts: list[_ParentDraft] = []
    for group in _chapter_groups(document, sections):
        units = [unit for section in group for unit in _section_units(section)]
        ranges = _balanced_ranges(units)
        by_label = {section.label: section for section in group}
        for part_index, (start, end) in enumerate(ranges, start=1):
            part_units = units[start:end]
            labels: list[str] = []
            for unit in part_units:
                if unit.section_label not in labels:
                    labels.append(unit.section_label)
            part_sections = [by_label[label] for label in labels if label in by_label]
            if not part_sections:
                part_sections = group[:1]
            domains, domain_source = _domains_for_sections(document, part_sections)
            drafts.append(
                _ParentDraft(
                    kind="theory",
                    sections=part_sections,
                    units=part_units,
                    domain=domains[0] if len(domains) == 1 else None,
                    domain_source=domain_source,
                    domains=domains,
                    question_number=None,
                    part_index=part_index,
                    part_total=len(ranges),
                )
            )
    return drafts


def _build_child_windows(units: list[TextUnit], target: int) -> list[tuple[list[TextUnit], int]]:
    windows: list[tuple[list[TextUnit], int]] = []
    start = 0
    while start < len(units):
        prefix = _window_prefix(units, start)
        selected = list(prefix)
        tokens = sum(unit.tokens for unit in prefix)
        end = start
        while end < len(units):
            unit_tokens = units[end].tokens
            if end > start and tokens + unit_tokens > CHILD_MAX_TOKENS:
                break
            selected.append(units[end])
            tokens += unit_tokens
            end += 1
            if tokens >= target:
                break
        if end == start:
            selected.append(units[start])
            tokens += units[start].tokens
            end += 1

        overlap_tokens = 0
        next_start = end
        if end < len(units):
            needed = max(1, round(target * CHILD_OVERLAP_RATIO * 0.85))
            accumulated = 0
            while next_start > start:
                accumulated += units[next_start - 1].tokens
                next_start -= 1
                if accumulated >= needed:
                    break
            overlap_tokens = accumulated
            if next_start <= start:
                next_start = end
                overlap_tokens = 0

        windows.append((selected, overlap_tokens))
        start = next_start

    if len(windows) >= 2:
        last_units, _ = windows[-1]
        if sum(unit.tokens for unit in last_units) < CHILD_MIN_TOKENS:
            previous_units, _ = windows[-2]
            previous_keys = {(unit.text, unit.section_label) for unit in previous_units}
            new_units = [
                unit for unit in last_units if (unit.text, unit.section_label) not in previous_keys
            ]
            combined = previous_units + new_units
            if sum(unit.tokens for unit in combined) <= CHILD_MAX_TOKENS:
                windows[-2] = (combined, windows[-2][1])
                windows.pop()
    return windows


def _child_windows(units: list[TextUnit]) -> list[tuple[list[TextUnit], int]]:
    total = sum(unit.tokens for unit in units)
    if total <= CHILD_MAX_TOKENS:
        return [(units, 0)]

    overlap_target = max(1, round(CHILD_TARGET_TOKENS * CHILD_OVERLAP_RATIO))
    max_count = max(2, math.ceil(total / CHILD_MIN_TOKENS) + 2)
    best: tuple[tuple[int, int, int], list[tuple[list[TextUnit], int]]] | None = None
    for count in range(1, max_count + 1):
        target = math.ceil((total + (count - 1) * overlap_target) / count)
        if count == 1:
            if total <= int(CHILD_MAX_TOKENS * 1.1):
                return [(units, 0)]
            continue
        if target > CHILD_MAX_TOKENS or target < CHILD_MIN_TOKENS:
            continue
        windows = _build_child_windows(units, target)
        sizes = [sum(unit.tokens for unit in window) for window, _ in windows]
        violations = sum(1 for size in sizes if size < CHILD_MIN_TOKENS or size > CHILD_MAX_TOKENS)
        if violations == 0:
            return windows
        key = (violations, abs(len(windows) - count), max(sizes) - min(sizes))
        if best is None or key < best[0]:
            best = (key, windows)
    if best is not None:
        return best[1]
    return _build_child_windows(units, CHILD_TARGET_TOKENS)


def _metadata(
    document: PdfDocument,
    draft: _ParentDraft,
    version: str,
    content_type: str,
) -> dict[str, Any]:
    sections = [section.label for section in draft.sections]
    return {
        "document": document.source_key,
        "document_title": document.title,
        "version": version,
        "kind": draft.kind,
        "content_type": content_type,
        "section": draft.sections[0].label,
        "sections": sections,
        "heading": draft.sections[0].heading,
        "page": draft.page_start,
        "page_end": draft.page_end,
        "domain": draft.domain,
        "domains": draft.domains,
        "domain_source": draft.domain_source,
        "question_number": draft.question_number,
        "part": draft.part_index,
        "parts": draft.part_total,
        "table_count": 0,
    }


def _child_metadata(
    document: PdfDocument,
    draft: _ParentDraft,
    units: list[TextUnit],
    version: str,
    parent_ordinal: int,
    child_ordinal: int,
    child_count: int,
    overlap_tokens: int,
) -> dict[str, Any]:
    labels: list[str] = []
    for unit in units:
        if unit.section_label not in labels:
            labels.append(unit.section_label)
    metadata = _metadata(document, draft, version, "child")
    metadata.update(
        {
            "section": labels[0] if labels else draft.sections[0].label,
            "sections": labels or [section.label for section in draft.sections],
            "heading": units[0].heading if units else draft.sections[0].heading,
            "page": min(unit.page_start for unit in units),
            "page_end": max(unit.page_end for unit in units),
            "parent_ordinal": parent_ordinal,
            "child_ordinal": child_ordinal,
            "child_count": child_count,
            "overlap_tokens": overlap_tokens,
        }
    )
    return metadata


def _table_chunks(document: PdfDocument, version: str, start_ordinal: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for table_index, table in enumerate(document.tables):
        rows = table.rows
        if not rows:
            continue
        content = table.to_markdown()
        metadata = table.to_metadata()
        metadata.update(
            {
                "document": document.source_key,
                "document_title": document.title,
                "version": version,
                "kind": "table",
                "content_type": "table",
                "page": table.page,
                "page_end": table.page,
                "section": f"Bảng {table_index + 1}",
                "sections": [],
                "heading": f"Bảng {table_index + 1} - trang {table.page}",
                "domain": None,
                "domains": [],
                "domain_source": "missing",
                "question_number": None,
                "part": 1,
                "parts": 1,
                "table_count": 1,
            }
        )
        chunks.append(
            Chunk(
                chunk_id=_chunk_uuid(
                    document.source_key,
                    version,
                    "table",
                    start_ordinal + table_index,
                ),
                document_source=document.source_key,
                parent_id=None,
                chunk_index=0,
                content=content,
                token_count=estimate_tokens(content),
                content_type="table",
                content_checksum=sha256_text(content),
                metadata=metadata,
            )
        )
    return chunks


def build_chunks(
    document: PdfDocument,
    sections: list[Section],
    version: str = DEFAULT_VERSION,
) -> list[Chunk]:
    question_sections = [section for section in sections if section.kind == "question"]
    theory_sections = [section for section in sections if section.kind != "question"]
    drafts = _question_drafts(document, question_sections)
    drafts.extend(_theory_drafts(document, theory_sections))
    drafts.sort(
        key=lambda draft: (
            draft.page_start,
            draft.question_number if draft.question_number is not None else -1,
            draft.part_index,
        )
    )

    chunks: list[Chunk] = []
    for parent_ordinal, draft in enumerate(drafts):
        parent_id = _chunk_uuid(document.source_key, version, "parent", parent_ordinal)
        parent_content = _join_units(draft.units)
        if draft.units and not draft.units[0].is_heading and draft.units[0].heading:
            parent_content = f"{draft.units[0].heading}\n{parent_content}".strip()
        parent_tokens = estimate_tokens(parent_content)
        chunks.append(
            Chunk(
                chunk_id=parent_id,
                document_source=document.source_key,
                parent_id=None,
                chunk_index=len(chunks),
                content=parent_content,
                token_count=parent_tokens,
                content_type="parent",
                content_checksum=sha256_text(parent_content),
                metadata=_metadata(document, draft, version, "parent"),
            )
        )
        windows = _child_windows(draft.units)
        for child_ordinal, (units, overlap_tokens) in enumerate(windows):
            content = _join_units(units)
            chunks.append(
                Chunk(
                    chunk_id=_chunk_uuid(
                        document.source_key,
                        version,
                        "child",
                        parent_ordinal,
                        child_ordinal,
                    ),
                    document_source=document.source_key,
                    parent_id=parent_id,
                    chunk_index=len(chunks),
                    content=content,
                    token_count=estimate_tokens(content),
                    content_type="child",
                    content_checksum=sha256_text(content),
                    metadata=_child_metadata(
                        document,
                        draft,
                        units,
                        version,
                        parent_ordinal,
                        child_ordinal,
                        len(windows),
                        overlap_tokens,
                    ),
                )
            )
    table_chunks = _table_chunks(document, version, len(drafts))
    for chunk in table_chunks:
        chunk.chunk_index = len(chunks)
        chunks.append(chunk)
    return chunks


def summarize_chunks(chunks: list[Chunk]) -> dict[str, Any]:
    parents = [chunk for chunk in chunks if chunk.content_type == "parent"]
    children = [chunk for chunk in chunks if chunk.content_type == "child"]
    tables = [chunk for chunk in chunks if chunk.content_type == "table"]
    parent_tokens = sorted(chunk.token_count for chunk in parents)
    child_tokens = sorted(chunk.token_count for chunk in children)

    def percentiles(values: list[int]) -> dict[str, int]:
        if not values:
            return {"min": 0, "median": 0, "max": 0}
        return {
            "min": values[0],
            "median": values[len(values) // 2],
            "max": values[-1],
        }

    return {
        "parents": len(parents),
        "children": len(children),
        "tables": len(tables),
        "parent_tokens": percentiles(parent_tokens),
        "child_tokens": percentiles(child_tokens),
    }
