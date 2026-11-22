"""Kiểm tra cách ly dữ liệu phiên giữa hai tài khoản Supabase thật.

Quy trình:
1. Tạo hai người dùng tạm bằng Admin API và lấy JWT qua password grant.
2. Gọi PostgREST bằng JWT người dùng để chứng minh RLS chặn đọc/ghi/xóa chéo.
3. Gọi FastAPI (TestClient) bằng JWT thật để chứng minh API trả 404 với phiên
   của người khác và lệnh xóa toàn bộ chỉ ảnh hưởng dữ liệu của chính mình.
4. Xóa người dùng tạm; khóa ngoại on delete cascade dọn phiên và tin nhắn.

Không in token, khóa hay chuỗi kết nối. Chạy:
    PYTHONPATH=backend python scripts/phase4_isolation_check.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "backend"))

import os  # noqa: E402

from app.core.auth import reset_verifier, supabase_api_base  # noqa: E402

BASE = supabase_api_base(os.environ["SUPABASE_URL"])
ANON = os.environ["SUPABASE_ANON_KEY"].strip()
SERVICE = os.environ["SUPABASE_SERVICE_ROLE_KEY"].strip()

RESULTS: list[tuple[str, str, str, bool]] = []


def record(name: str, expected: str, actual: str, passed: bool) -> None:
    RESULTS.append((name, expected, actual, passed))
    print(f"{'OK ' if passed else 'FAIL'} {name}: kỳ vọng {expected}, thực tế {actual}")


def admin_headers() -> dict[str, str]:
    return {"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"}


def user_headers(token: str) -> dict[str, str]:
    return {"apikey": ANON, "Authorization": f"Bearer {token}"}


def create_user(client: httpx.Client, suffix: str) -> tuple[str, str, str]:
    email = f"phase4-check-{uuid.uuid4().hex[:12]}-{suffix}@example.com"
    password = f"P4-{uuid.uuid4().hex}"
    response = client.post(
        f"{BASE}/auth/v1/admin/users",
        headers=admin_headers(),
        json={"email": email, "password": password, "email_confirm": True},
    )
    response.raise_for_status()
    return response.json()["id"], email, password


def password_grant(client: httpx.Client, email: str, password: str) -> str:
    response = client.post(
        f"{BASE}/auth/v1/token?grant_type=password",
        headers={"apikey": ANON},
        json={"email": email, "password": password},
    )
    response.raise_for_status()
    return response.json()["access_token"]


def delete_user(client: httpx.Client, user_id: str) -> None:
    client.delete(f"{BASE}/auth/v1/admin/users/{user_id}", headers=admin_headers())


def rls_checks(
    client: httpx.Client,
    token_a: str,
    token_b: str,
    id_a: str,
    id_b: str,
) -> str:
    rest = f"{BASE}/rest/v1"
    prefer = {"Prefer": "return=representation"}

    created = client.post(
        f"{rest}/sessions",
        headers={**user_headers(token_a), **prefer},
        json={"user_id": id_a, "title": "Phiên RLS của A"},
    )
    record("A tạo phiên qua PostgREST", "201", str(created.status_code), created.status_code == 201)
    session_id = created.json()[0]["id"]

    seen_by_a = client.get(
        f"{rest}/sessions", headers=user_headers(token_a), params={"id": f"eq.{session_id}"}
    )
    record(
        "A đọc phiên của mình",
        "1 dòng",
        f"{len(seen_by_a.json())} dòng",
        seen_by_a.status_code == 200 and len(seen_by_a.json()) == 1,
    )

    seen_by_b = client.get(
        f"{rest}/sessions", headers=user_headers(token_b), params={"id": f"eq.{session_id}"}
    )
    record(
        "B đọc phiên của A (RLS lọc)",
        "0 dòng",
        f"{len(seen_by_b.json())} dòng",
        seen_by_b.status_code == 200 and seen_by_b.json() == [],
    )

    message_by_b = client.post(
        f"{rest}/messages",
        headers=user_headers(token_b),
        json={"session_id": session_id, "role": "user", "content": "xâm nhập"},
    )
    record(
        "B ghi tin nhắn vào phiên của A",
        "403",
        str(message_by_b.status_code),
        message_by_b.status_code == 403,
    )

    update_by_b = client.patch(
        f"{rest}/sessions",
        headers={**user_headers(token_b), **prefer},
        params={"id": f"eq.{session_id}"},
        json={"title": "B chiếm"},
    )
    record(
        "B sửa phiên của A",
        "0 dòng",
        f"{len(update_by_b.json())} dòng",
        update_by_b.status_code == 200 and update_by_b.json() == [],
    )

    delete_by_b = client.delete(
        f"{rest}/sessions",
        headers={**user_headers(token_b), **prefer},
        params={"id": f"eq.{session_id}"},
    )
    record(
        "B xóa phiên của A",
        "0 dòng",
        f"{len(delete_by_b.json())} dòng",
        delete_by_b.status_code == 200 and delete_by_b.json() == [],
    )

    still_there = client.get(
        f"{rest}/sessions", headers=user_headers(token_a), params={"id": f"eq.{session_id}"}
    )
    record(
        "Phiên của A còn nguyên sau khi B xóa",
        "1 dòng",
        f"{len(still_there.json())} dòng",
        still_there.status_code == 200 and len(still_there.json()) == 1,
    )

    spoof = client.post(
        f"{rest}/sessions",
        headers={**user_headers(token_a), **prefer},
        json={"user_id": id_b, "title": "Mạo danh"},
    )
    record("A tạo phiên gán cho B", "403", str(spoof.status_code), spoof.status_code == 403)

    own_b = client.post(
        f"{rest}/sessions",
        headers={**user_headers(token_b), **prefer},
        json={"user_id": id_b, "title": "Phiên của B"},
    )
    record("B tạo phiên của chính mình", "201", str(own_b.status_code), own_b.status_code == 201)
    return session_id


def api_checks(token_a: str, token_b: str) -> None:
    from app.api.deps import set_session_repository
    from app.main import create_app
    from app.services.chat import set_chat_service
    from fastapi.testclient import TestClient

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    with TestClient(create_app()) as client:
        created = client.post("/sessions", json={"title": "Phiên API của A"}, headers=headers_a)
        record("A tạo phiên qua API", "201", str(created.status_code), created.status_code == 201)
        session_id = created.json()["id"]

        listed_b = client.get("/sessions", headers=headers_b)
        b_items = listed_b.json()["items"]
        b_before = len(b_items)
        leaked = any(item["id"] == session_id for item in b_items)
        record(
            "B không thấy phiên của A trong danh sách",
            "không chứa id phiên A",
            "chứa id phiên A" if leaked else "không chứa",
            listed_b.status_code == 200 and not leaked,
        )
        a_before = client.get("/sessions", headers=headers_a).json()["total"]

        for method, path, expected in (
            ("get", f"/sessions/{session_id}/messages", 404),
            ("patch", f"/sessions/{session_id}", 404),
            ("delete", f"/sessions/{session_id}", 404),
        ):
            kwargs: dict[str, Any] = {"headers": headers_b}
            if method == "patch":
                kwargs["json"] = {"title": "B chiếm"}
            response = getattr(client, method)(path, **kwargs)
            record(
                f"B {method.upper()} {path}",
                str(expected),
                str(response.status_code),
                response.status_code == expected,
            )

        chat_b = client.post(
            "/chat",
            headers=headers_b,
            json={"question": "S3 Standard là gì?", "session_id": session_id},
        )
        record(
            "B hỏi tiếp vào phiên của A",
            "404",
            str(chat_b.status_code),
            chat_b.status_code == 404,
        )

        anonymous = client.get("/sessions")
        record(
            "Không có token thì bị từ chối",
            "401",
            str(anonymous.status_code),
            anonymous.status_code == 401,
        )

        mine = client.get(f"/sessions/{session_id}/messages", headers=headers_a)
        record(
            "A đọc tin nhắn phiên của mình", "200", str(mine.status_code), mine.status_code == 200
        )

        created_b = client.post("/sessions", json={"title": "Phiên API của B"}, headers=headers_b)
        record(
            "B tạo phiên qua API", "201", str(created_b.status_code), created_b.status_code == 201
        )
        b_before = client.get("/sessions", headers=headers_b).json()["total"]

        wipe_a = client.delete("/sessions", headers=headers_a)
        remaining_a = client.get("/sessions", headers=headers_a).json()["total"]
        remaining_b = client.get("/sessions", headers=headers_b).json()["total"]
        record(
            "A xóa toàn bộ phiên của A",
            f"{a_before} phiên bị xóa, B còn nguyên {b_before}",
            (
                f"{wipe_a.json().get('deleted')} phiên bị xóa, "
                f"A còn {remaining_a}, B còn {remaining_b}"
            ),
            wipe_a.status_code == 200
            and wipe_a.json().get("deleted") == a_before
            and remaining_a == 0
            and remaining_b == b_before,
        )

    set_chat_service(None)
    set_session_repository(None)
    reset_verifier()


def main() -> int:
    if not (BASE and ANON and SERVICE):
        print("Thiếu cấu hình Supabase trong .env")
        return 2

    users: list[str] = []
    with httpx.Client(timeout=20.0) as client:
        try:
            id_a, email_a, password_a = create_user(client, "a")
            users.append(id_a)
            id_b, email_b, password_b = create_user(client, "b")
            users.append(id_b)
            token_a = password_grant(client, email_a, password_a)
            token_b = password_grant(client, email_b, password_b)

            print("\n== RLS qua PostgREST ==")
            rls_checks(client, token_a, token_b, id_a, id_b)

            print("\n== Cách ly qua FastAPI ==")
            api_checks(token_a, token_b)
        finally:
            for user_id in users:
                delete_user(client, user_id)
            print(f"\nĐã xóa {len(users)} người dùng tạm.")

    passed = sum(1 for *_, ok in RESULTS if ok)
    print(f"\nKết quả: {passed}/{len(RESULTS)} kiểm tra đạt.")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
