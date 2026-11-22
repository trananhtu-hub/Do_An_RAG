"""Kiểm tra ngắt kết nối giữa luồng SSE.

Kịch bản: bắt đầu /chat/stream, đọc tới token đầu tiên rồi hủy tiến trình curl
(mô phỏng đóng tab). Sau đó đọc lại tin nhắn của phiên để xác nhận câu trả lời
dở được lưu với trạng thái `interrupted`, và quét log máy chủ tìm lỗi 500.

Cần backend đang chạy và biến PHASE4_SERVER_LOG trỏ tới tệp log của uvicorn.
"""

from __future__ import annotations

import json
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
SERVER_LOG = os.environ.get("PHASE4_SERVER_LOG", "").strip()

QUESTION = "Multi-AZ và Read Replica của RDS khác nhau ở điểm nào?"


def _admin_headers() -> dict[str, str]:
    return {"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"}


def _setup(client: httpx.Client) -> tuple[str, str, str]:
    email = f"phase4-disc-{uuid.uuid4().hex[:12]}@example.com"
    password = f"P4-{uuid.uuid4().hex}"
    response = client.post(
        f"{BASE}/auth/v1/admin/users",
        headers=_admin_headers(),
        json={"email": email, "password": password, "email_confirm": True},
    )
    response.raise_for_status()
    user_id = response.json()["id"]
    grant = client.post(
        f"{BASE}/auth/v1/token?grant_type=password",
        headers={"apikey": ANON},
        json={"email": email, "password": password},
    )
    grant.raise_for_status()
    token = grant.json()["access_token"]
    session = client.post(
        f"{API}/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Kiểm tra ngắt kết nối"},
    )
    session.raise_for_status()
    return user_id, token, session.json()["id"]


def _first_token_then_hang_up(token: str, session_id: str) -> bool:
    payload = json.dumps({"question": QUESTION, "session_id": session_id}, ensure_ascii=False)
    proc = subprocess.Popen(
        [
            "curl",
            "-N",
            "-sS",
            "-X",
            "POST",
            f"{API}/chat/stream",
            "-H",
            f"Authorization: Bearer {token}",
            "-H",
            "Content-Type: application/json",
            "-d",
            payload,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )
    saw_token = False
    assert proc.stdout is not None
    try:
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", errors="replace").strip()
            if line.startswith("event: token"):
                saw_token = True
                break
    finally:
        proc.kill()
        proc.wait(timeout=10)
    return saw_token


def _log_has_500(path: str) -> tuple[bool, list[str]]:
    if not path or not Path(path).exists():
        return False, []
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    markers = [
        line.strip()
        for line in text.splitlines()
        if " 500 " in line or "Traceback (most recent call last)" in line
    ]
    return bool(markers), markers[-5:]


def main() -> int:
    if not (BASE and ANON and SERVICE):
        print("Thiếu cấu hình Supabase trong .env")
        return 2
    user_id = ""
    with httpx.Client(timeout=30.0) as client:
        try:
            user_id, token, session_id = _setup(client)
            saw_token = _first_token_then_hang_up(token, session_id)
            print(f"Đã nhận token đầu tiên trước khi ngắt: {saw_token}")
            deadline = time.monotonic() + 15.0
            assistant: dict | None = None
            while time.monotonic() < deadline:
                response = client.get(
                    f"{API}/sessions/{session_id}/messages",
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
                messages = response.json()["items"]
                assistant = next(
                    (item for item in reversed(messages) if item["role"] == "assistant"), None
                )
                status = (assistant or {}).get("metadata", {}).get("stream_status")
                if status == "interrupted":
                    break
                time.sleep(0.5)
            assert assistant is not None, "Không tìm thấy tin nhắn trợ lý"
            metadata = assistant.get("metadata") or {}
            content = assistant.get("content") or ""
            print(f"stream_status = {metadata.get('stream_status')}")
            print(f"độ dài nội dung lưu = {len(content)} ký tự")
            print(f"nội dung lưu = {content[:120]!r}")
            log_error, markers = _log_has_500(SERVER_LOG)
            print(f"log máy chủ có lỗi 500/Traceback: {log_error}")
            for marker in markers:
                print(f"  {marker}")
            client.delete(
                f"{API}/sessions/{session_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            interrupted = metadata.get("stream_status") == "interrupted"
            print(
                "\nKẾT LUẬN: "
                + (
                    "ĐẠT — máy chủ dừng sinh, lưu câu trả lời dở, không có 500."
                    if saw_token and interrupted and not log_error
                    else "KHÔNG ĐẠT"
                )
            )
            return 0 if saw_token and interrupted and not log_error else 1
        finally:
            if user_id:
                client.delete(f"{BASE}/auth/v1/admin/users/{user_id}", headers=_admin_headers())


if __name__ == "__main__":
    raise SystemExit(main())
