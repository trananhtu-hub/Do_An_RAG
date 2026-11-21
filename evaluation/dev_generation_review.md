# Review bộ dev nội bộ (Giai đoạn 3)

- Tổng số câu: **40**
- Câu trùng nhau: 0
- Câu thiếu trích dẫn nguồn: 0
- Câu có đáp án tham chiếu < 40 ký tự: 0
- Ngân hàng câu hỏi đối chiếu: 1577 chunk
- Dev set truy hồi Giai đoạn 2 đối chiếu: 40 câu

## Phân bố

| Tài liệu | Số câu |
| :--- | ---: |
| EC2 Tinh toan | 5 |
| IAM | 5 |
| RDS Aurora | 6 |
| S3 Storage Classes | 6 |
| VPC Networking | 6 |
| aws-saa-exam-guide | 12 |

| Loại câu hỏi | Số câu |
| :--- | ---: |
| nhieu_rang_buoc | 12 |
| so_sanh | 6 |
| tra_cuu | 21 |
| tron_thuat_ngu | 1 |

| Mức nhận thức | Số câu |
| :--- | ---: |
| K1 | 19 |
| K2 | 16 |
| K3 | 5 |

## Trùng lặp nội dung với ngân hàng câu hỏi công khai

Jaccard token cao nhất của từng câu dev so với mọi chunk ngân hàng:

| ID | Jaccard cao nhất |
| :--- | ---: |
| GD-030 | 0.197 |
| GD-028 | 0.191 |
| GD-032 | 0.186 |
| GD-018 | 0.169 |
| GD-031 | 0.163 |

## Trùng lặp với dev set truy hồi Giai đoạn 2

| ID | Jaccard cao nhất |
| :--- | ---: |
| GD-002 | 0.513 |
| GD-019 | 0.333 |
| GD-036 | 0.314 |
| GD-040 | 0.302 |
| GD-039 | 0.256 |

## Mẫu câu hỏi

### GD-001 — EC2 Tinh toan / Mục 1.1

**Hỏi:** Khi một EC2 instance bị Terminate theo mặc định, điều gì xảy ra với ổ EBS gốc và dữ liệu trên instance store?

**Đáp án tham chiếu:** Theo mặc định, Terminate sẽ xóa instance và xóa ổ EBS gốc; dữ liệu trên instance store mất vĩnh viễn.

**Trích dẫn nguồn:** Terminate: xóa instance và (mặc định) xóa ổ EBS gốc; instance store mất vĩnh viễn.

### GD-006 — IAM / Mục 1.2

**Hỏi:** Theo Mục 1.2 của tài liệu IAM, tiêu đề mục nêu hai nội dung trọng tâm nào?

**Đáp án tham chiếu:** Cấu trúc policy và logic đánh giá quyền.

**Trích dẫn nguồn:** Mục 1.2: Cấu trúc policy và logic đánh giá quyền

### GD-011 — RDS Aurora / Mục 1.1

**Hỏi:** Trong Amazon RDS, những hạng mục nào do AWS quản lý và những hạng mục nào do người dùng quản lý? Nêu ít nhất ba hạng mục cho mỗi bên.

**Đáp án tham chiếu:** AWS quản lý máy chủ, hệ điều hành, phần mềm cơ sở dữ liệu, vá lỗi, sao lưu tự động, giám sát hạ tầng và thay thế khi lỗi. Người dùng quản lý tối ưu truy vấn, thiết kế lược đồ, quản lý người dùng và quyền trong cơ sở dữ liệu, cấu hình tham số và quyết định thời điểm nâng cấp phiên bản lớn.

**Trích dẫn nguồn:** AWS quản lý: máy chủ, hệ điều hành, phần mềm cơ sở dữ liệu, vá lỗi, sao lưu tự động, giám sát hạ tầng, thay thế khi lỗi. | Người dùng quản lý: tối ưu truy vấn, thiết kế lược đồ, quản lý người dùng và quyền trong cơ sở dữ liệu, cấu hình tham số, quyết định thời điểm nâng cấp phiên bản lớn.

### GD-016 — RDS Aurora / Mục 1.12

**Hỏi:** Khi RDS Multi-AZ xảy ra failover, ứng dụng có cần đổi endpoint không, nên theo dõi gì để biết thời điểm, và xử lý replica lag lớn như thế nào?

**Đáp án tham chiếu:** Không cần đổi endpoint; ứng dụng kiểm tra kết nối lại qua DNS và theo dõi RDS event để biết thời điểm failover. Với replica lag lớn: giảm tải ghi, kiểm tra tác vụ nặng trên replica, cân nhắc thêm replica hoặc nâng instance.

**Trích dẫn nguồn:** không cần đổi endpoint. | Replica lag lớn: giảm tải ghi, kiểm tra tác vụ nặng trên replica, cân nhắc thêm replica hoặc

### GD-021 — S3 Storage Classes / Mục 1.10

**Hỏi:** Khi đặt quy tắc vòng đời để chuyển lớp lưu trữ S3, ngoài phí lưu trữ theo GB-tháng cần tính đến những thành phần chi phí nào và một sai lầm thường gặp là gì?

**Đáp án tham chiếu:** Cần tính: phí request cho PUT/GET/LIST và yêu cầu khôi phục; phí truy xuất theo GB ở Standard-IA, One Zone-IA và các lớp Glacier; phí xóa sớm; phí kích thước tối thiểu 128 KB cho đối tượng nhỏ ở lớp không thường xuyên/lưu trữ lạnh; phí chuyển lớp khi lifecycle transition; phí giám sát Intelligent-Tiering; phí truyền dữ liệu ra ngoài AWS và giữa các vùng. Sai lầm thường gặp: chỉ so sánh giá lưu trữ mỗi GB mà bỏ qua phí truy xuất, phí request và phí xóa sớm; hoặc bật Intelligent-Tiering cho hàng triệu đối tượng nhỏ hơn 128 KB.

**Trích dẫn nguồn:** Phí lưu trữ theo GB-tháng, khác nhau giữa các lớp: Standard cao nhất | Phí tính theo kích thước tối thiểu 128 KB cho đối tượng nhỏ ở các lớp không thường xuyên

### GD-026 — VPC Networking / Mục 1.6

**Hỏi:** Để thiết kế kết nối lai giữa on-premises và AWS bằng AWS Direct Connect chịu lỗi, AWS khuyến nghị tối thiểu bao nhiêu kết nối và đặt ở đâu; nếu chưa có đủ kết nối vật lý thì dùng phương án dự phòng nào và giao thức nào để tự động chuyển tuyến?

**Đáp án tham chiếu:** Khuyến nghị tối thiểu hai kết nối Direct Connect tại hai địa điểm khác nhau để tránh điểm lỗi đơn. Nếu chưa có hai kết nối vật lý, dùng Site-to-Site VPN làm đường dự phòng; AWS khuyến nghị mô hình kết hợp này cho hầu hết khách hàng. Dùng BGP để tự động chuyển tuyến khi một kết nối gặp sự cố.

**Trích dẫn nguồn:** Khuyến nghị tối thiểu hai kết nối Direct Connect tại hai địa điểm khác nhau để tránh điểm lỗi | Nếu chưa có hai kết nối vật lý, dùng Site-to-Site VPN làm đường dự phòng

### GD-031 — aws-saa-exam-guide / Mục 1.2

**Hỏi:** Một ứng dụng web cần chống DDoS và SQL injection, bảo vệ VPC bằng security group, route table, network ACL, NAT gateway, đồng thời phân tách public subnet và private subnet. Theo Mục 1.2, nên dùng những dịch vụ/thành phần bảo mật nào và bảo vệ kết nối vào/ra AWS Cloud bằng cách nào?

**Đáp án tham chiếu:** Dùng AWS Shield và AWS WAF để bảo vệ ứng dụng trước các vector như DDoS/SQL injection; thiết kế VPC với security group, route table, network ACL, NAT gateway; phân đoạn mạng bằng public subnet và private subnet; bảo vệ kết nối vào/ra bằng VPN hoặc AWS Direct Connect. Mục 1.2 cũng nêu Amazon Cognito, GuardDuty, Macie, IAM Identity Center, Secrets Manager cho trường hợp bảo mật phù hợp.

**Trích dẫn nguồn:** Kiểm soát cổng, giao thức và lưu lượng mạng trên AWS. | Tích hợp dịch vụ AWS để bảo vệ ứng dụng, ví dụ AWS Shield, AWS WAF, IAM Identity

### GD-036 — aws-saa-exam-guide / Mục 5.2.5

**Hỏi:** Theo Mục 5.2.5, những dịch vụ nào thuộc Nhóm Containers nằm trong phạm vi thi SAA-C03?

**Đáp án tham chiếu:** Nhóm Containers gồm Amazon ECS Anywhere, Amazon EKS Anywhere, Amazon EKS Distro, Amazon Elastic Container Registry (Amazon ECR), Amazon Elastic Container Service (Amazon ECS) và Amazon Elastic Kubernetes Service (Amazon EKS).

**Trích dẫn nguồn:** Amazon Elastic Container Registry (Amazon ECR) | Amazon Elastic Kubernetes Service (Amazon EKS)
