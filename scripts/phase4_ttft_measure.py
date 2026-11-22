"""Đo TTFT và tổng thời gian của POST /chat/stream bằng curl -N.

Mỗi mẫu dùng một phiên mới và một câu hỏi khác nhau để tránh bộ nhớ đệm truy hồi.
Cần backend đang chạy tại PHASE4_API_BASE (mặc định http://127.0.0.1:8000).

Chạy:
    PYTHONPATH=backend python scripts/phase4_ttft_measure.py
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "backend"))

from app.core.auth import supabase_api_base  # noqa: E402

BASE = supabase_api_base(os.environ.get("SUPABASE_URL", ""))
ANON = os.environ.get("SUPABASE_ANON_KEY", "").strip()
SERVICE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
API = os.environ.get("PHASE4_API_BASE", "http://127.0.0.1:8000").rstrip("/")

QUESTIONS = [
    "Amazon S3 là gì?",
    "So với Amazon EBS, Amazon S3 khác ở điểm nào?",
    "Khi nào nên dùng Amazon S3 và khi nào nên dùng Amazon EBS?",
    "Amazon EBS có tự động nhân bản dữ liệu qua nhiều Availability Zone không?",
    "RDS sao lưu tự động giữ bao lâu?",
    "RDS có thể phục hồi theo thời điểm về một thời điểm trong khoảng lưu giữ không?",
    "Khôi phục RDS tạo DB instance mới hay ghi đè instance hiện có?",
    "Snapshot thủ công khác sao lưu tự động của RDS ở điểm nào?",
    "IAM role là gì?",
    "Trust policy của IAM role dùng để làm gì?",
    "Thông tin xác thực tạm thời của IAM role sống được bao lâu?",
    "Có thu hồi ngay được thông tin xác thực tạm thời không?",
    "Multi-AZ và Read Replica khác nhau thế nào?",
    "Cái nào giúp tăng khả năng đọc trong RDS?",
    "Khi instance chính lỗi thì Multi-AZ hay Read Replica tự chuyển?",
    "Security group và network ACL khác nhau ở điểm nào?",
    "Cái nào có trạng thái trong security group và network ACL?",
    "Vì sao mở inbound 443 trên NACL vẫn không kết nối được?",
    "S3 Standard-IA khác S3 Standard ở điểm nào?",
    "Làm sao giảm chi phí lưu trữ log cũ trên S3?",
]


def _admin_headers() -> dict[str, str]:
    return {"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"}


def _create_user(client: httpx.Client) -> tuple[str, str, str]:
    email = f"phase4-ttft-{uuid.uuid4().hex[:12]}@example.com"
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


def _measure(token: str, session_id: str, question: str) -> dict[str, object]:
    payload = json.dumps({"question": question, "session_id": session_id}, ensure_ascii=False)
    args = [
        "curl",
        "-N",
        "-sS",
        "--max-time",
        "120",
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
    event = ""
    errors: list[str] = []
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    assert proc.stdout is not None
    try:
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            now_ms = (time.perf_counter() - started) * 1000
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
                if event == "meta" and meta_ms is None:
                    meta_ms = now_ms
                elif event == "token" and ttft_ms is None:
                    ttft_ms = now_ms
                elif event == "done" and done_ms is None:
                    done_ms = now_ms
                elif event == "error":
                    errors.append("event: error")
            elif line.startswith("data:") and event == "error":
                errors.append(line[5:].strip()[:200])
    finally:
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
        "total_ms": round(done_ms, 1),
        "errors": errors,
    }


def _percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percent / 100.0 * len(ordered)) - 1))
    return ordered[index]


def main() -> int:
    if not (BASE and ANON and SERVICE):
        print("Thiếu cấu hình Supabase trong .env")
        return 2
    try:
        health = httpx.get(f"{API}/health", timeout=5.0)
        health.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"Backend chưa sẵn sàng tại {API}: {type(exc).__name__}")
        return 2

    results: list[dict[str, object]] = []
    user_id = ""
    with httpx.Client(timeout=30.0) as client:
        try:
            user_id, email, password = _create_user(client)
            token = _password_grant(client, email, password)
            for index, question in enumerate(QUESTIONS, start=1):
                session_id = _create_session(client, token, f"TTFT {index:02d}")
                result = _measure(token, session_id, question)
                results.append(result)
                print(
                    f"{index:02d} meta={result['meta_ms']} ms "
                    f"ttft={result['ttft_ms']} ms total={result['total_ms']} ms "
                    f"{('LỖI: ' + '; '.join(result['errors'])) if result['errors'] else ''}"
                )
            client.delete(f"{API}/sessions", headers={"Authorization": f"Bearer {token}"})
        finally:
            if user_id:
                client.delete(f"{BASE}/auth/v1/admin/users/{user_id}", headers=_admin_headers())

    ttfts = [float(item["ttft_ms"]) for item in results if item["ttft_ms"] is not None]
    totals = [float(item["total_ms"]) for item in results if not item["errors"]]
    errors = sum(1 for item in results if item["errors"])
    if not ttfts:
        print("Không có mẫu TTFT hợp lệ.")
        return 1
    p50 = _percentile(ttfts, 50)
    p95 = _percentile(ttfts, 95)
    total_p95 = _percentile(totals, 95) if totals else float("nan")
    print(f"\nMẫu hợp lệ: {len(ttfts)}/{len(results)}; lỗi: {errors}")
    print(f"TTFT p50 = {p50:.1f} ms; p95 = {p95:.1f} ms (mục tiêu p95 ≤ 2000 ms)")
    print(f"Tổng thời gian p95 = {total_p95:.1f} ms (mục tiêu p95 ≤ 10000 ms)")
    return 0 if p95 <= 2000.0 and errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
