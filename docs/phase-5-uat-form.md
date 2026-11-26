# BIỂU MẪU UAT GIAI ĐOẠN 5

**Mục đích:** đánh giá mức độ dễ dùng và mức độ hài lòng của người học với giao diện MVP của chatbot RAG luyện thi AWS SAA-C03.

**Đối tượng:** 3–5 người, ưu tiên sinh viên ngành CNTT hoặc ứng viên đang ôn thi AWS SAA-C03. Mỗi người tham gia độc lập, không thảo luận với nhau trong lúc làm bài.

**Thời lượng dự kiến:** 20–30 phút cho mỗi người, gồm 5 phút giới thiệu, 15 phút thao tác và 5–10 phút trả lời câu hỏi mở.

**Người điều phối:** ghi tên và ngày thực hiện. Không ghi mật khẩu, khóa API hay chuỗi kết nối vào biểu mẫu.

## 1. Thông tin người tham gia

| Mã | Vai trò | Mức quen với AWS (1–5) | Thiết bị | Trình duyệt | Ngày |
| :--- | :--- | :---: | :--- | :--- | :--- |
| P1 |  |  |  |  |  |
| P2 |  |  |  |  |  |
| P3 |  |  |  |  |  |
| P4 |  |  |  |  |  |
| P5 |  |  |  |  |  |

Ghi chú về quyền riêng tư: chỉ lưu mã người tham gia và thông tin chuyên môn cần thiết. Không lưu họ tên, email, số điện thoại hay bản ghi màn hình nếu người tham gia không đồng ý.

## 2. Thang điểm 5 mức

| Điểm | Ý nghĩa |
| :---: | :--- |
| 1 | Hoàn toàn không đồng ý |
| 2 | Không đồng ý |
| 3 | Trung lập |
| 4 | Đồng ý |
| 5 | Hoàn toàn đồng ý |
| N/A | Không dùng tính năng này hoặc không đủ cơ sở đánh giá |

## 3. Kịch bản thao tác

Người điều phối giao tài khoản thử nghiệm và yêu cầu người tham gia tự thao tác, không hướng dẫn từng bước. Chỉ hỗ trợ khi người tham gia bị chặn hoàn toàn.

| Mã | Kịch bản | Điều kiện hoàn thành | Ghi nhận lỗi |
| :--- | :--- | :--- | :--- |
| T1 | Đăng nhập bằng tài khoản được cấp | Vào được `/chat`, thấy email ở góc trên bên phải |  |
| T2 | Hỏi một câu về Multi-AZ và Read Replica | Thấy câu trả lời xuất hiện dần, có nút dừng, có chip nguồn trích dẫn |  |
| T3 | Mở một chip trích dẫn | Xem được PDF đúng tài liệu và đúng trang, đóng được hộp thoại |  |
| T4 | Chuyển giữa “Trả lời nhanh” và “Giải thích từng bước”, hỏi lại một câu | Thấy chế độ được chọn và câu trả lời thay đổi cách trình bày |  |
| T5 | Vào `/quiz`, chọn một lĩnh vực, làm 5 câu, nộp bài | Thấy điểm, đáp án đúng và giải thích; lượt làm bài xuất hiện trong lịch sử |  |
| T6 | Vào `/history`, tìm, đổi tên rồi xóa cuộc trò chuyện vừa tạo | Tìm đúng phiên, đổi tên thành công, xóa có xác nhận |  |
| T7 | Vào `/settings`, đổi chế độ trả lời và ngôn ngữ, tải lại trang | Tùy chọn được giữ sau khi tải lại |  |
| T8 | Vào `/settings`, chọn “Xóa toàn bộ dữ liệu của tôi” | Có hộp thoại xác nhận; sau khi xóa, lịch sử trống và tùy chọn về mặc định |  |
| T9 | Mở `/admin` bằng tài khoản học viên | Thấy thông báo không có quyền, không thấy số liệu |  |
| T10 | Lặp lại T1–T7 trên màn hình điện thoại hoặc cửa sổ hẹp | Không phải cuộn ngang, nút bấm chạm được |  |

## 4. Bảng điểm tiêu chí

Mỗi người tham gia cho điểm từng tiêu chí. Người điều phối tính điểm trung bình theo cột.

| Mã | Tiêu chí | P1 | P2 | P3 | P4 | P5 | Trung bình | Ghi chú |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| C1 | Đăng nhập và điều hướng rõ ràng, dễ làm theo |  |  |  |  |  |  |  |
| C2 | Bố cục màn hình chat dễ nhìn, không rối |  |  |  |  |  |  |  |
| C3 | Câu trả lời hữu ích cho việc ôn thi SAA-C03 |  |  |  |  |  |  |  |
| C4 | Trích dẫn giúp kiểm chứng câu trả lời dễ dàng |  |  |  |  |  |  |  |
| C5 | Chế độ “Giải thích từng bước” hữu ích với câu hỏi vận dụng |  |  |  |  |  |  |  |
| C6 | Màn hình luyện đề dễ dùng và kết quả dễ hiểu |  |  |  |  |  |  |  |
| C7 | Lịch sử cho phép tìm, đổi tên và xóa thuận tiện |  |  |  |  |  |  |  |
| C8 | Cài đặt mô hình, chế độ, ngôn ngữ dễ hiểu |  |  |  |  |  |  |  |
| C9 | Giao diện dùng tốt trên màn hình nhỏ |  |  |  |  |  |  |  |
| C10 | Tổng thể đáng tin cậy, ít lỗi trong quá trình dùng |  |  |  |  |  |  |  |

**Cách tính:** điểm trung bình của từng tiêu chí là trung bình cộng các điểm hợp lệ (bỏ qua N/A). Điểm tổng thể là trung bình cộng của C1–C10.

**Ngưỡng đạt đề xuất:** điểm tổng thể từ 4,0 trở lên; không tiêu chí nào dưới 3,5; không còn lỗi mức chặn (không đăng nhập được, không gửi được câu hỏi, không nộp được bài, mất dữ liệu ngoài ý muốn).

## 5. Câu hỏi mở

1. Bước nào khó nhất khi bạn dùng thử? Vì sao?
2. Điều gì bạn thấy hữu ích nhất cho việc ôn thi?
3. Có chỗ nào chữ, nút hoặc thông báo khó hiểu không?
4. Bạn có gặp lỗi nào không? Mô tả thao tác dẫn tới lỗi.
5. Nếu được thay đổi một thứ, bạn sẽ thay đổi gì?
6. Bạn có tiếp tục dùng công cụ này để luyện thi không? Vì sao?

## 6. Nhật ký lỗi

| Mã lỗi | Người gặp | Kịch bản | Mô tả | Mức độ | Trạng thái |
| :--- | :--- | :--- | :--- | :--- | :--- |
|  |  |  |  |  |  |

Mức độ: chặn / nghiêm trọng / nhẹ / góp ý.

## 7. Tổng hợp kết quả

| Chỉ số | Giá trị |
| :--- | :--- |
| Số người tham gia |  |
| Điểm tổng thể trung bình |  |
| Số tiêu chí dưới 3,5 |  |
| Số lỗi mức chặn còn mở |  |
| Kết luận | Đạt / Không đạt |

Ghi chú của người điều phối:

---

Biểu mẫu này chưa có dữ liệu điền sẵn. Khi tổ chức UAT, điền đầy đủ và lưu bản đã ký hoặc ảnh chụp biểu mẫu vào `docs/evidence/phase-5/uat/`.
