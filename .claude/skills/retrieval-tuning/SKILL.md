---
name: retrieval-tuning
description: "Thiết kế và tinh chỉnh truy xuất hybrid (vector HNSW + full-text + RRF + rerank đa ngôn ngữ) cho RAG AWS SAA-C03. Dùng ở Giai đoạn 4."
---

# Skill: Retrieval Tuning

## Mô tả

Xây dựng tầng truy xuất theo kiến trúc trong CLAUDE.md: vector search trên HNSW, full-text search PostgreSQL (gọi đúng tên, không gọi là BM25), hợp nhất bằng RRF với k = 60, rerank bằng cross-encoder đa ngôn ngữ, chọn top-k thích ứng và mở rộng sang mục cha. Mọi thành phần phải cấu hình được và đo lường được bằng ablation.

## Khi nào dùng

- Giai đoạn 4: thiết lập baseline vector-only, rồi bật dần full-text, RRF, reranker, top-k thích ứng.
- Khi cần chẩn đoán vì sao một câu hỏi không tìm được ngữ cảnh đúng.
- Khi thay đổi embedding model, tham số RRF hoặc reranker.

## Các bước

1. Chốt baseline vector-only (HNSW, cosine) và lưu kết quả làm mốc.
2. Thêm full-text search (`tsvector`, cấu hình `simple` + `unaccent` nếu cần) và kiểm tra truy vấn Việt–Anh.
3. Hợp nhất hai nhánh bằng RRF, k = 60, tham số hóa số ứng viên mỗi nhánh.
4. Rerank số ứng viên giới hạn bằng cross-encoder đa ngôn ngữ; giữ cấu hình MiniLM cũ làm đối chứng.
5. Chọn số chunk đưa vào LLM thích ứng theo điểm và giới hạn ngữ cảnh; mở rộng mục cha khi cần tổng hợp.
6. Chạy ablation từng thành phần trên tập dev, ghi nhận Recall@k, MRR/nDCG@k và độ trễ.
7. Chốt cấu hình tốt nhất theo chất lượng và độ trễ, ghi quyết định vào `docs/`.

## Lệnh

```bash
make eval
python -m evaluation.runners.run --config evaluation/configs/<config>.yaml
```

Các lệnh đánh giá sẽ được nối vào Giai đoạn 2/4; ở Giai đoạn 0 chưa có runner.

## Tiêu chí nghiệm thu

- Không có top-k cố định cứng trong mã nguồn; mọi tham số đọc từ cấu hình.
- Có kết quả ablation riêng cho vector-only, hybrid, +RRF và +rerank trên cùng tập dev.
- RRF dùng đúng hằng số k = 60 (có thể đổi qua cấu hình) và tài liệu gọi đúng “full-text search”, không gọi sai là BM25.
- Reranker là mô hình đa ngôn ngữ; cấu hình tiếng Anh cũ chỉ dùng làm đối chứng.
- Độ trễ từng tầng được đo và ghi lại; không tăng quá ngưỡng đã chốt mà không có lý do.
