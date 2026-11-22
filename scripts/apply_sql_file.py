"""Chạy một tệp SQL trên Supabase PostgreSQL bằng psycopg.

Dùng giao thức simple query của libpq để tệp có thể chứa nhiều câu lệnh,
bao gồm khối DO $$ ... $$. Không in chuỗi kết nối hay bất kỳ khóa bí mật nào.

Ví dụ: python scripts/apply_sql_file.py supabase/migrations/20261122000000_conversation_phase4.sql
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv


def main() -> int:
    if len(sys.argv) != 2:
        print("Cách dùng: python scripts/apply_sql_file.py <đường-dẫn-tệp.sql>")
        return 2
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Không tìm thấy tệp: {path}")
        return 2

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Thiếu DATABASE_URL trong .env")
        return 2

    sql = path.read_text(encoding="utf-8")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.pgconn.exec_(sql.encode("utf-8"))
    print(f"Đã chạy {path.name} thành công.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
