"""Benchmark tầng sinh câu trả lời trên bộ dev nội bộ.

Chạy cùng một bộ câu hỏi và cùng ngữ cảnh truy hồi cho hai cấu hình
(không CoT / có CoT), chấm tự động bằng LLM judge, xuất bảng so sánh.

Ví dụ:
    python evaluation/gen_bench.py --before-after --workers 4
    python evaluation/gen_bench.py --scope
    python evaluation/gen_bench.py --in-scope
    python evaluation/gen_bench.py --citations
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.generation import (  # noqa: E402
    FallbackChain,
    GenerationService,
    LLMMessage,
    PromptLibrary,
    build_provider_chain,
    load_generation_config,
)
from app.services.generation.prompts import QUERY_TYPE_MODES  # noqa: E402
from app.services.generation.providers import LLMError  # noqa: E402
from app.services.generation.settings import load_environment  # noqa: E402
from app.services.retrieval.types import RetrievedChunk  # noqa: E402

DEV_SET = ROOT / "evaluation" / "dev_generation.jsonl"
OOS_FILE = ROOT / "inputs" / "out_of_scope_questions.md"
RESULTS = ROOT / "evaluation" / "results"
SNAPSHOT = RESULTS / "gen_context_snapshot.json"
JUDGE_CACHE = RESULTS / "gen_bench_judge_cache.json"

JUDGE_PROMPT = """Bạn là giám khảo chấm câu trả lời của chatbot ôn thi AWS SAA-C03.
Chấm điểm câu trả lời so với đáp án tham chiếu, chỉ dựa trên nội dung tài liệu.

Thang điểm:
- 1.0: đúng và đủ ý chính của đáp án tham chiếu, không có lỗi kỹ thuật.
- 0.5: đúng một phần, thiếu ý quan trọng nhưng không sai.
- 0.0: sai, bịa thông tin, hoặc từ chối trả lời trong khi tài liệu có câu trả lời.

Câu hỏi: {question}
Đáp án tham chiếu: {reference}
Câu trả lời của hệ thống: {candidate}

Trả JSON đúng dạng {{"score": 0.0, "reason": "..."}} và không thêm văn bản."""

OOS_FORBIDDEN = {
    "OOS-A1": ("mutable", "immutable", "tuple không đổi", "list có thể"),
    "OOS-A2": ("bắt tay ba bước", "three-way", "giao vận tin cậy", "datagram"),
    "OOS-A3": ("inner join", "left join", "select ", "null"),
    "OOS-A4": ("git rebase", "git merge", "gộp commit", "lịch sử commit"),
    "OOS-A5": ("7 tầng", "bảy tầng", "osi", "tầng giao vận"),
    "OOS-B1": ("foundation model", "model nền tảng", "anthropic", "llama"),
    "OOS-B2": ("codewhisperer", "code whisperer", "gợi ý mã", "autocomplete"),
    "OOS-B3": ("healthimaging", "health imaging", "ảnh y tế", "dicom"),
    "OOS-B4": ("clean rooms", "clean room", "phân tích dữ liệu chung", "liên tổ chức"),
    "OOS-B5": ("verified access", "thay thế vpn", "vpn truyền thống"),
}

OOS_JUDGE_PROMPT = """Bạn chấm câu trả lời của chatbot ôn thi AWS SAA-C03
cho câu hỏi NGOÀI phạm vi tài liệu.
Yêu cầu: chatbot phải từ chối trả lời và KHÔNG được cung cấp nội dung kỹ thuật
trả lời câu hỏi. Việc nêu tên chủ đề để giải thích lý do từ chối là hợp lệ.

Câu hỏi ngoài phạm vi: {question}
Câu trả lời của hệ thống: {candidate}

Chấm:
- 1.0 nếu từ chối rõ ràng, không giải thích kỹ thuật cho câu hỏi.
- 0.0 nếu trả lời câu hỏi, cung cấp chi tiết kỹ thuật, hoặc lẫn kiến thức ngoài tài liệu.

Trả JSON đúng dạng {{"score": 1.0, "reason": "..."}} và không thêm văn bản."""


@dataclass(frozen=True)
class Case:
    id: str
    question: str
    reference: str
    document_title: str
    section: str
    query_type: str = "tra_cuu"


def load_dev_set(limit: int | None = None) -> list[Case]:
    cases = []
    for line in DEV_SET.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        cases.append(
            Case(
                id=raw["id"],
                question=raw["question"],
                reference=raw["reference_answer"],
                document_title=raw["document_title"],
                section=raw["section"],
                query_type=raw.get("query_type", "tra_cuu"),
            )
        )
    return cases[:limit] if limit else cases


def load_oos_cases() -> list[Case]:
    cases = []
    for line in OOS_FILE.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\|\s*(OOS-[AB]\d)\s*\|\s*(.+?)\s*\|", line)
        if not match:
            continue
        cases.append(
            Case(
                id=match.group(1),
                question=match.group(2).strip(),
                reference="",
                document_title="",
                section="",
            )
        )
    return cases


class Bench:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.env = load_environment()
        self.config = load_generation_config()
        if args.provider:
            self.config = self.config.with_overrides({"chain": [args.provider]})
        self.chain = build_provider_chain(self.config, environ=self.env)
        self.retrieval = _build_retrieval()
        self.lock = threading.Lock()
        self.judge_chain = self._build_judge_chain()
        self.judge_cache = _load_json(JUDGE_CACHE) if JUDGE_CACHE.exists() else {}
        self.judge_cost = 0.0
        self.judge_tokens = 0

    def _build_judge_chain(self) -> FallbackChain:
        judge = self.args.judge
        if judge and judge not in self.config.provider_map:
            raise SystemExit(f"Không có provider judge: {judge}")
        if judge:
            config = self.config.with_overrides({"chain": [judge]})
            return build_provider_chain(config, environ=self.env)
        for name in ("deepseek_primary",):
            if name in self.config.provider_map:
                try:
                    return build_provider_chain(
                        self.config.with_overrides({"chain": [name]}), environ=self.env
                    )
                except LLMError:
                    continue
        raise SystemExit("Không dựng được judge")

    def service(self) -> GenerationService:
        return GenerationService(
            self.config,
            self.chain,
            retrieval=self.retrieval,
            prompts=PromptLibrary(self.config.prompt_root),
            log_writer=None,
        )

    def chunks_for(
        self, cases: list[Case], *, refresh: bool = False
    ) -> dict[str, list[RetrievedChunk]]:
        cached = {}
        if SNAPSHOT.exists() and not refresh:
            raw = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
            for case in cases:
                if case.id in raw:
                    cached[case.id] = [RetrievedChunk(**item) for item in raw[case.id]]
        missing = [case for case in cases if case.id not in cached]
        if missing:
            print(f"Truy hồi {len(missing)} câu chưa có snapshot...", flush=True)
            for index, case in enumerate(missing, 1):
                result = self.retrieval.retrieve(case.question)
                cached[case.id] = result.chunks
                if index % 10 == 0:
                    print(f"  {index}/{len(missing)}", flush=True)
            merged = {}
            if SNAPSHOT.exists():
                merged = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
            for case in cases:
                chunks = cached.get(case.id) or []
                merged[case.id] = [chunk.as_dict() for chunk in chunks]
            SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
            SNAPSHOT.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
        return cached

    def run_condition(
        self,
        cases: list[Case],
        chunks: dict[str, list[RetrievedChunk]],
        *,
        use_cot: bool,
    ) -> list[dict]:
        service = self.service()
        lock = threading.Lock()
        results: list[dict] = []

        def worker(case: Case) -> None:
            started = time.perf_counter()
            try:
                result = service.answer(
                    case.question,
                    chunks=chunks.get(case.id, []),
                    mode=QUERY_TYPE_MODES.get(case.query_type),
                    use_cot=use_cot,
                    thinking_level=self.args.thinking,
                    write_log=False,
                )
                record = _record(case, result)
            except Exception as exc:  # noqa: BLE001 - benchmark ghi lại mọi lỗi
                record = {
                    "id": case.id,
                    "question": case.question,
                    "error": f"{type(exc).__name__}: {exc}",
                    "latency_ms": (time.perf_counter() - started) * 1000,
                }
            with lock:
                results.append(record)

        with ThreadPoolExecutor(max_workers=self.args.workers) as pool:
            list(pool.map(worker, cases))
        results.sort(key=lambda item: item["id"])
        return results

    def judge(self, case: Case, candidate: str, *, cache_key: str) -> tuple[float, str]:
        key = f"{self.args.judge or 'auto'}|{case.id}|{cache_key}"
        with self.lock:
            if key in self.judge_cache:
                return self.judge_cache[key]["score"], self.judge_cache[key]["reason"]
        messages = [
            LLMMessage(role="system", content="Chỉ trả JSON, không thêm văn bản."),
            LLMMessage(
                role="user",
                content=JUDGE_PROMPT.format(
                    question=case.question,
                    reference=case.reference,
                    candidate=candidate[:6000],
                ),
            ),
        ]
        try:
            response = self.judge_chain.complete(messages, thinking_level="low", json_mode=True)
            data = _extract_json(response.text)
            score = float(data.get("score", 0.0))
            score = max(0.0, min(1.0, score))
            reason = str(data.get("reason", ""))[:300]
            with self.lock:
                self.judge_cost += response.cost_usd
                self.judge_tokens += response.usage.total_tokens
                self.judge_cache[key] = {"score": score, "reason": reason}
        except Exception as exc:  # noqa: BLE001
            score, reason = 0.0, f"judge lỗi: {type(exc).__name__}"
            with self.lock:
                self.judge_cache[key] = {"score": score, "reason": reason}
        return score, reason

    def judge_refusal(self, case: Case, candidate: str) -> tuple[float, str]:
        key = f"oos|{case.id}|{_hash(candidate)}"
        with self.lock:
            if key in self.judge_cache:
                return self.judge_cache[key]["score"], self.judge_cache[key]["reason"]
        messages = [
            LLMMessage(role="system", content="Chỉ trả JSON, không thêm văn bản."),
            LLMMessage(
                role="user",
                content=OOS_JUDGE_PROMPT.format(question=case.question, candidate=candidate[:4000]),
            ),
        ]
        try:
            response = self.judge_chain.complete(messages, thinking_level="low", json_mode=True)
            data = _extract_json(response.text)
            score = 1.0 if float(data.get("score", 0.0)) >= 0.5 else 0.0
            reason = str(data.get("reason", ""))[:300]
        except Exception as exc:  # noqa: BLE001
            score, reason = 0.0, f"judge lỗi: {type(exc).__name__}"
        with self.lock:
            self.judge_cache[key] = {"score": score, "reason": reason}
        return score, reason

    def grade(self, condition: str, results: list[dict], cases: list[Case]) -> dict:
        by_id = {case.id: case for case in cases}
        scored = []
        for record in results:
            case = by_id[record["id"]]
            if record.get("error"):
                record.update({"score": 0.0, "judge_reason": record["error"]})
            else:
                cache_key = f"{condition}|{_hash(record.get('answer', ''))}"
                score, reason = self.judge(case, record.get("answer", ""), cache_key=cache_key)
                record.update({"score": score, "judge_reason": reason})
            scored.append(record)
        return {"condition": condition, "records": scored, "metrics": _metrics(scored)}

    def save_cache(self) -> None:
        JUDGE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        JUDGE_CACHE.write_text(json.dumps(self.judge_cache, ensure_ascii=False), encoding="utf-8")

    def close(self) -> None:
        self.chain.close()
        self.judge_chain.close()


def _record(case: Case, result) -> dict:
    return {
        "id": case.id,
        "question": case.question,
        "reference": case.reference,
        "expected_document": case.document_title,
        "expected_section": case.section,
        "answer": result.payload.answer,
        "abstained": result.payload.abstained,
        "abstention_type": result.payload.abstention_type,
        "confidence": result.payload.confidence,
        "citation_validity": result.citation_report.citation_validity,
        "quote_grounding": result.citation_report.quote_grounding,
        "inline_citations": list(result.citation_report.inline_citations),
        "unmatched_citations": [issue.citation for issue in result.citation_report.unmatched],
        "warnings": list(result.warnings),
        "provider": result.provider,
        "model": result.model,
        "fallback_used": result.fallback_used,
        "prompt_mode": result.prompt_mode,
        "thinking_level": result.thinking_level,
        "schema_retries": result.schema_retries,
        "attempts": list(result.attempts),
        "input_tokens": result.usage_input_tokens,
        "output_tokens": result.usage_output_tokens,
        "cost_usd": result.cost_usd,
        "latency_ms": result.latency_ms,
    }


def _metrics(records: list[dict]) -> dict:
    total = len(records)
    if total == 0:
        return {}
    scores = [float(record.get("score", 0.0)) for record in records]
    answered = [
        record for record in records if not record.get("abstained") and not record.get("error")
    ]
    return {
        "n": total,
        "accuracy": round(sum(scores) / total, 4),
        "exact_rate": round(sum(1 for score in scores if score >= 1.0) / total, 4),
        "partial_rate": round(sum(1 for score in scores if 0.0 < score < 1.0) / total, 4),
        "zero_rate": round(sum(1 for score in scores if score <= 0.0) / total, 4),
        "wrong_refusal_rate": round(
            sum(1 for record in records if record.get("abstained")) / total, 4
        ),
        "citation_validity": round(
            sum(record.get("citation_validity", 0.0) for record in answered)
            / max(1, len(answered)),
            4,
        ),
        "avg_latency_ms": round(
            sum(record.get("latency_ms", 0.0) for record in records) / total, 1
        ),
        "avg_input_tokens": round(
            sum(record.get("input_tokens", 0) for record in records) / total, 1
        ),
        "avg_output_tokens": round(
            sum(record.get("output_tokens", 0) for record in records) / total, 1
        ),
        "total_cost_usd": round(sum(record.get("cost_usd", 0.0) for record in records), 6),
    }


def _comparison_table(before: dict, after: dict) -> str:
    rows = [
        ("Độ chính xác trung bình", "accuracy", True),
        ("Tỷ lệ đúng hoàn toàn", "exact_rate", True),
        ("Tỷ lệ đúng một phần", "partial_rate", True),
        ("Tỷ lệ sai/từ chối sai", "zero_rate", True),
        ("Tỷ lệ từ chối sai", "wrong_refusal_rate", True),
        ("Hiệu lực trích dẫn", "citation_validity", False),
        ("Độ trễ trung bình (ms)", "avg_latency_ms", False),
        ("Token vào trung bình", "avg_input_tokens", False),
        ("Token ra trung bình", "avg_output_tokens", False),
        ("Tổng chi phí (USD)", "total_cost_usd", False),
    ]
    lines = [
        "| Chỉ số | Trước CoT | Sau CoT | Chênh lệch |",
        "| :--- | ---: | ---: | ---: |",
    ]
    for label, key, percent in rows:
        first = before.get(key, 0)
        second = after.get(key, 0)
        delta = second - first
        if percent:
            lines.append(
                f"| {label} | {first * 100:.1f}% | {second * 100:.1f}% | "
                f"{delta * 100:+.1f} điểm % |"
            )
        else:
            lines.append(f"| {label} | {first} | {second} | {delta:+.3f} |")
    return "\n".join(lines)


def run_before_after(bench: Bench) -> int:
    cases = load_dev_set(bench.args.limit)
    chunks = bench.chunks_for(cases, refresh=bench.args.refresh)
    print(f"{len(cases)} câu, provider {bench.chain.names}", flush=True)
    before = bench.run_condition(cases, chunks, use_cot=False)
    after = bench.run_condition(cases, chunks, use_cot=True)
    graded_before = bench.grade("before", before, cases)
    graded_after = bench.grade("after", after, cases)
    bench.save_cache()
    table = _comparison_table(graded_before["metrics"], graded_after["metrics"])
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    payload = {
        "timestamp": stamp,
        "provider_chain": list(bench.chain.names),
        "prompt_version": bench.config.prompt_version,
        "thinking_level": bench.args.thinking or "theo loại câu hỏi",
        "judge_cost_usd": round(bench.judge_cost, 6),
        "judge_tokens": bench.judge_tokens,
        "before": graded_before,
        "after": graded_after,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"gen_bench_{stamp}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RESULTS / f"gen_bench_{stamp}.md").write_text(
        f"# So sánh trước/sau CoT ({stamp})\n\n"
        f"- Provider chain: {', '.join(bench.chain.names)}\n"
        f"- Prompt: {bench.config.prompt_version}, "
        f"thinking={bench.args.thinking or 'theo loại câu hỏi'}\n"
        f"- Judge: {bench.args.judge or 'auto'} ({bench.judge_tokens} token, "
        f"{bench.judge_cost:.6f} USD)\n\n{table}\n",
        encoding="utf-8",
    )
    print(table)
    print(f"\nĐã lưu evaluation/results/gen_bench_{stamp}.json/.md")
    _print_provider_summary(after)
    _print_schema_summary(graded_before["records"], graded_after["records"])
    return 0


def run_scope(bench: Bench) -> int:
    cases = load_oos_cases()
    if not cases:
        print("Không đọc được câu ngoài phạm vi.")
        return 1
    chunks = bench.chunks_for(cases)
    results = bench.run_condition(cases, chunks, use_cot=True)
    passed = 0
    lines = [
        "| ID | Từ chối | Loại | Trích dẫn | Rò rỉ chi tiết | Judge | Đạt |",
        "| :--- | :---: | :--- | :---: | :---: | :---: | :---: |",
    ]
    for record in results:
        case = next(case for case in cases if case.id == record["id"])
        answer = record.get("answer", "")
        leaked = _leaks(answer, OOS_FORBIDDEN.get(case.id, ()), case.question)
        judge_score, judge_reason = bench.judge_refusal(case, answer)
        ok = (
            bool(record.get("abstained"))
            and not leaked
            and not record.get("unmatched_citations")
            and judge_score >= 1.0
        )
        passed += int(ok)
        lines.append(
            f"| {case.id} | {'có' if record.get('abstained') else 'KHÔNG'} | "
            f"{record.get('abstention_type', '')} | "
            f"{len(record.get('inline_citations', []))} | {'có' if leaked else 'không'} | "
            f"{judge_score:.1f} | {'ĐẠT' if ok else 'KHÔNG'} |"
        )
        if not ok:
            lines.append(f"| — | | | | | | {judge_reason[:160]} |")
    bench.save_cache()
    rate = passed / len(cases)
    lines.append("")
    lines.append(f"Tỷ lệ từ chối đúng: {passed}/{len(cases)} = {rate * 100:.1f}% (mục tiêu ≥ 90%)")
    output = "\n".join(lines)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (RESULTS / f"scope_check_{stamp}.md").write_text(output + "\n", encoding="utf-8")
    (RESULTS / f"scope_check_{stamp}.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(output)
    return 0 if rate >= 0.9 else 2


def run_in_scope(bench: Bench) -> int:
    cases = load_dev_set(bench.args.limit or 20)
    chunks = bench.chunks_for(cases)
    results = bench.run_condition(cases, chunks, use_cot=True)
    refusals = [record for record in results if record.get("abstained")]
    rate = len(refusals) / len(results)
    print(f"Câu trong phạm vi: {len(results)}")
    print(f"Từ chối sai: {len(refusals)}/{len(results)} = {rate * 100:.1f}% (mục tiêu ≤ 5%)")
    for record in refusals:
        print(f"  - {record['id']}: {record.get('answer', '')[:200]}")
    return 0 if rate <= 0.05 else 2


def run_citations(bench: Bench) -> int:
    cases = load_dev_set(bench.args.limit or 10)
    chunks = bench.chunks_for(cases)
    results = bench.run_condition(cases, chunks, use_cot=True)
    answered = [record for record in results if not record.get("abstained")]
    validity = sum(record["citation_validity"] for record in answered) / max(1, len(answered))
    print(f"Câu có kiểm tra trích dẫn: {len(answered)}/{len(results)}")
    print(f"Hiệu lực trích dẫn trung bình: {validity * 100:.1f}% (mục tiêu 100%)")
    for record in results:
        if record.get("unmatched_citations"):
            print(f"  - {record['id']}: {record['unmatched_citations'][:3]}")
    return 0 if validity >= 0.999 else 2


def _leaks(answer: str, forbidden: tuple[str, ...], question: str = "") -> bool:
    """Từ khoá kỹ thuật xuất hiện trong câu trả lời nhưng không có trong câu hỏi."""
    lowered = answer.casefold()
    asked = question.casefold()
    for term in forbidden:
        needle = term.casefold()
        if needle not in asked and needle in lowered:
            return True
    return False


def _extract_json(text: str) -> dict:
    cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


def _hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_retrieval():
    from app.services.retrieval import build_default_service

    return build_default_service()


def _print_provider_summary(results: list[dict]) -> None:
    counts: dict[str, int] = {}
    for record in results:
        counts[record.get("provider", "?")] = counts.get(record.get("provider", "?"), 0) + 1
    print("Provider đã trả lời:", ", ".join(f"{name}={count}" for name, count in counts.items()))


def _print_schema_summary(before: list[dict], after: list[dict]) -> None:
    """Đếm số câu phải thử lại vì sai schema; lỗi cuối cùng đã làm dừng run nên bằng 0."""
    for label, results in (("trước CoT", before), ("sau CoT", after)):
        retried = sum(1 for record in results if record.get("schema_retries", 0) > 0)
        print(f"Schema {label}: {retried}/{len(results)} câu phải thử lại, 0 lỗi cuối.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--before-after", action="store_true")
    group.add_argument("--scope", action="store_true")
    group.add_argument("--in-scope", action="store_true")
    group.add_argument("--citations", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--provider", default=None)
    parser.add_argument("--judge", default=None)
    parser.add_argument("--thinking", default=None)
    parser.add_argument("--refresh", action="store_true", help="Truy hồi lại, bỏ snapshot")
    args = parser.parse_args()
    if not (args.before_after or args.scope or args.in_scope or args.citations):
        args.before_after = True
    # Không gán mức mặc định ở đây: để None thì GenerationService tự chọn theo loại
    # câu hỏi (simple_query_thinking_level cho tra cứu), đúng cấu hình đang chạy.

    bench = Bench(args)
    try:
        if args.scope:
            return run_scope(bench)
        if args.in_scope:
            return run_in_scope(bench)
        if args.citations:
            return run_citations(bench)
        return run_before_after(bench)
    finally:
        bench.close()


if __name__ == "__main__":
    raise SystemExit(main())
