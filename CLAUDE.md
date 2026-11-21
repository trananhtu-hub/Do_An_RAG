# CLAUDE.md — Chatbot RAG luyện thi AWS SAA-C03

Tài liệu này được nạp vào mỗi phiên làm việc. Chỉ ghi những điều kiểm chứng được.

## 1. Tổng quan dự án

- **Mục tiêu:** Chatbot RAG hỗ trợ tự học và luyện thi chứng chỉ AWS Certified Solutions Architect – Associate (SAA-C03).
- **Nền tảng:** Kế thừa kiến trúc 3 tầng của đồ án tham chiếu ISTQB (Next.js – FastAPI – Supabase/pgvector – Gemini), đồng thời khắc phục 13 nhược điểm W1–W13 dưới đây.
- **Phạm vi giai đoạn 0:** Khung repo chạy được, chưa xử lý dữ liệu, chưa xây RAG.

### Bảng 13 nhược điểm W1–W13

| Mã | Nhược điểm của đồ án tham chiếu | Giai đoạn xử lý |
| :--- | :--- | :--- |
| **W1** | Suy luận K3 “nhảy cóc”, kết luận thiếu kiểm chứng | Giai đoạn 5 (prompt CoT có kiểm chứng), Giai đoạn 8 |
| **W2** | Mất cấu trúc bảng/sơ đồ khi parse PDF | Giai đoạn 3 (ingestion), Giai đoạn 5 |
| **W3** | Chỉ đưa 3 chunk cố định vào LLM | Giai đoạn 4 (retrieval thích ứng) |
| **W4** | Mỗi lượt hỏi xử lý độc lập, thiếu ngữ cảnh hội thoại | Giai đoạn 6 (session + query rewriting) |
| **W5** | Chưa hỗ trợ streaming, thời gian phản hồi cao | Giai đoạn 6, Giai đoạn 7 (SSE) |
| **W6** | Chỉ một độ đo, bộ test nhỏ (160 câu) | Giai đoạn 2, Giai đoạn 8 |
| **W7** | Thiếu tìm kiếm Việt–Anh, reranker tiếng Anh chưa phù hợp | Giai đoạn 4 |
| **W8** | Phân tích lỗi khai “3 nhóm” nhưng chỉ liệt kê 2 | Giai đoạn 2, Giai đoạn 8 |
| **W9** | Kho tri thức hẹp, chưa có version index | Giai đoạn 3 |
| **W10** | Thiếu cấu hình RAG vector-only, chưa có ablation đầy đủ | Giai đoạn 4 |
| **W11** | Chênh lệch 3,13 điểm Pro/Flash chưa kiểm định thống kê | Giai đoạn 8 |
| **W12** | Gọi `ts_rank` của PostgreSQL là BM25 (không chính xác) | Giai đoạn 4 |
| **W13** | Bộ test lấy từ đề công khai, LLM có thể đã thấy đề | Giai đoạn 2 (câu tự biên soạn), Giai đoạn 8 |

## 2. Kiến trúc và stack

- **Frontend:** Next.js (App Router) + TypeScript, giao diện tiếng Việt có dấu.
- **Backend:** FastAPI (Python 3.11+), cấu hình pydantic-settings, logging JSON.
- **Cơ sở dữ liệu:** Supabase PostgreSQL + pgvector (embedding 768 chiều) + pg_trgm.
- **LLM:** Gemini 3.8 (`gemini-3.8-flash` mặc định cho sinh câu trả lời); embedding Gemini 768 chiều.
- **Parser PDF:** **pdfplumber** chạy cục bộ, mã nguồn mở. Không dùng LlamaParse, llama-cloud hay dịch vụ OCR/parse trả phí.
- **Truy xuất (Giai đoạn 4):** vector search (HNSW) + full-text search + RRF (k = 60) + reranker đa ngôn ngữ + top-k thích ứng + mở rộng mục cha.
- **Luồng 3 tầng:** Frontend → FastAPI → tầng truy xuất/sinh câu trả lời → Supabase (pgvector) và Gemini.
- **Đánh giá:** module `evaluation/` độc lập với ứng dụng.

## 3. Cấu trúc repo

```
.
├─ backend/            FastAPI app (app/api, app/core, app/services, app/models, tests)
├─ frontend/           Next.js + TypeScript
├─ ingestion/          Pipeline nạp tài liệu (Giai đoạn 1, 3)
├─ evaluation/         Bộ đánh giá và độ đo (Giai đoạn 2, 8)
├─ prompts/            Prompt template theo loại câu hỏi (Giai đoạn 5)
├─ supabase/migrations/ Migration SQL (pgvector, pg_trgm, RLS)
├─ data/raw/           Dữ liệu gốc — KHÔNG commit
├─ data/processed/     Dữ liệu đã xử lý
├─ data/external_test/ Bộ kiểm thử bên ngoài
├─ docs/               Báo cáo giai đoạn, quyết định
├─ scripts/            Script tiện ích
├─ tests/              Kiểm thử tích hợp cấp repo
└─ .claude/skills/     6 skill của dự án
```

## 4. Lệnh thường dùng

| Lệnh | Mô tả |
| :--- | :--- |
| `make install` | Tạo venv, cài backend và frontend dependencies |
| `make dev` | Chạy backend (cổng 8000) và frontend (cổng 3000) |
| `make lint` | ruff + black --check (backend) và eslint (frontend) |
| `make test` | pytest backend |
| `make ingest` | Nạp PDF trong `data/raw` vào Supabase (hỗ trợ `--force`) — Giai đoạn 1 |
| `make eval` | Chưa triển khai — Giai đoạn 2/8 |
| `curl http://localhost:8000/health` | Kiểm tra backend |
| `cd frontend && npm run build` | Build production frontend |

## 5. Quy ước mã nguồn

- Python 3.11+, type hints đầy đủ, độ dài dòng 100, định dạng bằng black, lint bằng ruff.
- TypeScript strict; ESLint + Prettier cho frontend.
- API trả JSON; log dạng JSON; không log khóa, token hay chuỗi kết nối.
- Chuỗi giao diện người dùng bằng tiếng Việt có dấu.
- Mọi thay đổi phải qua `make lint` và `make test` trước khi báo hoàn thành.

## 6. Biến môi trường

Khai báo trong `.env` ở thư mục gốc (không commit); mẫu tại `.env.example`:

| Biến | Ý nghĩa |
| :--- | :--- |
| `GEMINI_API_KEY` | Khóa Google AI Studio cho Gemini |
| `GEMINI_MODEL_DEFAULT` | Model sinh mặc định, giá trị `gemini-3.8-flash` |
| `SUPABASE_URL` | URL dự án Supabase |
| `SUPABASE_ANON_KEY` | Khóa công khai (RLS áp dụng) |
| `SUPABASE_SERVICE_ROLE_KEY` | Khóa máy chủ, bỏ qua RLS — chỉ dùng backend |
| `DATABASE_URL` | Chuỗi kết nối PostgreSQL |

Không thêm biến cho dịch vụ parse PDF bên ngoài.

## 7. Quy tắc dữ liệu

- `data/raw/` không được commit; mọi dữ liệu sinh ra phải tái lập được bằng script.
- Giữ nguyên nguồn, số trang và metadata của từng chunk để trích dẫn chính xác.
- Tách tập dev/test; không dùng tập test để tinh chỉnh; đóng băng test trước Giai đoạn 8.
- Không để rò rỉ dữ liệu giữa kho tri thức và bộ câu hỏi kiểm thử.
- Tôn trọng bản quyền tài liệu gốc; ghi nguồn trong báo cáo.

## 8. Thuật ngữ

| Thuật ngữ | Nghĩa |
| :--- | :--- |
| RAG | Retrieval-Augmented Generation — truy xuất tài liệu rồi sinh câu trả lời |
| Chunk cha–con | Chunk con nhỏ để truy xuất, chunk cha (cả mục) để cung cấp ngữ cảnh |
| Embedding | Vector 768 chiều biểu diễn ngữ nghĩa văn bản |
| HNSW | Chỉ mục ANN cho tìm kiếm vector |
| Hybrid search | Kết hợp vector search và full-text search |
| RRF | Reciprocal Rank Fusion — hợp nhất xếp hạng, k = 60 |
| Rerank | Xếp hạng lại ứng viên bằng cross-encoder đa ngôn ngữ |
| K1/K2/K3 | Mức nhận thức: nhớ, hiểu, vận dụng |
| TTFT | Thời gian tới token đầu tiên |

## 9. Quy tắc bất biến

1. Không commit `.env` hay bất kỳ khóa bí mật nào.
2. Không thêm LlamaParse, llama-cloud hoặc dịch vụ OCR/parse trả phí; parser PDF là pdfplumber.
3. Không mở quyền RLS mặc định; bảng mới phải bật RLS và mặc định đóng.
4. Không sửa hay dùng tập test để tinh chỉnh trong giai đoạn phát triển.
5. Không triển khai chức năng của giai đoạn sau khi chưa hoàn thành giai đoạn hiện tại.
6. Mọi thay đổi schema phải đi qua `supabase/migrations/`.
7. Không in giá trị khóa, mật khẩu hay chuỗi kết nối ra log, báo cáo hay hội thoại.

## 10. Trạng thái dự án

- **Giai đoạn 0 — Hoàn thành:** khung repo, backend `/health`, frontend khung, migration khởi tạo, CI, skills, báo cáo tại `docs/phase-0-report.md`.
- **Giai đoạn 1 — Hoàn thành:** pipeline nạp tri thức (pdfplumber, trích câu hỏi, chunking cha–con, embedding Gemini 768, Supabase); kho hiện có 7 tài liệu, 1.775 chunk, 390 câu hỏi (390/390 có đáp án, trong đó 21 câu bổ sung thủ công có căn cứ tại `ingestion/answer_overrides.json`); báo cáo tại `docs/phase-1-report.md`.
- **Giai đoạn 2–3 (cách đánh số của đề bài đồ án) — tương ứng Giai đoạn 4–5 dưới đây:**
  - **Giai đoạn 4 — Hoàn thành:** tầng truy hồi lai (vector HNSW + full-text + trigram + RRF k=60 + reranker đa ngôn ngữ + top-k thích ứng + mở rộng mục cha); dev set 40 câu; báo cáo tại `docs/phase-2-report.md` (đề bài gọi là Giai đoạn 2).
  - **Giai đoạn 5 — Một phần:** tầng sinh câu trả lời có kiểm chứng (prompt v1, schema JSON, CoT, hậu kiểm trích dẫn, từ chối `no_evidence`/`out_of_scope`), lớp `LLMProvider` (Gemini + adapter tương thích OpenAI + chuỗi dự phòng), ghi `query_logs`. Khóa Gemini hết hạn mức (HTTP 429) nên benchmark chạy bằng provider dự phòng; tiêu chí CoT tăng ≥5 điểm % chưa đạt. Báo cáo tại `docs/phase-3-report.md` (đề bài gọi là Giai đoạn 3).
- Kho tri thức đã có dữ liệu thật; chưa có session/streaming/giao diện RAG (Giai đoạn 6–7).
