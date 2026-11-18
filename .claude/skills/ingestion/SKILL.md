---
name: ingestion
description: "Nạp PDF AWS SAA-C03 bằng pdfplumber, chuẩn hóa mục Câu N, chunking cha–con, embedding Gemini 768 và upsert Supabase. Dùng ở Giai đoạn 1 và 3."
---

# Skill: Ingestion

## Mô tả

Xây dựng pipeline nạp tài liệu từ PDF vào Supabase/pgvector: trích văn bản bằng **pdfplumber** (chạy cục bộ, không dùng LlamaParse hay dịch vụ parse trả phí), nhận diện cấu trúc mục “Câu N”, tạo chunk cha–con, gắn metadata và embedding Gemini 768 chiều. Kết quả ghi vào bảng `documents` và `chunks`.

## Khi nào dùng

- Giai đoạn 1: khảo sát PDF, kiểm tra text layer, thống kê số mục, nhãn lĩnh vực, trang.
- Giai đoạn 3: nạp dữ liệu thật, tạo index và version index.
- Khi bổ sung tài liệu mới hoặc nạp lại sau khi sửa logic chunking.

## Các bước

1. Đặt PDF gốc vào `data/raw/` (không commit) và ghi nhận nguồn, giấy phép.
2. Khảo sát bằng pdfplumber: số trang, trang không có text layer, bảng/hình, lỗi font.
3. Tách cấu trúc mục “Câu N”: tiêu đề, lĩnh vực, giải thích tổng quan, đáp án đúng, phân tích phương án sai, tài liệu tham khảo.
4. Chunking cha–con: parent là cả mục; child theo loại đoạn (tổng quan, đáp án, phân tích, tham khảo); mỗi child có tiêu đề ngữ cảnh (số câu, tiêu đề, lĩnh vực đã chuẩn hóa).
5. Gắn metadata: số câu, lĩnh vực, dịch vụ AWS, loại đoạn, số trang, URL tham khảo, version.
6. Sinh embedding Gemini 768 chiều và upsert vào `documents`/`chunks` theo version.
7. Hậu kiểm: đếm chunk, phát hiện trùng, kiểm tra embedding đủ 768 chiều, lưu báo cáo vào `docs/`.

## Lệnh

```bash
python -m ingestion.inspect --input data/raw/<file>.pdf
python -m ingestion.pipeline --input data/raw/<file>.pdf --version v1
make ingest
```

`make ingest` hiện là chỗ giữ chỗ, sẽ được nối vào Giai đoạn 3.

## Tiêu chí nghiệm thu

- 100% trang được xử lý; mọi trang thiếu text layer được báo cáo rõ.
- Mỗi chunk có `document_id`, `chunk_index`, metadata trang và loại đoạn.
- Quan hệ cha–con đúng: mọi chunk con trỏ tới mục cha cùng “Câu N”.
- Embedding là vector 768 chiều, không có chunk rỗng.
- Không import hoặc gọi dịch vụ parse PDF bên ngoài; chỉ dùng pdfplumber.
- Báo cáo thống kê số mục/chunk/lĩnh vực được lưu lại và tái lập được.
