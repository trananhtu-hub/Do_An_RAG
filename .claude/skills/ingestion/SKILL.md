---
name: ingestion
description: "Nạp PDF AWS SAA-C03 bằng pdfplumber, chuẩn hóa mục Câu N, chunking cha–con, embedding Gemini 768 và upsert Supabase. Dùng ở Giai đoạn 1 và 3."
---

# Skill: Ingestion

## Mô tả

Pipeline nạp tài liệu từ PDF vào Supabase/pgvector: trích văn bản bằng **pdfplumber** (chạy cục bộ, không dùng LlamaParse hay dịch vụ parse trả phí), nhận diện cấu trúc mục “Câu N”, tách bảng thành Markdown, tạo chunk cha–con, gắn metadata nguồn và sinh embedding Gemini 768 chiều. Kết quả ghi vào `documents`, `chunks`, `questions`.

Mã nguồn: `ingestion/` — `inspect.py` (khảo sát), `loaders/` (PDF, bảng), `sections.py`, `questions.py`, `chunking.py`, `embeddings.py`, `store.py`, `pipeline.py`.

## Khi nào dùng

- Giai đoạn 1: khảo sát PDF, nạp dữ liệu thật, kiểm tra chất lượng chunk.
- Giai đoạn 3: nạp bổ sung tài liệu hoặc nạp lại sau khi sửa logic chunking.
- Khi cần tái lập kho tri thức từ `data/raw/`.

## Các bước

1. Áp migration theo thứ tự: `20261118000000_init_schema.sql` rồi `20261119000000_ingestion_schema.sql`.
2. Đặt PDF gốc vào `data/raw/` (không commit). Không đặt tài liệu vào `data/external_test/`.
3. Khảo sát cấu trúc: `python -m ingestion.inspect --input data/raw` (ghi `docs/ingestion-analysis.md`).
4. Nạp toàn bộ: `make ingest`. Nạp lại bắt buộc: `make ingest ARGS=--force`.
   Trên Windows, nếu đường dẫn dự án chứa ký tự có dấu, GNU Make không tự tìm thấy
   Makefile (lỗi cp1252 đã ghi ở Giai đoạn 0) — dùng `make -f Makefile ingest`.
5. Nạp một tệp: `python -m ingestion.pipeline --input data/raw/<file>.pdf`.
6. Đọc thống kê tại `data/processed/ingestion_stats.json` và đối chiếu hậu kiểm.

## Cơ chế chống trùng

- `documents.source_key` là khóa duy nhất theo đường dẫn tương đối.
- Mỗi tài liệu lưu `checksum` SHA-256 của PDF và `pipeline_version`.
- Lần chạy sau bỏ qua tài liệu khi checksum, phiên bản pipeline, số chunk và số câu khớp; không gọi lại Gemini.
- `--force` xóa và ghi lại từng tài liệu (cascade sang chunk và câu hỏi), sau đó sinh lại embedding.
- ID tài liệu/chunk/câu hỏi là UUIDv5 tất định, nên chạy lại cho cùng kết quả.

## Metadata và cấu trúc

- Chunk cha: 800–1200 token ước lượng (dung sai có ghi trong báo cáo), cả mục hoặc một phần mục.
- Chunk con: 300–500 token, có `parent_id`, chồng lấn mục tiêu 10–15%.
- Bảng: một chunk `content_type='table'`, nội dung Markdown, metadata `{type, page, table_index, rows, cols}`.
- Câu hỏi: `external_id`, `question`, `options` A–D, `correct_answer`, `explanation`, `domain`, `topic`, `source_page`, `language`, `checksum`.
- Không đọc hay nạp bất kỳ tệp nào trong `data/external_test/`.

## Kiểm thử

```bash
pytest tests/ingestion -q
make lint
make test
```

## Tiêu chí nghiệm thu

- 100% trang được xử lý; trang thiếu text layer được ghi vào `error_pages`.
- Mọi chunk có metadata nguồn: tài liệu, trang, đề mục; mọi chunk con trỏ tới cha cùng tài liệu.
- Không có chunk rỗng, không có embedding NULL, vector đúng 768 chiều.
- Chạy hai lần liên tiếp không tăng số bản ghi.
- Chỉ dùng pdfplumber; không thêm dịch vụ parse PDF bên ngoài.
- Thống kê tái lập được trong `data/processed/ingestion_stats.json`.
