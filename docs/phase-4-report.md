# BÁO CÁO GIAI ĐOẠN 4

**Trạng thái: MỘT PHẦN**

Ngày: 2026-11-23 (giờ địa phương; log và API ghi theo UTC).

Phạm vi: hội thoại đa lượt có phiên, viết lại câu hỏi phụ thuộc ngữ cảnh, tóm tắt phần cũ
của hội thoại, streaming SSE cho `/chat/stream`, ghi độ trễ và token vào `query_logs`,
RLS theo người dùng, hook `useChatStream` cho frontend, và bộ 10 kịch bản hội thoại
(`inputs/conversations.md`). Không bao gồm giao diện chat hoàn chỉnh (giai đoạn kế tiếp).

> **Lưu ý đánh số giai đoạn:** CLAUDE.md xếp hội thoại + streaming vào **Giai đoạn 6**;
> đề bài gọi công việc này là **Giai đoạn 4**. Báo cáo giữ cách gọi của đề bài.

> **Vì sao trạng thái là MỘT PHẦN:** hai tiêu chí nghiệm thu không đạt.
>
> - Bộ 10 kịch bản đạt **3/10** ở lần chạy 1 (`conversation_bench_stream_20261123-041140`,
>   27/40 lượt) và **2/10** ở lần chạy 2 (`conversation_bench_stream_20261123-042635`,
>   28/40 lượt); ngưỡng là ≥ 8/10. Cả hai lần đều được báo cáo, không chọn lần tốt hơn.
> - TTFT p95 **10.836,8 ms** ở phép đo 20 mẫu một lượt (ngưỡng ≤ 2.000 ms); tổng thời gian
>   p95 **19.887,6 ms** (ngưỡng ≤ 10.000 ms). Trên bộ dev đa lượt, TTFT p95 là 6.905,0 ms
>   (lần 2) và 8.125,2 ms (lần 1), cũng chưa đạt.
>
> Các tiêu chí kỹ thuật còn lại đều đạt: phiên và RLS (19/19), ngắt kết nối không lỗi 500,
> ngân sách hội thoại 12–14 lượt ≤ 1.500 token, hồi quy dev set Giai đoạn 3 ≥ 91,5%, và
> `/chat` một lượt giữ tương thích. Xem mục 2, 5 và 9.

## 1. Việc đã làm

### 1.1 Nhà cung cấp sinh văn bản: chỉ còn DeepSeek

Đây là thay đổi kiến trúc trung tâm của đợt khắc phục. Trước đây Gemini là provider đầu
chuỗi và chỉ khi Gemini trả HTTP 429 mới dùng DeepSeek dự phòng; nay DeepSeek là provider
duy nhất cho mọi tác vụ sinh văn bản, còn Gemini chỉ cấp embedding.

| Hạng mục | Trước bản sửa (2026-11-22) | Sau bản sửa (2026-11-23) |
| :--- | :--- | :--- |
| Chuỗi provider | `gemini_primary` → `deepseek_fallback` | `deepseek_primary` (duy nhất) |
| Trả lời, viết lại câu hỏi, tóm tắt, phân loại/tách truy vấn, judge | Gemini 3.8 Flash; DeepSeek chỉ khi Gemini lỗi | DeepSeek qua endpoint tương thích OpenAI; `.env` dùng `deepseek-v4-flash`, API báo `deepseek-flash` |
| Embedding | `gemini-embedding-001`, 768 chiều | Giữ nguyên; không đổi model, không đổi số chiều, không nạp lại kho |
| Dự phòng | Gemini trước, DeepSeek sau | Không fallback sang Gemini; lỗi trả có kiểm soát. Nếu stream rỗng và mức suy luận khác `none`, thử lại **một lần** với `reasoning_effort=none` trên cùng model DeepSeek |
| Adapter | `GeminiAdapter` + adapter tương thích OpenAI | Chỉ còn adapter tương thích OpenAI; `GeminiAdapter` và test riêng đã xóa |
| Judge | DeepSeek dự phòng | DeepSeek, cùng model với bộ sinh |

Kho tri thức giữ nguyên: 7 tài liệu, 1.775 chunk, 390 câu hỏi; không re-ingest và không
đổi embedding 768 chiều. Việc xóa adapter Gemini khỏi đường sinh văn bản là thay đổi có
chủ đích, không phải sự cố hạn mức; khóa Gemini vẫn chỉ dùng cho embedding.

### 1.2 Lược đồ dữ liệu

- `supabase/migrations/20261122000000_conversation_phase4.sql`:
  - `sessions`: thêm `summary`, `summary_updated_at`, `summary_message_count`, `token_count`,
    `message_count`; đặt `user_id NOT NULL` và khóa ngoại `auth.users` với `ON DELETE CASCADE`.
  - `messages`: thêm `token_count`, `rewritten_query`, `request_id`; chỉ mục duy nhất
    `(session_id, request_id)` khi `request_id` khác NULL để chống gửi trùng.
  - `query_logs`: thêm `ttft_ms`, `total_latency_ms`, `streaming`, `user_id`, `status`,
    `conversation_tokens`, các mốc `retrieval_ms`, `rerank_ms`, `parent_expand_ms`,
    `prompt_ms`, `prefill_ms`, `generation_ms`, `output_tokens`, `provider`, `judge_provider`.
  - RLS: bốn policy `sessions_select_own`, `sessions_insert_own`, `sessions_update_own`,
    `sessions_delete_own`; policy cho `messages` kiểm tra chủ sở hữu phiên qua truy vấn con.
    Chỉ cấp quyền cho `authenticated`; `query_logs` để RLS đóng hoàn toàn.
- `supabase/migrations/20261122010000_messages_seq.sql`: thứ tự tin nhắn ổn định trong phiên.
- Đợt khắc phục này không thêm migration mới và không mở quyền RLS.

### 1.3 API phiên

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

### 1.4 Hội thoại: viết lại câu hỏi và tóm tắt

- `backend/app/services/conversation/condense.py`: câu hỏi phụ thuộc ngữ cảnh được viết lại
  thành câu độc lập bằng một lần gọi DeepSeek nhẹ (4 lượt gần nhất, tối đa 256 token đầu ra,
  timeout 8 giây, mức suy luận `low`). Lưu cả câu gốc và câu viết lại (`rewritten_query`),
  kèm nguồn viết lại (`none`/`llm`/`fallback`/`topic_shift`) trong metadata.
- Phát hiện đổi chủ đề: khi câu hỏi mới không còn liên quan chủ đề trước, ngữ cảnh cũ bị loại
  và tóm tắt được đặt lại; có kiểm thử riêng.
- `backend/app/services/conversation/summarize.py`: sau 10 lượt hoặc 4.000 token, phần cũ được
  tóm tắt ở luồng nền (2 worker), giữ 6 lượt gần nhất trong trạng thái phiên, tóm tắt tối đa
  400 token. Trước khi chuẩn bị lượt kế tiếp, hệ thống chờ tối đa 5.000 ms cho tóm tắt nền
  (`await_ms: 5000`) để lượt kế chắc chắn dùng bản mới. Nếu LLM tóm tắt lỗi, dùng tóm tắt dự
  phòng có ghi nguồn `fallback`.
- `backend/app/services/conversation/context.py`: ngân sách ngữ cảnh hội thoại
  `max_conversation_tokens: 1500`; nội dung được đếm và cắt bằng **tokenizer DeepSeek thật**
  (`default_token_counter`), ước lượng 3,0 ký tự/token chỉ còn là phương án lùi khi thiếu
  tokenizer. Cắt bớt tin nhắn cũ khi vượt ngân sách.
- Cấu hình tại `config/conversation.yaml`.

### 1.5 Streaming SSE

- `POST /chat/stream` trả `text/event-stream` với các sự kiện `meta`, `token`, `citations`,
  `done`, `error`; mỗi sự kiện được flush ngay, không chờ sinh xong.
- Bộ sinh đồng bộ chạy trong luồng nền, đẩy sự kiện qua `queue.Queue`; lớp async đọc hàng đợi
  và ghi ra response. Khi client ngắt kết nối, `GeneratorExit` dừng bộ sinh, phần câu trả lời
  đã nhận được lưu với `stream_status = "interrupted"`.
- `AnswerStreamExtractor` trong `backend/app/services/generation/streaming.py` trích trường
  `"answer"` của JSON ngay khi mô hình còn sinh, không đợi toàn bộ JSON.
- Khi stream không parse được JSON cuối, `inline_citation_sources()` trích các nhãn
  `[Nguồn – Mục]` trong phần nội dung còn lại và điền vào sự kiện `citations`, tránh mất
  trích dẫn ở nhánh dự phòng.
- Adapter DeepSeek khi gặp stream rỗng với `reasoning_effort` khác `none` sẽ thử lại đúng một
  lần với `reasoning_effort=none`; nếu vẫn rỗng thì trả `LLMError` có kiểm soát. Không có
  fallback sang Gemini.

### 1.6 Đo lường

- `query_logs` ghi `ttft_ms`, `total_latency_ms`, `prompt_tokens`, `completion_tokens`,
  `streaming`, `status`, `conversation_tokens`, cùng các mốc thời gian truy hồi/sinh và
  `provider`/`judge_provider`.
- Metadata của mỗi tin nhắn trợ lý ghi `conversation_tokens`, `conversation_messages`,
  `summary_used`, `summary_source`, `summary_latency_ms`, `rewrite_source`,
  `condensation_latency_ms`, `citation_validity`.
- Không ghi khóa, token hay chuỗi kết nối vào log.

### 1.7 Frontend

- `frontend/hooks/useChatStream.ts`: hook đọc SSE, phân phát sự kiện `meta`/`token`/`citations`/
  `done`/`error`, hủy khi unmount và tự kết nối lại có backoff khi mất mạng tạm thời. Hook
  chưa được gắn vào trang giao diện (để giai đoạn kế tiếp).

### 1.8 Bộ đánh giá 10 kịch bản

- `inputs/conversations.md`: 10 kịch bản, mỗi kịch bản 4 lượt, có hành vi mong đợi và tiêu chí.
  Đây là bộ nghiệm thu đóng băng; SHA-256 được ghi trước và kiểm lại sau khi chạy.
- `evaluation/conversation_bench.py`: chạy trên `ChatService` + `GenerationService` + tầng truy
  hồi thật, dùng `InMemorySessionRepository`; judge phiên bản v3, 3 phiếu, lấy trung vị
  (≥0,75 → 1,0; ≥0,25 → 0,5), nhiệt độ 0; lịch sử đưa vào judge tối đa 4.000 ký tự; tiêu chí
  được lọc theo đúng lượt; mỗi lượt còn phải đạt các kiểm tra tự động (trích dẫn đúng tài
  liệu/mục, câu viết lại giữ đủ thực thể, từ chối không rò rỉ…). Kịch bản chỉ đạt khi cả
  4 lượt đạt.
- Hỗ trợ `--transport answer|stream|both` (mặc định `answer`), `--conversations` để chạy bộ dev
  riêng, và `--workers` (mặc định 1). Các lần nghiệm thu dùng `--transport stream` trên
  `inputs/conversations.md`.
- Kết quả lưu tại `evaluation/results/conversation_bench_stream_20261123-041140.{json,md}` và
  `conversation_bench_stream_20261123-042635.{json,md}`. Bản chấm tay 24 lượt (lượt 1–2 của
  cả 10 kịch bản và lượt 3–4 của hai kịch bản đầu) tại
  `evaluation/results/phase4_manual_worksheet_20261123-044149.md`; bản này **chưa được chấm
  điểm thủ công**, chỉ dùng để đối chiếu sau này.

### 1.9 Script vận hành

`scripts/phase4_serve.py` (chạy backend với provider chỉ định), `phase4_ttft_measure.py`
(20 mẫu SSE một lượt và chế độ dev đa lượt 4 lượt × 10 kịch bản), `phase4_budget_check.py`
(14 lượt thật), `phase4_isolation_check.py` (hai tài khoản), `phase4_disconnect_check.py`
(ngắt giữa chừng), `phase4_token_report.py` (kiểm toán token theo thành phần).

### 1.10 Kiểm thử

`tests/sessions/` (5 tệp) và `tests/streaming/` (3 tệp) gồm kiểm thử API phiên, repository,
viết lại câu hỏi, tóm tắt, ngân sách ngữ cảnh, SSE, ngắt kết nối, trích xuất answer. Bổ sung
kiểm thử cho tokenizer, cắt ngữ cảnh theo token thật, adapter DeepSeek (gồm thử lại stream
rỗng) và cấu hình một provider. Toàn bộ backend hiện có **293 kiểm thử**.

### 1.11 Hai phát hiện cấu hình

**Giới hạn đầu ra 3.072 token làm cắt cụt câu trả lời.** Với `max_output_tokens: 3072`,
6/40 lượt dev có `output_tokens` đúng bằng 3.072, hỏng schema JSON và mất trích dẫn. Đã nâng
lên **6.144** (trên mức lớn nhất từng thấy 5.605). Tuy vậy, ở lần nghiệm thu 1, KB-06 lượt 1
vẫn chạm đúng 6.144 token, sinh `SchemaError` và độ tin cậy 0,00 — giới hạn này vẫn là rủi ro
với câu trả lời dài, ghi tại mục 7.

**Ngân sách prompt tính bằng ước lượng, không khớp bản kiểm kê.** `_build_prompt` cũ thu ngữ
cảnh theo ước lượng ký tự/token trong khi bản kiểm kê dùng tokenizer DeepSeek; khối đầu luôn
được giữ nguyên nên prompt vẫn vượt trần 12.000 token ở KB-01 lượt 1 (12.256) và KB-06 lượt 1
(12.248) trong cả hai lần nghiệm thu, chỉ còn cảnh báo. Đã thêm `fit_context_to_tokens` trong
`backend/app/services/generation/context.py`: giữ các khối đầu còn vừa, cắt dần nội dung khối
kế tiếp và bỏ các khối sau, giữ nguyên nhãn tài liệu/mục; nếu ngân sách còn lại cho ngữ cảnh
dưới 128 token thì bỏ hội thoại trước. Có unit test hồi quy cho trường hợp ước lượng thấp hơn
tokenizer thật và trường hợp ngân sách 0.

> **Mốc thời gian:** bản sửa ngân sách prompt được thêm **sau** toàn bộ các phép đo nghiệm thu,
> TTFT và hồi quy trong báo cáo này. Các số liệu dưới đây phản ánh bản trước sửa. Không chạy
> lại bộ nghiệm thu sau khi sửa để tránh dùng bộ đóng băng như tập tinh chỉnh; bản sửa có kiểm
> thử hồi quy riêng.

## 2. Kết quả kiểm thử

| Hạng mục | Lệnh | Kỳ vọng | Thực tế | Đạt |
| :--- | :--- | :--- | :--- | :---: |
| Kiểm thử phiên + streaming | `pytest tests/sessions tests/streaming -q` | Tất cả đạt | Đạt trong toàn bộ suite | ĐẠT |
| Toàn bộ backend | `pytest -q` | Không hồi quy | **293 passed, 1 warning** (7,43 giây) | ĐẠT |
| Lint backend | `ruff check backend tests evaluation scripts` + `black --check` | Sạch | Sạch (2026-11-23) | ĐẠT |
| 10 kịch bản hội thoại — lần 1 | `conversation_bench.py --transport stream` | ≥ 8/10 | **3/10** (27/40 lượt), 873,3 giây, 0 lỗi | KHÔNG ĐẠT |
| 10 kịch bản hội thoại — lần 2 | `conversation_bench.py --transport stream` | ≥ 8/10 | **2/10** (28/40 lượt), 752,5 giây, 0 lỗi | KHÔNG ĐẠT |
| TTFT một lượt | `phase4_ttft_measure.py` (20 mẫu, warm) | p95 ≤ 2.000 ms | p50 **3.235,2 ms**, p95 **10.836,8 ms**; 20/20 mẫu, 0 lỗi | KHÔNG ĐẠT |
| Tổng thời gian một lượt | `phase4_ttft_measure.py` | p95 ≤ 10.000 ms | p95 **19.887,6 ms** | KHÔNG ĐẠT |
| TTFT đa lượt trên dev — lần 1 | `phase4_ttft_measure.py --conversations dev` | p95 ≤ 2.000 ms | p95 **8.125,2 ms**; tổng p95 **14.344,0 ms**; 40/40, 0 lỗi | KHÔNG ĐẠT |
| TTFT đa lượt trên dev — lần 2 | `phase4_ttft_measure.py --conversations dev` | p95 ≤ 2.000 ms | p95 **6.905,0 ms**; tổng p95 **13.957,0 ms**; 40/40, 0 lỗi | KHÔNG ĐẠT |
| Cách ly hai tài khoản | `phase4_isolation_check.py` | A không đọc/ghi được dữ liệu của B | **19/19 kiểm tra đạt** | ĐẠT |
| Ngắt giữa chừng | `phase4_disconnect_check.py` | Dừng sinh, không 500 | `stream_status = interrupted`, lưu 24 ký tự, không 500/Traceback | ĐẠT |
| Ngân sách ngữ cảnh 12–14 lượt | `phase4_budget_check.py` | ≤ 1.500 token | Lớn nhất **1.459 token**; tóm tắt được dùng từ lượt 11 | ĐẠT |
| Giữ 6 lượt gần nhất sau tóm tắt | log `conversation_messages` | 6 lượt gần nhất | Lưu trữ giữ 6 lượt; prompt chỉ còn tối đa 6 tin nhắn (~3 lượt) vì ngân sách 1.500 token | MỘT PHẦN |
| Hồi quy dev set Giai đoạn 3 | `gen_bench.py --before-after --provider deepseek_primary` | ≥ 91,5% | **95,0%** đúng hoàn toàn; **97,5%** độ chính xác trung bình | ĐẠT |
| Tương thích `/chat` một lượt | 14 lượt budget + dev bench gọi qua tầng sinh cũ | Không đổi hợp đồng | Chạy thành công, kiểm thử cũ đạt | ĐẠT |

Đối chiếu hồi quy: trước CoT 92,5% đúng hoàn toàn / 93,8% trung bình; sau CoT 95,0% / 97,5%
(`gen_bench_20261123-041113`). Mức 95,0% trên sàn 91,5% nên không hồi quy. Chênh lệch CoT là
**+2,5 điểm %** đúng hoàn toàn và **+3,7 điểm %** trung bình, vẫn dưới tiêu chí +5 điểm % của
Giai đoạn 3 (W1 còn một phần). Độ trễ trung bình 6.385,1 ms; token vào 10.151,7, token ra
1.553,8; hiệu lực trích dẫn 1,0; chi phí judge 0 USD.

## 3. Nghiệm thu 10 kịch bản

Hai lần chạy độc lập trên cùng bộ đóng băng, cùng cấu hình, `--transport stream`. SHA-256 của
`inputs/conversations.md` trước và sau khi chạy đều là
`74a3b3d60d39c04132a051bbfcfacd2fada36750dd4185badcd0c07b9ec275b7` (không đổi). Bộ dev riêng
`inputs/conversations_dev.md` có SHA-256
`4139256b3c49fca7a6218d6c619158c8a340027f756e41d7d05cd036b0f97951`.

| Kịch bản | Lần 1 | Lần 2 | Lượt hỏng lần 1 | Lượt hỏng lần 2 |
| :--- | :---: | :---: | :--- | :--- |
| KB-01 | KHÔNG | KHÔNG | 1, 2, 3, 4 | 1, 3 |
| KB-02 | KHÔNG | KHÔNG | 1 | 1 |
| KB-03 | KHÔNG | KHÔNG | 1, 4 | 1, 4 |
| KB-04 | KHÔNG | KHÔNG | 2, 4 | 4 |
| KB-05 | KHÔNG | ĐẠT | 3 | — |
| KB-06 | KHÔNG | KHÔNG | 1, 3 | 4 |
| KB-07 | ĐẠT | KHÔNG | — | 3 |
| KB-08 | KHÔNG | KHÔNG | 2 | 2 |
| KB-09 | ĐẠT | KHÔNG | — | 2, 3, 4 |
| KB-10 | ĐẠT | ĐẠT | — | — |

**Tổng: lần 1 đạt 3/10 (27/40 lượt); lần 2 đạt 2/10 (28/40 lượt).** Ngưỡng ≥ 8/10 không đạt.
Hai lần đều 0 lỗi hạ tầng, judge trùng nhà cung cấp với bộ sinh (`judge_self_preference=True`),
chi phí judge 0 USD.

Phân tích lỗi:

- **Thiếu một chi tiết bắt buộc (phần lớn):** 12/13 lượt hỏng ở lần 1 và 11/12 lượt ở lần 2 bị
  judge cho 0,5 vì câu trả lời đúng hướng nhưng thiếu một ý trong hành vi mong đợi (ví dụ
  KB-02 lượt 1 thiếu cửa sổ sao lưu; KB-03 lượt 1 thiếu thời hạn; KB-04 lượt 2 thiếu ngoại lệ
  Multi-AZ DB cluster; KB-08 lượt 2 thiếu điều kiện chỉ dùng Deep Archive khi gần như không
  đọc). Đây là lỗi **độ đầy đủ của tầng sinh**, không phải truy xuất sai.
- **Trích dẫn/mâu thuẫn ở KB-01 lượt 3:** kiểm tra tự động trích dẫn đúng tài liệu/mục thất bại
  ở cả hai lần; lần 1 judge cho 0,0 vì câu trả lời mâu thuẫn với lượt trước, lần 2 judge cho
  0,5. Lỗi thuộc tầng truy xuất/ngữ cảnh, không phải thiếu chi tiết.
- **Từ chối sai ở KB-09 lượt 3 (lần 2):** hệ thống trả `no_evidence` dù có căn cứ Mục 1.3,
  judge cho 0,0; đây là lỗi từ chối sai, không phải thiếu chi tiết.
- **Cắt cụt ở KB-06 lượt 1 (lần 1):** đầu ra đúng 6.144 token, `SchemaError`, độ tin cậy 0,00,
  judge 0,5; lần 2 lượt này đạt với 5.049 token nhưng prompt vẫn vượt trần.
- **Dao động giữa hai lần chạy:** KB-02 lượt 1 hỏng cả hai lần; KB-05 đạt cả 4 lượt ở lần 2
  nhưng hỏng lượt 3 ở lần 1; KB-06 lượt 1 hỏng lần 1, đạt lần 2; KB-07 đạt cả 4 lượt lần 1
  nhưng hỏng lượt 3 lần 2; KB-09 đạt cả 4 lượt lần 1 nhưng hỏng 3 lượt lần 2. Chênh lệch này
  cho thấy kết quả chịu ảnh hưởng của dao động sinh và cắt ngân sách, không chỉ của một lỗi
  cố định.
- **Prompt vượt trần 12.000 token:** KB-01 lượt 1 (12.256) và KB-06 lượt 1 (12.248) ở cả hai
  lần; đã sửa bằng `fit_context_to_tokens` sau các lần chạy này (mục 1.11).
- **Ngữ cảnh hội thoại bị bỏ:** ở lần 2, KB-01 lượt 2–3 và KB-07 lượt 3–4 có cảnh báo bỏ ngữ
  cảnh hội thoại để nhường ngân sách prompt; KB-07 lượt 3 hỏng (judge 0,5) trong tình huống đó.

## 4. TTFT và độ trễ

Định nghĩa không đổi: TTFT đo từ lúc gửi yêu cầu tới sự kiện `token` đầu tiên, tức đã gồm
truy xuất, xếp hạng lại và prefill. `meta` là thời điểm nhận sự kiện đầu tiên (phiên + viết lại
câu hỏi xong). `server_ttft_ms` chỉ dùng tham khảo.

### 4.1 Một lượt, 20 mẫu warm (SSE)

| Mẫu | meta (ms) | TTFT (ms) | Tổng (ms) |
| :---: | ---: | ---: | ---: |
| 01 | 456,2 | 2.876,4 | 5.345,9 |
| 02 | 429,7 | 10.519,6 | 19.887,6 |
| 03 | 434,7 | 10.836,8 | 18.628,1 |
| 04 | 445,3 | 2.956,1 | 5.005,6 |
| 05 | 405,1 | 2.955,9 | 5.352,6 |
| 06 | 428,8 | 3.174,1 | 5.198,6 |
| 07 | 440,2 | 3.627,5 | 6.146,4 |
| 08 | 413,3 | 6.875,8 | 13.867,3 |
| 09 | 439,5 | 2.592,6 | 4.614,3 |
| 10 | 439,5 | 3.301,0 | 6.350,6 |
| 11 | 509,4 | 3.681,1 | 5.242,2 |
| 12 | 477,8 | 2.432,3 | 4.079,5 |
| 13 | 432,8 | 3.315,5 | 9.593,6 |
| 14 | 425,5 | 3.213,2 | 5.684,8 |
| 15 | 439,3 | 2.262,1 | 5.225,8 |
| 16 | 402,0 | 15.167,8 | 20.598,8 |
| 17 | 426,4 | 3.189,3 | 6.269,7 |
| 18 | 423,1 | 3.802,9 | 6.543,3 |
| 19 | 393,6 | 5.232,4 | 12.086,3 |
| 20 | 417,3 | 3.235,2 | 9.312,7 |

- **TTFT p50 = 3.235,2 ms; p95 = 10.836,8 ms** (mục tiêu p95 ≤ 2.000 ms — không đạt).
- **Tổng thời gian p95 = 19.887,6 ms** (mục tiêu ≤ 10.000 ms — không đạt).
- 20/20 mẫu hợp lệ, không có sự kiện `error`. Hai mẫu 16 và 03 vượt 10 giây; mẫu 16 có TTFT
  15.167,8 ms và tổng 20.598,8 ms.

### 4.2 Đa lượt trên bộ dev (40 lượt, 4 lượt × 10 kịch bản)

| Lần chạy | Lượt | TTFT p50 (ms) | TTFT p95 (ms) | Tổng p50 (ms) | Tổng p95 (ms) | Lỗi |
| :--- | :---: | ---: | ---: | ---: | ---: | :---: |
| 1 (`031453`) | 40 | 5.234,7 | 8.125,2 | 8.995,0 | 14.344,0 | 0 |
| 2 (`035438`) | 40 | 4.040,2 | 6.905,0 | 6.749,4 | 13.957,0 | 0 |

Lần 2 theo từng lượt: lượt 1 TTFT p95 29.140,5 ms (một ngoại lệ DV-06), lượt 2 6.905,0 ms,
lượt 3 6.499,2 ms, lượt 4 9.341,1 ms; tổng p95 lần lượt 34.809,6 / 14.397,9 / 11.825,0 /
12.682,8 ms. Lần 1 có TTFT p95 8.125,2 ms và tổng p95 14.344,0 ms.

### 4.3 Độ trễ trong hai lần nghiệm thu (tham khảo)

| Lần | TTFT trung vị (ms) | TTFT p95 (ms) | TTFT lớn nhất (ms) | Tổng trung vị (ms) | Tổng p95 (ms) | Tổng lớn nhất (ms) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 (`041140`) | 3.474,5 | 11.023,1 | 25.178,1 | 6.682,6 | 21.728,2 | 27.349,9 |
| 2 (`042635`) | 3.014,8 | 9.167,1 | 19.624,3 | 6.165,4 | 19.640,4 | 25.598,7 |

### 4.4 Bảng cũ chỉ là lịch sử

Bảng TTFT cũ trong báo cáo ngày 2026-11-22 (p50 4.969,1 ms, p95 14.874,9 ms, tổng p95
23.455,4 ms) được đo khi Gemini trả HTTP 429 và mọi câu trả lời do provider dự phòng DeepSeek
sinh, với `max_context_tokens: 8000`, prompt và judge khác hiện tại. Bảng đó **không so sánh
trực tiếp** với số liệu mới; chỉ giữ để tra cứu lịch sử. Bản sao báo cáo cũ ở
`backups/phase4-fix-20261123/phase-4-report.md`.

### 4.5 Phân tích

`meta` chỉ 393–509 ms, nên phần lớn độ trễ nằm ở truy xuất + xếp hạng lại + prefill + sinh.
Prompt trung bình 10.429 token, p95 11.984, lớn nhất 12.256 (mục 5.2), nên DeepSeek phải
prefill khối lớn trước token đầu. Câu tra cứu đơn giản dùng `reasoning_effort=none`; câu so
sánh/nhiều ràng buộc dùng `medium`, tạo đuôi p95 dài. Các mẫu chậm nhất thường là câu nhiều
ràng buộc hoặc đầu ra dài. Không hạ ngưỡng; các đề xuất giảm độ trễ nêu ở mục 8 nhưng chưa
triển khai trong giai đoạn này.

## 5. Ngân sách ngữ cảnh và token

### 5.1 Kiểm tra 14 lượt

`scripts/phase4_budget_check.py` chạy một phiên thật 14 lượt, hỏi liên tiếp về lớp lưu trữ S3
và các chủ đề liên quan. Kết quả:

| Lượt | conversation_tokens | summary_used | summary_source | summary_latency_ms | conversation_messages |
| :---: | ---: | :---: | :--- | ---: | ---: |
| 01 | 0 | False | — | 0,0 | 0 |
| 02 | 380 | False | — | 0,0 | 2 |
| 03 | 487 | False | — | 0,0 | 4 |
| 04 | 923 | False | — | 0,0 | 6 |
| 05 | 1.141 | False | — | 0,0 | 8 |
| 06 | **1.459** | False | — | 0,0 | 10 |
| 07 | 1.431 | False | — | 0,0 | 8 |
| 08 | 1.354 | False | — | 0,0 | 8 |
| 09 | 1.384 | False | — | 0,0 | 6 |
| 10 | 1.394 | False | — | 0,0 | 6 |
| 11 | 1.080 | **True** | `stored` | 2.813,5 | 4 |
| 12 | 1.272 | True | `stored` | 113,5 | 6 |
| 13 | 129 | True | `stored` | 105,4 | 0 |
| 14 | 1.316 | True | `stored` | 2.425,6 | 2 |

- Ngân sách 1.500 token; lớn nhất **1.459 token** ở lượt 6, không vượt.
- Tóm tắt được dùng **từ lượt 11**, nguồn `stored`; độ trễ tóm tắt 2.813,5 ms ở lượt 11,
  sau đó 113,5 / 105,4 / 2.425,6 ms. Điều này khắc phục lỗi cũ `summary_used=False` suốt 12 lượt.
- **Giữ 6 lượt gần nhất:** lớp tóm tắt giữ 6 lượt trong trạng thái phiên, nhưng ngân sách
  1.500 token chỉ đưa được tối đa 6 **tin nhắn** (~3 lượt) vào prompt; log cho thấy
  `conversation_messages` là 4, 6, 0, 2 sau khi tóm tắt. Vì vậy tiêu chí "giữ 6 lượt gần nhất"
  chỉ đạt ở lớp lưu trữ, **chưa đạt trọn vẹn trong prompt** — ghi nhận là MỘT PHẦN.

### 5.2 Kiểm toán token prompt

`scripts/phase4_token_report.py` đọc `prompt_audit` của lần nghiệm thu 2 (40 lượt), đếm bằng
tokenizer DeepSeek thật (`tokenizer.json` của DeepSeek-V3):

| Thành phần | Trung bình | p50 | p95 | Lớn nhất | Tỷ lệ trung bình |
| :--- | ---: | ---: | ---: | ---: | ---: |
| System (không kể few-shot) | 4.099 | 3.802 | 4.673 | 4.673 | 39,3% |
| Few-shot trong system | 522 | 481 | 658 | 658 | 5,0% |
| Ngữ cảnh truy xuất | 5.161 | 5.093 | 6.781 | 7.849 | 49,5% |
| Ngữ cảnh hội thoại | 490 | 325 | 1.466 | 1.544 | 4,7% |
| Câu hỏi | 28 | 21 | 55 | 86 | 0,3% |
| Yêu cầu đầu ra | 69 | 69 | 69 | 69 | 0,7% |
| Overhead chat (ước lượng) | 16 | 16 | 16 | 16 | 0,2% |
| Khác (tiêu đề mục, phân cách) | 44 | 50 | 51 | 51 | 0,4% |
| **Tổng prompt** | **10.429** | **10.741** | **11.984** | **12.256** | **100%** |

- Tổng prompt theo tokenizer 417.155 so với tổng `input_tokens` API 417.995; lệch **−0,2%**,
  xác nhận tokenizer dùng đúng.
- Output token: trung bình 1.644, p95 4.759, lớn nhất 5.851.
- Ngữ cảnh hội thoại ở lượt 4: trung bình 699, p95 1.460, lớn nhất 1.460 token (ngưỡng 1.500).
  Nếu tính cả tiêu đề và phân cách của khối hội thoại trong prompt, trường
  `prompt_audit.conversation_tokens` lớn nhất là 1.544 token — vượt 44 token so với ngưỡng
  1.500; trường ngân sách `conversation_tokens` (nội dung hội thoại) vẫn ≤ 1.500.
- Hai lượt vượt trần prompt 12.000 (12.256 và 12.248) là các lượt có ngữ cảnh truy xuất lớn
  nhất; bản sửa `fit_context_to_tokens` xử lý sau khi các phép đo này hoàn tất.

## 6. Cách ly dữ liệu và bảo mật phiên

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

## 7. Vấn đề và hạn chế

1. **Chất lượng hội thoại chưa đạt:** 3/10 và 2/10 so với ngưỡng 8/10. Nguyên nhân chính là
   câu trả lời thiếu một chi tiết bắt buộc (judge 0,5), không phải truy xuất sai; KB-01 lượt 3
   hỏng kiểm tra trích dẫn ở cả hai lần, KB-09 lượt 3 lần 2 từ chối sai. Bộ nghiệm thu đóng
   băng, không dùng để tinh chỉnh.
2. **TTFT và tổng thời gian chưa đạt:** TTFT p95 10.836,8 ms (một lượt) và 6.905,0–8.125,2 ms
   (đa lượt); tổng p95 19.887,6 ms và 13.957,0–14.344,0 ms. Prompt lớn và suy luận `medium`
   ở câu phức tạp là nguyên nhân chính; không có fallback Gemini theo yêu cầu.
3. **Giới hạn đầu ra 6.144 token vẫn có thể chạm:** KB-06 lượt 1 lần 1 đúng 6.144 token, hỏng
   schema và mất độ tin cậy. Cần tiếp tục theo dõi hoặc rút ngắn CoT cho câu dài.
4. **Ngân sách prompt và hội thoại có độ lệch nhỏ:** trần prompt 12.000 token bị vượt ở 2/40
   lượt trước bản sửa; ngưỡng hội thoại 1.500 token tính theo nội dung, còn khối hội thoại đầy
   đủ trong prompt có thể cao hơn 44 token do tiêu đề/phân cách.
5. **Giữ 6 lượt gần nhất chưa trọn vẹn trong prompt:** lớp tóm tắt giữ 6 lượt, nhưng ngân sách
   1.500 token chỉ chứa tối đa 6 tin nhắn (~3 lượt) sau khi tóm tắt. Đây là xung đột giữa hai
   ràng buộc, ghi nhận MỘT PHẦN.
6. **Judge trùng nhà cung cấp:** judge và bộ sinh đều là DeepSeek (`judge_self_preference=True`),
   nên điểm có thể thiên vị. Bản chấm tay 24 lượt đã tạo nhưng **chưa chấm**, nên chưa có đối
   chứng độc lập cho rubric.
7. **Dao động giữa các lần chạy:** cùng bộ câu hỏi nhưng KB-05, KB-06, KB-07, KB-09 đổi kết quả
   giữa hai lần; không thể quy toàn bộ chênh lệch cho một nguyên nhân duy nhất.
8. **Các phép đo trước bản sửa prompt:** số liệu nghiệm thu, TTFT và hồi quy đều chạy trước khi
   thêm `fit_context_to_tokens`; bản sửa chỉ có unit test, chưa được đo lại trên bộ nghiệm thu.
9. **Tài nguyên máy:** mỗi tiến trình nạp reranker BGE; chạy đồng thời từng gây
   `RuntimeError: bad allocation` trên máy 16 GB. Các phép đo phải chạy tuần tự/`--workers 1`.
10. **W1 vẫn một phần:** CoT tăng +2,5 điểm % đúng hoàn toàn (dưới tiêu chí +5 điểm % của
    Giai đoạn 3); Giai đoạn 4 không thay đổi prompt sinh nên chưa khắc phục được.
11. **Gemini chỉ còn embedding:** đây là quyết định có chủ đích; không có phương án sinh văn
    bản dự phòng khác ngoài DeepSeek. Nếu DeepSeek lỗi, hệ thống trả lỗi có kiểm soát.

## 8. Đề xuất cho giai đoạn kế tiếp

- Gắn `useChatStream` vào giao diện chat: hiển thị token theo thời gian thực, danh sách phiên,
  nút xóa phiên/xóa toàn bộ, và render trích dẫn từ sự kiện `citations`.
- Chấm tay bản worksheet 24 lượt để có đối chứng độc lập với judge DeepSeek; nếu điểm tay thấp
  hơn đáng kể, điều chỉnh rubric hoặc bổ sung judge khác ở giai đoạn đánh giá.
- Cải thiện độ đầy đủ của câu trả lời nhiều ý trên **bộ dev** (không dùng 10 kịch bản nghiệm
  thu): bổ sung kiểm tra tự động cho các ý bắt buộc, thử prompt yêu cầu liệt kê đủ ý.
- Giảm TTFT: đo lại sau khi bản sửa ngân sách prompt được nghiệm thu; cân nhắc prompt caching,
  giảm ngữ cảnh truy xuất (đang chiếm 49,5% prompt), và rút ngắn CoT cho câu phức tạp. Không
  hạ ngưỡng nếu chưa có văn bản chấp thuận.
- Giải quyết xung đột "6 lượt gần nhất" với ngân sách 1.500 token: hoặc tăng ngân sách có đo
  lại, hoặc rút gọn từng tin nhắn để đủ 6 lượt, hoặc ghi rõ tiêu chí chỉ áp cho lớp lưu trữ.
- Điều tra KB-01 lượt 3 (trích dẫn/mâu thuẫn) và KB-09 lượt 3 (từ chối sai) trên bộ dev tương
  ứng; không sửa bộ nghiệm thu.
- Theo dõi `query_logs` (TTFT, tổng thời gian, token, trạng thái) bằng truy vấn tổng hợp để phát
  hiện hồi quy sớm.

## 9. Xác nhận Definition of Done

| Yêu cầu | Bằng chứng | Trạng thái |
| :--- | :--- | :---: |
| DeepSeek là provider duy nhất cho mọi tác vụ sinh văn bản | `config/generation.yaml` chain `deepseek_primary`; factory từ chối `type: gemini`; adapter Gemini đã xóa | ĐẠT |
| Gemini chỉ dùng embedding 768 chiều; không re-ingest | Kho 7 tài liệu/1.775 chunk/390 câu hỏi giữ nguyên | ĐẠT |
| Không fallback sang Gemini khi DeepSeek lỗi | Chain một provider; stream rỗng thử lại cùng model với `reasoning_effort=none`; lỗi trả có kiểm soát | ĐẠT |
| Dùng bảng `sessions`/`messages`, bổ sung cột còn thiếu | Hai migration Phase 4; `sessions.summary`, `token_count`, `updated_at`… | ĐẠT |
| API phiên đầy đủ (tạo, liệt kê, đọc tin nhắn, sửa, xóa) | `backend/app/api/routes.py`; `tests/sessions/test_session_api.py` | ĐẠT |
| Viết lại câu hỏi theo ngữ cảnh, lưu gốc + viết lại | `condense.py`; metadata `rewrite_source`; 14 lượt budget có viết lại | ĐẠT |
| Tóm tắt sau 10 lượt/4.000 token, dùng tóm tắt | `summarize.py`; `summary_used=True`, nguồn `stored` từ lượt 11 | ĐẠT |
| Giữ 6 lượt gần nhất sau tóm tắt | Lưu trữ giữ 6 lượt; prompt chỉ chứa tối đa 6 tin nhắn (~3 lượt) do ngân sách 1.500 token | MỘT PHẦN |
| `POST /chat/stream` SSE, đủ 5 sự kiện, flush từng sự kiện | `chat.py`, `sse.py`; `tests/streaming`; đo 20 mẫu SSE | ĐẠT |
| Xử lý ngắt kết nối, lưu câu trả lời dở | `phase4_disconnect_check.py`: `interrupted`, lưu 24 ký tự, không 500 | ĐẠT |
| Ghi TTFT, tổng thời gian, token vào `query_logs` | Migration + `generation/logger.py` + metadata tin nhắn | ĐẠT |
| RLS: mỗi người chỉ đọc/ghi phiên của mình; kiểm thử hai tài khoản | `phase4_isolation_check.py`: 19/19 | ĐẠT |
| Hook `useChatStream` cho SSE, tự kết nối lại | `frontend/hooks/useChatStream.ts`; `tsc --noEmit` và eslint đạt | ĐẠT (chưa gắn giao diện) |
| Script chạy 10 kịch bản và chấm theo rubric | `evaluation/conversation_bench.py`; hai lần chạy lưu JSON/MD | ĐẠT (script) |
| `pytest tests/sessions tests/streaming -q` | Toàn bộ suite 293 passed, 1 warning | ĐẠT |
| Chạy 10 kịch bản, bảng điểm từng kịch bản | Mục 3; lần 1 3/10, lần 2 2/10 | KHÔNG ĐẠT (ngưỡng 8/10) |
| TTFT 20 lần, p50/p95, mục tiêu p95 ≤ 2 giây | Mục 4.1: p50 3.235,2 ms; p95 10.836,8 ms | KHÔNG ĐẠT |
| Tổng thời gian p95 ≤ 10 giây | Mục 4.1: p95 19.887,6 ms | KHÔNG ĐẠT |
| Cách ly: A không đọc được phiên của B | Mục 6: 19/19 | ĐẠT |
| Ngắt giữa chừng: dừng sinh, không 500 | Mục 2: `interrupted`, không 500 | ĐẠT |
| Hồi quy dev set Giai đoạn 3 ≥ 91,5% | Mục 2: 95,0% đúng hoàn toàn; 97,5% trung bình | ĐẠT |
| Sau 12 lượt, ngữ cảnh không vượt ngân sách token | Mục 5.1: lớn nhất 1.459/1.500 token | ĐẠT |
| Không làm hỏng `/chat` một lượt | Budget check và dev bench gọi `/chat`; kiểm thử cũ đạt | ĐẠT |
| Không lưu nội dung nhạy cảm; có xóa phiên và xóa toàn bộ | `DELETE /sessions/{id}`, `DELETE /sessions`; mục 6 | ĐẠT |
| Không hạ ngưỡng hiệu năng khi chưa có chấp thuận | Báo cáo giữ nguyên ngưỡng 2.000/10.000 ms và 8/10 | ĐẠT |
| Dừng sau báo cáo, không bắt đầu giai đoạn kế tiếp | Báo cáo này | ĐẠT |

**Kết luận:** Giai đoạn 4 đã hoàn tất phần kỹ thuật (phiên, viết lại, tóm tắt, SSE, đo lường,
RLS, hook, script đánh giá, chuyển hẳn sinh văn bản sang DeepSeek) và đạt các tiêu chí an toàn,
cách ly, ngân sách, hồi quy dev set. Tuy nhiên **chưa đạt hai tiêu chí nghiệm thu về chất lượng
hội thoại (3/10 và 2/10 so với ≥ 8/10) và độ trễ (TTFT p95 10,8 giây so với ≤ 2 giây; tổng
p95 19,9 giây so với ≤ 10 giây)**; tiêu chí giữ 6 lượt gần nhất trong prompt cũng chỉ đạt một
phần. Trạng thái tổng thể là **MỘT PHẦN**. Không có ngưỡng nào bị hạ và giai đoạn kế tiếp chưa
được bắt đầu.
