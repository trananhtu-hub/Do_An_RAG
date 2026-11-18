---
name: prompting-rag
description: "Thiết kế prompt RAG có trích dẫn, xử lý câu hỏi K3 bằng CoT kiểm chứng, đầu ra JSON và từ chối khi thiếu căn cứ. Dùng ở Giai đoạn 5."
---

# Skill: Prompting RAG

## Mô tả

Thiết kế và đánh giá prompt cho tầng sinh câu trả lời theo CLAUDE.md: tách prompt theo loại câu hỏi (tra cứu, so sánh, tình huống K3), buộc mô hình xác định dữ kiện – điều kiện – quy tắc trước khi kết luận, yêu cầu trích dẫn nguồn từ chunk và từ chối khi tài liệu không đủ căn cứ. Đầu ra JSON theo schema, hỗ trợ streaming.

## Khi nào dùng

- Giai đoạn 5: xây prompt template và chạy ablation CoT.
- Khi câu trả lời sai ở nhóm K3 hoặc thiếu trích dẫn.
- Khi thay đổi model Gemini hoặc schema đầu ra.

## Các bước

1. Phân loại câu hỏi đầu vào (tra cứu, so sánh, tình huống nhiều ràng buộc).
2. Chọn template trong `prompts/` tương ứng; đưa tiêu đề ngữ cảnh và metadata chunk.
3. Với câu K3: yêu cầu liệt kê dữ kiện, điều kiện, quy tắc áp dụng, kiểm tra từng phương án, rồi mới kết luận.
4. Buộc trả về JSON đúng schema (câu trả lời, trích dẫn, độ tin cậy, lý do từ chối nếu có).
5. Thiết kế câu trả lời từ chối khi ngữ cảnh không chứa căn cứ; không suy đoán ngoài tài liệu.
6. Chạy ablation có/không CoT trên tập dev, đo độ chính xác và độ trung thực.
7. Ghi phiên bản prompt và kết quả vào `docs/`; không sửa test set.

## Lệnh

```bash
python -m evaluation.runners.run --config evaluation/configs/<config>.yaml
make eval
```

Các lệnh đánh giá sẽ được nối ở Giai đoạn 2/8; prompt hiện chưa được gọi từ mã nguồn Giai đoạn 0.

## Tiêu chí nghiệm thu

- Mọi câu trả lời có trích dẫn tới chunk nguồn; không có trích dẫn bịa.
- Câu K3 được phân tích tuần tự trước khi kết luận; có kết quả ablation CoT.
- Đầu ra đúng JSON schema, parse được 100% trong bộ dev.
- Có hành vi từ chối rõ ràng khi ngữ cảnh thiếu căn cứ.
- Prompt template nằm trong `prompts/`, có phiên bản và không chứa khóa bí mật.
