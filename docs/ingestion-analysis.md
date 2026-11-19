# PHÂN TÍCH CẤU TRÚC PDF — GIAI ĐOẠN 1

- **Ngày tạo:** 2026-11-19 16:56
- **Lệnh tái lập:** `python -m ingestion.inspect --input data/raw --report docs/ingestion-analysis.md`
- **Phạm vi:** toàn bộ `*.pdf` trong `data/raw/`; loại trừ `data/external_test/`
- **Công cụ parse:** pdfplumber (không OCR, không dịch vụ ngoài)
- **Quy ước token:** xấp xỉ `ceil(số ký tự / 3)` cho văn bản tiếng Việt; chỉ dùng để thiết kế chunk, không phải token của tokenizer.

## 1. Tổng quan

| Tài liệu | Trang | Trang trống | Mục lý thuyết | Câu hỏi | Bảng | Ảnh | Token ước tính |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `aws-saa-exam-guide.pdf` | 28 | 0 | 51 | 0 | 0 | 0 | 15.546 |
| `aws-saa-question-bank.pdf` | 461 | 0 | 0 | 390 | 0 | 0 | 399.590 |
| `EC2_Tinh_toan.pdf` | 11 | 0 | 13 | 0 | 0 | 0 | 7.449 |
| `IAM.pdf` | 11 | 0 | 12 | 0 | 0 | 0 | 7.410 |
| `RDS_Aurora.pdf` | 11 | 0 | 13 | 0 | 0 | 0 | 7.777 |
| `S3_Storage_Classes.pdf` | 11 | 0 | 13 | 0 | 0 | 0 | 7.267 |
| `VPC_Networking.pdf` | 12 | 0 | 13 | 0 | 0 | 0 | 8.302 |
| **Tổng** | **545** | **0** | **115** | **390** | **0** | **0** | **453.341** |

Toàn bộ 545 trang đều có lớp văn bản; không có trang trống. Corpus có 505 đề mục, trong đó 390 câu hỏi, 0 bảng và 0 ảnh.

## 2. Cấu trúc từng tài liệu

### `aws-saa-exam-guide.pdf`

- Nguồn: `data/raw/aws-saa-exam-guide.pdf`
- Số trang: 28
- Kiểu đề mục: `Mục X.Y:` (51)
- Số đề mục: 51
- Token mỗi đề mục: nhỏ nhất 134, trung vị 212, p95 699, lớn nhất 742, trung bình 305
- Trang trống: không có; trang ngắn (<50 ký tự): không có
- Bảng: 0; ảnh: 0; số đề mục có mục “Tài liệu tham khảo”: 51

### `aws-saa-question-bank.pdf`

- Nguồn: `data/raw/aws-saa-question-bank.pdf`
- Số trang: 461
- Kiểu đề mục: `Câu N:` (390)
- Số đề mục: 390
- Token mỗi đề mục: nhỏ nhất 240, trung vị 986, p95 1711, lớn nhất 2399, trung bình 1025
- Nhãn lĩnh vực gốc: “Thiết kế kiến trúc hiệu năng cao” (114), “Thiết kế kiến trúc bảo mật” (100), “Thiết kế kiến trúc kiên cường” (94), “Thiết kế kiến trúc tối ưu chi phí” (34), “Design Secure Architectures” (13), “Design High-Performing Architectures” (13), “Design Resilient Architectures” (11), “Thiết kế các ứng dụng và kiến trúc bảo mật” (2), “Design Cost-Optimized Architectures” (2)
- Câu thiếu dòng `Lĩnh vực:`: 18, 65, 241, 245, 249, 307, 368
- Trang trống: không có; trang ngắn (<50 ký tự): không có
- Bảng: 0; ảnh: 0; số đề mục có mục “Tài liệu tham khảo”: 385

### `EC2_Tinh_toan.pdf`

- Nguồn: `data/raw/EC2_Tinh_toan.pdf`
- Số trang: 11
- Kiểu đề mục: `Mục X.Y:` (13)
- Số đề mục: 13
- Token mỗi đề mục: nhỏ nhất 381, trung vị 560, p95 723, lớn nhất 755, trung bình 573
- Trang trống: không có; trang ngắn (<50 ký tự): không có
- Bảng: 0; ảnh: 0; số đề mục có mục “Tài liệu tham khảo”: 13

### `IAM.pdf`

- Nguồn: `data/raw/IAM.pdf`
- Số trang: 11
- Kiểu đề mục: `Mục X.Y:` (12)
- Số đề mục: 12
- Token mỗi đề mục: nhỏ nhất 504, trung vị 622, p95 688, lớn nhất 726, trung bình 618
- Trang trống: không có; trang ngắn (<50 ký tự): không có
- Bảng: 0; ảnh: 0; số đề mục có mục “Tài liệu tham khảo”: 12

### `RDS_Aurora.pdf`

- Nguồn: `data/raw/RDS_Aurora.pdf`
- Số trang: 11
- Kiểu đề mục: `Mục X.Y:` (13)
- Số đề mục: 13
- Token mỗi đề mục: nhỏ nhất 470, trung vị 609, p95 645, lớn nhất 673, trung bình 598
- Trang trống: không có; trang ngắn (<50 ký tự): không có
- Bảng: 0; ảnh: 0; số đề mục có mục “Tài liệu tham khảo”: 13

### `S3_Storage_Classes.pdf`

- Nguồn: `data/raw/S3_Storage_Classes.pdf`
- Số trang: 11
- Kiểu đề mục: `Mục X.Y:` (13)
- Số đề mục: 13
- Token mỗi đề mục: nhỏ nhất 412, trung vị 566, p95 660, lớn nhất 800, trung bình 559
- Trang trống: không có; trang ngắn (<50 ký tự): không có
- Bảng: 0; ảnh: 0; số đề mục có mục “Tài liệu tham khảo”: 13

### `VPC_Networking.pdf`

- Nguồn: `data/raw/VPC_Networking.pdf`
- Số trang: 12
- Kiểu đề mục: `Mục X.Y:` (13)
- Số đề mục: 13
- Token mỗi đề mục: nhỏ nhất 580, trung vị 619, p95 708, lớn nhất 797, trung bình 639
- Trang trống: không có; trang ngắn (<50 ký tự): không có
- Bảng: 0; ảnh: 0; số đề mục có mục “Tài liệu tham khảo”: 13

## 3. Phân tích ngân hàng câu hỏi

### 3.1 Số lượng và khoảng số câu

- Số câu phát hiện: **390**; số nhỏ nhất: 1; số lớn nhất: 390.
- Câu trùng số: không có; số bị thiếu trong dãy: không có.

### 3.2 Lĩnh vực

| Nhãn gốc trong PDF | Số câu | Nhãn chuẩn hóa |
| --- | --- | --- |
| “Thiết kế kiến trúc hiệu năng cao” | 114 | High-Performing |
| “Thiết kế kiến trúc bảo mật” | 100 | Secure |
| “Thiết kế kiến trúc kiên cường” | 94 | Resilient |
| “Thiết kế kiến trúc tối ưu chi phí” | 34 | Cost-Optimized |
| “Design Secure Architectures” | 13 | Secure |
| “Design High-Performing Architectures” | 13 | High-Performing |
| “Design Resilient Architectures” | 11 | Resilient |
| “Thiết kế các ứng dụng và kiến trúc bảo mật” | 2 | Secure |
| “Design Cost-Optimized Architectures” | 2 | Cost-Optimized |

Bảy câu không có dòng `Lĩnh vực:` và cách xử lý đề xuất:

| Câu | Tiêu đề rút gọn | Trang | Lĩnh vực gán thủ công |
| --- | --- | --- | --- |
| 18 | Amazon EFS: hệ thống tệp dùng chung cho nhiều phiên bản EC2 trong Auto | tr.21-22 | High-Performing |
| 65 | IAM policy: quản lý quyền truy cập cho định danh và tài nguyên trong A | tr.79-80 | Secure |
| 241 | Tự động mở rộng quy mô (Autoscaling) cho cụm Amazon EKS | tr.287-288 | High-Performing |
| 245 | Thời điểm bắt đầu và kết thúc tính phí của phiên bản EC2 | tr.292-293 | Cost-Optimized |
| 249 | Ổ SSD có IOPS được cấp phát (io1) cho khối lượng công việc I/O cao trê | tr.297-298 | High-Performing |
| 307 | Horizontal Pod Autoscaler trong Amazon EKS với IRSA | tr.363-364 | High-Performing |
| 368 | Amazon S3: lưu trữ tạm thời tệp nhật ký trong 12 giờ với chi phí thấp | tr.433-434 | Cost-Optimized |

Các giá trị gán thủ công nằm trong `MISSING_DOMAIN_OVERRIDES` (`ingestion/domains.py`) và sẽ được ghi vào metadata với nguồn `override`.

| Mã chuẩn | Nhãn tiếng Việt | Số câu | Tỷ lệ |
| --- | --- | --- | --- |
| Secure | Thiết kế kiến trúc bảo mật | 116 | 29,7% |
| Resilient | Thiết kế kiến trúc kiên cường | 105 | 26,9% |
| High-Performing | Thiết kế kiến trúc hiệu năng cao | 131 | 33,6% |
| Cost-Optimized | Thiết kế kiến trúc tối ưu chi phí | 38 | 9,7% |

Tổng sau chuẩn hóa: 390 câu; nguồn nhãn: explicit 383, override 7, missing 0. Tổng tỷ lệ: 100,0%.

### 3.3 Trích xuất đáp án đúng

| Mẫu câu (không phân biệt hoa thường) | Số câu chứa |
| --- | --- |
| “câu trả lời đúng là” | 179 |
| “đáp án đúng là” | 70 |
| “câu trả lời chính xác là” | 32 |
| “đáp án chính xác là” | 13 |

- Câu có ít nhất một trong bốn mẫu chính xác: **294/390**.
- Câu không có mẫu chính xác: 96 (24,6%).
- Câu có dấu hiệu đáp án nếu mở rộng mẫu: **336/390**.

Danh sách câu chưa khớp bốn mẫu chính xác:

```text
19, 20, 31, 36, 38, 67, 68, 74, 75, 85, 86, 87, 89, 90, 104, 105, 110, 112, 114, 115, 116, 121, 126, 133, 137, 142, 143, 147, 150, 158, 161, 169, 174, 180, 184, 190, 191, 192, 194, 195, 198, 211, 218, 220, 221, 225, 227, 229, 233, 234, 240, 244, 245, 248, 249, 250, 256, 263, 264, 265, 268, 272, 278, 280, 281, 286, 292, 295, 296, 297, 299, 304, 305, 314, 316, 320, 321, 322, 328, 331, 337, 338, 343, 344, 346, 351, 352, 354, 361, 364, 365, 366, 367, 379, 387, 389
```

### 3.4 Phương án nhiễu

| Tiền tố mở đầu đoạn nhiễu | Số đoạn |
| --- | --- |
| “tùy chọn ghi” | 482 |
| “việc ” | 200 |
| “tùy chọn có nội dung” | 72 |
| “các tùy chọn” | 21 |
| “thông tin cho rằng” | 7 |
| “phương án nêu” | 7 |
| “các phương án” | 4 |
| “lựa chọn ” | 3 |

| Số đoạn nhiễu nhận diện trong một câu | Số câu |
| --- | --- |
| 0 | 73 |
| 1 | 52 |
| 2 | 86 |
| 3 | 149 |
| 4 trở lên | 30 |

Các đoạn nhiễu còn dùng nhiều cách diễn đạt khác (ví dụ “Việc … là không chính xác”, “Các tùy chọn sau đây đều không chính xác:” kèm gạch đầu dòng). Bộ trích xuất sẽ dùng thêm mẫu tổng quát và ghi cảnh báo cho câu không tách được phương án.

### 3.5 Phương án A–D

Số câu có ít nhất hai dòng bắt đầu bằng `A.`, `B.`, `C.`, `D.` (hoặc `A)`, `B)`, …): **0**.
PDF không trình bày danh sách phương án A–D; mỗi câu chỉ có tiêu đề, phần giải thích, câu trả lời đúng và phân tích các phương án nhiễu. Pipeline sẽ tái dựng tối đa bốn phương án từ câu trả lời đúng và các đoạn nhiễu, ghi `options_source = reconstructed` trong metadata, và để trống danh sách nếu không đủ căn cứ.

### 3.6 Kích thước câu hỏi

| Khoảng token ước tính | Số câu |
| --- | --- |
| < 300 | 2 |
| 300 – 799 | 102 |
| 800 – 1.200 | 181 |
| > 1.200 | 105 |

Đề mục câu hỏi không đồng đều: phần lớn nằm trong 300–1.200 token nhưng có câu rất dài. Chunk cha giữ trọn đề mục nếu ≤ 1.200 token; đề mục dài được chia thành nhiều chunk cha theo ranh giới đoạn, mỗi chunk cha vẫn bao trùm các chunk con bên trong.

## 4. Tài liệu lý thuyết

| Tài liệu | Số mục | Token nhỏ nhất | Trung vị | Lớn nhất | Trung bình | Mục theo lĩnh vực |
| --- | --- | --- | --- | --- | --- | --- |
| `aws-saa-exam-guide.pdf` | 51 | 134 | 212 | 742 | 305 | Secure: 3, Resilient: 2, High-Performing: 5, Cost-Optimized: 4 |
| `EC2_Tinh_toan.pdf` | 13 | 381 | 560 | 755 | 573 | Secure: 1, Resilient: 3, High-Performing: 7, Cost-Optimized: 2 |
| `IAM.pdf` | 12 | 504 | 622 | 726 | 618 | Secure: 12, Resilient: 0, High-Performing: 0, Cost-Optimized: 0 |
| `RDS_Aurora.pdf` | 13 | 470 | 609 | 673 | 598 | Secure: 1, Resilient: 7, High-Performing: 2, Cost-Optimized: 3 |
| `S3_Storage_Classes.pdf` | 13 | 412 | 566 | 800 | 559 | Secure: 0, Resilient: 0, High-Performing: 2, Cost-Optimized: 11 |
| `VPC_Networking.pdf` | 13 | 580 | 619 | 797 | 639 | Secure: 5, Resilient: 4, High-Performing: 2, Cost-Optimized: 2 |

Phân bố token mục lý thuyết: <300: 32; 300–799: 82; 800–1.200: 1; >1.200: 0. Các mục ngắn hơn 800 token sẽ được gộp với mục kế tiếp cùng lĩnh vực khi tạo chunk cha; mục dài hơn 1.200 token được chia theo ranh giới đoạn.

## 5. Bảng, hình ảnh và trang lỗi

**Không phát hiện bảng hoặc hình ảnh nào** trong toàn bộ corpus: 0 bảng, 0 ảnh trên 545 trang. Điều này có nghĩa yêu cầu “kiểm tra ngẫu nhiên 5 bảng” không thể thực hiện trên dữ liệu thật.

Để bảo đảm chức năng trích bảng vẫn đúng, pipeline có bộ chuyển bảng sang Markdown và metadata `{type, page, rows, cols}`; phần kiểm thử dùng PDF/tệp mẫu tổng hợp có bảng. Khi bổ sung tài liệu có bảng ở giai đoạn sau, pipeline sẽ tạo chunk riêng `content_type = "table"` và không làm phẳng bảng vào văn bản.

- Trang không trích được văn bản: **0**.
- Trang có ít hơn 50 ký tự: **0**.
- Văn bản là tiếng Việt có dấu, chứa nhiều thuật ngữ tiếng Anh (tên dịch vụ AWS). Không phát hiện ký tự thay thế `�` trong quá trình khảo sát.

## 6. Hàm ý cho pipeline Giai đoạn 1

1. **Chunking cha–con:** mỗi đề mục là đơn vị ngữ nghĩa. Với ngân hàng câu hỏi, chunk cha là một câu (hoặc một phần của câu nếu >1.200 token); với tài liệu lý thuyết, các mục ngắn cùng lĩnh vực được gộp đến ngưỡng 800–1.200 token. Chunk con 300–500 token, chồng lấn 10–15%, luôn mang tiêu đề mục và số trang.
2. **Trích câu hỏi:** lấy số câu từ `Câu N:`, tiêu đề từ dòng tiêu đề (nối các dòng bị ngắt), lĩnh vực từ `Lĩnh vực:`, đáp án đúng từ các mẫu câu, phương án nhiễu từ các đoạn phân tích. Câu không xác định được đáp án được lưu với `correct_answer = null` và cảnh báo, không suy diễn.
3. **Phương án A–D:** không có trong PDF. Tái dựng từ đáp án đúng và các đoạn nhiễu; ghi rõ nguồn trong metadata và không tạo phương án giả khi thiếu căn cứ.
4. **Lĩnh vực:** chuẩn hóa 9 nhãn gốc về 4 mã; 7 câu thiếu dòng lĩnh vực dùng bảng gán thủ công và metadata `domain_source = override`.
5. **Bảng:** corpus hiện tại không có bảng; chức năng trích bảng vẫn được kiểm thử bằng mẫu tổng hợp.
6. **Idempotency:** checksum SHA-256 của tệp và của nội dung chunk/câu hỏi dùng để bỏ qua khi chạy lại; `--force` xóa và nạp lại theo tài liệu.
7. **Embedding:** `gemini-embedding-001`, 768 chiều, theo lô, có retry/backoff; không lưu vector vào tệp trung gian.
8. **Ước tính token:** dùng `ceil(len(text)/3)`; ghi rõ đây là xấp xỉ để thiết kế chunk, không dùng cho báo cáo chi phí token của Gemini.

## 7. Kết luận

Corpus gồm 7 tài liệu, 545 trang, 390 câu hỏi và 115 mục lý thuyết. Cấu trúc đề mục ổn định (`Câu N:` và `Mục X.Y:`), lớp văn bản đầy đủ, không có bảng/ảnh. Ba rủi ro chính cần xử lý minh bạch: thiếu phương án A–D, 7 câu thiếu nhãn lĩnh vực và một phần câu hỏi không có mẫu đáp án chính xác rõ ràng.
