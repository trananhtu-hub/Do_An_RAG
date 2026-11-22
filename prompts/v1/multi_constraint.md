# Câu hỏi tình huống nhiều ràng buộc (K3)

Áp dụng cùng `system_base.md` và `system_cot.md`.

## Mục tiêu

Chọn phương án đáp ứng **đồng thời tất cả** ràng buộc trong đề bài, không chỉ một ràng buộc
nổi bật. Mỗi kết luận phải truy được về đoạn tài liệu cụ thể.

## Quy tắc

1. Tách đề bài thành bảng ràng buộc, đánh số. Mỗi ràng buộc ghi đúng như đề nêu
   (ví dụ: "chi phí thấp nhất", "độ trễ dưới một chữ số mili giây", "không đổi mã ứng dụng").
2. Với mỗi ràng buộc, chỉ ra tài liệu nói gì. Nếu tài liệu không nói, ghi "chưa đủ căn cứ".
3. Loại phương án vi phạm ít nhất một ràng buộc **có căn cứ**; nêu lý do loại cho từng phương án.
4. Chỉ chọn phương án không vi phạm ràng buộc nào đã có căn cứ. Nếu nhiều phương án cùng thỏa,
   nêu tiêu chí phụ (chi phí, độ phức tạp vận hành) và trích dẫn căn cứ cho tiêu chí đó.
5. Nếu không phương án nào thỏa đủ, nói rõ ràng buộc nào không thể đáp ứng theo tài liệu;
   `confidence` ≤ 0,5. Ngoại lệ: khi các phương án đem ra so sánh đều vi phạm một ràng buộc
   nhưng ngữ cảnh còn phương án khác đáp ứng đủ, hãy chọn phương án còn lại đó kèm căn cứ và
   nêu lý do các phương án kia bị loại. Kết luận "không đáp ứng được" chỉ dùng khi thực sự
   không còn phương án nào trong ngữ cảnh.
6. Khi phương án chọn là lớp lưu trữ: nêu đủ phí truy xuất, thời gian lưu tối thiểu và phí xóa
   sớm của lớp đó nếu ngữ cảnh có. Khi thời gian lưu thực tế ngắn hơn mốc tối thiểu, nêu mốc
   tối thiểu của tất cả lớp đang cân nhắc và cân nhắc cả lớp không có mốc tối thiểu nếu ngữ
   cảnh nêu lớp đó.
7. Khi một ràng buộc thay đổi so với lượt trước (ví dụ thời gian lưu chỉ còn 20 ngày), đánh
   giá lại toàn bộ phương án đã nêu, không chỉ hai phương án đang được so sánh.

## Định dạng `answer`

```
**Tóm tắt:** <phương án chọn, một câu>

**Bảng kiểm ràng buộc**

| # | Ràng buộc | Phương án đáp ứng | Căn cứ |
| :--- | :--- | :--- | :--- |
| 1 | … | … | [tài liệu – mục] |

**Vì sao không chọn phương án khác**
- <phương án>: vi phạm <ràng buộc> [tài liệu – mục]

**Kết luận:** <phương án + điều kiện đi kèm>
```

## Ví dụ

Đề: "Ứng dụng đọc dữ liệu log cũ gần như không bao giờ truy cập lại, cần giữ 10 năm, chi phí
thấp nhất, thời gian truy xuất vài giờ chấp nhận được."

Kết luận đúng dạng: chọn lớp lưu trữ lạnh có căn cứ trong tài liệu (ví dụ S3 Glacier Deep Archive
nếu tài liệu nêu), kèm bảng chứng minh từng ràng buộc (tần suất truy cập, thời hạn lưu, chi phí,
thời gian truy xuất). Không nêu con số ngoài ngữ cảnh.
