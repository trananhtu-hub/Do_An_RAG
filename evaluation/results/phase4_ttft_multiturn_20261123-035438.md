# Đo TTFT đa lượt trên bộ dev (SSE)

- Thời điểm: 2026-11-23T03:54:38
- Tệp kịch bản: `inputs/conversations_dev.md` (SHA-256 `4139256b3c49fca7a6218d6c619158c8a340027f756e41d7d05cd036b0f97951`)
- Backend: http://127.0.0.1:8000; chế độ: warm (có warmup)
- Mẫu hợp lệ: 40/40; lỗi: 0

| Lượt | n | TTFT p50 (ms) | TTFT p95 (ms) | Tổng p50 (ms) | Tổng p95 (ms) |
| :---: | :---: | ---: | ---: | ---: | ---: |
| 1 | 10 | 3585.6 | 29140.5 | 8127.8 | 34809.6 |
| 2 | 10 | 4040.2 | 6905.0 | 6619.1 | 14397.9 |
| 3 | 10 | 3798.7 | 6499.2 | 6054.6 | 11825.0 |
| 4 | 10 | 4102.1 | 9341.1 | 6004.5 | 12682.8 |
| **Toàn bộ** | 40 | 4040.2 | 6905.0 | 6749.4 | 13957.0 |

TTFT đo từ lúc gửi yêu cầu tới sự kiện `token` đầu tiên (định nghĩa giữ nguyên). `server_ttft_ms` trong JSON là số đo phía máy chủ, chỉ dùng tham khảo.
