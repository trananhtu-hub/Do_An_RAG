# Kiểm toán token prompt (tokenizer DeepSeek)

- Thời điểm tổng hợp: 2026-11-23 03:50:33
- Nguồn: `conversation_bench_stream_20261123-033248.json`
- Số lượt có kiểm toán: 39
- Tokenizer: DeepSeek (tệp tokenizer.json, chính xác)
- Tổng prompt theo tokenizer: 390,971; tổng `input_tokens` API: 391,775; lệch -0.2%

## Phân bố token theo thành phần

| Thành phần | Trung bình | p50 | p95 | Lớn nhất | Tỷ lệ trung bình |
| :--- | ---: | ---: | ---: | ---: | ---: |
| System (không kể few-shot) | 4,089 | 3,802 | 4,673 | 4,673 | 40.8% |
| Few-shot trong system | 521 | 481 | 658 | 658 | 5.2% |
| Ngữ cảnh truy xuất | 4,740 | 4,961 | 6,713 | 6,794 | 47.3% |
| Ngữ cảnh hội thoại | 520 | 338 | 1,592 | 1,786 | 5.2% |
| Câu hỏi | 27 | 22 | 87 | 89 | 0.3% |
| Yêu cầu đầu ra | 69 | 69 | 69 | 69 | 0.7% |
| Overhead chat (ước lượng) | 16 | 16 | 16 | 16 | 0.2% |
| Tổng prompt | 10,025 | 10,347 | 11,849 | 11,947 | 100.0% |
| Khác (tiêu đề mục, phân cách) | 43 | 50 | 51 | 51 | 0.4% |

## Output và độ trễ

- Output token: trung bình 1,266, p95 3,148, lớn nhất 4,003.
- TTFT (theo lượt): p50 3,117 ms, p95 9,143 ms; tổng lượt: p50 7,400 ms, p95 15,374 ms.

## Ngân sách ngữ cảnh hội thoại ở lượt 4

- Trung bình 858 token, p95 1,453, lớn nhất 1,453 (ngưỡng 1.500).

