"""Demo chuỗi dự phòng: Gemini lỗi -> adapter DeepSeek trả lời.

Chạy 3 câu hỏi trong phạm vi với khóa Gemini không hợp lệ (không in giá trị khóa),
sau đó chạy lại với khóa Gemini bị bỏ trống để chứng minh factory bỏ qua provider
thiếu thông tin xác thực.

Cách dùng:
    python evaluation/fallback_demo.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.generation import (  # noqa: E402
    GenerationService,
    PromptLibrary,
    build_provider_chain,
    load_generation_config,
)
from app.services.generation.settings import load_environment  # noqa: E402

QUESTIONS = [
    "S3 Standard phù hợp với loại dữ liệu nào và độ bền được cam kết ra sao?",
    "Khác biệt chính giữa S3 Standard-IA và S3 One Zone-IA là gì?",
    "Khi nào nên dùng S3 Glacier Deep Archive thay vì S3 Glacier Flexible Retrieval?",
]

BROKEN_KEY = "demo-key-bi-vo-hieu-hoa"


def _build_retrieval():
    from app.services.retrieval import build_default_service

    return build_default_service()


def _run(label: str, env: dict[str, str], questions: list[str], retrieval) -> list[dict]:
    config = load_generation_config()
    try:
        chain = build_provider_chain(config, environ=env)
    except Exception as exc:  # noqa: BLE001
        print(f"[{label}] không dựng được chain: {type(exc).__name__}: {exc}")
        return []
    print(f"[{label}] chain: {' -> '.join(chain.names)}")
    service = GenerationService(
        config,
        chain,
        retrieval=retrieval,
        prompts=PromptLibrary(config.prompt_root),
        log_writer=None,
    )
    rows = []
    try:
        for question in questions:
            started = time.perf_counter()
            result = service.answer(question, mode="base", thinking_level="low", write_log=False)
            elapsed = (time.perf_counter() - started) * 1000
            row = {
                "question": question,
                "provider": result.provider,
                "model": result.model,
                "fallback_used": result.fallback_used,
                "attempts": result.attempts,
                "latency_ms": round(elapsed, 1),
                "abstained": result.payload.abstained,
                "answer": result.payload.answer[:280],
                "citation_validity": result.citation_report.citation_validity,
                "citations": list(result.citation_report.inline_citations[:4]),
                "input_tokens": result.usage_input_tokens,
                "output_tokens": result.usage_output_tokens,
            }
            rows.append(row)
            print(
                f"  - {row['provider']} | fallback={row['fallback_used']} | "
                f"{row['latency_ms']}ms | trích dẫn hợp lệ={row['citation_validity']:.0%}"
            )
    except Exception as exc:  # noqa: BLE001
        print(f"[{label}] lỗi: {type(exc).__name__}: {exc}")
    finally:
        chain.close()
    return rows


def main() -> int:
    env = dict(load_environment())
    if not env.get("OPENAI_API_KEY"):
        print("Thiếu OPENAI_API_KEY (DeepSeek) trong .env — không chạy được demo.")
        return 1

    retrieval = _build_retrieval()
    broken = dict(env)
    broken["GEMINI_API_KEY"] = BROKEN_KEY
    print("== Kịch bản 1: khóa Gemini không hợp lệ, DeepSeek hợp lệ ==")
    rows = _run("gemini hỏng", broken, QUESTIONS, retrieval)

    print("\n== Kịch bản 2: bỏ trống khóa Gemini, factory tự bỏ qua ==")
    missing = dict(env)
    missing["GEMINI_API_KEY"] = ""
    skipped = _run("gemini thiếu khóa", missing, QUESTIONS[:1], retrieval)

    payload = {
        "broken_gemini_key": rows,
        "missing_gemini_key": skipped,
        "all_fell_back": (
            all(row["fallback_used"] == "deepseek_fallback" for row in rows) if rows else False
        ),
    }
    output = ROOT / "evaluation" / "results" / "fallback_demo.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nĐã ghi {output}")
    if rows:
        print(
            "Kết luận: "
            + (
                "cả 3 câu đều do adapter dự phòng trả lời."
                if payload["all_fell_back"]
                else "CÓ câu không dùng dự phòng — kiểm tra lại log."
            )
        )
    return 0 if payload["all_fell_back"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
