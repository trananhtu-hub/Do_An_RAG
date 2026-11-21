---
name: prompting-rag
description: "Thiết kế prompt RAG có trích dẫn, xử lý câu hỏi K3 bằng CoT kiểm chứng, đầu ra JSON và từ chối khi thiếu căn cứ. Dùng ở Giai đoạn 3 (Giai đoạn 5 theo cách đánh số trong CLAUDE.md)."
---

# Skill: Prompting RAG

## Mô tả

Thiết kế và đánh giá prompt cho tầng sinh câu trả lời theo CLAUDE.md: tách prompt theo loại câu hỏi (tra cứu, so sánh, tình huống K3), buộc mô hình xác định dữ kiện – điều kiện – quy tắc trước khi kết luận, yêu cầu trích dẫn nguồn từ chunk và từ chối khi tài liệu không đủ căn cứ. Đầu ra JSON theo schema, kiểm chứng trích dẫn sau sinh.

## Khi nào dùng

- Xây hoặc sửa prompt template trong `prompts/` và chạy ablation CoT.
- Khi câu trả lời sai ở nhóm K3, thiếu trích dẫn hoặc từ chối sai.
- Khi thay đổi model Gemini/DeepSeek hoặc schema đầu ra.

## Cấu trúc prompt hiện có

`prompts/v1/` gồm 5 tệp, mỗi tệp có mục tiêu, quy tắc, định dạng đầu ra và ví dụ:

| Tệp | Vai trò |
| :--- | :--- |
| `system_base.md` | Vai trò, 5 quy tắc bắt buộc, schema JSON, mẫu từ chối |
| `system_cot.md` | Bật CoT kiểm chứng: phân loại K1/K2/K3, các bước suy luận, bảng kiểm ràng buộc |
| `multi_constraint.md` | Addendum cho câu nhiều ràng buộc: bảng `# | Ràng buộc | Phương án đáp ứng | Căn cứ` |
| `compare.md` | Addendum cho câu so sánh: bảng cùng tiêu chí, ô "không có trong tài liệu" |
| `abstain.md` | Quy tắc từ chối: `no_evidence` và `out_of_scope`, chủ đề gần nhất |

Prompt cuối = `system_base` + `system_cot` (nếu bật CoT) + addendum theo loại câu hỏi + `abstain`, nối bằng `PromptLibrary` trong `backend/app/services/generation/prompts.py`.

## Ràng buộc mô hình

- Gemini 3.8 Flash **không nhận** `temperature`, `top_p`, `top_k`. Mức suy luận chỉ điều khiển bằng `thinking_level` (`low` | `medium` | `high`, mặc định `medium`), gửi dưới dạng `generationConfig.thinkingConfig.thinkingLevel`.
- Provider dự phòng chạy qua giao diện tương thích OpenAI (`base_url` và `model` đọc từ `.env`); chuỗi dự phòng khai báo trong `config/generation.yaml`.
- Chi phí chỉ tính theo giá niêm yết Gemini; provider dự phòng để `pricing = 0` và ghi rõ khi báo cáo.

## Các bước

1. Phân loại câu hỏi đầu vào (`tra_cuu`, `so_sanh`, `nhieu_rang_buoc`, `tron_thuat_ngu`); ánh xạ sang mode trong `QUERY_TYPE_MODES`.
2. Đưa ngữ cảnh dưới dạng các khối `[ĐOẠN n]` kèm tài liệu và mục; không đưa toàn văn tài liệu vào prompt.
3. Với câu K3: yêu cầu liệt kê ràng buộc, trích quy tắc, đối chiếu từng phương án, tự kiểm tra rồi mới kết luận.
4. Buộc trả JSON đúng schema: `answer`, `reasoning_steps`, `citations` (`source`, `quote`), `confidence`, `abstained`, `abstention_type`, `nearest_topics`. Retry tối đa 1 lần khi sai schema.
5. Mọi khẳng định kỹ thuật gắn trích dẫn `[tên tài liệu – mục Y]`; hậu kiểm bằng `check_citations` so với chunk đã cấp.
6. Từ chối khi ngữ cảnh không chứa căn cứ: `citations: []`, `confidence ≤ 0.2`, nêu chủ đề gần nhất có thật trong ngữ cảnh.
7. Chạy ablation có/không CoT trên tập dev: `python evaluation/gen_bench.py --before-after`.
8. Ghi phiên bản prompt và kết quả vào `docs/`; không sửa test set.

## Lệnh

```bash
python evaluation/gen_bench.py --before-after
python evaluation/gen_bench.py --scope
python evaluation/gen_bench.py --in-scope
python evaluation/gen_bench.py --citations
python evaluation/fallback_demo.py
```

## Tiêu chí nghiệm thu

- Mọi câu trả lời có trích dẫn tới chunk nguồn; không có trích dẫn bịa.
- Câu K3 được phân tích tuần tự trước khi kết luận; có kết quả ablation CoT.
- Đầu ra đúng JSON schema, 0 lỗi schema sau retry trên bộ dev.
- Có hành vi từ chối rõ ràng khi ngữ cảnh thiếu căn cứ; không lẫn `no_evidence` với `out_of_scope`.
- Prompt template nằm trong `prompts/v1/`, có phiên bản và không chứa khóa bí mật.
