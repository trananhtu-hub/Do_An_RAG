# BÁO CÁO GIAI ĐOẠN 3

**Trạng thái: MỘT PHẦN**

Ngày: 2026-11-21 (giờ địa phương; log và API ghi theo UTC 2026-11-20/21).
Phạm vi: xây tầng sinh câu trả lời có kiểm chứng (`prompts/v1/`, schema JSON, hậu kiểm
trích dẫn, từ chối có phân loại) và lớp `LLMProvider` (Gemini + adapter tương thích OpenAI,
chuỗi dự phòng, retry/backoff, ghi `query_logs`). Không bao gồm streaming, session, giao diện
(Các giai đoạn 6–7).

> **Lưu ý đánh số giai đoạn:** CLAUDE.md xếp tầng sinh câu trả lời vào **Giai đoạn 5** và dành
> Giai đoạn 3 cho ingestion; đề bài này gọi công việc hiện tại là **Giai đoạn 3**. Báo cáo giữ
> cách gọi của đề bài. Khi cập nhật CLAUDE.md cần thống nhất lại cách đánh số.

> **W12:** mọi tài liệu và mã nguồn gọi tìm kiếm từ vựng là "full-text/lexical", không gọi
> "BM25". Giai đoạn này không thay đổi tầng truy hồi.

> **Vì sao trạng thái là MỘT PHẦN:** khóa Gemini của dự án đã hết hạn mức (HTTP 429
> `RESOURCE_EXHAUSTED`) trong toàn bộ thời gian đo, nên mọi câu trả lời trong benchmark do
> adapter dự phòng DeepSeek sinh ra, không phải `gemini-3.8-flash`. Đồng thời tiêu chí "CoT
> tăng ≥5 điểm % độ chính xác" không đạt (xem mục 3). Các tiêu chí còn lại đều đạt.

## 1. Việc đã làm

### 1.1 Tệp và mô-đun đã tạo

| Thành phần | Mô tả |
| :--- | :--- |
| `prompts/v1/system_base.md` | Vai trò, 5 quy tắc bắt buộc, schema JSON, định dạng trích dẫn `[tài liệu – mục Y]`, mẫu từ chối |
| `prompts/v1/system_cot.md` | CoT kiểm chứng: phân loại K1/K2/K3, bước suy luận tuần tự, tự kiểm tra trước kết luận |
| `prompts/v1/multi_constraint.md` | Addendum câu nhiều ràng buộc: bảng `# \| Ràng buộc \| Phương án đáp ứng \| Căn cứ` |
| `prompts/v1/compare.md` | Addendum câu so sánh: bảng cùng tiêu chí, ô "không có trong tài liệu" |
| `prompts/v1/abstain.md` | Quy tắc từ chối: `no_evidence` và `out_of_scope`, chủ đề gần nhất |
| `backend/app/services/generation/prompts.py` | `PromptLibrary` ghép `system_base + system_cot + addendum + abstain`; ánh xạ loại câu hỏi sang mode |
| `backend/app/services/generation/types.py` | Pydantic v2: `AnswerPayload`, `Citation`, `ReasoningStep`, `GenerationResult`, `CitationReport` |
| `backend/app/services/generation/schema.py` | Trích JSON từ đầu ra (bỏ fence), validate schema, thông điệp sửa lỗi cho lần thử lại |
| `backend/app/services/generation/context.py` | Dựng ngữ cảnh từ chunk đã truy hồi; nhóm theo chunk cha; nhãn `Tài liệu/Mục/Nội dung`; ngân sách token |
| `backend/app/services/generation/citations.py` | Hậu kiểm trích dẫn: đối chiếu tài liệu/mục với ngữ cảnh đã cấp; kiểm tra quote nguyên văn; chấp nhận nhãn mục con nằm trong chunk cha và danh sách mục phân tách bằng dấu phẩy |
| `backend/app/services/generation/service.py` | `GenerationService.answer()`: dựng ngữ cảnh → sinh → retry schema tối đa 1 → từ chối thì xóa trích dẫn/hạ confidence → hậu kiểm → ghi log |
| `backend/app/services/generation/providers/base.py` | Giao diện `LLMProvider.complete(messages, **kwargs)`, `LLMResponse`, `Usage`, `Pricing` |
| `backend/app/services/generation/providers/gemini.py` | `GeminiAdapter` REST: `systemInstruction`, `thinkingConfig.thinkingLevel`, JSON mode; retry/backoff |
| `backend/app/services/generation/providers/openai_compat.py` | `OpenAICompatAdapter`: `base_url`/`model` cấu hình được, gọi `/chat/completions`, retry/backoff |
| `backend/app/services/generation/providers/fallback.py` | `FallbackChain`: thử lần lượt theo `config/generation.yaml`, ghi `attempts`, ném `FallbackExhausted` khi hết |
| `backend/app/services/generation/providers/factory.py` | Khởi tạo provider từ config + môi trường; bỏ qua provider thiếu khóa |
| `backend/app/services/generation/logger.py` | Ghi `query_logs` (best effort, lỗi không làm hỏng luồng trả lời) |
| `backend/app/services/generation/settings.py` | Nạp `.env` cục bộ, không ghi giá trị bí mật ra log |
| `config/generation.yaml` | Chuỗi provider, thinking level, retry schema, ngân sách ngữ cảnh, giá niêm yết, bảng log |
| `supabase/migrations/20261121120000_generation_phase3.sql` | Thêm cột `prompt_version`, `cost_usd`, `fallback_used` vào `query_logs`; RLS vẫn bật, mặc định đóng |
| `evaluation/gen_dev_questions.py` | Sinh câu hỏi dev từ nội dung tài liệu (có checkpoint, chạy lại được) |
| `evaluation/dev_generation.jsonl` | 40 câu dev (GD-001..GD-040) kèm đáp án tham chiếu và đoạn trích căn cứ |
| `evaluation/dev_generation_review.md` | Rà soát dev set: trùng lặp, thiếu quote, đối chiếu ngân hàng câu hỏi và dev set truy hồi |
| `evaluation/gen_bench.py` | Benchmark sinh câu trả lời: `--before-after`, `--scope`, `--in-scope`, `--citations`; judge có cache; snapshot ngữ cảnh cố định giữa hai điều kiện |
| `evaluation/fallback_demo.py` | Mô phỏng khóa Gemini hỏng/thiếu để chứng minh chuỗi dự phòng |
| `evaluation/verify_query_logs.py` | Gửi một lượt sinh thật và đọc lại dòng `query_logs` mới nhất |
| `tests/generation/` | 87 unit test: schema, citations, context, prompts, service, factory, fallback, logger |

### 1.2 Quyết định kỹ thuật

- **Chỉ đưa chunk đã truy hồi vào prompt.** `build_context` dựng các khối `[ĐOẠN n]` từ
  `RetrievedChunk` (nhóm theo `parent_id`), cắt theo ngân sách `max_context_tokens = 8000`.
  Không có đường nào nạp toàn văn tài liệu.
- **Gemini 3.8 Flash không nhận `temperature`/`top_p`/`top_k`.** Mức suy luận chỉ điều khiển
  bằng `generationConfig.thinkingConfig.thinkingLevel` (`low`/`medium`/`high`, mặc định
  `medium`). Đây là khác biệt so với skill `prompting-rag` cũ và đã được bổ sung vào skill.
- **Hai lần gọi tối đa khi sai schema.** Lần đầu sinh bình thường; nếu `parse_answer` ném
  `SchemaError`, gửi lại kèm đầu ra cũ (cắt 4000 ký tự) và thông điệp sửa lỗi chứa schema
  mẫu. Quá một lần thì ném lỗi ra ngoài thay vì trả câu trả lời không kiểm chứng được.
- **Từ chối có phân loại.** `abstained=true` buộc `citations=[]` và `confidence ≤ 0.2`;
  `no_evidence` dùng khi ngữ cảnh thiếu căn cứ, `out_of_scope` khi câu hỏi ngoài phạm vi
  chứng chỉ. `nearest_topics` chỉ được nêu chủ đề có thật trong ngữ cảnh.
- **Hậu kiểm trích dẫn độc lập với mô hình.** Mọi nhãn `[...]` không phải markdown link được
  đối chiếu với tài liệu/mục thực có trong ngữ cảnh; quote trong trường `citations` phải xuất
  hiện nguyên văn (hoặc khớp 80% đầu với quote dài). Chunk cha gộp nhiều mục con nên nhãn mục
  xuất hiện trong nội dung chunk cũng được coi là hợp lệ.
- **Chuỗi dự phòng khai báo, không hard-code.** `config/generation.yaml` liệt kê
  `gemini_primary` → `deepseek_fallback`; provider thiếu khóa bị bỏ qua ngay khi khởi tạo.
  `FallbackChain` ghi lại `attempts` và `fallback_used` vào kết quả và log.
- **Chi phí chỉ tính theo giá niêm yết Gemini** (0,75/3,75 USD mỗi 1 triệu token vào/ra).
  Provider dự phòng để giá 0 và báo cáo ghi rõ, không tự bịa đơn giá.

### 1.3 Đối chiếu các nhược điểm liên quan

| Mã | Trạng thái sau giai đoạn này | Ghi chú |
| :--- | :--- | :--- |
| W1 (suy luận K3 nhảy cóc) | Đã xử lý một phần, đã đo | `system_cot.md` buộc phân rã dữ kiện – điều kiện – quy tắc và tự kiểm tra; ablation chưa chứng minh tăng ≥5 điểm % (mục 3) |
| W2 (mất cấu trúc bảng khi parse) | Giảm thiểu | Ngữ cảnh giữ nguyên văn từng mục, không tóm tắt lại; prompt câu so sánh/nhiều ràng buộc yêu cầu bảng có căn cứ từng ô |
| W4 (thiếu ngữ cảnh hội thoại) | Chưa xử lý | Thuộc Giai đoạn 6; `session_id` đã có trong `query_logs` để nối sau |
| W5 (chưa streaming) | Chưa xử lý | Thuộc Giai đoạn 6–7 |
| W8 (phân tích lỗi thiếu nhóm) | Đã xử lý một phần | Benchmark phân nhóm theo K1/K2/K3 và theo loại câu hỏi; kiểm định thống kê thuộc Giai đoạn 8 |
| W11/W13 | Không thuộc phạm vi | Thuộc Giai đoạn 2/8 |

## 2. Kết quả kiểm thử

| Hạng mục | Lệnh | Kỳ vọng | Thực tế | Đạt |
| :--- | :--- | :--- | :--- | :---: |
| Unit test tầng sinh | `pytest tests/generation -q` | 0 lỗi | `87 passed in 0.64s` | ĐẠT |
| Toàn bộ kiểm thử | `pytest backend tests -q` | 0 lỗi | `209 passed, 1 warning in 1.52s` | ĐẠT |
| Lint backend | `ruff check backend ingestion evaluation scripts tests` + `black --check ...` | 0 lỗi | `All checks passed!`; `96 files would be left unchanged` | ĐẠT |
| Lint frontend | `npm --prefix frontend run lint` | 0 lỗi | exit 0 | ĐẠT |
| CoT trước/sau | `python evaluation/gen_bench.py --before-after` | Tăng ≥5 điểm % | **Giảm 3,7 điểm %** (96,2% → 92,5%) | **KHÔNG ĐẠT** |
| Câu ngoài phạm vi | `python evaluation/gen_bench.py --scope` | Từ chối đúng ≥90%, không bịa | 10/10 = **100%** | ĐẠT |
| Câu trong phạm vi | `python evaluation/gen_bench.py --in-scope` | Từ chối sai ≤5% | 0/20 = **0%** | ĐẠT |
| Trích dẫn | `python evaluation/gen_bench.py --citations --limit 10` | 100% hợp lệ | 10/10 câu, **100,0%** | ĐẠT |
| Chuỗi dự phòng | `python evaluation/fallback_demo.py` | 3/3 câu do adapter dự phòng trả lời | 3/3 (khóa hỏng) + 1 câu (thiếu khóa, factory bỏ qua Gemini) | ĐẠT |
| Lỗi schema sau retry | `python evaluation/gen_bench.py --before-after` | 0 lỗi cuối | 80/80 câu có JSON hợp lệ; 1 câu phải thử lại đúng 1 lần; **0 lỗi cuối** | ĐẠT |
| Ghi `query_logs` | `python evaluation/verify_query_logs.py` | Đủ model, prompt_version, token, cost, latency, fallback_used | Đã đọc lại dòng thật, khớp toàn bộ trường | ĐẠT |
| `make lint` / `make test` | `make lint`, `make test` | Chạy được | GNU Make 4.4.1 bản Windows32 không mở được đường dẫn `D:\Đồ Án RAG` (ký tự `Đ`, ổ D không có tên 8.3) | KHÔNG CHẠY ĐƯỢC — đã chạy đúng các lệnh bên trong target |

## 3. So sánh trước/sau CoT

Chạy `python evaluation/gen_bench.py --before-after` lúc 16:22 ngày 2026-11-21, 40 câu dev,
cùng snapshot ngữ cảnh cho cả hai điều kiện, `thinking_level=medium`, judge tự động có cache.

**Cảnh báo quan trọng:** cả 80 câu trả lời (40 trước + 40 sau) do `deepseek_fallback` sinh ra vì
Gemini trả HTTP 429 trong suốt thời gian đo. Bảng dưới đo tác dụng của CoT trên mô hình dự
phòng, **không** phải trên `gemini-3.8-flash`.

| Chỉ số | Trước CoT | Sau CoT | Chênh lệch |
| :--- | ---: | ---: | ---: |
| Độ chính xác trung bình | 96,2% | 92,5% | **-3,7 điểm %** |
| Tỷ lệ đúng hoàn toàn | 92,5% | 87,5% | -5,0 điểm % |
| Tỷ lệ đúng một phần | 7,5% | 10,0% | +2,5 điểm % |
| Tỷ lệ sai/từ chối sai | 0,0% | 2,5% | +2,5 điểm % |
| Tỷ lệ từ chối sai | 0,0% | 0,0% | +0,0 điểm % |
| Hiệu lực trích dẫn | 1,000 | 1,000 | +0,000 |
| Độ trễ trung bình (ms) | 10.906,8 | 10.813,9 | -92,9 |
| Token vào trung bình | 6.880,2 | 8.015,2 | +1.135,0 |
| Token ra trung bình | 1.627,5 | 1.562,7 | -64,8 |
| Tổng chi phí (USD) | 0,0 | 0,0 | +0,000 |

Theo mức nhận thức (điểm trung bình câu):

| Mức | Trước CoT | Sau CoT | Số câu |
| :--- | ---: | ---: | ---: |
| K1 | 0,947 | 0,868 | 19 |
| K2 | 1,000 | 0,969 | 16 |
| K3 | 0,900 | 1,000 | 5 |

Chỉ 5/40 câu đổi điểm giữa hai điều kiện (GD-012 tăng 0,5→1,0; GD-023, GD-030, GD-035 giảm
1,0→0,5; GD-039 giảm 0,5→0,0). Độ chính xác trước CoT đã ở mức 96,2% nên **hiệu ứng trần**
khiến phép đo không còn dư địa thể hiện lợi ích của CoT; nhóm K3 (5 câu) tăng 0,9→1,0 nhưng
mẫu quá nhỏ để kết luận. Tiêu chí "CoT tăng ≥5 điểm %" vì vậy **không đạt**, và kết quả này
không đủ để bác bỏ hay khẳng định CoT trên mô hình chính.

## 4. Kiểm chứng trích dẫn và từ chối

### 4.1 Mười câu ngoài phạm vi

`python evaluation/gen_bench.py --scope` — bộ câu hỏi tại `inputs/out_of_scope_questions.md`
(5 câu kiến thức ngoài AWS: Python, TCP/UDP, SQL, git, OSI; 5 câu dịch vụ AWS ngoài tài liệu:
Bedrock, CodeWhisperer, HealthImaging, Clean Rooms, Verified Access).

| Chỉ số | Kết quả |
| :--- | :--- |
| Từ chối đúng | **10/10 = 100,0%** (mục tiêu ≥90%) |
| Phân loại `out_of_scope` | 4 câu (A1, A3, A4, B1) |
| Phân loại `no_evidence` | 6 câu (A2, A5, B2–B5) |
| Trích dẫn còn lại khi từ chối | 0 ở cả 10 câu |
| Rò rỉ nội dung kỹ thuật trả lời câu hỏi | Không có ở cả 10 câu |
| Điểm judge từ chối | 1,0 ở cả 10 câu |

### 4.2 Hai mươi câu trong phạm vi

`python evaluation/gen_bench.py --in-scope` — 20 câu đầu của dev set.

| Chỉ số | Kết quả |
| :--- | :--- |
| Từ chối sai | **0/20 = 0,0%** (mục tiêu ≤5%) |

### 4.3 Mười câu kiểm tra trích dẫn

`python evaluation/gen_bench.py --citations --limit 10` (sau khi sửa hậu kiểm):

```
Câu có kiểm tra trích dẫn: 10/10
Hiệu lực trích dẫn trung bình: 100.0% (mục tiêu 100%)
```

Hai lỗi hậu kiểm đã sửa trong giai đoạn này:

1. **Nhãn mục con nằm trong chunk cha:** chunk cha có thể có nhãn "Mục 1.2" nhưng nội dung gộp
   cả mục 1.6; trích dẫn "Mục 1.6" là hợp lệ. Hậu kiểm nay trích các nhãn `Mục X.Y` trong nội
   dung chunk và coi đó là đích hợp lệ.
2. **Danh sách nhiều mục:** `[tài liệu – Mục 1.4, Mục 1.5]` từng bị đối chiếu như một chuỗi
   duy nhất; nay tách theo dấu phẩy/chấm phẩy và kiểm tra từng mục.

Có unit test cho cả hai trường hợp; tổng 87 test tầng sinh đều đạt.

### 4.4 Ghi nhật ký

`python evaluation/verify_query_logs.py` gửi một câu thật qua `GenerationService` với
`write_log=True` rồi đọc lại dòng mới nhất:

```
provider: deepseek_fallback | model: deepseek-flash
prompt_version: v1 | mode: base
tokens: 7360 vào / 1032 ra
cost_usd: 0.0
latency_ms: 9009.88
fallback_used: deepseek_fallback
schema_retries: 0
query_logs (dòng mới nhất):
  question khớp: True
  model: deepseek-flash | prompt_version: v1
  tokens: 7360 vào / 1032 ra
  cost_usd: 0E-8 | latency_ms: 9010 | fallback_used: deepseek_fallback
  metadata.provider: deepseek_fallback
  metadata.citation_validity: 1.0
  metadata.schema_retries: 0
```

## 5. Chi phí và độ trễ

- **Độ trễ:** trung bình 10,9 giây/câu (trước CoT) và 10,8 giây/câu (sau CoT) trên DeepSeek.
  Đây là độ trễ của adapter dự phòng, không phải của Gemini; chưa có số TTFT vì chưa streaming.
- **Token:** trung bình 8.015 token vào / 1.563 token ra khi bật CoT; CoT làm tăng khoảng 1.135
  token vào mỗi câu do thêm chỉ dẫn và bước suy luận.
- **Chi phí đo được:** **0,0 USD/câu** trong log, vì câu trả lời do DeepSeek sinh và cấu hình cố
  ý chỉ tính giá Gemini đã niêm yết.
- **Ước tính nếu Gemini phục vụ** (0,75 USD/1M token vào, 3,75 USD/1M token ra): khoảng
  **0,0119 USD/câu** khi bật CoT và **0,0113 USD/câu** khi tắt CoT. Đây là ước tính từ số token
  đo được trên DeepSeek, **không phải** số đo thực tế của Gemini.

## 6. Vấn đề và rủi ro

| Vấn đề | Ảnh hưởng | Đã xử lý / hướng xử lý |
| :--- | :--- | :--- |
| Khóa Gemini hết hạn mức (HTTP 429 `RESOURCE_EXHAUSTED`) suốt thời gian đo | Không đo được `gemini-3.8-flash`; toàn bộ số liệu sinh câu trả lời là của DeepSeek | Đã chứng minh chuỗi dự phòng hoạt động đúng; cần bổ sung hạn mức/khóa mới rồi chạy lại benchmark trước khi chốt báo cáo đề án |
| CoT không tăng độ chính xác trên tập dev | Tiêu chí "tăng ≥5 điểm %" không đạt; kết luận về CoT chưa đủ mạnh | Nghi ngờ hiệu ứng trần: độ chính xác trước CoT đã 96,2%, chỉ 5/40 câu thay đổi điểm. Cần tập dev khó hơn (K3 nhiều hơn) và lặp lại nhiều lần để kiểm định (Giai đoạn 8) |
| Chất lượng adapter dự phòng khác mô hình chính | Số liệu benchmark không đại diện cho cấu hình mặc định `gemini-3.8-flash` | Ghi rõ trong mọi bảng; không suy diễn kết quả DeepSeek cho Gemini |
| Hậu kiểm trích dẫn dùng so khớp chuỗi đã chuẩn hóa | Có thể bỏ sót trích dẫn sai nhưng gần đúng, hoặc chấp nhận nhãn mục con nằm trong chunk cha | Đã bổ sung test cho hai trường hợp; hạn chế này đã ghi nhận và cần thêm LLM-judge khi chốt báo cáo đề án |
| Giá DeepSeek không đưa vào cấu hình | `cost_usd` của câu trả lời dự phòng bằng 0, không phản ánh chi phí thật | Cố ý: chỉ tính theo đơn giá đã niêm yết và kiểm chứng; khi có bảng giá chính thức, bổ sung vào `config/generation.yaml` |
| `make lint`/`make test` không chạy được trên máy này | GNU Make 4.4.1 bản Windows32 không mở được đường dẫn có ký tự `Đ`/dấu tiếng Việt (ổ D không bật tên 8.3) | Đã chạy đúng các lệnh bên trong target (`ruff`, `black --check`, `eslint`, `pytest backend tests`) và ghi lại kết quả ở mục 2 |

## 7. Đề xuất cho Giai đoạn 4

1. **Bổ sung hạn mức Gemini hoặc khóa mới** rồi chạy lại `evaluation/gen_bench.py --before-after`
   để có bảng so sánh đúng mô hình mặc định trước khi dùng số liệu trong báo cáo đề án.
2. **Giữ nguyên giao diện `LLMProvider`** khi thêm streaming ở Giai đoạn 6: thêm
   `complete_stream(messages, **kwargs)` vào giao diện, không đổi chữ ký `complete`.
3. **Truyền `session_id` và `rewritten_query`** từ tầng session (Giai đoạn 6) vào
   `GenerationService.answer()`; `query_logs` đã có sẵn hai cột này.
4. **Đưa `citation_report` ra API** dưới dạng trường riêng để frontend hiển thị cảnh báo trích
   dẫn thay vì chỉ ghi log.
5. **Làm khó tập dev** cho ablation CoT: tăng tỷ lệ K3 và câu nhiều ràng buộc, đồng thời chạy
   lặp nhiều lần để có kiểm định thống kê ở Giai đoạn 8.
6. **Bổ sung đơn giá DeepSeek** vào `config/generation.yaml` khi có bảng giá chính thức, để
   `cost_usd` phản ánh đúng chi phí dự phòng.

## 8. Xác nhận Definition of Done

| Tiêu chí | Kết quả |
| :--- | :--- |
| Prompt v1 đủ 5 tệp, có mục tiêu/quy tắc/định dạng/ví dụ, không ghi đè phiên bản cũ | Đạt |
| CoT tách bước suy luận trước kết luận; câu nhiều ràng buộc có bảng kiểm | Đạt |
| Schema JSON + Pydantic, retry tối đa 1 lần khi sai schema | Đạt |
| Mọi khẳng định có trích dẫn `[tài liệu – mục Y]`; hậu kiểm đối chiếu ngữ cảnh | Đạt (10/10 câu, 100% hiệu lực) |
| Từ chối đúng khi thiếu căn cứ; phân biệt `no_evidence`/`out_of_scope` | Đạt (10/10 câu ngoài phạm vi) |
| Không từ chối sai câu trong phạm vi | Đạt (0/20) |
| `LLMProvider` + `GeminiAdapter` + `OpenAICompatAdapter` + `FallbackChain` | Đạt |
| Retry/backoff, log token vào `query_logs` | Đạt (đã đọc lại dòng log thật) |
| Dev set 40–60 câu sinh từ tài liệu, không trùng ngân hàng câu hỏi | Đạt (40 câu, Jaccard cao nhất 0,197 so với ngân hàng) |
| Benchmark trước/sau CoT tự động, có bảng so sánh | Đạt (có bảng; nhưng tiêu chí tăng ≥5 điểm % **không đạt**) |
| 0 lỗi schema sau retry | Đạt (xem mục 2) |
| Chạy đúng mô hình chính `gemini-3.8-flash` | **Không đạt** — khóa hết hạn mức, toàn bộ do dự phòng trả lời |
| Báo cáo giai đoạn đầy đủ, trung thực | Đạt |

**Kết luận:** Giai đoạn 3 đạt phần lớn Definition of Done về mã nguồn, kiểm thử, trích dẫn và
từ chối. Hai tiêu chí chưa đạt là chạy bằng mô hình chính (bị chặn bởi hạn mức Gemini) và mức
tăng độ chính xác của CoT ≥5 điểm %. Vì vậy trạng thái giai đoạn là **MỘT PHẦN**, không phải
HOÀN THÀNH.
