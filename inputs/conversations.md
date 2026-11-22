# Kịch bản hội thoại — Giai đoạn 4

Tệp này đáp ứng bước 1 và bước 2 trong phần 1 – Chuẩn bị của Giai đoạn 4 (Sổ tay 3.5.1): mỗi kịch bản có mã kịch bản, mục tiêu, danh sách lượt hỏi của người dùng, hành vi mong đợi ở mỗi lượt và tiêu chí đạt. Bộ 10 kịch bản có đủ phân bố 3 – 2 – 2 – 1 – 1 – 1.

Các kịch bản chỉ dùng nội dung có trong 7 tài liệu của kho tri thức. Cột "Căn cứ" ghi tên tài liệu (trường `document_title`) và mục/trang để đối chiếu với trích dẫn của chatbot; mọi trích dẫn cuối phải trỏ đúng tài liệu và mục, đồng thời nằm trong khoảng trang tương ứng của chunk.

## Quy ước chạy và chấm

- Mỗi kịch bản chạy trong một phiên riêng, cùng một tài khoản test; không dùng lại phiên giữa các kịch bản.
- Chỉ gửi cột "Câu hỏi người dùng" cho chatbot. Các cột còn lại là tiêu chí chấm, không đưa vào prompt.
- Cột "Câu viết lại kỳ vọng" là đầu ra mong đợi của bước query condensation: câu độc lập, giữ nguyên ý, không thêm dữ kiện. Với lượt đã độc lập, ghi "Giữ nguyên".
- Kịch bản đạt khi tất cả lượt đạt; toàn bộ 10 kịch bản phải đạt ≥ 8 theo bảng kiểm Giai đoạn 4.
- Khi một lượt không đạt, ghi mã kịch bản, số lượt và lỗi thuộc tầng nào: condensation, retrieval, generation hay streaming/SSE.

## Phân bố 10 kịch bản

| Loại | Mã kịch bản | Số lượng |
| :--- | :--- | :---: |
| Tra cứu nối tiếp | KB-01, KB-02, KB-03 | 3 |
| So sánh | KB-04, KB-05 | 2 |
| Nhiều ràng buộc | KB-06, KB-07 | 2 |
| Đổi chủ đề giữa chừng | KB-08 | 1 |
| Người dùng hỏi lại làm rõ | KB-09 | 1 |
| Hỏi ngoài phạm vi | KB-10 | 1 |
| **Tổng** | | **10** |

| Mã | Chủ đề | Số lượt |
| :--- | :--- | :---: |
| KB-01 | S3 và EBS | 4 |
| KB-02 | Sao lưu và phục hồi RDS | 4 |
| KB-03 | IAM role và thông tin xác thực tạm thời | 4 |
| KB-04 | Multi-AZ và Read Replica | 4 |
| KB-05 | Security group và network ACL | 4 |
| KB-06 | Chọn lớp lưu trữ S3 theo ràng buộc | 4 |
| KB-07 | Chọn hình thức mua EC2 theo mẫu tải | 4 |
| KB-08 | Đổi chủ đề từ S3 sang IAM | 4 |
| KB-09 | Người dùng hỏi lại về NAT Gateway | 4 |
| KB-10 | Ngoài phạm vi giữa hội thoại S3 | 4 |

## KB-01 — Tra cứu nối tiếp: từ S3 sang so sánh với EBS

- **Mã kịch bản:** KB-01
- **Loại:** Tra cứu nối tiếp
- **Mục tiêu:** Kiểm tra query condensation khi lượt sau so sánh với EBS mà không nhắc lại S3; kiểm tra truy xuất chéo hai tài liệu (S3 Storage Classes và EC2 Tinh toan) và không trộn đặc điểm của hai dịch vụ.
- **Số lượt:** 4
- **Tài liệu:** S3 Storage Classes — Mục 1.1 (tr. 1), Mục 1.2 (tr. 2), Mục 1.4 (tr. 3–4); EC2 Tinh toan — Mục 1.4 (tr. 3–4)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | Amazon S3 là gì? | Giữ nguyên | Nêu S3 là dịch vụ lưu trữ đối tượng với nhiều lớp trên cùng không gian tên; lớp được gán khi tải lên hoặc chuyển bằng lifecycle; mặc định là Standard; ba nhóm lớp (truy cập thường xuyên, không thường xuyên, lưu trữ lạnh); các lớp đa AZ và một AZ. | S3 Storage Classes — Mục 1.1 (tr. 1) |
| 2 | So với EBS thì khác ở đâu? | So với Amazon EBS, Amazon S3 khác ở điểm nào? | Lập bảng so sánh: S3 là lưu trữ đối tượng, truy cập qua API, nhiều lớp, có lớp đa AZ và lớp một AZ; EBS là ổ đĩa khối gắn với EC2 trong cùng AZ, tồn tại độc lập với vòng đời instance, sao lưu bằng snapshot lên S3; không thay thế nhau. | S3 Storage Classes — Mục 1.1 (tr. 1), Mục 1.2 (tr. 2); EC2 Tinh toan — Mục 1.4 (tr. 3–4) |
| 3 | Vậy khi nào dùng cái nào? | Khi nào nên dùng Amazon S3 và khi nào nên dùng Amazon EBS? | Trả lời S3 cho đối tượng, nội dung tĩnh, phân tích dữ liệu lớn, sao lưu; EBS cho ổ đĩa khối của EC2, workload cần IOPS/độ trễ thấp; nêu kết hợp: snapshot EBS được lưu trong S3. | S3 Storage Classes — Mục 1.2 (tr. 2), Mục 1.4 (tr. 3–4); EC2 Tinh toan — Mục 1.4 (tr. 3–4) |
| 4 | EBS có tự nhân bản qua nhiều AZ không? | Amazon EBS có tự động nhân bản dữ liệu qua nhiều Availability Zone không? | Trả lời không: EBS gắn với một AZ và chỉ gắn được cho instance cùng AZ; snapshot là bản sao tăng dần lưu trong S3 do AWS quản lý, có thể tạo volume ở AZ/Region khác sau khi copy snapshot; Multi-Attach chỉ trong cùng AZ. | EC2 Tinh toan — Mục 1.4 (tr. 3–4) |

**Tiêu chí đạt:**

- 4/4 lượt đúng; lượt 2–3 có bảng hoặc cấu trúc so sánh rõ S3 và EBS.
- Câu viết lại lượt 2 chứa "S3" và "EBS"; không truy xuất chỉ bằng từ "khác" hoặc "EBS".
- Không gán đặc điểm của EBS cho S3 hoặc ngược lại; không nói EBS tự nhân bản nhiều AZ.
- Trích đúng cả hai tài liệu ở lượt 2–3; lượt 4 trích EC2 Mục 1.4.
- Không bịa thông số IOPS/dung lượng ngoài tài liệu.

## KB-02 — Tra cứu nối tiếp: sao lưu và phục hồi RDS

- **Mã kịch bản:** KB-02
- **Loại:** Tra cứu nối tiếp
- **Mục tiêu:** Kiểm tra chuỗi hồi quy sao lưu RDS: thời gian lưu giữ → PITR → hành vi khôi phục → phân biệt snapshot thủ công; kiểm tra đại từ "nó" ở lượt 3.
- **Số lượt:** 4
- **Tài liệu:** RDS Aurora — Mục 1.3 (tr. 3)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | RDS sao lưu tự động giữ bao lâu? | Giữ nguyên | Trả lời 0–35 ngày; đặt 0 là tắt; backup chạy trong backup window nên đặt giờ thấp điểm; nêu xóa instance giữ snapshot cuối nếu tùy chọn bật. | RDS Aurora — Mục 1.3 (tr. 3) |
| 2 | Có khôi phục được về một giờ trước không? | RDS có thể phục hồi theo thời điểm về một thời điểm trong khoảng lưu giữ không? | Trả lời có, PITR tới bất kỳ giây nào trong khoảng lưu giữ, thường trong vòng 5 phút kể từ thời điểm gần nhất; không hứa chính xác từng giây ngoài khoảng. | Mục 1.3 (tr. 3) |
| 3 | Khôi phục xong nó ghi đè DB cũ hay tạo cái mới? | Khôi phục RDS tạo DB instance mới hay ghi đè instance hiện có? | Trả lời luôn tạo instance mới với endpoint mới; không ghi đè; cần cập nhật DNS/endpoint ứng dụng. | Mục 1.3 (tr. 3) |
| 4 | Vậy snapshot thủ công khác gì? | Snapshot thủ công khác sao lưu tự động của RDS ở điểm nào? | Trả lời snapshot thủ công giữ đến khi bị xóa, kể cả sau khi xóa DB instance; có thể copy sang Region khác; snapshot mã hóa chỉ chia sẻ khi nguồn cho phép; khôi phục cũng tạo instance mới. | Mục 1.3 (tr. 3) |

**Tiêu chí đạt:**

- 4/4 lượt đúng; không nói khôi phục ghi đè instance hiện có.
- Lượt 2 nêu đúng PITR trong khoảng lưu giữ; lượt 3 nêu endpoint mới.
- Lượt 4 phân biệt rõ sao lưu tự động và snapshot thủ công.
- Trích dẫn đúng Mục 1.3.

## KB-03 — Tra cứu nối tiếp: IAM role và thông tin xác thực tạm thời

- **Mã kịch bản:** KB-03
- **Loại:** Tra cứu nối tiếp
- **Mục tiêu:** Kiểm tra chuỗi khái niệm IAM role: định nghĩa → trust policy → thời hạn credential → thu hồi; kiểm tra đại từ "của nó".
- **Số lượt:** 4
- **Tài liệu:** IAM — Mục 1.3 (tr. 2–3), Mục 1.12 (tr. 10–11)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | IAM role là gì? | Giữ nguyên | Trả lời là cách cấp quyền tạm thời cho ứng dụng/dịch vụ/tài khoản khác mà không lưu credential dài hạn; nêu hai phần trust policy và permission policy; ví dụ EC2 instance profile, Lambda execution role, cross-account role. | IAM — Mục 1.3 (tr. 2–3) |
| 2 | Trust policy của nó dùng để làm gì? | Trust policy của IAM role xác định điều gì? | Trả lời xác định ai được assume role; không cấp quyền truy cập tài nguyên; permission policy mới quy định role được làm gì. | Mục 1.3 (tr. 2–3); Mục 1.12 (tr. 10–11) |
| 3 | Thông tin xác thực tạm thời sống được bao lâu? | Thời hạn của thông tin xác thực tạm thời do STS cấp cho IAM role là bao lâu? | Trả lời 15 phút đến 12 giờ tùy max session duration; mặc định 1 giờ; role chaining thường giới hạn 1 giờ. | Mục 1.3 (tr. 2–3) |
| 4 | Có thu hồi ngay được không? | Có thể thu hồi ngay thông tin xác thực tạm thời của IAM role không? | Trả lời không thu hồi ngay được; phải thu hồi quyền của role hoặc dùng policy điều kiện; nêu khuyến nghị dùng role thay access key dài hạn. | Mục 1.3 (tr. 2–3); Mục 1.12 (tr. 10–11) |

**Tiêu chí đạt:**

- 4/4 lượt đúng; không nói trust policy cấp quyền tài nguyên.
- Nêu đúng khoảng 15 phút–12 giờ và mặc định 1 giờ.
- Lượt 4 không nói có thể thu hồi tức thời.
- Trích đúng Mục 1.3; riêng bẫy trust policy có thể trích thêm Mục 1.12.

## KB-04 — So sánh: Multi-AZ và Read Replica

- **Mã kịch bản:** KB-04
- **Loại:** So sánh
- **Mục tiêu:** Kiểm tra so sánh xuyên lượt Multi-AZ và Read Replica; các lượt sau dùng "cái nào" nên phải giữ đúng hai đối tượng so sánh.
- **Số lượt:** 4
- **Tài liệu:** RDS Aurora — Mục 1.2 (tr. 2)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | Multi-AZ và Read Replica khác nhau thế nào? | Giữ nguyên | Lập bảng so sánh tối thiểu 5 tiêu chí: mục tiêu (sẵn sàng cao vs mở rộng đọc), cơ chế (đồng bộ vs bất đồng bộ), khả năng đọc (standby không đọc vs replica đọc được), failover (tự động vs thủ công), chi phí; kết luận hai cơ chế không thay thế nhau. | RDS Aurora — Mục 1.2 (tr. 2) |
| 2 | Cái nào giúp tăng khả năng đọc? | Multi-AZ hay Read Replica giúp tăng khả năng đọc? | Trả lời Read Replica; nêu standby của Multi-AZ cổ điển không phục vụ đọc; nêu ngoại lệ Multi-AZ DB cluster (1 writer + 2 instance đọc được) cho MySQL/PostgreSQL/MariaDB. | Mục 1.2 (tr. 2) |
| 3 | Khi instance chính lỗi thì cái nào tự chuyển? | Khi instance chính gặp sự cố, Multi-AZ hay Read Replica tự động failover? | Trả lời Multi-AZ tự động failover khoảng 60–120 giây, DNS giữ nguyên; Read Replica không tự failover, phải chuyển endpoint thủ công. | Mục 1.2 (tr. 2) |
| 4 | Nếu cần cả hai thì sao? | Nếu cần cả chịu lỗi và mở rộng đọc thì nên kết hợp Multi-AZ và Read Replica thế nào? | Trả lời bật Multi-AZ cho instance chính và thêm read replica cho đọc; nếu đọc ở châu lục khác dùng cross-region read replica hoặc Aurora Global Database. | Mục 1.2 (tr. 2) |

**Tiêu chí đạt:**

- Lượt 1 có bảng so sánh; 4/4 lượt không mâu thuẫn với bảng.
- Không nói Read Replica tự động failover; không nói standby Multi-AZ phục vụ đọc, trừ ngoại lệ Multi-AZ DB cluster.
- Lượt 2–3 viết lại vẫn giữ cả hai đối tượng so sánh.
- Trích đúng Mục 1.2.

## KB-05 — So sánh: security group và network ACL

- **Mã kịch bản:** KB-05
- **Loại:** So sánh
- **Mục tiêu:** Kiểm tra so sánh security group và network ACL, sau đó áp dụng vào tình huống gỡ lỗi; các lượt sau dùng "cái nào", "vậy".
- **Số lượt:** 4
- **Tài liệu:** VPC Networking — Mục 1.4 (tr. 3–4)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | Security group và network ACL khác nhau ở điểm nào? | Giữ nguyên | Bảng so sánh: cấp áp dụng (ENI/instance vs subnet), trạng thái (stateful vs stateless), loại rule (chỉ allow vs allow+deny), cách đánh giá (mọi rule vs theo thứ tự dừng ở rule khớp đầu), mặc định. | VPC Networking — Mục 1.4 (tr. 3–4) |
| 2 | Cái nào có trạng thái? | Security group hay network ACL là stateful? | Trả lời security group stateful, phản hồi tự động được phép; NACL stateless, phải mở cả hai chiều kể cả cổng tạm thời. | Mục 1.4 (tr. 3–4) |
| 3 | Vì sao mở inbound 443 trên NACL vẫn không kết nối được? | Vì sao chỉ mở inbound cổng 443 trên network ACL vẫn không kết nối được? | Trả lời do NACL stateless: phải mở outbound dải cổng tạm thời 1024–65535 (và ngược lại); nhắc kiểm tra thêm security group. | Mục 1.4 (tr. 3–4) |
| 4 | Vậy khi debug nên kiểm tra theo thứ tự nào? | Khi gỡ lỗi kết nối trong VPC nên kiểm tra security group, NACL, route table và DNS theo thứ tự nào? | Trả lời thứ tự: security group của nguồn và đích → NACL hai chiều → route table → DNS. | Mục 1.4 (tr. 3–4) |

**Tiêu chí đạt:**

- Bảng lượt 1 đúng 5 tiêu chí; 4/4 lượt nhất quán.
- Không nói NACL stateful hoặc security group có rule deny.
- Lượt 3 nêu đúng dải cổng tạm thời 1024–65535.
- Trích đúng Mục 1.4.

## KB-06 — Nhiều ràng buộc: chọn lớp lưu trữ S3

- **Mã kịch bản:** KB-06
- **Loại:** Nhiều ràng buộc
- **Mục tiêu:** Kiểm tra lập bảng ràng buộc trước khi kết luận và cập nhật khi ràng buộc thay đổi; chống W1 (nhảy cóc) và W2 (bỏ ràng buộc).
- **Số lượt:** 4
- **Tài liệu:** S3 Storage Classes — Mục 1.1 (tr. 1), 1.2 (tr. 2), 1.4 (tr. 3–4), 1.5 (tr. 4), 1.6 (tr. 5), 1.11 (tr. 8–9), 1.13 (tr. 10–11)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | Tôi có 80 TB ảnh thumbnail có thể tạo lại từ nguồn gốc, chỉ đọc vài lần mỗi tháng nhưng cần truy xuất trong mili giây, lưu 6 tháng, chi phí thấp nhất. Chọn lớp S3 nào? | Giữ nguyên | Lập bảng 5 ràng buộc (tần suất, độ trễ, thời gian lưu, khả năng tái tạo, chi phí); chọn One Zone-IA vì một AZ chấp nhận được với dữ liệu tái tạo, truy xuất mili giây, tối thiểu 30 ngày, rẻ hơn Standard-IA; nêu phí truy xuất và phí xóa sớm. | S3 Storage Classes — Mục 1.1 (tr. 1); Mục 1.5 (tr. 4); Mục 1.13 (tr. 10–11) |
| 2 | Nếu ảnh gốc không thể tạo lại thì sao? | Nếu dữ liệu không thể tái tạo thì nên chọn lớp S3 nào thay cho One Zone-IA? | Loại One Zone-IA vì một AZ; chọn một lớp đa AZ có truy xuất mili giây: Standard-IA hoặc Glacier Instant Retrieval; nếu chọn Glacier Instant Retrieval phải nêu phí truy xuất cao hơn và mốc 90 ngày; nếu chọn Standard-IA phải nêu giá lưu trữ cao hơn; không quay lại lớp một AZ. | Mục 1.1 (tr. 1); Mục 1.4 (tr. 3–4); Mục 1.6 (tr. 5); Mục 1.13 (tr. 10–11) |
| 3 | Glacier Instant Retrieval có rẻ hơn Standard-IA không? | So với Standard-IA, Glacier Instant Retrieval có tổng chi phí thấp hơn cho dữ liệu đọc vài lần mỗi tháng không? | Không trả lời "có" vô điều kiện: giá lưu trữ thấp hơn nhưng phí truy xuất cao hơn và tối thiểu 90 ngày; tổng chi phí phụ thuộc lượng đọc; cần tính đủ phí truy xuất, request, xóa sớm. | Mục 1.4 (tr. 3–4); Mục 1.6 (tr. 5); Mục 1.11 (tr. 8–9) |
| 4 | Nếu chỉ lưu 20 ngày thì sao? | Nếu dữ liệu chỉ được lưu 20 ngày thì Standard-IA hoặc One Zone-IA có còn phù hợp không? | Trả lời không tối ưu: hai lớp này tối thiểu 30 ngày và xóa trước hạn vẫn bị tính đủ 30 ngày; với 20 ngày nên cân nhắc S3 Standard; không khẳng định Standard-IA rẻ hơn. | Mục 1.2 (tr. 2); Mục 1.4 (tr. 3–4); Mục 1.5 (tr. 4); Mục 1.11 (tr. 8–9) |

**Tiêu chí đạt:**

- Lượt 1 và 2 có bảng kiểm tra đủ 5 ràng buộc; không bỏ ràng buộc "có thể tái tạo".
- Lượt 1 chọn One Zone-IA; lượt 2 chuyển khỏi One Zone-IA sang lớp đa AZ (Standard-IA hoặc Glacier Instant Retrieval) với lý do đúng.
- Lượt 3 không trả lời yes/no đơn giản; nêu đánh đổi, phí truy xuất và mốc 90 ngày.
- Lượt 4 nhận ra mốc 30 ngày và phí xóa sớm; không mâu thuẫn các lượt trước.
- Trích dẫn đúng các mục; không trích Mục 1.3 (Intelligent-Tiering) nếu không dùng.

## KB-07 — Nhiều ràng buộc: chọn hình thức mua EC2

- **Mã kịch bản:** KB-07
- **Loại:** Nhiều ràng buộc
- **Mục tiêu:** Kiểm tra tách bài toán theo mẫu tải (web 24/7 không gián đoạn và batch đêm), không áp một lựa chọn cho cả hai; chống việc chọn Spot chỉ vì rẻ.
- **Số lượt:** 4
- **Tài liệu:** EC2 Tinh toan — Mục 1.3 (tr. 2–3)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | Website chạy 24/7 ổn định 12 tháng, không thể gián đoạn, muốn giảm chi phí tối đa và có thể cam kết 1 năm. Nên mua instance thế nào? | Giữ nguyên | Lập bảng ràng buộc; chọn Reserved Instance hoặc Savings Plans cho phần nền 24/7; On-Demand cho đỉnh ngắn/không dự đoán; không dùng Spot cho web không thể gián đoạn. | EC2 Tinh toan — Mục 1.3 (tr. 2–3) |
| 2 | Sao không dùng Spot cho web cho rẻ? | Vì sao không nên dùng Spot Instance cho website chạy 24/7 không thể gián đoạn? | Trả lời Spot có thể bị thu hồi với thông báo 2 phút, chỉ phù hợp workload chịu lỗi/stateless; không dùng cho cơ sở dữ liệu chính hoặc ứng dụng không thể gián đoạn. | Mục 1.3 (tr. 2–3) |
| 3 | Savings Plans khác Reserved Instance thế nào? | Savings Plans khác Reserved Instance ở điểm nào? | Trả lời Savings Plans cam kết mức chi tiêu theo giờ 1/3 năm, Compute Savings Plans áp dụng cho EC2/Lambda/Fargate; RI cam kết cấu hình instance 1/3 năm, Standard giảm sâu nhưng ít linh hoạt, Convertible đổi được họ instance. | Mục 1.3 (tr. 2–3) |
| 4 | Còn batch xử lý ảnh chạy 2 giờ mỗi đêm thì sao? | Với batch xử lý ảnh chạy 2 giờ mỗi đêm có thể dừng và chạy lại, nên dùng hình thức mua nào? | Trả lời Spot phù hợp vì batch chịu lỗi và có thể chạy lại; nếu không thể gián đoạn thì On-Demand; có thể kết hợp Savings Plans/RI cho nền và Spot cho batch. | Mục 1.3 (tr. 2–3) |

**Tiêu chí đạt:**

- Lượt 1 có bảng ràng buộc và không chọn Spot cho web.
- Lượt 2 nêu đúng thông báo 2 phút và tiêu chí chịu lỗi.
- Lượt 3 phân biệt đúng Savings Plans và RI; không nói RI áp dụng cho Lambda.
- Lượt 4 chọn Spot cho batch, không áp Spot cho web.
- Trích đúng Mục 1.3.

## KB-08 — Đổi chủ đề giữa chừng: từ S3 sang IAM

- **Mã kịch bản:** KB-08
- **Loại:** Đổi chủ đề giữa chừng
- **Mục tiêu:** Kiểm tra phát hiện đổi chủ đề và reset ngữ cảnh; câu hỏi mới về IAM không được viết lại bằng từ khóa S3/log.
- **Số lượt:** 4
- **Tài liệu:** S3 Storage Classes — Mục 1.8 (tr. 6), 1.10 (tr. 7–8), 1.11 (tr. 8–9), 1.13 (tr. 10–11); IAM — Mục 1.6 (tr. 5), 1.12 (tr. 10–11)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | Làm sao giảm chi phí lưu log cũ trên S3? | Giữ nguyên | Trả lời dùng lifecycle chuyển log cũ sang Standard-IA/Glacier/Deep Archive theo tần suất truy cập; nêu lifecycle chạy bất đồng bộ và có phí chuyển lớp; kiểm tra bằng Storage Lens. | S3 Storage Classes — Mục 1.10 (tr. 7–8); Mục 1.11 (tr. 8–9); Mục 1.13 (tr. 10–11) |
| 2 | Vậy log nên chuyển sang Deep Archive sau bao lâu? | Nên chuyển log S3 sang Glacier Deep Archive sau bao lâu? | Trả lời tối thiểu 180 ngày; chỉ nên dùng khi gần như không đọc; nêu phí truy xuất/khôi phục và thời gian khôi phục 12–48 giờ. | Mục 1.8 (tr. 6); Mục 1.10 (tr. 7–8) |
| 3 | Đổi chủ đề: trong IAM, MFA nên bật cho những ai? | Trong IAM, MFA nên được bật cho những đối tượng nào? | Phát hiện đổi chủ đề; trả lời root và người dùng có quyền cao; nêu policy condition `aws:MultiFactorAuthPresent`; không trích S3, không nhắc log. | IAM — Mục 1.6 (tr. 5); Mục 1.12 (tr. 10–11) |
| 4 | Có bắt buộc MFA cho mọi user không? | Có bắt buộc bật MFA cho mọi IAM user không? | Trả lời tài liệu khuyến nghị bắt buộc cho người dùng quyền cao và root, không nêu yêu cầu tuyệt đối cho mọi user; có thể chặn hành động nhạy cảm khi chưa MFA bằng condition; với Identity Center, MFA quản lý tại IdP hoặc Identity Center tùy cấu hình. | IAM — Mục 1.6 (tr. 5) |

**Tiêu chí đạt:**

- Lượt 3 nhận diện đổi chủ đề; không có trích dẫn hoặc nội dung S3 trong lượt 3–4.
- Câu viết lại lượt 3 không chứa "log", "S3", "Deep Archive".
- Lượt 4 trả lời đúng sắc thái "khuyến nghị/không tuyệt đối", không bịa chính sách bắt buộc mọi user.
- Trích đúng IAM Mục 1.6; có thể thêm Mục 1.12.

## KB-09 — Người dùng hỏi lại làm rõ: NAT Gateway

- **Mã kịch bản:** KB-09
- **Loại:** Người dùng hỏi lại làm rõ
- **Mục tiêu:** Kiểm tra người dùng hỏi lại để làm rõ câu trả lời trước; chatbot phải giải thích lại đúng trọng tâm, giữ ngữ cảnh, không coi là câu hỏi mới hoàn toàn.
- **Số lượt:** 4
- **Tài liệu:** VPC Networking — Mục 1.3 (tr. 2–3), Mục 1.4 (tr. 3–4)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | NAT Gateway có cần gắn security group không? | Giữ nguyên | Trả lời không: NAT gateway là dịch vụ quản lý, không gắn security group; kiểm soát bằng security group của tài nguyên và NACL của subnet. | VPC Networking — Mục 1.3 (tr. 2–3) |
| 2 | Ý bạn là NAT Gateway không có security group, vậy tôi bảo vệ nó bằng cách nào? | NAT Gateway không có security group thì bảo vệ lưu lượng bằng cách nào? | Giải thích lại: dùng security group trên tài nguyên, NACL trên subnet, route table; NAT gateway do AWS quản lý; không gắn security group cho chính NAT gateway. | Mục 1.3 (tr. 2–3); Mục 1.4 (tr. 3–4) |
| 3 | Còn NAT instance thì có security group không? | NAT instance có gắn được security group không? | Trả lời có, NAT instance là EC2 tự quản nên gắn được security group; phải tự vá lỗi, tự cấu hình, tự đảm bảo dự phòng; rẻ hơn với lưu lượng nhỏ. | Mục 1.3 (tr. 2–3) |
| 4 | Vậy khi nào nên chọn cái nào? | Khi nào nên chọn NAT Gateway và khi nào nên chọn NAT instance? | Trả lời NAT gateway cho tính sẵn sàng/quản lý, một NAT mỗi AZ; NAT instance cho môi trường phát triển/lưu lượng nhỏ và chấp nhận tự quản; nêu phí chéo AZ và gateway endpoint cho S3/DynamoDB. | Mục 1.3 (tr. 2–3) |

**Tiêu chí đạt:**

- Lượt 2 là câu hỏi lại làm rõ; chatbot phải xác nhận "đúng, NAT Gateway không có security group" và giải thích cách kiểm soát, không lái sang dịch vụ khác.
- Lượt 3 phân biệt NAT instance (EC2, có security group) và NAT gateway (không có security group).
- Lượt 4 nêu tiêu chí chọn đúng; không nói NAT gateway hỗ trợ IPv6.
- Trích đúng Mục 1.3; có thể thêm Mục 1.4.

## KB-10 — Hỏi ngoài phạm vi giữa hội thoại S3

- **Mã kịch bản:** KB-10
- **Loại:** Hỏi ngoài phạm vi
- **Mục tiêu:** Kiểm tra từ chối đúng hai loại ngoài phạm vi (ngoài lĩnh vực AWS và dịch vụ AWS không có trong kho) giữa một hội thoại đang đúng chủ đề; sau đó quay lại được.
- **Số lượt:** 4
- **Tài liệu:** S3 Storage Classes — Mục 1.2 (tr. 2), Mục 1.4 (tr. 3–4); đối chiếu `inputs/out_of_scope_questions.md`

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | S3 Standard-IA khác Standard ở điểm nào? | Giữ nguyên | So sánh: Standard-IA giá lưu trữ thấp hơn, có phí truy xuất, tối thiểu 30 ngày, truy xuất mili giây, đa AZ; Standard không phí truy xuất, không thời gian lưu tối thiểu, giá lưu trữ cao hơn. | S3 Storage Classes — Mục 1.2 (tr. 2); Mục 1.4 (tr. 3–4) |
| 2 | Viết cho tôi đoạn Python để upload file lên S3. | Giữ nguyên | Từ chối: ngoài phạm vi hỗ trợ vì không phải nội dung ôn thi SAA trong kho; không viết code, không nêu thư viện; có thể mời quay lại câu hỏi AWS SAA. | Không trích dẫn |
| 3 | Vậy Amazon Bedrock là gì? | Amazon Bedrock là dịch vụ gì? | Từ chối đúng loại "không có trong tài liệu": nói 7 tài liệu không chứa Bedrock; không mô tả foundation model, giá, tính năng; không trích dẫn. | Không trích dẫn |
| 4 | Quay lại S3: Standard-IA có truy xuất mili giây không? | S3 Standard-IA có truy xuất trong mili giây không? | Trả lời có, truy xuất mili giây, không cần chờ khôi phục; trả lời đúng ngữ cảnh S3 sau hai lượt ngoài phạm vi. | S3 Storage Classes — Mục 1.4 (tr. 3–4) |

**Tiêu chí đạt:**

- Lượt 2 không có code, không giải thích Python; `abstained = true`, lý do ngoài phạm vi.
- Lượt 3 không có tên mô hình, giá, tính năng Bedrock; `abstained = true`, lý do không có trong tài liệu.
- Lượt 2–3 không có citations.
- Lượt 4 trả lời đúng và có trích dẫn; chứng minh hội thoại phục hồi sau khi từ chối.
- Không dùng các dịch vụ đã có trong kho (Comprehend, Polly, Rekognition, IoT Core, Braket) làm câu ngoài phạm vi.

## Bảng tổng hợp chấm điểm

| Mã | Loại | Số lượt | Đạt | Lỗi chính (condensation / retrieval / generation / streaming) |
| :--- | :--- | :---: | :---: | :--- |
| KB-01 | Tra cứu nối tiếp | 4 | | |
| KB-02 | Tra cứu nối tiếp | 4 | | |
| KB-03 | Tra cứu nối tiếp | 4 | | |
| KB-04 | So sánh | 4 | | |
| KB-05 | So sánh | 4 | | |
| KB-06 | Nhiều ràng buộc | 4 | | |
| KB-07 | Nhiều ràng buộc | 4 | | |
| KB-08 | Đổi chủ đề giữa chừng | 4 | | |
| KB-09 | Người dùng hỏi lại làm rõ | 4 | | |
| KB-10 | Hỏi ngoài phạm vi | 4 | | |

**Tổng số kịch bản đạt:** ___ / 10 (ngưỡng Giai đoạn 4: ≥ 8/10).

## Ghi chú khi sử dụng

- Đây là kịch bản kiểm thử hành vi hội thoại, không phải prompt huấn luyện. Không đưa nội dung cột "Hành vi mong đợi" vào ngữ cảnh gửi mô hình.
- Chạy sau khi đã đóng băng cấu hình Giai đoạn 4; không sửa kịch bản giữa các lần chạy để tránh làm sai lệch so sánh.
- Với mỗi lượt không đạt, lưu `session_id`, số lượt, `rewritten_query`, danh sách chunk truy xuất và câu trả lời để phân tích nguyên nhân.
- Các kịch bản này không thay thế bộ test ngoại kho ≥ 150 câu của Giai đoạn 6; chúng chỉ đo hành vi nhiều lượt, condensation và từ chối ở Giai đoạn 4.
