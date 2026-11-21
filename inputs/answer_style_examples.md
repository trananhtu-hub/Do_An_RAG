# Ví dụ câu trả lời mẫu — Giai đoạn 3

Tệp này cung cấp 4 câu trả lời mẫu để dùng làm few-shot cho prompt sinh câu trả lời ở Giai đoạn 3. Mỗi ví dụ gồm ba phần: câu hỏi, câu trả lời mẫu và ghi chú cần học. Các câu trả lời mẫu dài 150–250 từ, có bước suy luận, trích dẫn và kết luận riêng.

## Quy ước trích dẫn

- Cú pháp: `[tên tài liệu – mục Y]`, dùng dấu gạch ngang dài `–`.
- "Tên tài liệu" lấy đúng theo trường `document_title` trong metadata của chunk, để bộ kiểm tra trích dẫn so khớp tự động với ngữ cảnh đã truy xuất.
- "Mục Y" lấy đúng nhãn mục (trường `section` hoặc `heading`) của chunk chứa nội dung được trích.
- Mỗi khẳng định chỉ trích tài liệu và mục có trong ngữ cảnh truy xuất; không trích theo trí nhớ của mô hình và không tự suy ra số mục. Nhiều mục thì viết nhiều ngoặc, ví dụ `[S3 Storage Classes – Mục 1.4] [S3 Storage Classes – Mục 1.6]`.

| `document_title` | Tệp trong `data/raw/` |
| :--- | :--- |
| S3 Storage Classes | `S3_Storage_Classes.pdf` |
| VPC Networking | `VPC_Networking.pdf` |
| RDS Aurora | `RDS_Aurora.pdf` |
| IAM | `IAM.pdf` |
| EC2 Tinh toan | `EC2_Tinh_toan.pdf` |
| aws-saa-exam-guide | `aws-saa-exam-guide.pdf` |
| aws-saa-question-bank | `aws-saa-question-bank.pdf` |

Tên `EC2 Tinh toan` giữ nguyên theo metadata hiện có (không dấu) để khớp với bộ kiểm tra trích dẫn.

Định dạng `[tên tài liệu – mục Y]` thay cho `[tên tài liệu, tr. X]` theo yêu cầu Giai đoạn 3; mọi prompt trong `prompts/v1/` dùng cùng định dạng này.

## Ví dụ 1 — Tra cứu một bước

### Câu hỏi

Amazon RDS hỗ trợ IAM database authentication cho những engine nào và token xác thực có hiệu lực bao lâu?

### Câu trả lời mẫu

Các bước suy luận:

1) Xác định câu hỏi cần hai dữ kiện: danh sách engine hỗ trợ IAM database authentication và thời hạn của token xác thực.
2) Tra mục bảo mật của tài liệu RDS: IAM database authentication hỗ trợ MySQL, MariaDB, PostgreSQL và Aurora tương ứng; SQL Server và Oracle dùng xác thực Active Directory hoặc Kerberos tùy engine.
3) Kiểm tra cơ chế token: ứng dụng dùng token tạm thời thay cho mật khẩu, token hết hạn sau 15 phút.
4) Rút ra hệ quả thiết kế: vì token ngắn hạn, ứng dụng phải xin token mới theo chu kỳ và không cần lưu mật khẩu dài hạn cho các engine này; với engine dùng mật khẩu, tài liệu nêu Secrets Manager có thể tự động xoay mật khẩu định kỳ.

Kết luận: IAM database authentication áp dụng cho MySQL, MariaDB, PostgreSQL và Aurora tương ứng; token có hiệu lực 15 phút [RDS Aurora – Mục 1.6]. SQL Server và Oracle không nằm trong nhóm này mà dùng Active Directory hoặc Kerberos tùy engine [RDS Aurora – Mục 1.6].

### Ghi chú cần học

- Trả lời đúng hai dữ kiện được hỏi, không mở rộng sang engine hay cơ chế xác thực khác khi tài liệu không nêu.
- Mỗi khẳng định kỹ thuật đều có trích dẫn; hai dữ kiện cùng nằm ở một trang nên trích một lần cho mỗi câu.
- Phân biệt rõ dữ kiện tra được trong tài liệu với hệ quả suy ra từ dữ kiện đó.
- Kết luận đứng riêng, đọc độc lập vẫn đủ ý, không bắt người đọc phải suy lại từ các bước trên.

## Ví dụ 2 — So sánh hai dịch vụ

### Câu hỏi

So sánh Amazon EBS và instance store về độ bền dữ liệu, khả năng snapshot, hiệu năng và chi phí. Khi nào nên dùng mỗi loại?

### Câu trả lời mẫu

Các bước suy luận:

1) Chọn tiêu chí so sánh: độ bền dữ liệu, khả năng snapshot và di chuyển, hiệu năng, chi phí và trường hợp sử dụng.
2) Đối chiếu từng tiêu chí theo tài liệu:

| Tiêu chí | Amazon EBS | Instance store |
| :--- | :--- | :--- |
| Độ bền | Bền vững | Mất khi stop, terminate hoặc máy chủ gặp sự cố; còn khi reboot |
| Snapshot, di chuyển | Snapshot được, gắn lại được | Không snapshot, không gắn sang instance khác |
| Hiệu năng | Độ trễ thấp vừa phải | Độ trễ rất thấp, IOPS cao |
| Chi phí | Tính phí riêng | Đã gồm trong giá instance |

Nguồn cho bảng: [EC2 Tinh toan – Mục 1.4].

3) Xác định hệ quả: instance store phù hợp cache, buffer, scratch space có thể tái tạo; không dùng cho dữ liệu cần bền vững hoặc dữ liệu giao dịch chính. EBS bền vững và gắn lại được nên phù hợp dữ liệu chính.

Kết luận: dùng EBS cho dữ liệu chính và instance store cho cache; thiết kế tốt thường kết hợp cả hai [EC2 Tinh toan – Mục 1.4]. Nếu dữ liệu phải tồn tại qua lần stop hoặc terminate, hoặc cần chuyển sang instance khác, chỉ EBS đáp ứng [EC2 Tinh toan – Mục 1.4].

### Ghi chú cần học

- Bảng giúp đối chiếu đủ tiêu chí mà không bỏ sót; mỗi ô chỉ nêu đặc điểm có trong nguồn.
- Không dùng tính từ tuyệt đối không có trong tài liệu (ví dụ "nhanh nhất") khi nguồn chỉ ghi "độ trễ rất thấp".
- Kết luận nêu tiêu chí quyết định (độ bền và khả năng di chuyển) thay vì liệt kê lại toàn bộ bảng.
- Nêu cả trường hợp biên: dữ liệu phải sống qua stop/terminate thì chỉ EBS đáp ứng.

## Ví dụ 3 — Tình huống nhiều ràng buộc

### Câu hỏi

Công ty có khoảng 200 TB dữ liệu hình ảnh y tế, chỉ được truy cập vài lần mỗi quý nhưng khi kiểm toán phải xem được ngay trong mili giây. Dữ liệu phải được lưu tối thiểu 3 năm, phải nằm trên ít nhất ba Availability Zone và cần chi phí lưu trữ thấp nhất có thể. Nên chọn lớp lưu trữ S3 nào?

### Câu trả lời mẫu

Các bước suy luận:

1) Liệt kê năm ràng buộc: tần suất thấp; độ trễ mili giây; lưu 3 năm; ít nhất ba Availability Zone; chi phí thấp nhất.

2) Kiểm tra từng ràng buộc:

| Ràng buộc | Yêu cầu | Lớp đáp ứng | Lớp bị loại |
| :--- | :--- | :--- | :--- |
| Tần suất | Vài lần/quý | Standard-IA, các lớp Glacier | Standard (đắt), Intelligent-Tiering (mẫu đã biết) |
| Độ trễ | Mili giây | Standard-IA, Glacier Instant Retrieval | Glacier Flexible (phút–giờ), Deep Archive (12–48 giờ) |
| Thời gian lưu | ≥ 3 năm | Tất cả (Glacier Instant Retrieval: 90 ngày) | Không loại |
| Số AZ | ≥ 3 | Standard-IA, Glacier Instant Retrieval | One Zone-IA, Express One Zone |
| Chi phí | Thấp nhất | Glacier Instant Retrieval | Standard-IA |

Nguồn: [S3 Storage Classes – Mục 1.4] [S3 Storage Classes – Mục 1.6] [S3 Storage Classes – Mục 1.9].

3) Nguồn: Standard-IA đa AZ [S3 Storage Classes – Mục 1.4]; One Zone-IA một AZ [S3 Storage Classes – Mục 1.4]; Express One Zone một AZ [S3 Storage Classes – Mục 1.9]; Glacier Instant Retrieval đa AZ, mili giây, tối thiểu 90 ngày, rẻ hơn Standard-IA [S3 Storage Classes – Mục 1.6].

Kết luận: chọn S3 Glacier Instant Retrieval vì đáp ứng năm ràng buộc [S3 Storage Classes – Mục 1.6]. Cần tính phí truy xuất cao hơn và mốc 90 ngày khi dự toán [S3 Storage Classes – Mục 1.6].

### Ghi chú cần học

- Bảng kiểm tra từng ràng buộc được lập trước khi kết luận; không bỏ ràng buộc nào và không gộp ràng buộc.
- Loại dần theo ràng buộc cứng (độ trễ, số Availability Zone) rồi mới tối ưu chi phí; chi phí không bao giờ được xét trước ràng buộc kỹ thuật.
- Nêu đánh đổi của lớp được chọn (phí truy xuất, thời gian lưu tối thiểu) thay vì chỉ nói lớp đó rẻ nhất.
- Mỗi kết luận loại trừ đều có trích dẫn riêng, kể cả khi cùng một tài liệu.

## Ví dụ 4 — Chẩn đoán nguyên nhân

### Câu hỏi

Tôi đã gắn policy Allow cho IAM user nhưng khi gọi API vẫn nhận AccessDenied. Những nguyên nhân nào có thể khiến policy Allow không có hiệu lực?

### Câu trả lời mẫu

Các bước suy luận:

1) Nhắc lại nguyên tắc nền: IAM mặc định từ chối mọi yêu cầu; chỉ cho phép khi có ít nhất một đường cho phép hợp lệ và không có từ chối tường minh [IAM – Mục 1.1].
2) Kiểm tra từ chối tường minh trước: explicit deny luôn thắng mọi allow, bất kể đến từ SCP, permission boundary hay bucket policy [IAM – Mục 1.1] [IAM – Mục 1.6].
3) Kiểm tra các lớp giới hạn: SCP và permission boundary không cấp quyền, chỉ giới hạn quyền tối đa; với identity policy và boundary, quyền hiệu lực phải nằm trong cả hai [IAM – Mục 1.1] [IAM – Mục 1.6].
4) Kiểm tra các nguồn còn lại: resource-based policy có thể cho phép hoặc chặn; session policy thu hẹp quyền khi AssumeRole; Condition về MFA, IP, VPC endpoint hoặc org ID có thể không thỏa [IAM – Mục 1.1]. Với cross-account, thường cần cả identity policy ở tài khoản nguồn và bucket/resource policy ở tài khoản đích; KMS key policy có thể cấp quyền trực tiếp nếu nêu rõ principal [IAM – Mục 1.6]. Trust policy chỉ kiểm soát ai được assume role [IAM – Mục 1.6].

Kết luận: kiểm tra theo thứ tự explicit deny, SCP/boundary, resource policy, condition rồi session policy. Policy Allow đơn lẻ không đủ nếu bất kỳ lớp nào phía trên đang chặn [IAM – Mục 1.1] [IAM – Mục 1.6].

### Ghi chú cần học

- Đi theo đúng thứ tự đánh giá quyền của IAM, không liệt kê nguyên nhân lộn xộn.
- Phân biệt "không cấp quyền" (SCP, permission boundary) với "chặn quyền" (explicit deny); đây là hai cơ chế khác nhau.
- Nêu nhiều nguyên nhân khả dĩ và cách kiểm tra từng lớp, không khẳng định một nguyên nhân cụ thể khi chưa có dữ liệu về tài khoản.
- Trích cả hai mục: logic đánh giá và danh sách bẫy thường gặp.

## Nguyên tắc rút ra cho prompt Giai đoạn 3

- Mọi khẳng định kỹ thuật phải truy được về chunk đã truy xuất; không dùng kiến thức nền của mô hình để lấp chỗ trống.
- Không bịa tên tài liệu hoặc số trang; nếu không tìm thấy nguồn, nói rõ không có trong tài liệu.
- Câu trả lời 150–250 từ, có bước suy luận và kết luận riêng.
- Câu hỏi nhiều ràng buộc phải có bảng kiểm tra từng ràng buộc trước khi kết luận.
- Câu hỏi ngoài phạm vi xử lý theo `inputs/out_of_scope_questions.md`: từ chối trả lời thay vì suy đoán.
