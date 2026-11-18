---
name: rag-evaluation
description: "Xây bộ kiểm thử và khung đánh giá RAG AWS SAA-C03 gồm độ đo truy xuất, trung thực, trích dẫn, từ chối, độ trễ, chi phí và kiểm định thống kê. Dùng ở Giai đoạn 2 và 8."
---

# Skill: RAG Evaluation

## Mô tả

Thiết kế bộ dữ liệu kiểm thử và quy trình đánh giá theo CLAUDE.md: tối thiểu 300 câu, phân tầng theo trọng số 4 lĩnh vực AWS SAA-C03 (30/26/24/20), có nhãn K1/K2/K3, tách dev/test, đo cả chất lượng truy xuất lẫn câu trả lời, kèm khoảng tin cậy và kiểm định McNemar.

## Khi nào dùng

- Giai đoạn 2: soạn bộ câu hỏi, chốt schema và taxonomy lỗi.
- Sau mỗi thay đổi lớn ở Giai đoạn 4–5: chạy trên tập dev để so sánh.
- Giai đoạn 8: đóng băng test, chạy đánh giá chính thức và phân tích lỗi.

## Các bước

1. Soạn câu hỏi có đáp án và nguồn đúng; bổ sung câu tự biên soạn để giảm rủi ro LLM đã thấy đề công khai.
2. Phân tầng theo lĩnh vực, độ khó K1/K2/K3 và dạng câu hỏi; kiểm tra không trùng lặp, không rò rỉ với kho tri thức.
3. Chốt taxonomy lỗi trước khi chạy; viết script kiểm tra tổng số lỗi theo nhóm bằng đúng tổng lỗi.
4. Tách dev/test; chỉ tinh chỉnh trên dev; đóng băng test trước Giai đoạn 8.
5. Đo truy xuất: Recall@k, MRR, nDCG@k. Đo sinh: độ chính xác, trung thực, trích dẫn đúng, từ chối khi thiếu căn cứ.
6. Đo vận hành: độ trễ (gồm TTFT), chi phí mỗi câu.
7. Báo cáo kèm khoảng tin cậy 95%; so sánh cấu hình bằng McNemar; lưu kết quả thô.

## Lệnh

```bash
python -m evaluation.validate_dataset --input data/external_test/<file>.jsonl
python -m evaluation.runners.run --config evaluation/configs/<config>.yaml
make eval
```

Các lệnh sẽ được nối vào Giai đoạn 2/8; ở Giai đoạn 0 chưa có runner.

## Tiêu chí nghiệm thu

- Tối thiểu 300 câu, phân bố 4 lĩnh vực theo trọng số, có nhãn K1/K2/K3.
- Tập test được đóng băng và không dùng để tinh chỉnh.
- Báo cáo có đủ độ đo truy xuất, sinh câu trả lời, độ trễ và chi phí.
- Mọi con số trong báo cáo truy được về log hoặc tệp kết quả thô.
- Phân tích lỗi phủ đủ các nhóm đã khai, tổng nhóm bằng tổng lỗi.
- Có so sánh thống kê (khoảng tin cậy, McNemar) cho các cấu hình chính.
