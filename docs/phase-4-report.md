# BÁO CÁO GIAI ĐOẠN 4

**Trạng thái: MỘT PHẦN**

Ngày: 2026-11-22 (giờ địa phương; log và API ghi theo UTC).

Phạm vi: hội thoại đa lượt có phiên, viết lại câu hỏi phụ thuộc ngữ cảnh, tóm tắt phần cũ
của hội thoại, streaming SSE cho `/chat/stream`, ghi độ trễ và token vào `query_logs`,
RLS theo người dùng, hook `useChatStream` cho frontend, và bộ 10 kịch bản hội thoại
(`inputs/conversations.md`). Không bao gồm giao diện chat hoàn chỉnh (Giai đoạn 5).

> **Lưu ý đánh số giai đoạn:** CLAUDE.md xếp hội thoại + streaming vào **Giai đoạn 6**;
> đề bài gọi công việc này là **Giai đoạn 4**. Báo cáo giữ cách gọi của đề bài.

> **Vì sao trạng thái là MỘT PHẦN:** hai tiêu chí nghiệm thu không đạt — bộ 10 kịch bản chỉ
> đạt **2/10** (ngưỡng ≥ 8/10) và TTFT p95 **14.874,9 ms** (ngưỡng ≤ 2.000 ms; tổng thời gian
> p95 23.455,4 ms so với ngưỡng ≤ 10.000 ms). Nguyên nhân chính là khóa Gemini hết hạn mức
> (HTTP 429) nên mọi câu trả lời do DeepSeek sinh, cộng với prompt dài và prefill chậm.
> Các tiêu chí còn lại đều đạt; xem mục 2 và mục 8.

## 1. Việc đã làm

### 1.1 Lược đồ dữ liệu

- `supabase/migrations/20261122000000_conversation_phase4.sql`:
  - `sessions`: thêm `summary`, `summary_updated_at`, `summary_message_count`, `token_count`,
    `message_count`; đặt `user_id NOT NULL` và khóa ngoại `auth.users` với `ON DELETE CASCADE`.
  - `messages`: thêm `token_count`, `rewritten_query`, `request_id`; chỉ mục duy nhất
    `(session_id, request_id)` khi `request_id` khác NULL để chống gửi trùng.
  - `query_logs`: thêm `ttft_ms`, `total_latency_ms`, `streaming`, `user_id`, `status`,
    `conversation_tokens`.
  - RLS: bốn policy `sessions_select_own`, `sessions_insert_own`, `sessions_update_own`,
    `sessions_delete_own`; policy cho `messages` kiểm tra chủ sở hữu phiên qua truy vấn con.
    Chỉ cấp quyền cho `authenticated`; `query_logs` để RLS đóng hoàn toàn.
- `supabase/migrations/20261122010000_messages_seq.sql`: thứ tự tin nhắn ổn định trong phiên.

### 1.2 API phiên

Các endpoint (đều yêu cầu Bearer token; sai chủ sở hữu trả 404, thiếu token trả 401):

| Phương thức | Đường dẫn | Chức năng |
| :--- | :--- | :--- |
| POST | `/sessions` | Tạo phiên |
| GET | `/sessions` | Liệt kê phiên của chính người dùng |
| GET | `/sessions/{id}/messages` | Đọc tin nhắn của phiên |
| PATCH | `/sessions/{id}` | Đổi tiêu đề |
| DELETE | `/sessions/{id}` | Xóa một phiên |
| DELETE | `/sessions` | Xóa toàn bộ phiên của người dùng |

`/chat` một lượt được giữ nguyên hợp đồng cũ; `session_id` là tùy chọn, không có phiên thì
hành vi như trước. `/chat/stream` là endpoint mới.

### 1.3 Hội thoại: viết lại câu hỏi và tóm tắt

- `backend/app/services/conversation/condense.py`: câu hỏi phụ thuộc ngữ cảnh được viết lại
  thành câu độc lập bằng một lần gọi LLM nhẹ (4 lượt gần nhất, tối đa 256 token đầu ra,
  timeout 8 giây). Lưu cả câu gốc và câu viết lại (`rewritten_query`), kèm nguồn viết lại
  (`none`/`llm`/`fallback`/`topic_shift`) trong metadata.
- Phát hiện đổi chủ đề: khi câu hỏi mới không còn liên quan chủ đề trước, ngữ cảnh cũ bị loại
  và tóm tắt được đặt lại; có kiểm thử riêng.
- `backend/app/services/conversation/summarize.py`: sau 10 lượt hoặc 4.000 token, phần cũ được
  tóm tắt ở luồng nền (2 worker), giữ 6 lượt gần nhất nguyên văn, tóm tắt tối đa 400 token.
  Nếu LLM tóm tắt lỗi, dùng tóm tắt dự phòng có ghi nguồn `fallback`.
- `backend/app/services/conversation/context.py`: ngân sách ngữ cảnh hội thoại
  `max_conversation_tokens: 1500`, ước lượng 3,0 ký tự/token, cắt bớt tin nhắn cũ khi vượt.
- Cấu hình tại `config/conversation.yaml`.

### 1.4 Streaming SSE

- `POST /chat/stream` trả `text/event-stream` với các sự kiện `meta`, `token`, `citations`,
  `done`, `error`; mỗi sự kiện được flush ngay, không chờ sinh xong.
- Bộ sinh đồng bộ chạy trong luồng nền, đẩy sự kiện qua `queue.Queue`; lớp async đọc hàng đợi
  và ghi ra response. Khi client ngắt kết nối, `GeneratorExit` dừng bộ sinh, phần câu trả lời
  đã nhận được lưu với `stream_status = "interrupted"`.
- `AnswerStreamExtractor` trong `backend/app/services/generation/streaming.py` trích trường
  `"answer"` của JSON ngay khi mô hình còn sinh, không đợi toàn bộ JSON; đã sửa lỗi thứ tự
  nhánh khiến token đầu tiên bị nuốt và bổ sung 9 kiểm thử.
- `/chat` một lượt không bị thay đổi hành vi.

### 1.5 Đo lường

- `query_logs` ghi `ttft_ms`, `total_latency_ms`, `prompt_tokens`, `completion_tokens`,
  `streaming`, `status`, `conversation_tokens`.
- Metadata của mỗi tin nhắn trợ lý ghi `conversation_tokens`, `conversation_messages`,
  `summary_used`, `rewrite_source`, `condensation_latency_ms`, `citation_validity`.
- Không ghi khóa, token hay chuỗi kết nối vào log.

### 1.6 Frontend

- `frontend/hooks/useChatStream.ts`: hook đọc SSE, phân phát sự kiện `meta`/`token`/`citations`/
  `done`/`error`, hủy khi unmount và tự kết nối lại có backoff khi mất mạng tạm thời. Hook
  chưa được gắn vào trang giao diện (để Giai đoạn 5).

### 1.7 Bộ đánh giá 10 kịch bản

- `inputs/conversations.md`: 10 kịch bản, mỗi kịch bản 4 lượt, có hành vi mong đợi và tiêu chí.
- `evaluation/conversation_bench.py`: chạy trên `ChatService` + `GenerationService` + tầng truy
  hồi thật, dùng `InMemorySessionRepository`; judge phiên bản v2, 3 phiếu, lấy trung vị
  (≥0,75 → 1,0; ≥0,25 → 0,5), nhiệt độ 0; mỗi lượt còn phải đạt các kiểm tra tự động
  (trích dẫn đúng tài liệu/mục, câu viết lại giữ đủ thực thể, từ chối không rò rỉ…).
  Kịch bản chỉ đạt khi cả 4 lượt đạt.
- Kết quả lưu tại `evaluation/results/conversation_bench_20261122-130341.json` và `.md`;
  lượt chạy quan sát riêng KB-01 tại `conversation_bench_20261122-130909.*`.

### 1.8 Script vận hành

`scripts/phase4_serve.py` (chạy backend với provider chỉ định), `phase4_ttft_measure.py`
(20 mẫu SSE), `phase4_budget_check.py` (12 lượt thật), `phase4_isolation_check.py` (hai tài
khoản), `phase4_disconnect_check.py` (ngắt giữa chừng).

### 1.9 Kiểm thử

`tests/sessions/` (5 tệp) và `tests/streaming/` (3 tệp) gồm 40 kiểm thử: API phiên, repository,
viết lại câu hỏi, tóm tắt, ngân sách ngữ cảnh, SSE, ngắt kết nối, trích xuất answer. Toàn bộ
backend có 269 kiểm thử.

## 2. Kết quả kiểm thử

| Hạng mục | Lệnh | Kỳ vọng | Thực tế | Đạt |
| :--- | :--- | :--- | :--- | :---: |
| Kiểm thử phiên + streaming | `pytest tests/sessions tests/streaming -q` | Tất cả đạt | `40 passed, 1 warning in 0.89s` | ĐẠT |
| Toàn bộ backend | `pytest -q` | Không hồi quy | `269 passed, 1 warning in 2.03s` | ĐẠT |
| Lint backend | `ruff check backend tests` + `black --check backend tests evaluation scripts` | Sạch | Sạch (2026-11-22) | ĐẠT |
| 10 kịch bản hội thoại | `python evaluation/conversation_bench.py --provider deepseek_fallback` | ≥ 8/10 | **2/10** (26/40 lượt), 1.111,1 giây | KHÔNG ĐẠT |
| TTFT | `python scripts/phase4_ttft_measure.py` | p95 ≤ 2.000 ms | p50 **4.969,1 ms**, p95 **14.874,9 ms**; 20/20 mẫu, 0 lỗi | KHÔNG ĐẠT |
| Tổng thời gian | `python scripts/phase4_ttft_measure.py` | p95 ≤ 10.000 ms | p95 **23.455,4 ms** | KHÔNG ĐẠT |
| Cách ly hai tài khoản | `python scripts/phase4_isolation_check.py` | A không đọc/ghi được dữ liệu của B | **19/19 kiểm tra đạt** | ĐẠT |
| Ngắt giữa chừng | `python scripts/phase4_disconnect_check.py` | Dừng sinh, không 500 | `stream_status = interrupted`, lưu 12 ký tự, không 500/Traceback | ĐẠT |
| Ngân sách ngữ cảnh sau 12 lượt | `python scripts/phase4_budget_check.py` | ≤ 1.500 token | Lớn nhất **1.420 token** | ĐẠT |
| Hồi quy dev set Giai đoạn 3 | `python evaluation/gen_bench.py --before-after --provider deepseek_fallback --judge deepseek_fallback --workers 4` | ≥ 91,5% (không giảm quá 1 điểm %) | **96,2%** độ chính xác trung bình; 92,5% đúng hoàn toàn; 0 lỗi schema; lưu `gen_bench_20261122-165948` | ĐẠT |
| Tương thích `/chat` một lượt | 12 lượt budget + dev bench gọi qua tầng sinh cũ | Không đổi hợp đồng | Chạy thành công, kiểm thử cũ đạt | ĐẠT |

Đối chiếu hồi quy: báo cáo Giai đoạn 3 ghi 92,5% độ chính xác trung bình sau CoT; lượt chạy
này đạt 96,2%, trên sàn 91,5% nên không có hồi quy. Trong lượt chạy này trước và sau CoT đều
96,2% (chênh 0,0 điểm %), nên tiêu chí "CoT tăng ≥ 5 điểm %" của Giai đoạn 3 vẫn chưa đạt —
Giai đoạn 4 không thay đổi prompt sinh. Chi phí judge 0 USD (DeepSeek), 0 lỗi schema cuối.

## 3. Bảng 10 kịch bản

Kết quả lượt chạy đầy đủ (`conversation_bench_20261122-130341`), provider `deepseek_fallback`:

| Kịch bản | Số lượt | Đạt | Ghi chú |
| :--- | :---: | :---: | :--- |
| KB-01 | 4 | KHÔNG | Lượt 3 judge 0,5 — so sánh đúng nhưng thiếu ý bắt buộc |
| KB-02 | 4 | ĐẠT | 4/4 lượt đạt |
| KB-03 | 4 | KHÔNG | Lượt 1 và 4 judge 0,5 — thiếu chi tiết về trust policy/thời hạn |
| KB-04 | 4 | KHÔNG | Lượt 2 và 4 judge 0,5 — thiếu ngoại lệ Multi-AZ/Read Replica |
| KB-05 | 4 | KHÔNG | Lượt 3 judge 0,5 — thiếu ý về NACL/security group |
| KB-06 | 4 | KHÔNG | Lượt 1, 3, 4 judge 0,5 — thiếu mốc lưu tối thiểu của lớp |
| KB-07 | 4 | KHÔNG | Lượt 3 và 4 judge 0,5 — thiếu điều kiện dùng On-Demand |
| KB-08 | 4 | KHÔNG | Lượt 2 trượt kiểm tra trích dẫn tự động (tầng truy xuất) |
| KB-09 | 4 | KHÔNG | Lượt 2 và 3 judge 0,5 — thiếu ý về NAT instance/gateway |
| KB-10 | 4 | ĐẠT | 4/4 lượt đạt, gồm hai lượt từ chối đúng |

**Tổng: 2/10 kịch bản, 26/40 lượt đạt.** Ngưỡng nghiệm thu ≥ 8/10 không đạt. Phần lớn lỗi
là judge cho 0,5 vì thiếu một chi tiết bắt buộc trong câu trả lời, không phải truy xuất sai;
riêng KB-08 lượt 2 là lỗi trích dẫn của tầng truy xuất. Đây là bộ nghiệm thu đã đóng băng,
không dùng để tinh chỉnh trong giai đoạn phát triển.

## 4. TTFT và độ trễ

Đo bằng `scripts/phase4_ttft_measure.py`: mỗi mẫu một phiên mới, một câu hỏi khác nhau, gọi
`POST /chat/stream` bằng `curl -N`, backend chạy cục bộ với provider `deepseek_fallback`.
`meta` là thời điểm nhận sự kiện đầu tiên (phiên + viết lại câu hỏi xong); TTFT tính đến sự
kiện `token` đầu tiên, tức đã gồm truy xuất, xếp hạng lại và prefill của mô hình.

| Mẫu | meta (ms) | TTFT (ms) | Tổng (ms) |
| :---: | ---: | ---: | ---: |
| 01 | 424,7 | 7.647,8 | 13.189,9 |
| 02 | 448,7 | 14.874,9 | 23.455,4 |
| 03 | 437,2 | 18.097,5 | 28.561,9 |
| 04 | 411,4 | 4.969,1 | 8.233,4 |
| 05 | 391,1 | 4.890,4 | 6.832,0 |
| 06 | 396,1 | 4.344,7 | 8.822,4 |
| 07 | 395,9 | 4.504,7 | 7.134,6 |
| 08 | 599,1 | 7.538,6 | 15.197,7 |
| 09 | 361,4 | 4.772,1 | 9.321,6 |
| 10 | 390,4 | 4.363,1 | 6.389,2 |
| 11 | 390,6 | 4.491,8 | 7.068,5 |
| 12 | 389,2 | 2.759,8 | 6.306,8 |
| 13 | 573,0 | 7.426,0 | 15.458,1 |
| 14 | 376,4 | 6.178,3 | 9.480,3 |
| 15 | 408,1 | 3.725,4 | 7.109,4 |
| 16 | 391,5 | 6.249,8 | 13.414,0 |
| 17 | 419,4 | 4.273,5 | 6.739,1 |
| 18 | 364,9 | 5.371,4 | 9.145,8 |
| 19 | 392,1 | 8.004,6 | 16.253,0 |
| 20 | 413,2 | 9.170,6 | 18.791,8 |

- **TTFT p50 = 4.969,1 ms; p95 = 14.874,9 ms** (mục tiêu p95 ≤ 2.000 ms — không đạt).
- **Tổng thời gian p95 = 23.455,4 ms** (mục tiêu ≤ 10.000 ms — không đạt).
- 20/20 mẫu hợp lệ, không có sự kiện `error`.

Phân tích: `meta` chỉ 361–599 ms, nên độ trễ nằm ở truy xuất + xếp hạng lại + prefill. Lần đo
SSE trực tiếp trước đó ghi nhận prompt 12.292 token và completion 1.953 token cho một câu hỏi;
`max_context_tokens: 8000` là ngân sách ước lượng theo 3,5 ký tự/token, trong khi tiếng Việt
thực tế tốn nhiều token hơn, nên prompt thật vượt 8.000 token. Lượt hồi quy dev set cũng ghi
token vào trung bình 9.832,5 sau CoT, xác nhận khoảng cách này. DeepSeek phải prefill toàn bộ
prompt trước khi sinh token đầu tiên; Gemini (mô hình mặc định) vẫn trả HTTP 429 nên không
dùng được.

## 5. Cách ly dữ liệu và bảo mật phiên

- RLS bật trên `sessions`, `messages`, `query_logs`. `sessions` chỉ chủ sở hữu đọc/ghi/sửa/xóa;
  `messages` kiểm tra quyền qua phiên cha; `query_logs` không cấp quyền cho `anon`/`authenticated`.
- Kiểm thử `scripts/phase4_isolation_check.py` dùng hai tài khoản Supabase thật (A và B) và
  kiểm tra cả PostgREST lẫn FastAPI: **19/19 đạt**, gồm:
  - B đọc danh sách phiên của A: 0 dòng; B ghi tin nhắn vào phiên A: 403; B sửa/xóa phiên A:
    0 dòng; phiên A còn nguyên sau khi B xóa.
  - A không thể tạo phiên gán cho B: 403.
  - Qua API: B gọi `GET/PATCH/DELETE /sessions/{id}` của A đều nhận 404; B hỏi tiếp vào phiên
    A nhận 404; không có token nhận 401.
  - `DELETE /sessions` của A xóa đúng phiên của A, không ảnh hưởng phiên của B.
- Xóa dữ liệu: `DELETE /sessions/{id}` xóa một phiên (tin nhắn xóa theo khóa ngoại cascade);
  `DELETE /sessions` xóa toàn bộ phiên của người dùng. Hai người dùng tạm được xóa sau kiểm thử.
- Không lưu nội dung nhạy cảm ngoài nội dung hội thoại cần thiết; không ghi khóa, token hay
  chuỗi kết nối vào log. `query_logs` chỉ ghi số đo và trạng thái.

## 6. Vấn đề và rủi ro

1. **Gemini hết hạn mức:** toàn bộ phép đo dùng DeepSeek thay cho `gemini-3.8-flash`, nên số
   liệu chất lượng và độ trễ không đại diện cho mô hình mặc định. Cần khôi phục hạn mức Gemini
   trước khi chốt số liệu Giai đoạn 5/8.
2. **TTFT và tổng thời gian không đạt:** nguyên nhân là prompt dài (12.292 token quan sát được)
   cộng prefill chậm của DeepSeek; Gemini 429 khiến không có phương án nhanh hơn. Đây là rủi ro
   trực tiếp cho trải nghiệm streaming ở Giai đoạn 5.
3. **Chỉ 2/10 kịch bản đạt:** judge yêu cầu 1,0 cho mỗi lượt và cả 4 lượt phải đạt; phần lớn
   lượt hỏng ở mức 0,5 do thiếu một chi tiết. Ngoài ra KB-08 lượt 2 hỏng ở kiểm tra trích dẫn
   (tầng truy xuất), và kết quả có dao động giữa các lần chạy (KB-01 lượt 1 đạt 1,0 ở lượt đầy
   đủ nhưng 0,5 ở lượt quan sát riêng). Không tinh chỉnh trên bộ kịch bản này.
4. **Ước lượng token chưa sát:** `chars_per_token: 3.5` và `max_context_tokens: 8000` dẫn đến
   prompt thật vượt ngân sách. Cần đếm token bằng tokenizer của nhà cung cấp hoặc hạ ngân sách.
5. **Tóm tắt nền chưa kịp dùng trong 12 lượt:** log cho thấy tóm tắt chỉ cập nhật sau lượt 12
   và dùng nguồn `fallback` (LLM tóm tắt lỗi), nên `summary_used = False` ở cả 12 lượt; ngân
   sách vẫn giữ nhờ cắt bớt tin nhắn. Cần kiểm tra độ trễ và độ tin cậy của khâu tóm tắt.
6. **Tài nguyên máy:** mỗi tiến trình nạp reranker BGE; ba tiến trình nạp mô hình đồng thời từng
   gây `RuntimeError: bad allocation` trên máy 16 GB. Các phép đo phải chạy tuần tự.
7. **W1 vẫn một phần:** tiêu chí CoT tăng ≥ 5 điểm % của Giai đoạn 3 chưa đạt; Giai đoạn 4
   không thay đổi tầng sinh nên chưa khắc phục được.

## 7. Đề xuất cho giai đoạn 5

- Gắn `useChatStream` vào giao diện chat: hiển thị token theo thời gian thực, danh sách phiên,
  nút xóa phiên/xóa toàn bộ, và render trích dẫn từ sự kiện `citations`.
- Khôi phục hạn mức Gemini hoặc dùng khóa trả phí; đo lại TTFT trên mô hình mặc định. Nếu vẫn
  chậm, giảm prompt thật (đếm token bằng tokenizer, hạ `max_context_tokens`, giới hạn mở rộng
  mục cha) và cân nhắc prompt caching.
- Làm tóm tắt hội thoại đáng tin hơn: kiểm tra lỗi/timeout của LLM tóm tắt, có thể tóm tắt đồng
  bộ ngay khi vượt ngưỡng hoặc chạy trước lượt kế tiếp; ghi log nguồn tóm tắt.
- Phân tích 14 lượt hỏng còn lại trên dev set (không dùng 10 kịch bản nghiệm thu) để cải thiện
  độ đầy đủ của câu trả lời nhiều ý; bổ sung kiểm tra tự động cho các ý bắt buộc.
- Điều tra KB-08 lượt 2: trích dẫn không khớp tài liệu/mục, nhiều khả năng do mở rộng mục cha
  hoặc xếp hạng lại; kiểm tra lại nhãn mục sau khi hợp nhất chunk.
- Theo dõi `query_logs` (TTFT, tổng thời gian, token, trạng thái) bằng truy vấn tổng hợp để phát
  hiện hồi quy sớm.

## 8. Xác nhận Definition of Done

| Yêu cầu | Bằng chứng | Trạng thái |
| :--- | :--- | :---: |
| Dùng bảng `sessions`/`messages`, bổ sung cột còn thiếu | Hai migration Phase 4; `sessions.summary`, `token_count`, `updated_at`… | ĐẠT |
| API phiên đầy đủ (tạo, liệt kê, đọc tin nhắn, sửa, xóa) | `backend/app/api/routes.py`; `tests/sessions/test_session_api.py` | ĐẠT |
| Viết lại câu hỏi theo ngữ cảnh, lưu gốc + viết lại | `condense.py`; metadata `rewrite_source`; 12 lượt budget có viết lại | ĐẠT |
| Tóm tắt sau 10 lượt/4.000 token, dùng tóm tắt + 6 lượt gần | `summarize.py`; kiểm thử đơn vị; log cập nhật tóm tắt (nguồn fallback) | ĐẠT (có ghi chú độ trễ) |
| `POST /chat/stream` SSE, đủ 5 sự kiện, flush từng sự kiện | `chat.py`, `sse.py`; `tests/streaming`; đo 20 mẫu SSE | ĐẠT |
| Xử lý ngắt kết nối, lưu câu trả lời dở | `phase4_disconnect_check.py`: `interrupted`, không 500 | ĐẠT |
| Ghi TTFT, tổng thời gian, token vào `query_logs` | Migration + `generation/logger.py` + metadata tin nhắn | ĐẠT |
| RLS: mỗi người chỉ đọc/ghi phiên của mình; kiểm thử hai tài khoản | `phase4_isolation_check.py`: 19/19 | ĐẠT |
| Hook `useChatStream` cho SSE, tự kết nối lại | `frontend/hooks/useChatStream.ts`; `tsc --noEmit` và eslint đạt | ĐẠT (chưa gắn giao diện) |
| Script chạy 10 kịch bản và chấm theo rubric | `evaluation/conversation_bench.py`; kết quả 2/10 | ĐẠT (script) |
| `pytest tests/sessions tests/streaming -q` | `40 passed, 1 warning in 0.89s` | ĐẠT |
| Chạy 10 kịch bản, bảng điểm từng kịch bản | Mục 3; JSON/MD trong `evaluation/results/` | ĐẠT (2/10) |
| TTFT 20 lần, p50/p95, mục tiêu p95 ≤ 2 giây | Mục 4: p50 4.969,1 ms; p95 14.874,9 ms | KHÔNG ĐẠT |
| Cách ly: A không đọc được phiên của B | Mục 5: 19/19 | ĐẠT |
| Ngắt giữa chừng: dừng sinh, không 500 | Mục 2: `interrupted`, không 500 | ĐẠT |
| Hồi quy dev set Giai đoạn 3 ≥ 91,5% | Mục 2: 96,2% độ chính xác trung bình; 92,5% đúng hoàn toàn | ĐẠT |
| Sau 12 lượt, ngữ cảnh không vượt ngân sách token | Mục 2: lớn nhất 1.420/1.500 token | ĐẠT |
| Không làm hỏng `/chat` một lượt | Budget check và dev bench gọi `/chat`; kiểm thử cũ đạt | ĐẠT |
| Không lưu nội dung nhạy cảm; có xóa phiên và xóa toàn bộ | `DELETE /sessions/{id}`, `DELETE /sessions`; mục 5 | ĐẠT |
| Dừng sau báo cáo, không bắt đầu Giai đoạn 5 | Báo cáo này | ĐẠT |

**Kết luận:** Giai đoạn 4 đạt phần lớn yêu cầu kỹ thuật (phiên, viết lại, tóm tắt, SSE, đo
lường, RLS, hook, script đánh giá) nhưng **chưa đạt hai tiêu chí nghiệm thu về chất lượng
hội thoại (2/10 so với ≥ 8/10) và độ trễ (TTFT p95 14,9 giây so với ≤ 2 giây)**; trạng thái
tổng thể là **MỘT PHẦN**.
