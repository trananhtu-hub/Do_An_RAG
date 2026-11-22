"""Chạy 10 kịch bản hội thoại Giai đoạn 4 và chấm theo rubric.

Mỗi kịch bản chạy trong một phiên riêng của cùng một người dùng thử, gửi lần lượt
cột "Câu hỏi người dùng" qua ChatService thật (condensation + retrieval + generation).
Kết quả từng lượt được chấm bằng LLM judge, kèm các kiểm tra tự động cho ràng buộc
cứng (câu viết lại, trích dẫn, từ chối, mốc thời gian).

Chỉ đọc kịch bản từ inputs/conversations.md; không sửa kịch bản giữa các lần chạy.

Ví dụ:
    python evaluation/conversation_bench.py --workers 1 --transport answer
    python evaluation/conversation_bench.py --workers 1 --transport stream
    python evaluation/conversation_bench.py --scenarios KB-01,KB-10 --transport both
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.chat import ChatService  # noqa: E402
from app.services.conversation import load_conversation_config  # noqa: E402
from app.services.generation import (  # noqa: E402
    GenerationConfig,
    GenerationService,
    LLMMessage,
    PromptLibrary,
    build_provider_chain,
    load_generation_config,
)
from app.services.generation.providers import LLMError  # noqa: E402
from app.services.generation.settings import load_environment  # noqa: E402
from app.services.retrieval import build_default_service  # noqa: E402
from app.services.sessions.memory import InMemorySessionRepository  # noqa: E402

CONVERSATIONS = ROOT / "inputs" / "conversations.md"
RESULTS = ROOT / "evaluation" / "results"
JUDGE_CACHE = RESULTS / "conversation_bench_judge_cache.json"
USER_ID = UUID("44444444-4444-4444-8444-444444444444")
JUDGE_VERSION = "v3"
HISTORY_ANSWER_CHARS = 4000
JUDGE_VOTES = 3

DOCUMENT_TITLES = (
    "aws-saa-exam-guide",
    "aws-saa-question-bank",
    "EC2 Tinh toan",
    "IAM",
    "RDS Aurora",
    "S3 Storage Classes",
    "VPC Networking",
)

REFUSAL_FORBIDDEN = {
    "KB-10:2": ("```", "boto3", "import ", "def ", "client.upload", "put_object"),
    "KB-10:3": (
        "foundation model",
        "model nền tảng",
        "anthropic",
        "claude",
        "llama",
        "giá ",
        "chi phí",
        "tính năng",
    ),
}

JUDGE_PROMPT = """Bạn là giám khảo chấm MỘT LƯỢT trong hội thoại nhiều lượt của chatbot
ôn thi AWS SAA-C03. Chỉ dựa trên tài liệu của kho tri thức, không dùng kiến thức ngoài.

Kịch bản: {code} — {title}
Mục tiêu: {objective}
Các lượt trước:
{history}

Câu hỏi người dùng: {question}
Câu viết lại kỳ vọng: {expected_rewrite}
Câu viết lại thực tế: {rewritten}
Hành vi mong đợi: {expected_behavior}
Căn cứ: {evidence}
Tiêu chí đạt liên quan đến lượt này:
{criteria}

Câu trả lời của hệ thống:
{answer}

Trích dẫn: {citations}
Từ chối trả lời: {abstained} (loại: {abstention_type})

Chấm:
- 1.0: đáp ứng đầy đủ hành vi mong đợi và các tiêu chí liên quan; câu viết lại giữ đúng ý,
  đủ thực thể và độc lập khi cần; trích dẫn phù hợp với căn cứ; không mâu thuẫn lượt trước.
- 0.5: đúng một phần, thiếu ý quan trọng nhưng không sai; hoặc câu viết lại chưa đạt.
- 0.0: sai, bịa, bỏ ràng buộc, mâu thuẫn, từ chối khi có căn cứ, hoặc trả lời khi phải từ chối.

Trích dẫn thêm ngoài cột Căn cứ: nếu mục được trích thật sự tồn tại trong tài liệu và
nội dung mục đó hỗ trợ câu trả lời thì KHÔNG trừ điểm. Chỉ trừ khi trích sai tài liệu/mục,
trích mục không tồn tại, hoặc trích dẫn không liên quan đến câu trả lời.

Không trừ điểm vì khác cách diễn đạt hay độ dài. Trả JSON đúng dạng
{{"score": 0.0, "reason": "..."}} và không thêm văn bản."""

REFUSAL_JUDGE_PROMPT = """Bạn chấm một lượt chatbot ôn thi AWS SAA-C03 phải TỪ CHỐI.
Yêu cầu: từ chối rõ ràng, không cung cấp nội dung kỹ thuật trả lời câu hỏi.
Nêu tên chủ đề để giải thích lý do từ chối là hợp lệ.

Câu hỏi: {question}
Hành vi mong đợi: {expected_behavior}
Câu trả lời: {answer}
Cờ abstained: {abstained} (loại: {abstention_type})
Số trích dẫn: {citation_count}

Chấm:
- 1.0 nếu từ chối rõ ràng và không giải thích kỹ thuật/không viết code/không liệt kê
  tính năng, giá, mô hình của dịch vụ được hỏi.
- 0.0 nếu trả lời câu hỏi hoặc cung cấp chi tiết kỹ thuật.

Trả JSON đúng dạng {{"score": 1.0, "reason": "..."}} và không thêm văn bản."""


@dataclass(frozen=True)
class Turn:
    number: int
    question: str
    expected_rewrite: str
    expected_behavior: str
    evidence: str

    @property
    def expects_refusal(self) -> bool:
        return self.evidence.strip().casefold() == "không trích dẫn"


@dataclass(frozen=True)
class Scenario:
    code: str
    title: str
    kind: str
    objective: str
    documents: tuple[str, ...]
    turns: tuple[Turn, ...]
    criteria: tuple[str, ...]
    document_sections: tuple[tuple[str, frozenset[str]], ...] = ()


def _document_sections(documents_line: str) -> tuple[tuple[str, frozenset[str]], ...]:
    """Ánh xạ từng tài liệu trong dòng "Tài liệu" sang các mục nó cung cấp."""
    positions = sorted(
        (documents_line.find(title), title) for title in DOCUMENT_TITLES if title in documents_line
    )
    mapping: list[tuple[str, frozenset[str]]] = []
    for index, (position, title) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(documents_line)
        mapping.append((title, frozenset(_section_numbers(documents_line[position:end]))))
    return tuple(mapping)


def load_scenarios(path: Path = CONVERSATIONS) -> list[Scenario]:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"^## ((?:KB|DV)-\d+) — (.+?)\n(.*?)(?=^## |\Z)", re.S | re.M)
    scenarios: list[Scenario] = []
    for match in pattern.finditer(text):
        code, title, body = match.group(1), match.group(2).strip(), match.group(3)
        kind = _field(body, "Loại")
        objective = _field(body, "Mục tiêu")
        documents_line = _field(body, "Tài liệu")
        documents = tuple(title_ for title_ in DOCUMENT_TITLES if title_ in documents_line)
        turns = _parse_turns(body)
        criteria = _parse_criteria(body)
        scenarios.append(
            Scenario(
                code,
                title,
                kind,
                objective,
                documents,
                turns,
                criteria,
                _document_sections(documents_line),
            )
        )
    if len(scenarios) != 10:
        raise ValueError(f"Cần đúng 10 kịch bản, đọc được {len(scenarios)}")
    for scenario in scenarios:
        if len(scenario.turns) != 4:
            raise ValueError(f"{scenario.code} phải có 4 lượt, có {len(scenario.turns)}")
    return scenarios


def _field(body: str, name: str) -> str:
    match = re.search(rf"- \*\*{name}:\*\* (.+)", body)
    return match.group(1).strip() if match else ""


def _parse_turns(body: str) -> tuple[Turn, ...]:
    turns: list[Turn] = []
    for line in body.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5 or not cells[0].isdigit():
            continue
        turns.append(
            Turn(
                number=int(cells[0]),
                question=cells[1],
                expected_rewrite=cells[2],
                expected_behavior=cells[3],
                evidence=cells[4],
            )
        )
    return tuple(turns)


def _parse_criteria(body: str) -> tuple[str, ...]:
    match = re.search(r"\*\*Tiêu chí đạt:\*\*\n\n(.*?)(?:\n\n|\Z)", body, re.S)
    if not match:
        return ()
    lines = []
    for line in match.group(1).splitlines():
        line = line.strip().lstrip("- ").strip()
        if line:
            lines.append(line)
    return tuple(lines)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _extract_json(text: str) -> dict:
    cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


class RecordingRetrieval:
    """Ghi lại kết quả truy hồi gần nhất của từng luồng để phục vụ phân tích lỗi."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self._local = threading.local()

    def retrieve(self, query: str, **kwargs: Any):
        result = self.inner.retrieve(query, **kwargs)
        self._local.last = result
        return result

    def last(self):
        return getattr(self._local, "last", None)


class Judge:
    def __init__(self, chain) -> None:
        self.chain = chain
        self.lock = threading.Lock()
        self.cache = (
            json.loads(JUDGE_CACHE.read_text(encoding="utf-8")) if JUDGE_CACHE.exists() else {}
        )
        self.tokens = 0
        self.cost = 0.0

    def score(
        self,
        scenario: Scenario,
        turn: Turn,
        history: str,
        record: dict[str, Any],
    ) -> tuple[float, str]:
        key = _hash(
            "|".join(
                [
                    JUDGE_VERSION,
                    scenario.code,
                    str(turn.number),
                    record.get("answer", ""),
                    record.get("rewritten_query", ""),
                    str(record.get("abstained")),
                    "|".join(item.get("source", "") for item in record.get("citations", [])),
                ]
            )
        )
        with self.lock:
            if key in self.cache:
                return self.cache[key]["score"], self.cache[key]["reason"]

        if turn.expects_refusal:
            prompt = REFUSAL_JUDGE_PROMPT.format(
                question=turn.question,
                expected_behavior=turn.expected_behavior,
                answer=record.get("answer", "")[:4000],
                abstained=record.get("abstained"),
                abstention_type=record.get("abstention_type"),
                citation_count=len(record.get("citations", [])),
            )
        else:
            criteria = _criteria_for_turn(scenario, turn)
            prompt = JUDGE_PROMPT.format(
                code=scenario.code,
                title=scenario.title,
                objective=scenario.objective,
                history=history or "(chưa có lượt trước)",
                question=turn.question,
                expected_rewrite=turn.expected_rewrite,
                rewritten=record.get("rewritten_query", ""),
                expected_behavior=turn.expected_behavior,
                evidence=turn.evidence,
                criteria="\n".join(f"- {item}" for item in criteria)
                or "- (không có tiêu chí riêng; chấm theo hành vi mong đợi và căn cứ)",
                answer=record.get("answer", "")[:6000],
                citations=", ".join(item.get("source", "") for item in record.get("citations", []))
                or "(không có)",
                abstained=record.get("abstained"),
                abstention_type=record.get("abstention_type") or "none",
            )
        messages = [
            LLMMessage(role="system", content="Chỉ trả JSON, không thêm văn bản."),
            LLMMessage(role="user", content=prompt),
        ]
        # Judge chạy ở temperature 0 nhưng nhà cung cấp vẫn có thể lệch giữa các lần gọi;
        # lấy trung vị của JUDGE_VOTES lần để điểm không phụ thuộc một lần chấm may rủi.
        verdicts: list[tuple[float, str]] = []
        for _ in range(JUDGE_VOTES):
            try:
                response = self.chain.complete(messages, thinking_level="low", json_mode=True)
                data = _extract_json(response.text)
                verdicts.append((float(data.get("score", 0.0)), str(data.get("reason", ""))))
                with self.lock:
                    self.tokens += response.usage.total_tokens
                    self.cost += response.cost_usd
            except Exception as exc:  # noqa: BLE001 - benchmark ghi lại lỗi judge
                verdicts.append((0.0, f"judge lỗi: {type(exc).__name__}: {exc}"))
        ordered = sorted(score for score, _ in verdicts)
        median_raw = ordered[len(ordered) // 2]
        score = 1.0 if median_raw >= 0.75 else (0.5 if median_raw >= 0.25 else 0.0)
        reason = next(text for value, text in verdicts if value == median_raw)[:400]
        if len(set(ordered)) > 1:
            reason = f"{reason} [điểm 3 lần: {ordered}]"[:600]
        with self.lock:
            self.cache[key] = {"score": score, "reason": reason}
        return score, reason

    def save(self) -> None:
        JUDGE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        JUDGE_CACHE.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _rewritten_equals_original(record: dict[str, Any]) -> bool:
    return _normalize(record["rewritten_query"]) == _normalize(record["question"])


def _contains(text: str, *terms: str) -> bool:
    lowered = text.casefold()
    return all(term.casefold() in lowered for term in terms)


def _citation_sources(record: dict[str, Any]) -> list[str]:
    return [citation["source"] for citation in record.get("citations", [])]


def _section_numbers(text: str) -> set[str]:
    return set(re.findall(r"Mục\s+([\d.]+)", text))


def _citation_requirements(
    scenario: Scenario, turn: Turn
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Trả về (tài liệu bắt buộc đủ, tài liệu chỉ cần ít nhất một).

    Khi ô Căn cứ không nêu tên tài liệu, không được đòi mọi tài liệu của kịch bản:
    chỉ đòi tài liệu thật sự chứa các mục được dẫn, hoặc tối thiểu một tài liệu
    liên quan nếu không ánh xạ được mục nào.
    """
    named = tuple(title for title in DOCUMENT_TITLES if title in turn.evidence)
    if named:
        return named, ()
    sections = _section_numbers(turn.evidence)
    candidates = tuple(
        title for title, owned in scenario.document_sections if sections and sections & set(owned)
    )
    if candidates:
        return (), candidates
    return (), scenario.documents


def _relevant_documents(scenario: Scenario, turn: Turn) -> set[str]:
    required, any_of = _citation_requirements(scenario, turn)
    return set(required) | set(any_of)


def _source_document(source: str) -> str | None:
    lowered = source.casefold()
    return next((title for title in DOCUMENT_TITLES if title.casefold() in lowered), None)


def _source_has_section(source: str, section: str) -> bool:
    pattern = rf"Mục\s+{re.escape(section)}(?!\.?\d)"
    return re.search(pattern, source, re.I) is not None


def _citation_document_ok(scenario: Scenario, turn: Turn, sources: list[str]) -> bool:
    if turn.expects_refusal:
        return not sources
    required, any_of = _citation_requirements(scenario, turn)
    found = {document for document in (_source_document(source) for source in sources) if document}
    if required and not all(document in found for document in required):
        return False
    if any_of and not found.intersection(any_of):
        return False
    if not required and not any_of and not sources:
        return False
    sections = _section_numbers(turn.evidence)
    if not sections:
        return True
    relevant = [
        source
        for source in sources
        if not (required or any_of) or _source_document(source) in (set(required) | set(any_of))
    ]
    return any(_source_has_section(source, section) for source in relevant for section in sections)


def _criteria_for_turn(scenario: Scenario, turn: Turn) -> tuple[str, ...]:
    """Chỉ giữ tiêu chí thật sự nói về lượt hiện tại.

    Tiêu chí có nhắc "lượt N" (kể cả khoảng "lượt 2–3") chỉ áp dụng cho các lượt đó;
    tiêu chí nêu tài liệu/mục chỉ áp dụng khi lượt hiện tại dẫn đúng tài liệu/mục ấy.
    Tiêu chí chung không nêu lượt hay tài liệu vẫn được giữ.
    """
    relevant_documents = _relevant_documents(scenario, turn)
    relevant_sections = _section_numbers(turn.evidence)
    selected: list[str] = []
    for criterion in scenario.criteria:
        mentions = {int(number) for number in re.findall(r"lượt\s+(\d+)", criterion, re.I)}
        mentions.update(
            int(number)
            for start, end in re.findall(r"lượt\s+(\d+)\s*[–-]\s*(\d+)", criterion, re.I)
            for number in range(int(start), int(end) + 1)
        )
        if mentions and turn.number not in mentions:
            continue
        documents = {title for title in DOCUMENT_TITLES if title.casefold() in criterion.casefold()}
        if documents and not documents & relevant_documents:
            continue
        sections = _section_numbers(criterion)
        if sections and not sections & relevant_sections:
            # Tiêu chí dẫn mục không có trong Căn cứ của lượt này là của lượt khác.
            continue
        selected.append(criterion)
    return tuple(selected)


def auto_checks(
    scenario: Scenario,
    turn: Turn,
    record: dict[str, Any],
    sources: list[str],
) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    answer = record.get("answer", "")
    rewritten = record.get("rewritten_query", "")

    if turn.expects_refusal:
        checks.append(
            (
                "từ chối + không trích dẫn",
                bool(record.get("abstained")) and not sources,
                f"abstained={record.get('abstained')}, citations={len(sources)}",
            )
        )
        forbidden = REFUSAL_FORBIDDEN.get(f"{scenario.code}:{turn.number}", ())
        leaked = [term for term in forbidden if term.casefold() in answer.casefold()]
        checks.append(("không rò rỉ nội dung kỹ thuật", not leaked, f"khớp: {leaked}"))
    elif turn.expected_rewrite.strip().casefold() == "giữ nguyên":
        checks.append(
            (
                "câu viết lại giữ nguyên",
                _rewritten_equals_original(record),
                f"viết lại={rewritten[:120]}",
            )
        )

    checks.append(
        (
            "trích dẫn đúng tài liệu/mục",
            _citation_document_ok(scenario, turn, sources),
            f"nguồn={sources[:4]}",
        )
    )

    key = f"{scenario.code}:{turn.number}"
    specific: list[tuple[str, bool, str]] = []
    if key == "KB-01:2":
        specific.append(("viết lại chứa S3 và EBS", _contains(rewritten, "s3", "ebs"), rewritten))
    elif key == "KB-01:4":
        specific.append(
            (
                "khẳng định EBS không tự nhân bản nhiều AZ",
                "không" in answer.casefold()
                and ("az" in answer.casefold() or "zone" in answer.casefold()),
                answer[:160],
            )
        )
    elif key == "KB-02:3":
        specific.append(("nêu instance/endpoint mới", _contains(answer, "mới"), answer[:160]))
    elif key == "KB-03:4":
        specific.append(
            (
                "nói không thu hồi ngay",
                "không" in answer.casefold() and "thu hồi" in answer.casefold(),
                answer[:160],
            )
        )
    elif key in ("KB-04:2", "KB-04:3") and turn.expected_rewrite.strip().casefold() != "giữ nguyên":
        specific.append(
            (
                "viết lại giữ cả Multi-AZ và Read Replica",
                _contains(rewritten, "multi-az", "read replica"),
                rewritten,
            )
        )
    elif key == "KB-05:3":
        specific.append(
            (
                "nêu dải cổng tạm thời 1024-65535",
                bool(re.search(r"1024\D{0,30}65535", answer)),
                answer[:200],
            )
        )
    elif key == "KB-06:1":
        specific.append(("chọn One Zone-IA", "one zone-ia" in answer.casefold(), answer[:200]))
        specific.append(("nêu truy xuất mili giây", "mili giây" in answer.casefold(), answer[:200]))
    elif key == "KB-06:2":
        specific.append(
            (
                "chuyển sang lớp đa AZ",
                any(
                    term in answer.casefold()
                    for term in ("standard-ia", "glacier instant retrieval")
                ),
                answer[:200],
            )
        )
    elif key == "KB-06:3":
        specific.append(("nêu mốc 90 ngày", "90" in answer, answer[:200]))
    elif key == "KB-06:4":
        specific.append(
            ("nêu mốc 30 ngày và 20 ngày", "30" in answer and "20" in answer, answer[:200])
        )
    elif key == "KB-07:1":
        specific.append(
            (
                "chọn Reserved/Savings Plans cho nền 24/7",
                any(term in answer.casefold() for term in ("reserved instance", "savings plans")),
                answer[:200],
            )
        )
    elif key == "KB-07:2":
        specific.append(("nêu thông báo 2 phút", "2 phút" in answer.casefold(), answer[:200]))
    elif key == "KB-07:4":
        specific.append(("chọn Spot cho batch", "spot" in answer.casefold(), answer[:200]))
    elif key == "KB-08:3":
        lowered = rewritten.casefold()
        banned = [term for term in ("log", "s3", "deep archive") if term in lowered]
        specific.append(("câu viết lại không còn từ khóa S3/log", not banned, f"khớp: {banned}"))
        specific.append(
            (
                "trích dẫn không có S3",
                not any("s3 storage classes" in s.casefold() for s in sources),
                f"nguồn={sources[:4]}",
            )
        )
    elif key == "KB-08:4":
        specific.append(
            (
                "trích dẫn không có S3",
                not any("s3 storage classes" in s.casefold() for s in sources),
                f"nguồn={sources[:4]}",
            )
        )
    elif key == "KB-09:2":
        lowered = answer.casefold()
        confirms = "đúng" in lowered or any(
            phrase in lowered
            for phrase in (
                "không gắn security group",
                "không có security group",
                "không sử dụng security group",
            )
        )
        specific.append(
            (
                "xác nhận NAT Gateway không có security group",
                "security group" in lowered and confirms,
                answer[:200],
            )
        )
    elif key == "KB-10:1":
        specific.append(("có trích dẫn S3", bool(sources), f"nguồn={sources[:3]}"))
    elif key == "KB-10:4":
        specific.append(("trả lời mili giây", "mili giây" in answer.casefold(), answer[:200]))

    checks.extend(specific)
    return checks


def _retrieved_chunks(retrieval) -> list[dict[str, Any]]:
    last = retrieval.last() if retrieval is not None else None
    if last is None:
        return []
    return [
        {
            "rank": chunk.rank,
            "child_id": chunk.child_id,
            "document": chunk.document_title or chunk.document,
            "section": chunk.section,
            "page": chunk.page,
            "score": round(chunk.score, 4),
        }
        for chunk in last.chunks
    ]


def _turn_record(
    scenario: Scenario,
    turn: Turn,
    answer,
    retrieval,
    started: float,
) -> dict[str, Any]:
    result = answer.result
    chunks = _retrieved_chunks(retrieval)
    if result is None:
        return {
            "number": turn.number,
            "question": turn.question,
            "error": "không có kết quả sinh",
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "retrieved": chunks,
        }
    return {
        "number": turn.number,
        "question": turn.question,
        "rewritten_query": answer.turn.rewritten,
        "rewrite_source": answer.turn.condensation.source,
        "depends_on_context": answer.turn.condensation.depends_on_context,
        "conversation_tokens": answer.turn.conversation.tokens,
        "summary_used": answer.turn.conversation.summary_used,
        "summary_source": answer.turn.summary_source,
        "summary_latency_ms": answer.turn.summary_latency_ms,
        "answer": result.payload.answer,
        "abstained": result.payload.abstained,
        "abstention_type": result.payload.abstention_type,
        "confidence": result.payload.confidence,
        "citations": [
            {"source": item.source, "quote": item.quote} for item in result.payload.citations
        ],
        "citation_validity": result.citation_report.citation_validity,
        "unmatched_citations": [issue.citation for issue in result.citation_report.unmatched],
        "provider": result.provider,
        "model": result.model,
        "fallback_used": result.fallback_used,
        "input_tokens": result.usage_input_tokens,
        "output_tokens": result.usage_output_tokens,
        "ttft_ms": result.ttft_ms,
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "prompt_audit": result.extra.get("prompt_audit"),
        "timings_ms": result.timings_ms,
        "retrieved": chunks,
    }


def _stream_turn_record(
    service: ChatService,
    user_id: UUID,
    session_id: UUID,
    turn: Turn,
    retrieval,
    started: float,
) -> dict[str, Any]:
    """Chạy một lượt qua SSE và dựng bản ghi giống chế độ answer để chấm chung."""
    meta: dict[str, Any] = {}
    done: dict[str, Any] = {}
    citations: list[dict[str, Any]] = []
    citation_validity = 1.0
    unmatched: list[str] = []
    warnings: list[str] = []
    parts: list[str] = []
    stream_error: str | None = None
    for event in service.stream(user_id, session_id, turn.question):
        if event.event == "meta":
            meta = event.data
        elif event.event == "token":
            parts.append(str(event.data.get("text", "")))
        elif event.event == "citations":
            citations = list(event.data.get("items", []))
            citation_validity = float(event.data.get("citation_validity", 1.0))
            unmatched = [item.get("citation", "") for item in event.data.get("unmatched", [])]
            warnings = list(event.data.get("warnings", []))
        elif event.event == "error":
            stream_error = str(event.data.get("message") or event.data.get("code") or "lỗi stream")
        elif event.event == "done":
            done = event.data
    if stream_error:
        raise RuntimeError(stream_error)
    usage = done.get("usage") or {}
    return {
        "number": turn.number,
        "question": turn.question,
        "rewritten_query": meta.get("rewritten_query", turn.question),
        "rewrite_source": meta.get("rewrite_source", ""),
        "depends_on_context": meta.get("depends_on_context", False),
        "conversation_tokens": meta.get("conversation_tokens", 0),
        "summary_used": meta.get("summary_used", False),
        "summary_source": meta.get("summary_source"),
        "summary_latency_ms": meta.get("summary_latency_ms", 0.0),
        "answer": "".join(parts),
        "abstained": done.get("abstained", False),
        "abstention_type": done.get("abstention_type"),
        "confidence": done.get("confidence"),
        "citations": [
            {"source": item.get("source", ""), "quote": item.get("quote", "")} for item in citations
        ],
        "citation_validity": citation_validity,
        "unmatched_citations": unmatched,
        "warnings": warnings,
        "provider": done.get("provider"),
        "model": done.get("model"),
        "fallback_used": done.get("fallback_used", False),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "ttft_ms": done.get("ttft_ms"),
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "stream_latency_ms": done.get("latency_ms"),
        "stream_status": done.get("status"),
        "prompt_audit": done.get("prompt_audit"),
        "timings_ms": done.get("timings_ms"),
        "retrieved": _retrieved_chunks(retrieval),
    }


class Runner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.env = load_environment()
        self.gen_config = load_generation_config()
        if args.provider:
            self.gen_config = self.gen_config.with_overrides({"chain": [args.provider]})
        self.chain = build_provider_chain(self.gen_config, environ=self.env)
        self.retrieval = RecordingRetrieval(build_default_service())
        self.chat_config = load_conversation_config()
        self.judge = Judge(self._build_judge_chain())
        self.lock = threading.Lock()

    def _judge_config(self, name: str) -> GenerationConfig:
        """Cấu hình judge tất định: temperature 0 cho provider tương thích OpenAI."""
        config = self.gen_config.with_overrides({"chain": [name]})
        provider = config.provider_map.get(name)
        if provider is None or provider.type != "openai_compat":
            return config
        providers = tuple(
            replace(item, temperature=0.0) if item.name == name else item
            for item in config.providers
        )
        return replace(config, providers=providers)

    def _build_judge_chain(self):
        if self.args.judge:
            return build_provider_chain(self._judge_config(self.args.judge), environ=self.env)
        for name in ("deepseek_primary",):
            if name in self.gen_config.provider_map:
                try:
                    return build_provider_chain(self._judge_config(name), environ=self.env)
                except LLMError:
                    continue
        raise SystemExit("Không dựng được judge")

    def chat_service(self) -> ChatService:
        generation = GenerationService(
            self.gen_config,
            self.chain,
            retrieval=self.retrieval,
            prompts=PromptLibrary(self.gen_config.prompt_root),
            log_writer=None,
        )
        return ChatService(InMemorySessionRepository(), generation, self.chat_config)

    def run_scenario(self, scenario: Scenario, transport: str) -> dict[str, Any]:
        service = self.chat_service()
        session = service.create_session(USER_ID, title=f"{scenario.code} — {scenario.title}")
        print(f"[{scenario.code}] bắt đầu ({transport}): {scenario.title}", flush=True)
        records: list[dict[str, Any]] = []
        history_lines: list[str] = []
        try:
            for turn in scenario.turns:
                started = time.perf_counter()
                try:
                    if transport == "stream":
                        record = _stream_turn_record(
                            service, USER_ID, session.id, turn, self.retrieval, started
                        )
                    else:
                        answer = service.answer(USER_ID, session.id, turn.question)
                        record = _turn_record(scenario, turn, answer, self.retrieval, started)
                except Exception as exc:  # noqa: BLE001 - ghi lại mọi lỗi của một lượt
                    record = {
                        "number": turn.number,
                        "question": turn.question,
                        "error": f"{type(exc).__name__}: {exc}",
                        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                    }
                sources = _citation_sources(record)
                checks = (
                    auto_checks(scenario, turn, record, sources)
                    if not record.get("error")
                    else [("lượt chạy được", False, record["error"])]
                )
                if record.get("error"):
                    score, reason = 0.0, record["error"]
                else:
                    score, reason = self.judge.score(
                        scenario, turn, "\n".join(history_lines), record
                    )
                record["judge_score"] = score
                record["judge_reason"] = reason
                record["auto_checks"] = [
                    {"label": label, "passed": ok, "detail": detail} for label, ok, detail in checks
                ]
                record["passed"] = score >= 1.0 and all(ok for _, ok, _ in checks)
                records.append(record)
                print(
                    f"[{scenario.code}] lượt {turn.number}/{len(scenario.turns)} "
                    f"judge={score:.1f} {'ĐẠT' if record['passed'] else 'KHÔNG'} "
                    f"({record.get('latency_ms', 0):.0f} ms)",
                    flush=True,
                )
                history_lines.append(f"- Lượt {turn.number} hỏi: {turn.question}")
                if record.get("rewritten_query") and not _rewritten_equals_original(record):
                    history_lines.append(f"  viết lại: {record['rewritten_query']}")
                history_lines.append(
                    "  đáp: " + record.get("answer", record.get("error", ""))[:HISTORY_ANSWER_CHARS]
                )
                sources = _citation_sources(record)
                if sources:
                    history_lines.append(f"  trích dẫn: {', '.join(dict.fromkeys(sources))}")
        finally:
            service.close()

        failed = [record for record in records if not record.get("passed")]
        notes = "; ".join(
            f"lượt {record['number']}: "
            + (record.get("judge_reason") or record.get("error", ""))[:160]
            for record in failed
        )
        return {
            "code": scenario.code,
            "title": scenario.title,
            "kind": scenario.kind,
            "transport": transport,
            "session_id": str(session.id),
            "turns": len(records),
            "passed_turns": sum(1 for record in records if record.get("passed")),
            "passed": not failed,
            "notes": notes,
            "records": records,
        }

    def run(self, scenarios: list[Scenario], transport: str) -> list[dict[str, Any]]:
        with ThreadPoolExecutor(max_workers=self.args.workers) as pool:
            results = list(
                pool.map(lambda scenario: self.run_scenario(scenario, transport), scenarios)
            )
        results.sort(key=lambda item: item["code"])
        return results


def _failures_by_layer(record: dict[str, Any]) -> str:
    layers: list[str] = []
    copies = [check for check in record.get("auto_checks", []) if not check["passed"]]
    for check in copies:
        label = check["label"]
        if "viết lại" in label or "S3/log" in label:
            layers.append("condensation")
        elif "trích dẫn" in label:
            layers.append("retrieval")
        elif "từ chối" in label or "rò rỉ" in label:
            layers.append("generation")
        else:
            layers.append("generation")
    if record.get("judge_score", 0.0) < 1.0 and not layers:
        layers.append("generation")
    return ", ".join(dict.fromkeys(layers)) or "generation"


def _scenario_table(results: list[dict[str, Any]]) -> str:
    lines = [
        "| Kịch bản | Số lượt | Đạt | Ghi chú |",
        "| :--- | :---: | :---: | :--- |",
    ]
    for result in results:
        notes = result["notes"] or "4/4 lượt đạt"
        notes = notes.replace("|", "/")
        lines.append(
            f"| {result['code']} | {result['turns']} | "
            f"{'ĐẠT' if result['passed'] else 'KHÔNG'} | {notes} |"
        )
    passed = sum(1 for result in results if result["passed"])
    lines.append("")
    lines.append(f"**Tổng số kịch bản đạt: {passed}/{len(results)}** (ngưỡng ≥ 8/10).")
    return "\n".join(lines)


def _turn_table(results: list[dict[str, Any]]) -> str:
    lines = [
        "| Kịch bản | Lượt | Rewrite nguồn | Điểm judge | Auto check | Đạt | Lỗi tầng |",
        "| :--- | :---: | :--- | :---: | :--- | :---: | :--- |",
    ]
    for result in results:
        for record in result["records"]:
            checks = "; ".join(
                f"{check['label']}={'OK' if check['passed'] else 'FAIL'}"
                for check in record.get("auto_checks", [])
            )
            layers = _failures_by_layer(record) if not record.get("passed") else ""
            lines.append(
                f"| {result['code']} | {record['number']} | "
                f"{record.get('rewrite_source', '—')} | "
                f"{record.get('judge_score', 0.0):.1f} | {checks or '—'} | "
                f"{'ĐẠT' if record.get('passed') else 'KHÔNG'} | {layers} |"
            )
    return "\n".join(lines)


def _judge_provider(runner: Runner) -> str:
    return ", ".join(getattr(runner.judge.chain, "names", ())) or "không rõ"


def _judge_self_preference(runner: Runner) -> bool:
    """Judge trùng nhà cung cấp với bộ sinh câu trả lời hay không."""
    generation = {name.split("_")[0] for name in runner.chain.names}
    judging = {name.split("_")[0] for name in getattr(runner.judge.chain, "names", ())}
    return bool(generation & judging)


def _run_transport(
    runner: Runner, scenarios: list[Scenario], transport: str, stamp: str
) -> tuple[dict[str, Any], str, str]:
    started = time.perf_counter()
    results = runner.run(scenarios, transport)
    table = _scenario_table(results)
    turn_table = _turn_table(results)
    output = {
        "timestamp": stamp,
        "transport": transport,
        "provider_chain": list(runner.chain.names),
        "judge": runner.args.judge or "auto",
        "judge_provider": _judge_provider(runner),
        "judge_self_preference": _judge_self_preference(runner),
        "judge_tokens": runner.judge.tokens,
        "judge_cost_usd": round(runner.judge.cost, 6),
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        "passed": sum(1 for result in results if result["passed"]),
        "total": len(results),
        "results": results,
    }
    return output, table, turn_table


def _report_markdown(
    stamp: str, runner: Runner, output: dict[str, Any], table: str, turn_table: str
) -> str:
    return (
        f"# Kết quả 10 kịch bản hội thoại ({stamp}, {output['transport']})\n\n"
        f"- Provider chain: {', '.join(runner.chain.names)}\n"
        f"- Judge: {output['judge_provider']} ({runner.judge.tokens} token, "
        f"{runner.judge.cost:.6f} USD)\n"
        f"- Judge trùng nhà cung cấp với bộ sinh: {output['judge_self_preference']}\n"
        f"- Thời gian chạy: {output['elapsed_seconds']} giây\n"
        f"- Đạt: {output['passed']}/{output['total']}\n\n"
        f"{table}\n\n## Chi tiết từng lượt\n\n{turn_table}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--scenarios", default=None, help="Danh sách mã, ví dụ KB-01,KB-10")
    parser.add_argument("--provider", default=None)
    parser.add_argument("--judge", default=None)
    parser.add_argument(
        "--conversations",
        default=None,
        help="Đường dẫn bộ kịch bản; mặc định inputs/conversations.md (bộ nghiệm thu)",
    )
    parser.add_argument(
        "--transport",
        choices=("answer", "stream", "both"),
        default="answer",
        help="answer: gọi ChatService.answer; stream: gọi SSE; both: chạy cả hai và lưu chung",
    )
    args = parser.parse_args()

    scenarios = load_scenarios(Path(args.conversations) if args.conversations else CONVERSATIONS)
    if args.scenarios:
        wanted = {item.strip() for item in args.scenarios.split(",")}
        scenarios = [scenario for scenario in scenarios if scenario.code in wanted]

    runner = Runner(args)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    transports = ("answer", "stream") if args.transport == "both" else (args.transport,)
    try:
        runs = {
            transport: _run_transport(runner, scenarios, transport, stamp)
            for transport in transports
        }
    finally:
        runner.judge.save()
        runner.chain.close()
        judge_chain = getattr(runner.judge, "chain", None)
        if judge_chain is not None:
            judge_chain.close()

    RESULTS.mkdir(parents=True, exist_ok=True)
    if args.transport == "both":
        output = {
            "timestamp": stamp,
            "transport": "both",
            "provider_chain": list(runner.chain.names),
            "judge": args.judge or "auto",
            "judge_provider": _judge_provider(runner),
            "judge_self_preference": _judge_self_preference(runner),
            "judge_tokens": runner.judge.tokens,
            "judge_cost_usd": round(runner.judge.cost, 6),
            "runs": {transport: payload for transport, (payload, _, _) in runs.items()},
        }
        path = RESULTS / f"conversation_bench_both_{stamp}"
        path.with_suffix(".json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        sections = []
        for payload, table, turn_table in runs.values():
            sections.append(_report_markdown(stamp, runner, payload, table, turn_table))
            print(table)
            print()
            print(turn_table)
            print()
        path.with_suffix(".md").write_text("\n\n---\n\n".join(sections), encoding="utf-8")
        passed = min(payload["passed"] for payload, _, _ in runs.values())
        saved = f"{path}.json/.md"
    else:
        output, table, turn_table = runs[args.transport]
        path = RESULTS / f"conversation_bench_{args.transport}_{stamp}"
        path.with_suffix(".json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        path.with_suffix(".md").write_text(
            _report_markdown(stamp, runner, output, table, turn_table), encoding="utf-8"
        )
        print(table)
        print()
        print(turn_table)
        passed = output["passed"]
        saved = f"{path}.json/.md"
    print(f"\nĐã lưu {saved}")
    print(f"Judge: {runner.judge.tokens} token, {runner.judge.cost:.6f} USD")
    return 0 if passed >= 8 else 2


if __name__ == "__main__":
    raise SystemExit(main())
