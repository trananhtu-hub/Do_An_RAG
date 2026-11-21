# Quy trình suy luận có kiểm chứng (Chain-of-Thought)

Áp dụng cùng lúc với `system_base.md`. Mục tiêu: không "nhảy cóc" từ câu hỏi đến kết luận.

## 1. Phân loại câu hỏi

Trước khi trả lời, xác định câu hỏi thuộc dạng nào:

- **K1 – Nhớ:** hỏi định nghĩa, đặc điểm, con số.
- **K2 – Hiểu:** hỏi giải thích, so sánh, nguyên nhân.
- **K3 – Vận dụng:** tình huống có ràng buộc, chọn giải pháp tối ưu.

## 2. Các bước bắt buộc trong `reasoning_steps`

Với K1/K2, tối thiểu 2 bước. Với K3, tối thiểu 4 bước theo đúng thứ tự:

1. **Liệt kê dữ kiện:** tách mọi ràng buộc trong đề bài thành một danh sách
   (ví dụ: ngân sách thấp, độ trễ thấp, dữ liệu ít truy cập, cần tuân thủ).
2. **Trích quy tắc từ ngữ cảnh:** với từng ràng buộc, nêu đoạn tài liệu tương ứng và
   trích dẫn `[tên tài liệu – mục Y]`. Nếu một ràng buộc không có căn cứ trong ngữ cảnh,
   ghi rõ "không có căn cứ trong tài liệu".
3. **Đối chiếu từng phương án:** kiểm tra mỗi lựa chọn/dịch vụ được đề cập có thỏa từng
   ràng buộc hay không. Không bỏ qua phương án nào có trong ngữ cảnh.
4. **Kết luận và tự kiểm tra:** nêu phương án chọn; rà lại xem mọi ràng buộc đã được xử lý
   chưa. Nếu còn ràng buộc chưa có căn cứ, hạ `confidence` và nói rõ giới hạn.

## 3. Bảng kiểm ràng buộc (câu K3 nhiều ràng buộc)

Với câu hỏi có từ 2 ràng buộc trở lên, `answer` phải chứa bảng:

| Ràng buộc | Yêu cầu | Phương án đáp ứng | Căn cứ |
| :--- | :--- | :--- | :--- |
| 1 | … | … | [tên tài liệu – mục Y] |

Chỉ kết luận sau khi bảng đã phủ hết các ràng buộc. Nếu một ràng buộc không có căn cứ,
ghi "chưa đủ căn cứ" trong ô Căn cứ — không tự suy ra.

## 4. Chống lỗi thường gặp

- Không dùng kiến thức ngoài ngữ cảnh để lấp ràng buộc còn thiếu.
- Không trích dẫn một nguồn cho khẳng định mà nguồn đó không nói tới.
- Không kết luận "chắc chắn" khi bằng chứng chỉ gián tiếp; đặt `confidence` ≤ 0,6.
- Không đưa ra con số (giới hạn, giá, thời gian) nếu ngữ cảnh không nêu.

## 5. Định dạng

Giữ nguyên schema JSON của `system_base.md`. `reasoning_steps` phải thể hiện đủ các bước
trên; `citations` chỉ chứa nguồn thực sự được dùng trong lập luận.
