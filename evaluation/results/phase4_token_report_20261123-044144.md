# Kiểm toán token prompt (tokenizer DeepSeek)

- Thời điểm tổng hợp: 2026-11-23 04:41:44
- Nguồn: `conversation_bench_stream_20261123-042635.json`
- Số lượt có kiểm toán: 40
- Tokenizer: DeepSeek (tệp tokenizer.json, chính xác)
- Tổng prompt theo tokenizer: 417,155; tổng `input_tokens` API: 417,995; lệch -0.2%

## Phân bố token theo thành phần

| Thành phần | Trung bình | p50 | p95 | Lớn nhất | Tỷ lệ trung bình |
| :--- | ---: | ---: | ---: | ---: | ---: |
| System (không kể few-shot) | 4,099 | 3,802 | 4,673 | 4,673 | 39.3% |
| Few-shot trong system | 522 | 481 | 658 | 658 | 5.0% |
| Ngữ cảnh truy xuất | 5,161 | 5,093 | 6,781 | 7,849 | 49.5% |
| Ngữ cảnh hội thoại | 490 | 325 | 1,466 | 1,544 | 4.7% |
| Câu hỏi | 28 | 21 | 55 | 86 | 0.3% |
| Yêu cầu đầu ra | 69 | 69 | 69 | 69 | 0.7% |
| Overhead chat (ước lượng) | 16 | 16 | 16 | 16 | 0.2% |
| Tổng prompt | 10,429 | 10,741 | 11,984 | 12,256 | 100.0% |
| Khác (tiêu đề mục, phân cách) | 44 | 50 | 51 | 51 | 0.4% |

## Output và độ trễ

- Output token: trung bình 1,644, p95 4,759, lớn nhất 5,851.
- TTFT (theo lượt): p50 3,014 ms, p95 9,167 ms; tổng lượt: p50 6,144 ms, p95 19,640 ms.

## Ngân sách ngữ cảnh hội thoại ở lượt 4

- Trung bình 699 token, p95 1,460, lớn nhất 1,460 (ngưỡng 1.500).

