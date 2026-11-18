---
name: thesis-report
description: "Viết báo cáo giai đoạn và báo cáo đề án có truy vết số liệu, minh bạch hạn chế, bám trạng thái W1–W13. Dùng ở cuối mỗi giai đoạn và Giai đoạn 9."
---

# Skill: Thesis Report

## Mô tả

Chuẩn hóa cách viết báo cáo giai đoạn và báo cáo đề án: mỗi kết luận phải truy vết được về log, kết quả thực nghiệm hoặc mã nguồn; nêu trung thực hạn chế; theo dõi trạng thái 13 nhược điểm W1–W13. Báo cáo lưu trong `docs/` theo mẫu thống nhất.

## Khi nào dùng

- Kết thúc mỗi giai đoạn: viết báo cáo theo mẫu `docs/phase-<n>-report.md`.
- Giai đoạn 9: tổng hợp báo cáo đề án, phần hạn chế và hướng phát triển.
- Khi cần chuẩn bị số liệu, bảng, hình cho buổi bảo vệ.

## Các bước

1. Thu thập kết quả thô: log kiểm thử, tệp kết quả đánh giá, commit hash.
2. Lập bảng kiểm thử gồm Hạng mục, Lệnh, Kỳ vọng, Thực tế, Đạt.
3. Viết phần việc đã làm, tệp/cấu trúc đã tạo, vấn đề và rủi ro.
4. Đối chiếu từng mục W1–W13: đã xử lý, đang xử lý hay chưa bắt đầu; không đánh dấu hoàn thành khi chưa có thực nghiệm.
5. Ghi đề xuất cho giai đoạn kế tiếp, không vượt phạm vi.
6. Kiểm tra mọi số liệu trong báo cáo khớp với kết quả thô; không làm tròn gây hiểu nhầm.
7. Lưu báo cáo và cập nhật mục “Trạng thái dự án” trong CLAUDE.md nếu cần.

## Lệnh

```bash
git log --oneline -5
git status
make test
make lint
```

## Tiêu chí nghiệm thu

- Báo cáo đúng mẫu, có đủ 6 mục theo yêu cầu của giai đoạn.
- Mọi con số truy được về log/tệp kết quả; không có số liệu tự suy diễn.
- Bảng W1–W13 phản ánh đúng thực tế, không đánh dấu sớm.
- Phần hạn chế và rủi ro được nêu rõ, có đề xuất xử lý.
- Không xuất hiện giá trị khóa, mật khẩu hay chuỗi kết nối trong báo cáo.
