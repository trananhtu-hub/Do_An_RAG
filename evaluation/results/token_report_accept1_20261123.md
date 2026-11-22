# Kiểm toán token prompt (tokenizer DeepSeek)

- Thời điểm tổng hợp: 2026-11-23 04:26:50
- Nguồn: `conversation_bench_stream_20261123-041140.json`
- Số lượt có kiểm toán: 40
- Tokenizer: DeepSeek (tệp tokenizer.json, chính xác)
- Tổng prompt theo tokenizer: 425,384; tổng `input_tokens` API: 426,274; lệch -0.2%

## Phân bố token theo thành phần

| Thành phần | Trung bình | p50 | p95 | Lớn nhất | Tỷ lệ trung bình |
| :--- | ---: | ---: | ---: | ---: | ---: |
| System (không kể few-shot) | 4,143 | 3,802 | 4,673 | 4,673 | 39.0% |
| Few-shot trong system | 530 | 481 | 658 | 658 | 5.0% |
| Ngữ cảnh truy xuất | 5,322 | 5,562 | 6,769 | 7,849 | 50.0% |
| Ngữ cảnh hội thoại | 485 | 304 | 1,550 | 1,563 | 4.6% |
| Câu hỏi | 27 | 21 | 55 | 73 | 0.3% |
| Yêu cầu đầu ra | 69 | 69 | 69 | 69 | 0.6% |
| Overhead chat (ước lượng) | 16 | 16 | 16 | 16 | 0.2% |
| Tổng prompt | 10,635 | 11,027 | 11,957 | 12,256 | 100.0% |
| Khác (tiêu đề mục, phân cách) | 43 | 50 | 51 | 51 | 0.4% |

## Output và độ trễ

- Output token: trung bình 1,812, p95 4,896, lớn nhất 6,144.
- TTFT (theo lượt): p50 3,331 ms, p95 11,023 ms; tổng lượt: p50 6,634 ms, p95 21,728 ms.

## Ngân sách ngữ cảnh hội thoại ở lượt 4

- Trung bình 1,039 token, p95 1,499, lớn nhất 1,499 (ngưỡng 1.500).

