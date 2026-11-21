# BÁO CÁO GIAI ĐOẠN 2

**Trạng thái: HOÀN THÀNH**

Ngày: 2026-11-21 (giờ địa phương; log và API ghi theo UTC 2026-11-20/21).
Phạm vi: xây dựng tầng truy hồi lai và xếp hạng lại cho chatbot RAG AWS SAA-C03, đánh giá trên dev set 40 câu. Không bao gồm sinh câu trả lời, streaming hay giao diện (các giai đoạn sau).

Toàn bộ phép đo được chạy lại đầy đủ sau khi thay khóa Gemini: benchmark sạch lúc 10:37, 10 truy vấn thủ công lúc 10:42, mô phỏng timeout trực tuyến lúc 10:44 ngày 2026-11-21 (giờ địa phương). Không còn hạng mục nào bị chặn.

> **Lưu ý đánh số giai đoạn:** CLAUDE.md xếp tầng truy hồi vào **Giai đoạn 4** và dành Giai đoạn 2 cho bộ kiểm thử/khung đánh giá; đề bài này gọi công việc hiện tại là **Giai đoạn 2**. Báo cáo giữ cách gọi của đề bài. Khi cập nhật CLAUDE.md cần thống nhất lại cách đánh số để tránh lệch trạng thái.

> **W12:** tìm kiếm từ vựng dùng full-text search của PostgreSQL (`tsvector` + `ts_rank_cd`), **không phải BM25**. Mọi tài liệu, tên cấu hình và báo cáo đều gọi đúng là "full-text/lexical", không gọi "BM25".

## 1. Việc đã làm

### 1.1 Tệp và mô-đun đã tạo

| Thành phần | Mô tả |
| :--- | :--- |
| `config/retrieval.yaml` | Toàn bộ tham số vận hành: embedding, trọng số vector/lexical/trigram, ngưỡng cosine, RRF k, rerank, phân loại, top-k thích ứng, decomposition, cache, ngân sách token. Không có tham số nào hard-code trong mã |
| `backend/app/services/retrieval/config.py` | Nạp YAML thành dataclass bất biến, kiểm tra hợp lệ, `fingerprint()` dùng cho khóa cache; hỗ trợ `with_overrides()` để chạy ablation |
| `backend/app/services/retrieval/embedder.py` | `GeminiQueryEmbedder` gọi `batchEmbedContents` 768 chiều, retry/backoff, xoay vòng nhiều khóa, cache LRU trong tiến trình |
| `backend/app/services/retrieval/store.py` | `PgChunkStore` (psycopg3): vector search cosine + `ef_search`, full-text `tsquery`, trigram `ILIKE` cho thuật ngữ tiếng Anh, đọc chunk cha |
| `backend/app/services/retrieval/text.py` | Chuẩn hóa truy vấn, tách thuật ngữ từ vựng, tách thuật ngữ tiếng Anh, dựng `tsquery` an toàn |
| `backend/app/services/retrieval/fusion.py` | RRF có trọng số: `score(d) = Σ weight_l / (k + rank_l(d))`, rank từ 1, cắt theo `fusion.candidates` |
| `backend/app/services/retrieval/rerank.py` | `CrossEncoderReranker` chạy cục bộ `BAAI/bge-reranker-v2-m3` (batch, fp16 trên GPU, lazy load, warmup); `TimeoutReranker` bọc timeout, lỗi/quá hạn trả `None` để fallback RRF |
| `backend/app/services/retrieval/classify.py` | Phân loại truy vấn `tra_cuu` / `so_sanh` / `nhieu_rang_buoc` / `tron_thuat_ngu` bằng heuristic, gọi LLM nhẹ khi độ tin cậy thấp |
| `backend/app/services/retrieval/topk.py` | Chọn top-k thích ứng theo loại câu (3–8), sàn điểm tương đối, ngân sách token |
| `backend/app/services/retrieval/decompose.py` | Tách 2–3 truy vấn con (heuristic + LLM), chạy song song, hợp nhất kết quả; bật/tắt bằng config |
| `backend/app/services/retrieval/cache.py` | `TTLCache` TTL + LRU (mặc định 1 giờ, 512 mục) |
| `backend/app/services/retrieval/service.py` | `RetrievalService.retrieve(query, top_k=None)` — API nội bộ ổn định; điều phối phân loại → decomposition → embedding → ba nhánh tìm kiếm song song → RRF → rerank có fallback → chọn top-k → mở rộng mục cha; đo thời gian từng tầng; lọc nguồn ngân hàng câu hỏi cho câu hỏi lý thuyết |
| `supabase/migrations/20261121090000_retrieval_phase2.sql` | Bật `unaccent`, hàm `immutable_unaccent`, cột sinh `search_text`/`search_vector_unaccented`, chỉ mục GIN full-text và trigram; không đổi RLS (vẫn bật, mặc định đóng) |
| `evaluation/build_dev_set.py`, `evaluation/dev_set.jsonl`, `evaluation/dev_set_review.md` | Dev set 40 câu tự biên soạn (10 câu mỗi loại), có mã câu, tài liệu/mục đúng và căn cứ để rà soát thủ công |
| `evaluation/retrieval_bench.py` | Chạy dev set theo nhiều cấu hình, tính Recall@5, MRR, nDCG@10, p50/p95 tổng và từng tầng; xuất CSV + Markdown |
| `evaluation/manual_queries.py` | 10 truy vấn thủ công (tra cứu, so sánh, nhiều ràng buộc, thuật ngữ tiếng Anh), in top-5 kèm tài liệu/mục/điểm, ghi Markdown |
| `evaluation/rerank_timeout_demo.py` | Mô phỏng reranker quá hạn (timeout 1 ms), so thứ tự với hybrid+RRF; cờ `--offline` dùng vector sẵn có trong DB khi không gọi được Gemini |
| `tests/retrieval/` | 76 unit test: config, text, fusion, cache, classifier, decompose, top-k, reranker/fallback, store, service (mock toàn bộ LLM và reranker) |

### 1.2 Quyết định kỹ thuật

- **Truy hồi ba nhánh song song:** vector HNSW (cosine, `ef_search=100`, ngưỡng 0,5) + full-text PostgreSQL trên cột sinh đã bỏ dấu + trigram cho thuật ngữ tiếng Anh. Ba nhánh chạy trong thread pool, mỗi truy vấn con một bộ ba tác vụ.
- **Hợp nhất RRF có trọng số** thay vì cộng điểm thô: trọng số vector 1,0 / lexical 0,3 / trigram 0,2; `k = 60`; giữ 30 ứng viên trước rerank; khử trùng lặp theo (tài liệu, mục) trước khi chọn top-k để top-k không bị tiêu hao vào nhiều chunk con cùng mục.
- **Rerank cục bộ đa ngôn ngữ:** `BAAI/bge-reranker-v2-m3`, batch 16, `max_length=512`, fp16 trên GPU; văn bản đưa vào cross-encoder là `"{tài liệu} - {mục}. {tiêu đề}\n{nội dung mục cha}"` để giữ ngữ cảnh mục (giảm W2 khi ngữ cảnh nằm ở mục cha). Quá hạn 3 giây hoặc lỗi mô hình → giữ nguyên thứ tự RRF, ghi `rerank_fallback`, không ném lỗi ra ngoài.
- **Top-k thích ứng:** dải theo loại câu (`tra_cuu` 3–5, `so_sanh` 4–8, `nhieu_rang_buoc` 5–8, `tron_thuat_ngu` 4–7), sàn điểm tương đối 0,35 so với điểm cao nhất, ngân sách 6.000 token; tôn trọng `top_k` do caller truyền.
- **Cha–con:** chunk con dùng để truy xuất, chunk cha cung cấp ngữ cảnh cho LLM; tài liệu/mục/tiêu đề/trang của kết quả **lấy từ metadata chunk con** để trích dẫn chính xác (kể cả khi mục cha gộp nhiều mục).
- **Lọc nguồn:** với câu hỏi lý thuyết, loại chunk `kind = "question"` khỏi pool rerank; tự động bỏ lọc khi truy vấn nhắc số câu hỏi (`câu 25`, `question 12`). Lý do: 88,3% chunk con trong kho là ngân hàng câu hỏi; nếu không lọc, câu hỏi lý thuyết dễ bị các chunk đề thi lấn chỗ. Đây là giả định cần kiểm chứng lại trên tập test độc lập (xem mục 5).
- **Cache:** khóa = fingerprint cấu hình + truy vấn chuẩn hóa + `top_k`; TTL 1 giờ; không cache kết quả đã fallback.
- **API ổn định:** `retrieve(query: str, top_k: int | None = None) -> RetrievalResult`, kèm `service.retrieve` và hàm module-level `retrieve`; không đổi chữ ký cho giai đoạn sau.

### 1.3 Đối chiếu các nhược điểm liên quan

| Mã | Trạng thái sau giai đoạn này | Ghi chú |
| :--- | :--- | :--- |
| W3 (chỉ 3 chunk cố định) | Đã xử lý, đã đo | Top-k thích ứng 3–8 theo loại câu + ngân sách token; đo trên dev set (mục 3) |
| W7 (thiếu Việt–Anh, reranker tiếng Anh) | Đã xử lý | Trigram cho thuật ngữ tiếng Anh + cross-encoder đa ngôn ngữ `bge-reranker-v2-m3` |
| W10 (thiếu cấu hình vector-only, ablation) | Đã xử lý | 5 cấu hình chạy cùng một lệnh benchmark, cùng dev set |
| W12 (`ts_rank` bị gọi là BM25) | Đã xử lý | Thuật ngữ và tài liệu dùng "full-text/lexical"; không có chuỗi "BM25" trong mã hay báo cáo |
| W6 (một độ đo, bộ test nhỏ) | Một phần | Dev set 40 câu, 4 độ đo; tập test độc lập và kiểm định thuộc Giai đoạn 8 |
| W2 (mất cấu trúc bảng/sơ đồ) | Không thuộc phạm vi | Cải thiện parsing thuộc pipeline nạp; giai đoạn này chỉ giữ metadata mục/trang |

## 2. Kết quả kiểm thử

| Hạng mục | Lệnh | Kỳ vọng | Thực tế | Đạt |
| :--- | :--- | :--- | :--- | :--- |
| Unit test tầng truy hồi | `pytest tests/retrieval -q` | Tất cả đạt | `76 passed in 0.68s` | Đạt |
| Toàn bộ test repo | `make -f Makefile test` | Tất cả đạt | `122 passed, 1 warning in 1.20s` | Đạt |
| Lint | `make -f Makefile lint` | Không lỗi | ruff: All checks passed; black: 64 tệp không đổi; eslint: sạch | Đạt |
| Benchmark dev set | `python evaluation/retrieval_bench.py --config config/retrieval.yaml` | 5 cấu hình × 40 câu, không lỗi | 5 cấu hình × 40 câu, 0 lỗi; kết quả tại `retrieval_bench_20261121-103738.{csv,md}`; decomposition tách 15 câu bằng heuristic, tổng 4,9 ms | Đạt |
| 10 truy vấn thủ công | `python evaluation/manual_queries.py` | In top-5 và nhận xét cho 10 câu | Chạy đủ 10 câu, exit 0; kết quả tại `manual_queries_20261121-104240.md`; 7/10 có mục lý thuyết trả lời trực tiếp trong top-5, 1 câu trúng một phần, 2 câu là lỗ hổng phủ của kho | Đạt |
| Mô phỏng reranker quá hạn | `python evaluation/rerank_timeout_demo.py` | `rerank_fallback = "timeout"`, thứ tự trùng RRF | Trực tuyến: `rerank_fallback = 'timeout'`; thứ tự 5 chunk trùng hoàn toàn với hybrid+RRF; tầng rerank 10,9 ms; tổng 1.824 ms. Chạy offline trước đó cho cùng kết quả | Đạt |
| Migration và chỉ mục | Truy vấn `pg_indexes` trên Supabase | Có HNSW, GIN full-text, GIN trigram; RLS bật | `chunks_embedding_hnsw_idx` (hnsw vector_cosine_ops), `chunks_search_vector_unaccented_idx`, `chunks_search_text_trgm_idx`, `chunks_content_trgm_idx`; `RLS chunks = true` | Đạt |
| Toàn vẹn kho tri thức | Truy vấn `documents`/`chunks` | 7 tài liệu, 1.775 chunk | 7 tài liệu; 1.775 chunk = 1.577 `question` + 198 `theory`; 514 chunk cha | Đạt |

Ghi chú số liệu kho: 1.775 chunk gồm 1.577 chunk `question` (1.114 con + 463 cha) và 198 chunk `theory` (147 con + 51 cha); 514 chunk cha; 88,3% chunk con thuộc ngân hàng câu hỏi.

## 3. Bảng so sánh cấu hình

Lần chạy hợp lệ: `evaluation/results/retrieval_bench_20261121-103738.{csv,md}` — 40 câu dev, chấm theo (tài liệu, mục), nhị phân, khử trùng lặp theo mục; chạy sau khi sửa bug decomposition và nhãn thời gian.

### 3.1 So sánh ba cấu hình bắt buộc (và hai cấu hình bổ sung)

| Cấu hình | Recall@5 | MRR | nDCG@10 | p50 (ms) | p95 (ms) | Đạt mục tiêu |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| vector_only | 0,867 | 0,688 | 0,717 | 632 | 705 | Không |
| hybrid_rrf | 0,838 | 0,602 | 0,650 | 705 | 806 | Không |
| **hybrid_rrf_rerank** | **0,900** | **0,825** | **0,817** | 935 | 1.111 | **Có** |
| hybrid_rrf_rerank_adaptive | 0,892 | 0,825 | 0,813 | 961 | 1.305 | Gần đạt (Recall@5 thiếu 0,008) |
| hybrid_rrf_rerank_adaptive_decomposition | 0,892 | 0,825 | 0,813 | 951 | 1.164 | Không đạt Recall@5; chất lượng ngang adaptive |

Mục tiêu: Recall@5 ≥ 0,90; MRR ≥ 0,75; nDCG@10 ≥ 0,80; p95 ≤ 1.500 ms. Cấu hình **hybrid + RRF + rerank** đạt cả bốn.

Nhận xét:

- Hybrid + RRF **thấp hơn** vector-only (0,838 so với 0,867). Với kho nhỏ và trọng số lexical 0,3/trigram 0,2, hai nhánh từ vựng thêm ứng viên nhiễu; reranker đa ngôn ngữ sửa được và đưa lên 0,900 (+0,062 so với vector-only, +0,073 so với hybrid+RRF). Đây là bằng chứng định lượng cho W7.
- Adaptive mất 0,008 Recall@5 do một câu (DS-013) bị cắt xuống k = 4 trong khi nhãn có 3 mục; hai mục vẫn trúng, một mục rơi khỏi top-4.
- Decomposition (heuristic-only vì benchmark tắt LLM để tái lập) tách 15/40 câu, tổng thời gian decompose 4,9 ms; Recall/MRR/nDCG trùng khít adaptive trên cả 40 câu (0/40 dòng khác biệt). Nguyên nhân: rerank chấm lại theo **truy vấn gốc** trên pool đã hợp nhất nên khác biệt giữa các truy vấn con bị san phẳng ở bước cuối. Chế độ LLM-assisted chưa được đo; vì vậy không có bằng chứng định lượng để bật decomposition mặc định — `config/retrieval.yaml` đặt `enabled: false`, profile benchmark vẫn bật riêng để tái lập phép ablation.

### 3.2 Độ trễ từng tầng (p50 / p95, ms)

Bảng lấy trực tiếp từ tệp `.md` của lần chạy sạch `retrieval_bench_20261121-103738`; nhãn `select` đã đúng ngữ nghĩa (`select` chỉ là bước chọn top-k, `parent` là toàn bộ thời gian đọc chunk cha).

| Cấu hình | classify | decompose | embed | vector | lexical | trigram | fusion | parent | rerank | select | total |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| vector_only | 0 / 0 | 0 / 0 | 339 / 379 | 195 / 255 | 0 / 0 | 0 / 0 | 0 / 0 | 93 / 98 | 0 / 0 | 0 / 0 | 632 / 705 |
| hybrid_rrf | 0 / 0 | 0 / 0 | 329 / 420 | 196 / 246 | 235 / 278 | 258 / 365 | 0 / 0 | 93 / 95 | 0 / 0 | 0 / 0 | 705 / 806 |
| hybrid_rrf_rerank | 0 / 1 | 0 / 0 | 345 / **430** | 196 / 248 | 234 / 264 | 259 / 360 | 0 / 0 | 90 / 135 | 193 / 397 | 0 / 0 | 935 / 1.111 |
| hybrid_rrf_rerank_adaptive | 0 / 1 | 0 / 0 | 366 / 420 | 215 / 287 | 252 / 336 | 268 / **457** | 0 / 0 | 98 / 147 | 191 / 415 | 0 / 0 | 961 / 1.305 |
| hybrid_rrf_rerank_adaptive_decomposition | 0 / 1 | 0 / 0 | 386 / **435** | 205 / 253 | 244 / 281 | 261 / 342 | 0 / 1 | 93 / 137 | 195 / 395 | 0 / 0 | 951 / 1.164 |

- **Tầng chậm nhất theo p95:** cấu hình rerank là **embed (430 ms)**; hybrid_rrf là embed (420 ms); vector_only là embed (379 ms); adaptive là **trigram (457 ms)**; decomposition là embed (435 ms).
- Embedding là tầng chậm nhất theo p50 ở cả năm cấu hình và là chi phí mạng duy nhất; ba nhánh SQL chạy song song nên p95 tổng không cộng dồn p95 từng nhánh.
- Tầng rerank có p95 397–415 ms khi bật — dưới mức trần timeout 3.000 ms.
- Cả năm cấu hình đều dưới ngưỡng p95 1.500 ms; cao nhất là adaptive 1.305 ms. p95 dao động giữa các lần chạy (adaptive 1.000 → 1.305 ms) do tải máy, nên chỉ nên đọc đây là trần đo được, không phải hằng số.

### 3.3 Theo loại câu (cấu hình rerank)

| Loại | Số câu | Recall@5 | MRR | nDCG@10 |
| :--- | ---: | ---: | ---: | ---: |
| tra_cuu | 10 | 1,000 | 0,850 | 0,886 |
| so_sanh | 10 | 1,000 | 0,800 | 0,852 |
| nhieu_rang_buoc | 10 | 0,800 | 0,900 | 0,793 |
| tron_thuat_ngu | 10 | 0,800 | 0,750 | 0,739 |

Câu nhiều ràng buộc có MRR cao nhất nhưng Recall@5 thấp hơn vì hai câu cần hai mục mà chỉ trúng một (DS-005, DS-006). Câu trộn thuật ngữ tiếng Anh thấp nhất do hai câu có nhãn nằm ngoài chỉ mục (DS-039, DS-040).

## 4. Phân tích 5 lỗi truy hồi tiêu biểu

### 4.1 DS-014 — rerank đẩy mục đúng ra khỏi top-5 (hồi quy)

- **Câu hỏi:** "Ứng dụng trong private subnet cần gọi S3 và DynamoDB nhưng không được đi qua NAT Gateway, đồng thời phải giới hạn được tài nguyên nào được phép truy cập…"
- **Nhãn:** `VPC_Networking.pdf` — Mục 1.8 "VPC Endpoint và AWS PrivateLink".
- **Kết quả:** vector-only Recall@5 = 1,0; hybrid+RRF = 1,0; **hybrid+RRF+rerank = 0,0** (MRR 0,0). Đây là trường hợp duy nhất reranker đẩy mục đúng ra hoàn toàn khỏi top-5 (1,0 → 0,0).
- **Top-5 thực tế (lần chạy sạch):** 1) Mục 1.3 "NAT Gateway, NAT Instance và chi phí…" — 0,984; 2) Mục 1.2 "Subnet, route table và Internet Gateway" — 0,982; 3) exam guide Mục 1.2 — 0,171; 4) Mục 1.13 — 0,050; 5) Mục 1.7 — 0,002. Mục 1.8 không có mặt.
- **Phân tích:** hai mục đứng đầu khớp bề mặt với "NAT Gateway" và hạ tầng mạng private, đạt điểm rerank gần bão hòa trong khi mục đúng vắng mặt. Cross-encoder ưu tiên khớp từ khóa "NAT Gateway" hơn khái niệm "gateway endpoint" của Mục 1.8.
- **Hướng xử lý:** thử đưa cả nội dung chunk con vào văn bản rerank (thay vì chỉ mục cha) cho câu nhiều ràng buộc, hoặc thêm tín hiệu khớp tiêu đề mục vào đầu vào cross-encoder; đo lại trên dev set trước khi đổi mặc định.

### 4.2 DS-005 — trúng 1/2 mục (thiếu mục xác nhận định lượng)

- **Nhãn:** Mục 1.13 (chọn lớp theo tình huống) và Mục 1.8 (Glacier Deep Archive: Bulk ~48 giờ, lưu tối thiểu 180 ngày) của `S3_Storage_Classes.pdf`.
- **Kết quả:** Recall@5 = 0,5, MRR = 1,0 — Mục 1.8 đứng hạng 1 (0,995), Mục 1.13 ngoài top-5.
- **Top-5 thực tế:** 1) Mục 1.8 — 0,995; 2) Mục 1.4 — 0,992; 3) Mục 1.5 — 0,991; 4) Mục 1.7 — 0,991; 5) Mục 1.6 — 0,991.
- **Phân tích:** câu hỏi có hai vế (chọn lớp rẻ nhất và thời gian lưu tối thiểu). Reranker giữ đúng mục chứa con số 48 giờ/180 ngày nhưng bốn mục còn lại đều là các lớp lưu trữ riêng lẻ với điểm gần bão hòa (chênh 0,004); mục "chọn lớp theo tình huống" (1.13) bị đẩy ra. Văn bản rerank là cả mục cha nên các mục lớp có nội dung gần nhau san phẳng điểm.
- **Hướng xử lý:** với câu `nhieu_rang_buoc`, chấm điểm ở mức chunk con (có tiêu đề mục) thay vì mục cha, hoặc tăng `max_length` cho nhóm câu này; thử nghiệm có kiểm soát trên dev set.

### 4.3 DS-006 — trúng 1/2 mục (thiếu mục quy tắc 30 ngày)

- **Nhãn:** Mục 1.10 (lifecycle rule) và Mục 1.4 (Standard-IA, lưu tối thiểu 30 ngày) của `S3_Storage_Classes.pdf`.
- **Kết quả:** Recall@5 = 0,5, MRR = 1,0 — Mục 1.4 hạng 1 (0,976), Mục 1.10 (lifecycle) ngoài top-5.
- **Top-5 thực tế:** 1) Mục 1.4 — 0,976; 2) Mục 1.6 — 0,962; 3) Mục 1.5 — 0,956; 4) Mục 1.3 — 0,713; 5) Mục 1.2 — 0,652.
- **Phân tích:** cùng dạng với DS-005 — câu hỏi đòi hai mảnh thông tin ở hai mục; rerank giữ được mục nêu quy tắc 30 ngày của Standard-IA nhưng mục lifecycle (1.10) bị các mục lớp lưu trữ khác chiếm chỗ. Quy tắc 30 ngày cũng xuất hiện ở One Zone-IA nên tín hiệu từ vựng không phân biệt được mục đích, nhưng đây chỉ là giả thuyết.
- **Hướng xử lý:** như DS-005; cân nhắc thêm bước "mở rộng mục liên quan" khi điểm rerank của các ứng viên sát nhau (chênh < 0,05) để lấy thêm một mục trong cùng tài liệu.

### 4.4 DS-039 — nhãn trỏ tới mục không tồn tại trong chỉ mục

- **Câu hỏi:** dịch vụ thuộc nhóm Networking and Content Delivery theo Exam Guide; Global Accelerator và Transit Gateway có trong danh sách không.
- **Nhãn:** `aws-saa-exam-guide.pdf` — Mục 5.2.13.
- **Kết quả:** 0,0 ở cả năm cấu hình.
- **Bằng chứng:** tài liệu exam guide trong kho có 34 mục phân biệt; danh sách gồm 5.2.12 và 5.2.14 nhưng **không có 5.2.13**. Nhãn này không thể trúng với bất kỳ bộ truy hồi nào trên chỉ mục hiện tại.
- **Hướng xử lý:** thuộc phạm vi nạp dữ liệu — rà lại parsing exam guide để không mất mục 5.2.13 (và 5.2.4, 5.3.5 ở DS-040); sau khi nạp lại phải chạy lại benchmark. Không sửa nhãn để "cho đẹp" số liệu.

### 4.5 DS-040 — hai nhãn đều trỏ tới mục không tồn tại

- **Câu hỏi:** Amazon Lightsail có trong scope thi không, thuộc nhóm Compute in-scope hay out-of-scope, kể tên dịch vụ Compute in-scope.
- **Nhãn:** Mục 5.3.5 và 5.2.4 của exam guide.
- **Kết quả:** 0,0 ở cả năm cấu hình.
- **Bằng chứng:** chỉ mục có 5.3.4 và 5.3.7 nhưng **không có 5.3.5**; **không có 5.2.4**. Cùng gốc với DS-039.
- **Hướng xử lý:** như DS-039. Hai câu này đặt trần lý thuyết của Recall@5 trên dev set ở 38/40 = 0,950; mức 0,900 hiện tại còn cách trần 0,05, tương ứng đúng ba lỗi còn sửa được (DS-014, DS-005, DS-006).

### 4.6 Ghi chú thêm về nhãn

- **DS-030:** nhãn là Mục 1.4 ("Amazon EBS — các loại volume và snapshot") nhưng khi đối chiếu nội dung đã nạp, các con số gp3 (3.000 IOPS, 125 MiB/s, tối đa 16.000 IOPS, 1.000 MiB/s) nằm trong chunk Mục 1.3. Cấu hình rerank vẫn trúng nhãn 1.4 (Recall@5 = 1,0) nên không tính là lỗi truy hồi, nhưng nhãn và nội dung lệch nhau — cần rà khi làm sạch bộ đánh giá.
- **DS-013:** adaptive cắt k = 4 trong khi nhãn có 3 mục nên mất một mục; đây là đánh đổi có chủ đích của top-k thích ứng, không phải lỗi truy hồi.

## 5. Vấn đề và rủi ro

1. **Hạn mức Gemini — đã giải quyết:** khóa mới được thêm ngày 2026-11-21; probe embedding trả HTTP 200 với vector 768 chiều. Benchmark sạch, 10 truy vấn thủ công và timeout demo trực tuyến đều đã chạy xong; không còn hạng mục bị chặn. Rủi ro còn lại: hạn mức miễn phí vẫn có thể cạn nếu chạy benchmark nhiều lần trong ngày — cần theo dõi hoặc dùng khóa dự phòng.
2. **Decomposition chưa chứng minh được lợi ích:** lần chạy sạch cho kết quả trùng khít adaptive (0/40 câu khác biệt) ở chế độ heuristic, trong khi chế độ LLM-assisted chưa được đo. `config/retrieval.yaml` đặt `decomposition.enabled: false`; chỉ bật lại khi có phép đo cho chế độ LLM và p95 vẫn ≤ 1,5 giây.
3. **Nhãn thời gian từng tầng — đã xử lý:** `select_ms` từng bao gồm thời gian nạp chunk cha; lần chạy sạch ghi trực tiếp `select`/`parent` tách bạch (bảng 3.2).
4. **Độ phủ kho tri thức và bộ lọc nguồn:** 7 tài liệu, 1.775 chunk; 88,3% chunk con là ngân hàng câu hỏi. Bộ lọc nguồn (`exclude_kinds: [question]`) giúp câu hỏi lý thuyết nhưng tạo lỗ hổng khi kiến thức chỉ có trong ngân hàng câu hỏi: 10 truy vấn thủ công có hai ca như vậy — quy tắc peering không bắc cầu chỉ nằm ở Câu 71 (Q2) và so sánh Transfer Acceleration/CloudFront chỉ nằm ở Câu 166/111/10 (Q10, sau lọc còn 2 ứng viên, k = 2). Dev set không có nhãn nào trỏ vào ngân hàng câu hỏi nên kết quả có thể lạc quan cho kịch bản hỏi đề.
5. **Lỗi nhãn dev set:** 40 câu / 53 nhãn; 3 nhãn (5.2.13 của DS-039; 5.3.5 và 5.2.4 của DS-040) không tồn tại trong chỉ mục; DS-030 lệch mục. Không sửa nhãn trong giai đoạn này để tránh tinh chỉnh theo kết quả; ghi nhận và xử lý ở khâu nạp dữ liệu/đánh giá.
6. **Top-k thích ứng đánh đổi Recall:** mất 0,008 Recall@5 (DS-013) để giảm số chunk đưa vào LLM. Cần đo thêm chi phí token và chất lượng câu trả lời ở giai đoạn sinh trước khi chốt mặc định.
7. **Cache trong bộ nhớ tiến trình:** TTL 1 giờ nhưng không chia sẻ giữa các tiến trình/worker; khi triển khai nhiều worker (giai đoạn sau) cần cân nhắc cache ngoài hoặc chấp nhận tỷ lệ trúng thấp.
8. **Độ trễ còn dư địa:** p95 cao nhất 1,305 giây (adaptive) so với mục tiêu 1,5 giây; cấu hình rerank 1,111 giây với embed p95 430 ms. Biên an toàn mỏng hơn lần chạy trước (adaptive từng 1,000 ms) do dao động tải máy; nếu bật decomposition có LLM, p95 có thể vượt ngưỡng.
9. **Lệch đánh số giai đoạn giữa CLAUDE.md và đề bài** (đã nêu ở đầu báo cáo).
10. **W12:** không dùng chữ "BM25" cho full-text PostgreSQL ở bất kỳ đâu; đã kiểm tra mã nguồn và tài liệu.

## 6. Đề xuất cho giai đoạn 3

1. **Giữ nguyên hợp đồng API:** dùng `retrieve(query, top_k=None)` → `RetrievalResult`; trường `chunks[i].content` là nội dung mục cha (ngữ cảnh), `child_content` là chunk con, `document/section/heading/page` lấy từ chunk con để trích dẫn. Không đổi chữ ký này khi tích hợp.
2. **Truyền ngân sách token:** tôn trọng `top_k.token_budget` khi ghép ngữ cảnh; nếu prompt cần thêm ngữ cảnh hội thoại (W4), hạ top-k thay vì cắt ngữ cảnh mục cha.
3. **Xử lý fallback tường minh:** kiểm tra `result.rerank_fallback`; khi có giá trị, ghi log mức warn kèm định danh truy vấn (không log khóa) và vẫn trả kết quả RRF.
4. **Khởi động nóng:** tạo service một lần khi khởi động ứng dụng (warmup reranker + mở kết nối), không khởi tạo theo từng yêu cầu.
5. **Xử lý lỗi nạp exam guide:** bổ sung mục 5.2.13, 5.3.5, 5.2.4 vào chỉ mục trước khi chốt bộ đánh giá; sau đó chạy lại benchmark để trần Recall@5 phản ánh đúng dữ liệu.
6. **Thử nghiệm có kiểm soát cho câu nhiều ràng buộc:** rerank theo chunk con + tiêu đề mục; mở rộng mục liên quan khi điểm sát nhau. Chỉ đổi mặc định nếu Recall@5 trên dev set tăng và p95 vẫn ≤ 1,5 giây.
7. **Đo chế độ decomposition có LLM trước khi bật mặc định:** hiện `enabled: false` trong config; nếu đo thấy Recall@5 tăng và p95 ≤ 1,5 giây mới bật, giới hạn 2 truy vấn con.
8. **Bổ sung test tích hợp nhẹ:** một test chạy service thật với store giả (không gọi mạng) cho luồng đầy đủ, và test cache theo fingerprint cấu hình.

## 7. Xác nhận Definition of Done

| Hạng mục | Trạng thái | Bằng chứng |
| :--- | :--- | :--- |
| Config đầy đủ tham số, không hard-code | Đạt | `config/retrieval.yaml`; `test_config.py` kiểm giá trị mặc định và override |
| Vector search pgvector + full-text tiếng Việt + trigram tiếng Anh | Đạt | `store.py`, migration `20261121090000_retrieval_phase2.sql`; chỉ mục xác nhận bằng `pg_indexes` |
| RRF với k đọc từ config | Đạt | `fusion.py`, `test_fusion.py` |
| Rerank cross-encoder cục bộ, batch, timeout + fallback | Đạt | `rerank.py`, `test_rerank.py`; demo trực tuyến: `rerank_fallback='timeout'`, thứ tự trùng RRF, rerank 10,9 ms |
| Top-k thích ứng 3–8 theo loại câu + ngân sách token | Đạt | `classify.py`, `topk.py`, `test_topk.py`, `test_classify.py`; đo trên dev set (adaptive 0,892) |
| Cha–con: trả mục cha, giữ liên kết chunk con | Đạt | `service.py` (`_to_retrieved`), `test_service.py` |
| Decomposition 2–3 truy vấn con, bật/tắt bằng config | Đạt | `decompose.py`, `test_decompose.py`; lần chạy sạch: 15/40 câu tách bằng heuristic, 4,9 ms, metrics ngang adaptive; mặc định `enabled: false` vì chưa có lợi ích đo được |
| Cache theo hash truy vấn, TTL 1 giờ | Đạt | `cache.py`, `test_cache.py`, `test_service.py` |
| Benchmark Recall@5, MRR, nDCG@10, p50/p95, CSV + Markdown | Đạt | `evaluation/retrieval_bench.py`; `retrieval_bench_20261121-103738.{csv,md}` |
| So sánh 3 cấu hình + adaptive + decomposition | Đạt | Mục 3.1 |
| 10 truy vấn thủ công, top-5 kèm nhận xét | Đạt | `manual_queries_20261121-104240.md`; 10 câu, exit 0 |
| p95 từng tầng và tầng chậm nhất | Đạt | Mục 3.2, lấy trực tiếp từ `.md` của lần chạy sạch |
| Mô phỏng reranker timeout, xác nhận fallback | Đạt | Trực tuyến: `evaluation/results/timeout_demo_online.log`; offline bổ sung: `timeout_demo_offline.log` |
| Không gọi reranker/LLM thật trong unit test | Đạt | Toàn bộ `tests/retrieval` dùng mock/Fake; 76 test chạy 0,68 giây |
| API nội bộ ổn định `retrieve(query, top_k=None)` | Đạt | `service.py:146`, hàm module-level `retrieve` |
| Lint và test toàn repo | Đạt | `make -f Makefile lint` sạch; `make -f Makefile test` 122 passed |
| Không dùng tập test ngoài để tinh chỉnh | Đạt | Chỉ dùng `evaluation/dev_set.jsonl`; `data/external_test/` không được đọc |
| Không lộ khóa/bí mật | Đạt | Báo cáo không chứa giá trị khóa hay chuỗi kết nối; chỉ nêu tên biến |

**Kết luận:** toàn bộ Definition of Done đã đạt. Cấu hình **hybrid + RRF + rerank** đạt cả bốn mục tiêu trên dev set (Recall@5 0,900; MRR 0,825; nDCG@10 0,817; p95 1.111 ms). Adaptive và decomposition không thêm chất lượng đo được trong lần chạy sạch — adaptive mất 0,008 Recall@5, decomposition trùng kết quả adaptive — nên decomposition để tắt mặc định, adaptive giữ bật và sẽ được đánh giá tiếp ở giai đoạn sinh câu trả lời. Trạng thái tổng thể: **HOÀN THÀNH**.
