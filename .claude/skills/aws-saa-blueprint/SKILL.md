---
name: aws-saa-blueprint
description: "Chuẩn hóa kiến thức và câu hỏi theo blueprint AWS SAA-C03 (4 lĩnh vực, trọng số 30/26/24/20, K1–K3). Dùng khi soạn đề, gắn nhãn và kiểm tra độ phủ."
---

# Skill: AWS SAA Blueprint

## Mô tả

Bảo đảm nội dung, nhãn và bộ câu hỏi bám sát blueprint kỳ thi AWS Certified Solutions Architect – Associate (SAA-C03): 4 lĩnh vực với trọng số tham chiếu 30/26/24/20, các nhóm dịch vụ AWS và mức nhận thức K1/K2/K3. Dùng để chuẩn hóa 9 biến thể nhãn lĩnh vực về 4 lĩnh vực thống nhất.

## Khi nào dùng

- Giai đoạn 1–2: chuẩn hóa nhãn lĩnh vực, kiểm tra phân bố và độ phủ dịch vụ.
- Khi soạn câu hỏi mới hoặc rà soát câu hỏi hiện có.
- Khi thiết kế prompt cho câu hỏi tình huống nhiều ràng buộc.

## Các bước

1. Ánh xạ mọi nhãn lĩnh vực về 4 giá trị chuẩn: High-Performing, Secure, Resilient, Cost-Optimized.
2. Kiểm tra phân bố mục/câu hỏi theo trọng số 30/26/24/20; ghi rõ phần lệch và lý do.
3. Gắn nhãn K1/K2/K3 theo yêu cầu nhận thức; câu K3 phải có nhiều ràng buộc kiến trúc.
4. Rà soát độ phủ nhóm dịch vụ AWS trọng yếu (S3, EC2, VPC, IAM, Lambda, RDS, v.v.).
5. Viết lại câu hỏi mơ hồ thành tình huống có ràng buộc rõ ràng, đáp án đúng duy nhất.
6. Kiểm tra câu hỏi không trùng, không mâu thuẫn với tài liệu nguồn.

## Lệnh

```bash
python -m evaluation.validate_dataset --input data/external_test/<file>.jsonl
python -m ingestion.inspect --input data/raw/<file>.pdf
```

## Tiêu chí nghiệm thu

- Không còn nhãn lĩnh vực ngoài 4 giá trị chuẩn.
- Báo cáo phân bố kèm so sánh với trọng số 30/26/24/20.
- Mỗi câu hỏi có lĩnh vực, mức K, đáp án và nguồn tham chiếu.
- Câu K3 có tối thiểu hai ràng buộc và yêu cầu suy luận tuần tự.
- Không có câu hỏi trùng lặp hoặc mâu thuẫn với kho tri thức.
