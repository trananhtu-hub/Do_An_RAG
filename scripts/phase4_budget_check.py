"""Chạy 12 lượt thật trong một phiên và kiểm tra ngân sách ngữ cảnh hội thoại.

Đọc `context.max_conversation_tokens` từ config/conversation.yaml, gọi /chat 12 lượt,
rồi lấy `conversation_tokens` trong metadata từng tin nhắn trợ lý.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import httpx
import yaml
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
    "Amazon S3 Standard dùng cho loại dữ liệu nào?",
    "Nó có độ bền ra sao?",
    "Còn Standard-IA thì sao?",
    "Cái nào có thời gian lưu tối thiểu 30 ngày?",
    "Glacier Instant Retrieval dùng khi nào?",
    "Còn Glacier Flexible Retrieval?",
    "Deep Archive để làm gì?",
    "Muốn tự động chuyển lớp thì dùng gì?",
    "Lifecycle có chuyển ngay được không?",
    "Có mất phí xóa sớm không?",
    "Storage Lens dùng để làm gì?",
    "Tóm lại nên chọn lớp nào cho log cũ?",
]


def _admin_headers() -> dict[str, str]:
    return {"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"}


def main() -> int:
    if not (BASE and ANON and SERVICE):
        print("Thiếu cấu hình Supabase trong .env")
        return 2
    config = yaml.safe_load((ROOT / "config" / "conversation.yaml").read_text("utf-8"))
    budget = int(config["context"]["max_conversation_tokens"])
    user_id = ""
    with httpx.Client(timeout=180.0) as client:
        try:
            email = f"phase4-budget-{uuid.uuid4().hex[:12]}@example.com"
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
            headers = {"Authorization": f"Bearer {token}"}
            session = client.post(f"{API}/sessions", headers=headers, json={})
            session.raise_for_status()
            session_id = session.json()["id"]
            for index, question in enumerate(QUESTIONS, start=1):
                turn = client.post(
                    f"{API}/chat",
                    headers=headers,
                    json={"question": question, "session_id": session_id},
                )
                turn.raise_for_status()
                body = turn.json()
                print(
                    f"{index:02d} rewritten={body['rewritten_query'][:70]!r} "
                    f"latency={body['latency_ms']:.0f} ms"
                )
            messages = client.get(f"{API}/sessions/{session_id}/messages", headers=headers).json()[
                "items"
            ]
            assistant = [item for item in messages if item["role"] == "assistant"]
            print("\nLượt | conversation_tokens | summary_used | conversation_messages")
            values: list[int] = []
            for index, item in enumerate(assistant, start=1):
                metadata = item.get("metadata") or {}
                value = int(metadata.get("conversation_tokens") or 0)
                values.append(value)
                print(
                    f"{index:02d}   | {value:>19} | "
                    f"{metadata.get('summary_used')} | {metadata.get('conversation_messages')}"
                )
            maximum = max(values) if values else 0
            print(f"\nNgân sách: {budget} token; lớn nhất: {maximum} token")
            print(
                "KẾT LUẬN: ĐẠT — ngữ cảnh sau 12 lượt nằm trong ngân sách."
                if maximum <= budget
                else "KẾT LUẬN: KHÔNG ĐẠT — vượt ngân sách."
            )
            client.delete(f"{API}/sessions/{session_id}", headers=headers)
            return 0 if maximum <= budget else 1
        finally:
            if user_id:
                client.delete(f"{BASE}/auth/v1/admin/users/{user_id}", headers=_admin_headers())


if __name__ == "__main__":
    raise SystemExit(main())
