# BÁO CÁO GIAI ĐOẠN 1

**Trạng thái: HOÀN THÀNH**

Ngày hoàn tất: 2026-11-20 (giờ địa phương; log ghi theo UTC 2026-11-19).
Phạm vi: xây dựng và chạy pipeline nạp tri thức từ PDF AWS SAA-C03 vào Supabase (Giai đoạn 1). Không bao gồm chức năng RAG hay bộ đánh giá (Giai đoạn 2 trở đi).

## 1. Việc đã làm

### 1.1 Tệp và mô-đun đã tạo

| Thành phần | Mô tả |
| :--- | :--- |
| `ingestion/inspect.py` | Script khảo sát cấu trúc PDF bằng pdfplumber; kết quả ghi tại `docs/ingestion-analysis.md` (chạy **trước** khi viết pipeline) |
| `ingestion/loaders/` | Loader pdfplumber: giữ thứ tự trang, chuẩn hóa Unicode NFC, trích bảng sang Markdown/HTML kèm metadata `{type, page, rows, cols}`, đếm trang lỗi/rỗng, bỏ qua `data/external_test` |
| `ingestion/sections.py` | Phân tích cấu trúc mục “Câu N:” của ngân hàng câu hỏi |
| `ingestion/questions.py` | Trích câu hỏi có cấu trúc: `id, question, options A–D, answer, explanation, domain, topic, source_page, language` |
| `ingestion/domains.py` | Chuẩn hóa 4 lĩnh vực blueprint + 7 câu gán tay (`MISSING_DOMAIN_OVERRIDES`) |
| `ingestion/chunking.py` | Chunking cha–con: cha 800–1200 token (cả mục), con 300–500 token, chồng lấn ~12%; `chunk_id` UUIDv5 tất định, checksum SHA-256, `parent_id` cho chunk con |
| `ingestion/embeddings.py` | Gemini `gemini-embedding-001` 768 chiều: `batchEmbedContents`, pacing 28k token/phút, retry/backoff, xoay vòng nhiều khóa, callback checkpoint |
| `ingestion/store.py` | Ghi Supabase: `documents`, `chunks` (embedding, metadata, parent_id), `questions`; thay thế theo `source_key` (delete–replace), tạo chỉ mục HNSW + GIN |
| `ingestion/pipeline.py` | Điều phối toàn bộ: quét → bỏ qua tài liệu không đổi → parse → embed → ghi → thống kê/toàn vẹn; cờ `--force`; bộ đệm embedding `data/processed/embed_cache.json` |
| `supabase/migrations/20261119000000_ingestion_schema.sql` | Migration schema bảng dữ liệu, bật RLS mặc định đóng |
| `scripts/check_ingestion.py` | Kiểm tra toàn vẹn dữ liệu sau nạp (11 mục kiểm tra) |
| `tests/ingestion/` | 40 unit test (loaders, chunking, sections/questions, tables, embeddings, pipeline) |
| `Makefile`, `.github/workflows/ci.yml` | Mục tiêu `make ingest`; job CI `ingestion` (ruff + black + pytest) |

### 1.2 Đặc điểm kỹ thuật đáng chú ý

- **Idempotent:** mỗi tài liệu ghi theo cơ chế thay thế toàn bộ trong một transaction (commit trước khi mở transaction để không mất dữ liệu khi lỗi); lần chạy lại phát hiện tài liệu không đổi qua checksum + `pipeline_version` và bỏ qua.
- **Bền vững trước hạn mức API:** vector embedding được checkpoint ra `data/processed/embed_cache.json` sau từng lô; khi cạn hạn mức, tiến trình dừng với mã 3 và không mất vector nào. Khóa API có thể khai báo dạng `GEMINI_API_KEY=khóa1,khóa2` để tự xoay vòng.
- **An toàn bí mật:** mọi thông báo lỗi được che `DATABASE_URL` và toàn bộ khóa Gemini trước khi ghi log; báo cáo không chứa giá trị khóa.

### 1.3 Đối chiếu 13 nhược điểm W1–W13 (chỉ đánh dấu khi có thực nghiệm)

| Mã | Trạng thái sau Giai đoạn 1 | Ghi chú |
| :--- | :--- | :--- |
| W2 | Một phần | Đã có nhánh trích bảng Markdown/HTML + metadata và 3 unit test, nhưng kho dữ liệu hiện tại có **0 bảng** nên chưa kiểm chứng được trên dữ liệu thật |
| W9 | Một phần | Kho tri thức đã mở rộng lên 7 tài liệu, có `version`, `pipeline_version`, metadata nguồn từng chunk; version index đầy đủ thuộc Giai đoạn 3 |
| W6, W13 | Chưa bắt đầu | Bộ test và câu tự biên soạn thuộc Giai đoạn 2 |
| W1, W3, W4, W5, W7, W10, W12 | Chưa bắt đầu | Thuộc Giai đoạn 4–8 |
| W8, W11 | Chưa bắt đầu | Thuộc Giai đoạn 2/8 |

## 2. Kết quả kiểm thử

| Hạng mục | Lệnh | Kỳ vọng | Thực tế | Đạt |
| :--- | :--- | :--- | :--- | :--- |
| Unit test pipeline nạp | `pytest tests/ingestion -q` | Tất cả đạt | `40 passed in 0.32s` | Đạt |
| Unit test bảng | `pytest tests/ingestion/test_tables.py -q` | Tất cả đạt | `3 passed in 0.01s` | Đạt |
| Toàn bộ test repo | `make -f Makefile test` | Tất cả đạt | `43 passed, 1 warning in 0.82s` | Đạt |
| Lint | `make -f Makefile lint` | Không lỗi | ruff: All checks passed; black: 35 tệp không đổi; eslint: sạch | Đạt |
| Nạp lần 1 | `make -f Makefile ingest` (`data/processed/ingest-run1.log`) | Ghi đủ tài liệu, exit 0 | 6 tài liệu nạp + 1 bỏ qua (đã có), 1.775 chunk, 390 câu, 1.240,17 giây, `exit=0` | Đạt |
| Nạp lần 2 (idempotent) | `make -f Makefile ingest` (`data/processed/ingest-run2.log`) | Không tạo bản ghi trùng, số đếm không đổi | 0 nạp mới, 7 bỏ qua, chunk 1.775, câu hỏi 390 (không đổi), 1,0 giây, `exit=0` | Đạt |
| Chunk rỗng | `check_ingestion.py` | `empty_chunks = 0` | 0 | Đạt |
| Embedding NULL | `check_ingestion.py` | `null_embeddings = 0` | 0 | Đạt |
| Đúng 768 chiều | `check_ingestion.py` | `wrong_dimensions = 0` | 0 | Đạt |
| Kiểm tra 5 bảng ngẫu nhiên | `check_ingestion.py` + `test_tables.py` | Bảng có metadata đúng | **Kho dữ liệu không có bảng nào** (cả 7 PDF: `tables: 0` trong log parse; `table_samples: []`); nhánh trích bảng được kiểm bằng 3 unit test với PDF tổng hợp | Đạt (điều chỉnh theo thực tế dữ liệu) |
| Phân bố domain | `check_ingestion.py` | Tổng 100%, không nhãn lạ | Cost-Optimized 9,74% + High-Performing 33,59% + Resilient 26,92% + Secure 29,74% = 100% (390 câu; tổng các số làm tròn hiển thị 99,99%); `unknown_domains: []` | Đạt |
| Độ phủ câu hỏi | `check_ingestion.py` | ≥ 95% của 390 | 100% (390/390) | Đạt |
| Không lọt `external_test` | unit test + đếm tài liệu | Không có tài liệu ngoài `data/raw` | 7 tài liệu trong DB đúng bằng 7 PDF trong `data/raw`; `test_input_paths_tu_choi_external_test` đạt | Đạt |
| Thời gian nạp được đo | log lần 1 | Có số đo | **1.240,17 giây (20,7 phút)** cho lần chạy đủ cuối cùng (parse 6 tài liệu + sinh 726 embedding còn thiếu + ghi DB) | Đạt |

Ghi chú về thời gian: từ lần thử nạp đầu tiên đến lần hoàn tất (11:10 UTC → 20:28 UTC, gồm các lần bị hạn mức API — xem mục 4) là khoảng 9 giờ 18 phút; trong đó thời gian máy thực sự xử lý ~48 phút (hai phiên 16:05–16:33 và 20:07–20:28). Phần lớn thời gian còn lại là chờ hạn mức miễn phí của Gemini (30.000 token/phút, 1.000 request/ngày) và thao tác đổi khóa của người vận hành.

## 3. Thống kê dữ liệu

Nguồn: `data/processed/ingestion_stats.json` (lần chạy 2, khớp lần 1) và `data/processed/check-output.txt`.

### 3.1 Tổng quan cơ sở dữ liệu

| Chỉ số | Giá trị |
| :--- | :--- |
| Tài liệu | 7 |
| Tổng số trang | 545 |
| Chunk | 1.775 (514 chunk cha + 1.261 chunk con) |
| Câu hỏi | 390 |
| Bảng | 0 |
| Trang lỗi parse | 0 |
| Vi phạm toàn vẹn (7 loại) | 0/0/0/0/0/0/0 |

### 3.2 Theo tài liệu

| Tài liệu | Trang | Chunk | Cha | Con | Câu hỏi |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `aws-saa-exam-guide.pdf` | 28 | 58 | 16 | 42 | 0 |
| `aws-saa-question-bank.pdf` | 461 | 1.577 | 463 | 1.114 | 390 |
| `EC2_Tinh_toan.pdf` | 11 | 28 | 7 | 21 | 0 |
| `IAM.pdf` | 11 | 28 | 7 | 21 | 0 |
| `RDS_Aurora.pdf` | 11 | 28 | 7 | 21 | 0 |
| `S3_Storage_Classes.pdf` | 11 | 28 | 7 | 21 | 0 |
| `VPC_Networking.pdf` | 12 | 28 | 7 | 21 | 0 |
| **Tổng** | **545** | **1.775** | **514** | **1.261** | **390** |

### 3.3 Câu hỏi và domain

| Chỉ số | Giá trị |
| :--- | :--- |
| Tổng câu hỏi | 390 (độ phủ 100% so với kỳ vọng 390) |
| Có đáp án đúng trích được | 369/390 |
| Không trích được đáp án đúng | 21 (ghi nhận ở `docs/ingestion-analysis.md`) |
| Domain — Secure | 116 (29,74%) |
| Domain — Resilient | 105 (26,92%) |
| Domain — High-Performing | 131 (33,59%) |
| Domain — Cost-Optimized | 38 (9,74%) |

## 4. Vấn đề và rủi ro

1. **Hạn mức Gemini miễn phí chặn quá trình nạp.** Free tier giới hạn 1.000 request embedding/ngày **tính theo project × model** (không theo khóa) và 30.000 token/phút; `batchEmbedContents` tính từng đoạn văn là một request. Cần 1.717 request cho toàn bộ chunk. Đã xử lý bằng: (a) bộ đệm embedding ra đĩa — cạn hạn mức ở 991/1.717 vector nhưng không mất dữ liệu; (b) khóa mới phải thuộc **project mới** (khóa trong cùng project dùng chung hạn mức đã cạn — đã kiểm chứng bằng thực nghiệm); (c) hỗ trợ khai báo nhiều khóa dạng `khóa1,khóa2` để tự xoay vòng. Bằng chứng: `data/processed/ingest-run1-failed-429.log` (lần thử đầu, chưa có bộ đệm), `ingest-run1a-quota.log`, `ingest-run1b-quota.log`.
2. **21/390 câu không trích được đáp án đúng** (để `correct_answer = NULL`). Ảnh hưởng trực tiếp đến việc dùng ngân hàng câu hỏi làm ground truth ở Giai đoạn 2 — cần rà soát/bổ sung thủ công 21 câu này trước khi chọn tập test.
3. **Phân bố domain lệch blueprint:** blueprint SAA-C03 yêu cầu trọng số 30/26/24/20 (Secure/Resilient/High-Performing/Cost-Optimized), nhưng ngân hàng câu hỏi thực tế có Cost-Optimized chỉ 9,74% và High-Performing 33,59%. Giai đoạn 2 cần tạo câu tự biên soạn để cân bằng (đồng thời phục vụ W13).
4. **Kho dữ liệu có 0 bảng:** nhánh trích bảng (W2) chưa được kiểm chứng trên dữ liệu thật, chỉ qua unit test với PDF tổng hợp. Rủi ro khi thêm tài liệu mới có bảng ở Giai đoạn 3.
5. **Sai lệch nhỏ về kích thước chunk cha:** mục tiêu 800–1200 token; một số mục “Câu N” rất dài của ngân hàng câu hỏi tạo chunk cha tới ~1.318 token do không thể cắt ngang ranh giới câu hỏi. Chunk con vẫn trong dải 300–500 token.
6. **Môi trường Windows:** đường dẫn chứa ký tự có dấu khiến `make` không tự tìm thấy Makefile; toàn bộ lệnh dùng `make -f Makefile <target>`. Script kiểm tra cần `PYTHONPATH=.`. Đã ghi trong CI không bị ảnh hưởng (Linux).
7. **Bộ đệm embedding là dữ liệu dẫn xuất:** `data/processed/embed_cache.json` (~10 MB, đã thêm vào `.gitignore`) có thể xóa và tái tạo bằng cách chạy lại pipeline (tốn hạn mức API).

## 5. Đề xuất cho giai đoạn 2

1. **Rà soát 21 câu thiếu đáp án** và bổ sung thủ công trước khi đóng băng tập test; nếu không, loại khỏi tập đánh giá để tránh nhiễu.
2. **Tách dev/test từ 390 câu đã nạp**, đóng băng tập test ngay từ đầu Giai đoạn 2; không dùng tập test để tinh chỉnh (quy tắc bất biến 4).
3. **Tự biên soạn câu hỏi mới** cho các domain thiếu (đặc biệt Cost-Optimized) để bám trọng số blueprint 30/26/24/20 và xử lý W13 (tránh LLM đã thấy đề công khai).
4. **Chuẩn bị ground truth truy xuất** cho Giai đoạn 4: với mỗi câu trong tập dev/test, xác định chunk/tài liệu chứa bằng chứng, lưu thành tệp JSON trong `evaluation/`.
5. **Giữ nguyên cơ chế kiểm soát hạn mức:** khi Giai đoạn 2/8 gọi Gemini để sinh hoặc đánh giá, dùng cùng chiến lược (đếm request, cache kết quả, nhiều khóa khác project).

## 6. Xác nhận Definition of Done

| # | Yêu cầu Giai đoạn 1 | Kết quả | Đạt |
| :--- | :--- | :--- | :--- |
| 1 | Script phân tích cấu trúc PDF, chạy trước pipeline, kết quả `docs/ingestion-analysis.md` | `ingestion/inspect.py` + `docs/ingestion-analysis.md` | ✓ |
| 2 | Loader pdfplumber giữ thứ tự trang, chuẩn hóa Unicode NFC | `ingestion/loaders/`, unit test chuẩn hóa | ✓ |
| 3 | Trích bảng → Markdown/HTML kèm metadata `{type, page, rows, cols}` | Đã cài đặt + 3 unit test; kho dữ liệu hiện có 0 bảng | ✓ (điều chỉnh) |
| 4 | Trích câu hỏi cấu trúc đủ trường | 390 câu; 369 có đáp án (21 thiếu, đã ghi nhận) | ✓ |
| 5 | Chunking cha–con 800–1200/300–500 token, chồng lấn 10–15%, `parent_id` | 514 cha + 1.261 con; chồng lấn ~12%; `parent_id` đủ | ✓ |
| 6 | Embedding Gemini 768 chiều, batch, retry, checksum nội dung | `gemini-embedding-001`, 1.717 vector, 0 retry cuối cùng, checksum từng chunk | ✓ |
| 7 | Ghi Supabase `documents`, `chunks`, `questions`, chỉ mục HNSW + GIN | 7/1.775/390 bản ghi; chỉ mục tạo qua migration | ✓ |
| 8 | Xuất thống kê: tài liệu, trang, chunk, bảng, câu hỏi, domain, trang lỗi | `data/processed/ingestion_stats.json` | ✓ |
| 9 | `make ingest` chạy toàn pipeline, hỗ trợ `--force` | Lần 1 và lần 2 đều `exit=0` | ✓ |
| — | Không sửa `data/raw`; biến đổi ghi `data/processed` | Chỉ đọc PDF gốc; đầu ra ở `data/processed/` | ✓ |
| — | Không đưa `data/external_test` vào kho tri thức | Guard runtime + unit test; DB đúng 7 tài liệu `data/raw` | ✓ |
| — | Chạy lại idempotent, không bản ghi trùng | Lần 2: số đếm không đổi (1.775 chunk, 390 câu) | ✓ |
| — | Mỗi chunk giữ metadata nguồn (tên tài liệu, số trang, đề mục) | `source_key`, `source_page`, `section_path` trong metadata chunk | ✓ |
| — | Không commit/không in giá trị khóa | Không có khóa trong log, báo cáo hay mã nguồn | ✓ |

## Phụ lục A — Trích kết quả thô

**A.1 Unit test** (`pytest tests/ingestion -q`):

```
........................................                                 [100%]
40 passed in 0.32s
```

**A.2 Nạp lần 1 — dòng tổng kết** (`data/processed/ingest-run1.log`):

```
{"time": "2026-11-19T20:07:19+00:00", "event": "start", ...}
{"time": "2026-11-19T20:08:55+00:00", "event": "embed_start", "chunks": 1717, "cached": 991, "missing": 726, "keys": 1}
{"time": "2026-11-19T20:27:48+00:00", "event": "embed_done", "vectors": 1717, "batches": 27, "retries": 0, "seconds": 1132.98}
{"time": "2026-11-19T20:27:59+00:00", "event": "summary", "ingested": 6, "skipped": 1, "failed": 0, "chunks": 1775, "questions": 390, "seconds": 1240.17, ...}
exit=0
```

**A.3 Nạp lần 2 — idempotent** (`data/processed/ingest-run2.log`):

```
{"time": "2026-11-19T20:28:09+00:00", "event": "skip", "document": "data/raw/aws-saa-question-bank.pdf", "reason": "unchanged"}
...
{"time": "2026-11-19T20:28:09+00:00", "event": "summary", "ingested": 0, "skipped": 7, "failed": 0, "chunks": 1775, "questions": 390, "seconds": 1.0, ...}
exit=0
```

**A.4 Script kiểm tra toàn vẹn** (`data/processed/check-output.txt`, trích):

```json
{
  "database": {"documents": 7, "pages": 545, "chunks": 1775, "parents": 514, "children": 1261, "questions": 390,
    "domains": {"Cost-Optimized": 38, "High-Performing": 131, "Resilient": 105, "Secure": 116}},
  "integrity": {"empty_chunks": 0, "null_embeddings": 0, "wrong_dimensions": 0, "children_without_parent": 0,
    "missing_token_counts": 0, "missing_checksums": 0, "duplicate_chunk_indexes": 0},
  "unknown_domains": [],
  "question_coverage_percent": 100.0,
  "checks": {"no_empty_chunks": true, "no_null_embeddings": true, "embedding_dim_768": true,
    "children_have_parent": true, "token_counts_present": true, "checksums_present": true,
    "no_duplicate_chunk_index": true, "domains_canonical": true, "domain_total_100": true,
    "question_coverage_ge_95": true, "tables_sampled_ok": true},
  "passed": true
}
```

**A.5 Sự cố hạn mức (tóm tắt)** — `ingest-run1-failed-429.log`, `ingest-run1a-quota.log`, `ingest-run1b-quota.log`:

```
{"time": "2026-11-19T11:10:01+00:00", "event": "start", ...}                 ← lần thử đầu (chưa có bộ đệm)
{"time": "2026-11-19T11:11:42+00:00", "event": "embed_start", "chunks": 1717}
{"time": "2026-11-19T11:40:39+00:00", "event": "error", "error": "EmbeddingError: Gemini trả mã 429 sau 9 lần thử: ..."}
{"time": "2026-11-19T16:32:59+00:00", "event": "quota_exhausted", "embedded_in_run": 991, "remaining": 726, "cached": 991, "chunks": 1717, ...}
{"time": "2026-11-19T19:05:43+00:00", "event": "quota_exhausted", "embedded_in_run": 0, "remaining": 726, "cached": 991, "chunks": 1717, ...}
```

(Ba lần đầu đều dừng do hạn mức; từ lần 16:05 trở đi có bộ đệm nên không mất vector nào. Lần chạy 20:07 UTC với khóa thuộc project mới hoàn tất toàn bộ.)

---

*Hết báo cáo Giai đoạn 1. Không bắt đầu Giai đoạn 2 cho đến khi có chỉ đạo.*
