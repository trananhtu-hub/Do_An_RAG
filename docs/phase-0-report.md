# BÁO CÁO GIAI ĐOẠN 0

Trạng thái: HOÀN THÀNH

Ngày hoàn thành: 2026-11-18

## 1. Việc đã làm

1. **Cấu trúc monorepo:** tạo đủ các thư mục `backend/`, `frontend/`, `ingestion/`, `evaluation/`, `prompts/`, `supabase/migrations/`, `data/raw/`, `data/processed/`, `data/external_test/`, `docs/`, `scripts/`, `tests/`, `.claude/skills/` (các thư mục chưa có mã nguồn giữ `.gitkeep`).
2. **CLAUDE.md:** 10 mục đúng yêu cầu, gồm bảng 13 nhược điểm W1–W13 kèm giai đoạn xử lý; mục kiến trúc ghi rõ parser PDF là **pdfplumber** (mã nguồn mở, chạy cục bộ); 6 biến môi trường; 7 quy tắc bất biến.
3. **6 skills:** `ingestion`, `retrieval-tuning`, `rag-evaluation`, `aws-saa-blueprint`, `prompting-rag`, `thesis-report`; mỗi thư mục có `SKILL.md` gồm mô tả, khi nào dùng, các bước, lệnh, tiêu chí nghiệm thu, khớp kiến trúc trong CLAUDE.md.
4. **Backend FastAPI:** `GET /health` trả `{"status":"ok"}`; cấu hình pydantic-settings đọc `.env` ở thư mục gốc; logging JSON (timestamp UTC, level, logger, message); cấu trúc `app/api`, `app/core`, `app/services`, `app/models`; pytest (3 test) + ruff + black; `pyproject.toml`, `Dockerfile`.
5. **Frontend Next.js + TypeScript:** trang chủ tiếng Việt có dấu hiển thị tên dự án và trạng thái kết nối backend (đang kiểm tra / đã kết nối / không kết nối được, có nút "Kiểm tra lại"); ESLint 9 + Prettier; `Dockerfile`.
6. **Migration Supabase:** bật `vector` và `pg_trgm`; 6 bảng `documents`, `chunks` (embedding `vector(768)`, `content`, `metadata jsonb`, `parent_id`), `questions`, `sessions`, `messages`, `query_logs`; chỉ mục HNSW cosine cho embedding; cột `search_vector` sinh tự động + chỉ mục GIN; chỉ mục trigram; **bật RLS toàn bộ 6 bảng, không policy (mặc định đóng)**.
7. **Cấu hình hạ tầng:** `.env.example` đúng 6 biến (không có biến dịch vụ parse PDF ngoài); `.gitignore` có `.env` và `!.env.example`; `Makefile` (`install`, `dev`, `test`, `lint`, `ingest`, `eval` — hai lệnh sau ghi chú "chưa triển khai"); `docker-compose.yml` cho backend + frontend; `scripts/dev.py` chạy song song hai server.
8. **Chất lượng mã:** `.pre-commit-config.yaml` (ruff `--fix`, black, eslint frontend); GitHub Actions CI chạy lint, test backend, build frontend.
9. **README:** hướng dẫn chạy trong đúng 3 lệnh (`cp .env.example .env`, `make install`, `make dev`).
10. **Bảo mật:** `.env` không bị Git theo dõi (đã kiểm chứng); không có khóa/mật khẩu/chuỗi kết nối trong bất kỳ tệp nào được commit hay trong báo cáo này.

## 2. Kết quả kiểm thử

| Hạng mục | Lệnh | Kỳ vọng | Thực tế | Đạt |
| :--- | :--- | :--- | :--- | :---: |
| Lint backend + frontend | `make lint` | ruff, black, eslint đều qua | ruff: "All checks passed!", black: 11 files unchanged, eslint exit 0 | Đạt |
| Kiểm thử backend | `make test` | pytest xanh | `3 passed, 1 warning in 0.32s` | Đạt |
| Endpoint health | `curl http://localhost:8000/health` | 200 + `{"status":"ok"}` | `HTTP/1.1 200 OK`, body `{"status":"ok"}` | Đạt |
| Logging JSON | log khởi động backend | một dòng JSON hợp lệ | `{"timestamp": "2026-11-18T10:00:28.491725+00:00", "level": "INFO", "logger": "app.main", "message": "Khởi tạo ứng dụng FastAPI"}` | Đạt |
| Build frontend | `cd frontend && npm run build` | build thành công | Next.js 16.4.6 (Turbopack), `✓ Compiled successfully in 233ms`, route `/` static, exit 0 | Đạt |
| `.env` không bị theo dõi | `git status`, `git check-ignore -v .env`, `git ls-files .env` | `.env` không xuất hiện, bị ignore | `git status`: `.env` không có trong untracked; check-ignore: `.gitignore:1:.env  .env`; `git ls-files .env`: rỗng | Đạt |
| Skills | đếm thư mục và `SKILL.md` trong `.claude/skills/` | đúng 6/6 | 6 thư mục, 6 tệp `SKILL.md` | Đạt |
| `.env.example` | đọc tệp | đúng 6 biến | `GEMINI_API_KEY`, `GEMINI_MODEL_DEFAULT=gemini-3.8-flash`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL` | Đạt |
| Không có LlamaParse | grep "llama" trong `requirements*.txt`, `.env.example`, `package.json`, `CLAUDE.md` | không có phụ thuộc/biến | Không có kết quả trong phụ thuộc và cấu hình; chỉ xuất hiện trong CLAUDE.md ở câu quy định **cấm** dùng LlamaParse/llama-cloud | Đạt |
| Chạy song song hai server | `make dev` | backend 8000 + frontend 3000 cùng chạy | `/health` trả `{"status":"ok"}`, frontend trả HTTP 200 | Đạt |

Kết quả thô tiêu biểu:

```text
===== make lint =====
".venv/Scripts/python.exe" -m ruff check backend
All checks passed!
".venv/Scripts/python.exe" -m black --check backend
All done! ✨ 🍰 ✨
11 files would be left unchanged.
npm --prefix frontend run lint
> frontend@0.1.0 lint
> eslint
exit=0

===== make test =====
".venv/Scripts/python.exe" -m pytest backend -q
...                                                                      [100%]
3 passed, 1 warning in 0.32s
exit=0

===== curl -i http://localhost:8000/health =====
HTTP/1.1 200 OK
date: Wed, 18 Nov 2026 10:00:31 GMT
server: uvicorn
content-length: 15
content-type: application/json

{"status":"ok"}
```

```text
===== git status =====
On branch master
Changes not staged for commit:
	modified:   .gitignore
	modified:   README.md

Untracked files:
	.claude/
	.env.example
	.github/
	.pre-commit-config.yaml
	CLAUDE.md
	Makefile
	backend/
	data/
	docker-compose.yml
	evaluation/
	frontend/
	ingestion/
	prompts/
	scripts/
	supabase/
	tests/
```

`.env` không xuất hiện trong `git status` vì đã bị `.gitignore` chặn (xác nhận bằng `git check-ignore -v .env` → `.gitignore:1:.env	.env`).

## 3. Tệp và cấu trúc đã tạo

```text
.
├─ .claude/skills/
│  ├─ ingestion/SKILL.md
│  ├─ retrieval-tuning/SKILL.md
│  ├─ rag-evaluation/SKILL.md
│  ├─ aws-saa-blueprint/SKILL.md
│  ├─ prompting-rag/SKILL.md
│  └─ thesis-report/SKILL.md
├─ .github/workflows/ci.yml
├─ .pre-commit-config.yaml
├─ .env.example                    (6 biến, không chứa giá trị thật)
├─ .gitignore                      (có .env, !.env.example)
├─ CLAUDE.md
├─ Makefile
├─ README.md
├─ docker-compose.yml
├─ backend/
│  ├─ app/
│  │  ├─ api/routes.py
│  │  ├─ core/config.py, core/logging.py
│  │  ├─ models/schemas.py
│  │  ├─ services/__init__.py
│  │  └─ main.py
│  ├─ tests/test_health.py
│  ├─ pyproject.toml
│  ├─ requirements.txt, requirements-dev.txt
│  └─ Dockerfile
├─ frontend/
│  ├─ app/layout.tsx, app/page.tsx, app/page.module.css, app/globals.css
│  ├─ .prettierrc.json, .prettierignore
│  ├─ eslint.config.mjs, tsconfig.json, next.config.ts
│  └─ Dockerfile, .dockerignore, package.json
├─ supabase/migrations/20261118000000_init_schema.sql
├─ scripts/dev.py
├─ ingestion/, evaluation/, prompts/, tests/   (.gitkeep)
├─ data/raw/, data/processed/, data/external_test/  (.gitkeep, data/raw bị ignore)
└─ docs/phase-0-report.md
```

## 4. Vấn đề và rủi ro

1. **GNU Make trên đường dẫn có dấu tiếng Việt (đã xử lý, cần biết):** GNU Make 4.4.1 (ezwinports, cài bằng winget) dùng API ANSI với codepage cp1252 nên không mở được makefile mặc định trong thư mục `D:\Đồ Án RAG`; lệnh trần `make lint` báo `make: *** No rule to make target 'lint'. Stop.`. Chạy `make -f Makefile lint` (hoặc `make --file=Makefile ...`) hoạt động đúng và đã được dùng cho toàn bộ kiểm thử ở mục 2. CI trên Linux và docker-compose không bị ảnh hưởng. Cách khắc phục lâu dài (chọn một): giữ cách gọi `-f Makefile`; cài MSYS2 make; hoặc chuyển repo sang đường dẫn ASCII.
2. **`make` chưa có trên PATH:** winget cài vào `%LOCALAPPDATA%\Microsoft\WinGet\Packages\...\bin` nhưng shell hiện tại không nhận PATH mới; cần mở terminal mới hoặc thêm thư mục đó vào PATH.
3. **Mã hóa console khi cài đặt:** pip/rich từng lỗi `UnicodeEncodeError: 'charmap' codec can't encode characters` với đường dẫn tiếng Việt trên cp1252. Makefile đã đặt `PYTHONUTF8=1` và `PYTHONIOENCODING=utf-8` cho mọi lệnh Python nên `make install` chạy được.
4. **Cảnh báo npm audit:** 14 lỗ hổng mức high trong cây phụ thuộc Next.js, chưa xử lý ở giai đoạn 0; cần theo dõi và nâng cấp khi có bản vá.
5. **DeprecationWarning của Starlette TestClient** (alias `anyio.abc.BlockingPortal`): chỉ là cảnh báo, 3/3 test vẫn đạt.
6. **Migration chưa được áp lên Supabase thật:** SQL đã viết đầy đủ nhưng giai đoạn 0 chưa kết nối cơ sở dữ liệu; việc chạy migration và kiểm chứng RLS để sang giai đoạn 1.
7. **Phiên bản môi trường:** venv dùng Python 3.13.3 (yêu cầu 3.11+, CI ghim 3.11); Node v24.14.1, npm 11.11.0 (yêu cầu Node 20+, CI ghim 20); Next.js 16.4.6.

## 5. Đề xuất cho giai đoạn 1

1. **Khảo sát PDF bằng pdfplumber:** viết script thống kê số trang, văn bản, bảng, hình cho từng tệp trong `data/raw/`; lưu báo cáo khảo sát vào `docs/` (không commit tài liệu gốc).
2. **Chuẩn hóa cấu trúc "Câu N":** xác định ranh giới câu hỏi, đáp án, lời giải; thiết kế chunk cha–con khớp cột `parent_id` và `chunk_index` đã có trong migration.
3. **Chạy migration trên Supabase** và kiểm chứng RLS mặc định đóng trước khi nạp dữ liệu; dùng `service_role` chỉ ở backend.
4. **Đóng gói pipeline ingestion** vào `ingestion/` với CLI tái lập được, thêm `pdfplumber` vào `requirements.txt` khi bắt đầu giai đoạn 1 (chưa thêm ở giai đoạn 0 để giữ phụ thuộc tối thiểu).
5. **Tách dev/test ngay từ đầu:** câu hỏi tự biên soạn (W13), không dùng đề công khai cho tập test; đóng băng tập test trước Giai đoạn 8.

## 6. Xác nhận Definition of Done

- [x] Cấu trúc monorepo đầy đủ theo yêu cầu.
- [x] `CLAUDE.md` 10 mục, có bảng W1–W13 và parser PDF là pdfplumber.
- [x] Đúng 6 skill, mỗi skill có `SKILL.md` đủ 5 phần.
- [x] `GET /health` trả `{"status":"ok"}`; cấu hình đọc `.env`; logging JSON; đủ 4 tầng thư mục; pytest + ruff.
- [x] Frontend hiển thị tên dự án và trạng thái kết nối backend, chuỗi tiếng Việt có dấu; ESLint + Prettier.
- [x] Migration: `vector`, `pg_trgm`, 6 bảng, HNSW, GIN tsvector, RLS mặc định đóng.
- [x] `.env.example` đúng 6 biến; `.env` không bị theo dõi.
- [x] Makefile đủ `dev`, `test`, `lint`, `ingest`, `eval` (hai lệnh sau ghi chú); `docker-compose.yml`.
- [x] Pre-commit (ruff, black, eslint) và CI (lint, test, build).
- [x] README hướng dẫn chạy trong 3 lệnh.
- [x] Không có LlamaParse/llama-cloud trong phụ thuộc hay cấu hình; không in giá trị khóa ở bất kỳ đâu.
- [x] `make lint` đạt, `make test` đạt (3 passed), `npm run build` đạt, `curl /health` đạt.

Không triển khai chức năng của các giai đoạn sau. Kết thúc Giai đoạn 0.
