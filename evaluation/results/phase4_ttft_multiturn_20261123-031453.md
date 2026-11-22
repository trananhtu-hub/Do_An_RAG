# Đo TTFT đa lượt trên bộ dev (SSE)

- Thời điểm: 2026-11-23T03:14:53
- Tệp kịch bản: `inputs/conversations_dev.md` (SHA-256 `4139256b3c49fca7a6218d6c619158c8a340027f756e41d7d05cd036b0f97951`)
- Backend: http://127.0.0.1:8000; chế độ: warm (có warmup)
- Mẫu hợp lệ: 40/40; lỗi: 0

| Lượt | n | TTFT p50 (ms) | TTFT p95 (ms) | Tổng p50 (ms) | Tổng p95 (ms) |
| :---: | :---: | ---: | ---: | ---: | ---: |
| 1 | 10 | 4430.8 | 8125.2 | 9837.6 | 14591.6 |
| 2 | 10 | 5291.1 | 8333.9 | 9759.7 | 14344.0 |
| 3 | 10 | 5656.0 | 7861.0 | 8111.6 | 14359.7 |
| 4 | 10 | 5072.6 | 9691.6 | 7636.4 | 12620.8 |
| **Toàn bộ** | 40 | 5234.7 | 8125.2 | 8995.0 | 14344.0 |

TTFT đo từ lúc gửi yêu cầu tới sự kiện `token` đầu tiên (định nghĩa giữ nguyên). `server_ttft_ms` trong JSON là số đo phía máy chủ, chỉ dùng tham khảo.
