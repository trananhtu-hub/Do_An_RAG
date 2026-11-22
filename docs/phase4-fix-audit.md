# Audit khắc phục Giai đoạn 4 — 2026-11-23

Nhánh `phase4-fix`. Bản sao báo cáo và kết quả cũ tại
`backups/phase4-fix-20261123/`.

## 1. Nhà cung cấp sinh văn bản

| File | Lỗi | Thay đổi | Cách đo |
| :--- | :--- | :--- | :--- |
| `config/generation.yaml` | Chain Gemini trước, DeepSeek dự phòng; tên `deepseek_fallback` | Provider duy nhất `deepseek_primary`; bỏ mọi provider Gemini khỏi chain | `chain.names == ("deepseek_primary",)` trong test factory |
| `backend/app/services/generation/providers/factory.py` | Dựng được adapter Gemini để sinh văn bản | Chỉ chấp nhận `openai_compat`; provider type `gemini` bị từ chối | Test cấu hình từ chối `type: gemini` |
| `backend/app/services/generation/providers/gemini.py` | Đường sinh văn bản Gemini còn tồn tại | Xóa adapter và test riêng | `grep -r GeminiAdapter backend/app` rỗng |
| `backend/app/services/retrieval/llm.py`, `classify.py`, `decompose.py` | Phân loại/tách truy vấn gọi Gemini (`gemini-3.8-flash`) | Client JSON tương thích OpenAI gọi DeepSeek; thiếu khóa thì chỉ dùng heuristic | Test classify với transport giả; không còn URL Gemini |
| `backend/app/core/config.py`, `backend/app/services/*/settings.py`, `.env.example` | Biến `OPENAI_*`, `GEMINI_MODEL_DEFAULT` dùng cho sinh văn bản | Thêm `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`; `GEMINI_API_KEY` chỉ còn cho embedding 768 | Test `Settings` mặc định DeepSeek; smoke test retrieval |
| `evaluation/gen_bench.py`, `evaluation/conversation_bench.py`, `scripts/phase4_serve.py` | Nhãn provider cũ, judge ưu tiên `deepseek_fallback` | Nhãn `deepseek_primary`; judge chỉ DeepSeek | Báo cáo bench in `provider_chain` |

## 2. Đo lường và công bằng bộ test

| File | Lỗi | Thay đổi | Cách đo |
| :--- | :--- | :--- | :--- |
| `evaluation/conversation_bench.py::_citation_document_ok` | Khi ô Căn cứ không nêu tên tài liệu, hàm đòi đủ mọi tài liệu của kịch bản → KB-08 lượt 2 trượt oan | Chỉ đòi tài liệu suy ra từ chính ô Căn cứ; nếu ô chỉ nêu mục thì đòi tài liệu chứa mục đó | Test hồi quy KB-08 lượt 2 |
| Judge | Lịch sử cắt 800 ký tự; mọi tiêu chí của kịch bản áp cho mọi lượt | Lịch sử tối đa 4.000 ký tự; lọc tiêu chí theo lượt; nêu rõ quy tắc trích dẫn thừa | Chạy lại 10 kịch bản, so điểm từng lượt |
| Bench | Chỉ chạy `service.answer`, chưa đo SSE | Thêm `--transport stream`, chấm câu trả lời ghép từ token và trích dẫn từ sự kiện `citations` | Cùng bộ, chạy cả `answer` và `stream` |
| `query_logs` | Thiếu mốc thời gian truy hồi/sinh và token đầu ra | Ghi `retrieval_ms`, `rerank_ms`, `parent_expand_ms`, `prompt_ms`, `prefill_ms`, `generation_ms`, `output_tokens`, `ttft_ms`, `total_ms`, `provider`, `judge_provider` | Đọc metadata bản ghi mới sau một lượt |
| `scripts/phase4_ttft_measure.py` | Chỉ đo 20 câu một lượt | Thêm chế độ dev đa lượt 4 lượt × 10 kịch bản, p50/p95 theo lượt; đo lại 20 mẫu cũ, ghi cold/warm | Log mới có nhãn nguồn |

## 3. Hội thoại và ngân sách

| File | Lỗi | Thay đổi | Cách đo |
| :--- | :--- | :--- | :--- |
| `backend/app/services/chat.py` | Tóm tắt chạy nền sau lượt trả lời; lượt kế đọc phiên trước khi tóm tắt xong → `summary_used=False` suốt 12 lượt | Chờ có giới hạn trước khi chuẩn bị lượt; ghi `summary_source`, `summary_latency_ms` | Test 13–14 lượt khẳng định `summary_used=True` |
| `backend/app/services/generation/tokens.py` (mới) | Ước lượng 3,5 ký tự/token, không có trần prompt | Đếm bằng tokenizer DeepSeek (hoặc proxy ghi rõ), thêm `max_prompt_tokens` và cắt ngữ cảnh có kiểm soát | Script audit token theo thành phần |
| Prompt/ngữ cảnh | Prompt thực tế ~12k token, đầu ra tới 16k | Giảm `max_context_tokens`, `max_output_tokens`; đo lại dev set, sụt chất lượng ≤ 2 điểm % | `gen_bench.py` trước/sau |
| `config/generation.yaml` | Đặt `max_output_tokens: 3072` làm 6/40 lượt dev cắt cụt đúng mốc 3.072, hỏng schema JSON và mất trích dẫn | Nâng lên 6.144 (trên mức lớn nhất từng thấy 5.605); ghi lại số đo trong YAML | Đếm lượt có `output_tokens == 3072` và cảnh báo SchemaError trong JSON bench |
| `generation/service.py`, `generation/citations.py` | Khi stream không parse được JSON, phần nội dung còn lại bị bỏ trích dẫn nội tuyến → sự kiện `citations` rỗng | `inline_citation_sources()` trích `[Nguồn – Mục]` và điền vào `payload.citations` của nhánh dự phòng | Test đơn vị với JSON bị cắt |
| `conversation/context.py` | Ngân sách 1.500 token tính bằng ký tự/3,0; tokenizer thật cho thấy tới 1.666 token | Đếm và cắt bằng tokenizer DeepSeek dùng chung (`default_token_counter`) | `conversation_tokens` trong metadata bằng số đếm thật; script budget kiểm lại |
| `backend/app/services/generation/service.py`, `providers/openai_compat.py`, `config/generation.yaml` | Mọi câu hỏi chạy `reasoning_effort=medium`; DeepSeek sinh phần suy luận ẩn trước token đầu nên TTFT cao | Câu tra cứu đơn giản (`tra_cuu`, `tron_thuat_ngu`) dùng `simple_query_thinking_level` (`none` tắt suy luận ẩn); câu so sánh/nhiều ràng buộc giữ `medium`; adapter gửi `reasoning_effort` | Test cấu hình/adapter/service; TTFT 40 lượt dev trước/sau, chất lượng dev không sụt quá 2 điểm % |
| `evaluation/gen_bench.py` | Luôn truyền `thinking_level=medium` nên bỏ qua mức theo loại câu hỏi | Chỉ truyền khi có `--thinking`; mặc định để service tự chọn | `thinking=theo loại câu hỏi` trong báo cáo gen_bench |
| `evaluation/conversation_bench.py` | CLI chỉ đọc bộ nghiệm thu | Thêm `--conversations` để chạy bộ dev mà không đụng bộ nghiệm thu | Lệnh chạy dev nêu đường dẫn `inputs/conversations_dev.md` |
| `generation/providers/openai_compat.py` | 1/40 lượt dev mỗi lần chạy có phản hồi rỗng (`finish_reason=length`, token suy luận ăn hết hạn mức); chain một provider nên lỗi thành "Không tạo được câu trả lời" | Static stream rỗng và có `reasoning_effort` khác `none`: thử lại đúng một lần với `reasoning_effort=none` trên cùng model DeepSeek; vẫn rỗng thì trả `LLMError` có kiểm soát | Test adapter: lượt đầu rỗng → lượt hai mang `reasoning_effort=none`; khi đã `none` mà rỗng thì chỉ gọi một lần rồi lỗi |
| `generation/service.py`, `generation/context.py` | Vòng thu ngữ cảnh tính bằng ước lượng ký tự/token trong khi bản kiểm kê dùng tokenizer DeepSeek; khối đầu luôn được giữ nguyên nên prompt vẫn vượt trần (12.248–12.256 > 12.000) và chỉ còn cảnh báo | Thêm `fit_context_to_tokens` cắt theo tokenizer thật: giữ các khối đầu còn vừa, cắt dần khối kế tiếp và bỏ khối sau, giữ nguyên nhãn tài liệu/mục; bỏ hội thoại trước nếu ngân sách còn lại cho ngữ cảnh dưới 128 token | Unit test hồi quy: context vừa theo ước lượng nhưng vượt theo tokenizer thật → `over_limit=False`; test ngân sách 0 trả ngữ cảnh rỗng. Hai lần chạy nghiệm thu trước bản sửa này, ghi rõ trong báo cáo |

## 4. Đo lại và nghiệm thu

- Chạy tuần tự hoặc `--workers 1` để tránh `bad allocation` của reranker.
- TTFT đo từ lúc gửi yêu cầu tới token đầu tiên; không đổi định nghĩa.
- Kết quả Gemini cũ chỉ là lịch sử, không so trực tiếp.
- Ghi SHA-256 `inputs/conversations.md` trước và sau khi chạy nghiệm thu.
- Nếu không đạt ngưỡng, ghi MỘT PHẦN với số thật; không hạ ngưỡng.
