"""Đo TTFT và tổng thời gian đa lượt qua POST /chat/stream (SSE) trên bộ dev.

Mỗi kịch bản DV-* trong ``inputs/conversations_dev.md`` chạy trong một phiên riêng,
4 lượt tuần tự. TTFT đo từ lúc gửi yêu cầu tới sự kiện ``token`` đầu tiên; tổng thời
gian đo tới sự kiện ``done``. Không dùng bộ nghiệm thu ``inputs/conversations.md``.

Cần backend đang chạy tại PHASE4_API_BASE (mặc định http://127.0.0.1:8000).
Chạy tuần tự để tránh nhiều tiến trình reranker cùng lúc:

    PYTHONPATH=backend;. python scripts/phase4_ttft_multiturn.py
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.core.auth import supabase_api_base  # noqa: E402

from evaluation.conversation_bench import load_scenarios  # noqa: E402

BASE = supabase_api_base(os.environ.get("SUPABASE_URL", ""))
ANON = os.environ.get("SUPABASE_ANON_KEY", "").strip()
SERVICE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
API = os.environ.get("PHASE4_API_BASE", "http://127.0.0.1:8000").rstrip("/")
DEV = ROOT / "inputs" / "conversations_dev.md"
RESULTS = ROOT / "evaluation" / "results"


def _admin_headers() -> dict[str, str]:
    return {"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"}


def _create_user(client: httpx.Client) -> tuple[str, str, str]:
    email = f"phase4-ttft-mt-{uuid.uuid4().hex[:12]}@example.com"
    password = f"P4-{uuid.uuid4().hex}"
    response = client.post(
        f"{BASE}/auth/v1/admin/users",
        headers=_admin_headers(),
        json={"email": email, "password": password, "email_confirm": True},
    )
    response.raise_for_status()
    return response.json()["id"], email, password


def _password_grant(client: httpx.Client, email: str, password: str) -> str:
    response = client.post(
        f"{BASE}/auth/v1/token?grant_type=password",
        headers={"apikey": ANON},
        json={"email": email, "password": password},
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _create_session(client: httpx.Client, token: str, title: str) -> str:
    response = client.post(
        f"{API}/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": title},
    )
    response.raise_for_status()
    return response.json()["id"]


def _measure_turn(token: str, session_id: str, question: str) -> dict[str, object]:
    payload = json.dumps({"question": question, "session_id": session_id}, ensure_ascii=False)
    args = [
        "curl",
        "-N",
        "-sS",
        "--max-time",
        "180",
        "-X",
        "POST",
        f"{API}/chat/stream",
        "-H",
        f"Authorization: Bearer {token}",
        "-H",
        "Content-Type: application/json",
        "-d",
        payload,
    ]
    started = time.perf_counter()
    meta_ms: float | None = None
    ttft_ms: float | None = None
    done_ms: float | None = None
    done_data: dict[str, object] = {}
    event = ""
    data_lines: list[str] = []
    errors: list[str] = []

    def flush_event() -> None:
        nonlocal meta_ms, ttft_ms, done_ms, done_data, event, data_lines
        if event == "meta" and meta_ms is None:
            meta_ms = (time.perf_counter() - started) * 1000
        elif event == "token" and ttft_ms is None:
            ttft_ms = (time.perf_counter() - started) * 1000
        elif event == "done" and done_ms is None:
            done_ms = (time.perf_counter() - started) * 1000
            raw = "\n".join(data_lines)
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                done_data = parsed
        elif event == "error":
            errors.append("; ".join(data_lines)[:200] or "event: error")
        event = ""
        data_lines = []

    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    assert proc.stdout is not None
    try:
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                flush_event()
            elif line.startswith("event:"):
                if event:
                    flush_event()
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
    finally:
        flush_event()
        proc.wait(timeout=10)
        stderr = (proc.stderr.read() if proc.stderr is not None else b"").decode(
            "utf-8", errors="replace"
        )
    if done_ms is None:
        done_ms = (time.perf_counter() - started) * 1000
    if proc.returncode not in (0, 28) and not errors:
        errors.append(f"curl exit {proc.returncode}: {stderr.strip()[:160]}")
    return {
        "question": question,
        "meta_ms": None if meta_ms is None else round(meta_ms, 1),
        "ttft_ms": None if ttft_ms is None else round(ttft_ms, 1),
        "server_ttft_ms": done_data.get("ttft_ms"),
        "total_ms": round(done_ms, 1),
        "provider": done_data.get("provider"),
        "model": done_data.get("model"),
        "status": done_data.get("status"),
        "errors": errors,
    }


def _percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percent / 100.0 * len(ordered)) - 1))
    return ordered[index]


def _stats(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "n": len(values),
        "p50": round(_percentile(values, 50), 1),
        "p95": round(_percentile(values, 95), 1),
        "max": round(max(values), 1),
    }


def _summarize(records: list[dict[str, object]]) -> dict[str, object]:
    by_turn: dict[str, object] = {}
    for number in (1, 2, 3, 4):
        turns = [item for item in records if item["turn"] == number and not item["errors"]]
        by_turn[str(number)] = {
            "ttft_ms": _stats([float(item["ttft_ms"]) for item in turns if item["ttft_ms"]]),
            "total_ms": _stats([float(item["total_ms"]) for item in turns if item["total_ms"]]),
        }
    valid = [item for item in records if not item["errors"]]
    return {
        "runs": len(records),
        "valid": len(valid),
        "errors": len(records) - len(valid),
        "ttft_ms": _stats([float(item["ttft_ms"]) for item in valid if item["ttft_ms"]]),
        "total_ms": _stats([float(item["total_ms"]) for item in valid if item["total_ms"]]),
        "meta_ms": _stats([float(item["meta_ms"]) for item in valid if item["meta_ms"]]),
        "by_turn": by_turn,
    }


def _markdown(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    lines = [
        "# Đo TTFT đa lượt trên bộ dev (SSE)",
        "",
        f"- Thời điểm: {payload['timestamp']}",
        f"- Tệp kịch bản: `inputs/conversations_dev.md` (SHA-256 `{payload['dev_sha256']}`)",
        f"- Backend: {API}; chế độ: {'warm (có warmup)' if payload['warmup'] else 'cold'}",
        f"- Mẫu hợp lệ: {summary['valid']}/{summary['runs']}; lỗi: {summary['errors']}",
        "",
        "| Lượt | n | TTFT p50 (ms) | TTFT p95 (ms) | Tổng p50 (ms) | Tổng p95 (ms) |",
        "| :---: | :---: | ---: | ---: | ---: | ---: |",
    ]
    for number in ("1", "2", "3", "4"):
        item = summary["by_turn"][number]
        ttft = item["ttft_ms"] or {}
        total = item["total_ms"] or {}
        lines.append(
            f"| {number} | {ttft.get('n', 0)} | {ttft.get('p50', '—')} | {ttft.get('p95', '—')} "
            f"| {total.get('p50', '—')} | {total.get('p95', '—')} |"
        )
    overall_ttft = summary["ttft_ms"] or {}
    overall_total = summary["total_ms"] or {}
    lines.append(
        f"| **Toàn bộ** | {overall_ttft.get('n', 0)} | {overall_ttft.get('p50', '—')} "
        f"| {overall_ttft.get('p95', '—')} | {overall_total.get('p50', '—')} "
        f"| {overall_total.get('p95', '—')} |"
    )
    lines.extend(
        [
            "",
            "TTFT đo từ lúc gửi yêu cầu tới sự kiện `token` đầu tiên (định nghĩa giữ nguyên). "
            "`server_ttft_ms` trong JSON là số đo phía máy chủ, chỉ dùng tham khảo.",
            "",
        ]
    )
    failed = [item for item in payload["records"] if item["errors"]]
    if failed:
        lines.append("## Lượt lỗi")
        lines.append("")
        for item in failed:
            lines.append(
                f"- {item['code']} lượt {item['turn']}: {'; '.join(item['errors'])} "
                f"(tổng {item['total_ms']} ms)"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="", help="Chỉ chạy một mã, ví dụ DV-01")
    parser.add_argument("--turns", type=int, default=4, help="Số lượt mỗi kịch bản (mặc định 4)")
    parser.add_argument("--warmup", action="store_true", help="Chạy một lượt warmup trước khi đo")
    parser.add_argument("--output-prefix", default="phase4_ttft_multiturn")
    args = parser.parse_args()

    if not (BASE and ANON and SERVICE):
        print("Thiếu cấu hình Supabase trong .env")
        return 2
    try:
        httpx.get(f"{API}/health", timeout=5.0).raise_for_status()
    except httpx.HTTPError as exc:
        print(f"Backend chưa sẵn sàng tại {API}: {type(exc).__name__}")
        return 2

    import hashlib

    dev_bytes = DEV.read_bytes()
    dev_sha = hashlib.sha256(dev_bytes).hexdigest()
    scenarios = load_scenarios(DEV)
    if args.scenario:
        scenarios = [scenario for scenario in scenarios if scenario.code == args.scenario]
        if not scenarios:
            print(f"Không có kịch bản {args.scenario}")
            return 2

    records: list[dict[str, object]] = []
    warmup_result: dict[str, object] | None = None
    user_id = ""
    with httpx.Client(timeout=30.0) as client:
        try:
            user_id, email, password = _create_user(client)
            token = _password_grant(client, email, password)
            if args.warmup:
                session_id = _create_session(client, token, "Warmup")
                warmup_result = _measure_turn(
                    token, session_id, "Amazon S3 là gì? Trả lời ngắn gọn."
                )
                print(
                    f"warmup ttft={warmup_result['ttft_ms']} ms "
                    f"total={warmup_result['total_ms']} ms",
                    flush=True,
                )
            for scenario in scenarios:
                session_id = _create_session(client, token, f"{scenario.code} — TTFT")
                for turn in scenario.turns[: args.turns]:
                    result = _measure_turn(token, session_id, turn.question)
                    record = {
                        "code": scenario.code,
                        "kind": scenario.kind,
                        "turn": turn.number,
                        **result,
                    }
                    records.append(record)
                    state = "OK" if not result["errors"] else "LỖI"
                    print(
                        f"{scenario.code} lượt {turn.number}: {state} "
                        f"meta={result['meta_ms']} ttft={result['ttft_ms']} "
                        f"server_ttft={result['server_ttft_ms']} total={result['total_ms']} "
                        f"provider={result['provider']}",
                        flush=True,
                    )
            client.delete(f"{API}/sessions", headers={"Authorization": f"Bearer {token}"})
        finally:
            if user_id:
                client.delete(f"{BASE}/auth/v1/admin/users/{user_id}", headers=_admin_headers())

    summary = _summarize(records)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "api_base": API,
        "warmup": args.warmup,
        "warmup_result": warmup_result,
        "dev_sha256": dev_sha,
        "records": records,
        "summary": summary,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS / f"{args.output_prefix}_{timestamp}.json"
    md_path = RESULTS / f"{args.output_prefix}_{timestamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")

    overall_ttft = summary["ttft_ms"] or {}
    overall_total = summary["total_ms"] or {}
    print(f"\nMẫu hợp lệ: {summary['valid']}/{summary['runs']}; lỗi: {summary['errors']}")
    print(f"TTFT p50 = {overall_ttft.get('p50')} ms; p95 = {overall_ttft.get('p95')} ms")
    print(f"Tổng p50 = {overall_total.get('p50')} ms; p95 = {overall_total.get('p95')} ms")
    print(f"Đã lưu {json_path.name} và {md_path.name}")
    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
