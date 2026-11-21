# Rà soát dev set truy xuất — Giai đoạn 2

Tệp dữ liệu: `evaluation/dev_set.jsonl`. Tài liệu này liệt kê từng câu để bạn đối chiếu nhãn `expected_section` với nội dung thật trong kho tri thức Giai đoạn 1.

## 1. Thông tin tệp

- 40 dòng JSONL, mã hóa UTF-8, mỗi dòng một đối tượng JSON.
- Trường bắt buộc theo Sổ tay: `id`, `query`, `expected_section`, `note`.
- Trường bổ sung: `expected_document` (khóa tài liệu đúng bằng `metadata["document"]` của chunk), `query_type` (phân loại câu), `expected_sections` (danh sách mục liên quan, có ở 12 câu).
- Lý do thêm `expected_document`: nhãn `Mục 1.x` lặp lại ở cả 5 tài liệu chuyên đề, nếu chỉ so `expected_section` thì không biết chunk thuộc tài liệu nào. Khi chấm, nên so cả `document` và `section`.
- Số trang trong tài liệu này là số trang PDF của bản chuẩn hóa đã nạp ở Giai đoạn 1, không phải số trang in trên chân trang.

## 2. Phân bố

| Loại câu | Số câu |
| :--- | ---: |
| Tra cứu | 10 |
| So sánh | 10 |
| Nhiều ràng buộc | 10 |
| Trộn thuật ngữ tiếng Anh | 10 |
| **Tổng** | **40** |

| Tài liệu | Số câu |
| :--- | ---: |
| S3 Storage Classes (`data/raw/S3_Storage_Classes.pdf`) | 8 |
| VPC Networking (`data/raw/VPC_Networking.pdf`) | 8 |
| RDS / Aurora (`data/raw/RDS_Aurora.pdf`) | 6 |
| IAM (`data/raw/IAM.pdf`) | 6 |
| EC2 / Tính toán (`data/raw/EC2_Tinh_toan.pdf`) | 7 |
| Exam Guide SAA-C03 (`data/raw/aws-saa-exam-guide.pdf`) | 5 |

## 3. Danh sách câu hỏi để rà soát

Cột **Mục** là nhãn chính dùng để chấm Recall@5/MRR/nDCG@10. Cột **Mục liên quan** chỉ ra các mục bổ sung chứa cùng câu trả lời; khi chấm có thể chấp nhận hit ở bất kỳ mục nào trong danh sách.

### 3.1. Tra cứu (10 câu)

| ID | Câu hỏi | Tài liệu | Mục | Trang | Mục liên quan | Căn cứ trong mục |
| :--- | :--- | :--- | :--- | ---: | :--- | :--- |
| DS-001 | Lớp S3 Standard-IA bắt buộc lưu dữ liệu tối thiểu bao nhiêu ngày, và khi đọc dữ liệu có phải trả thêm phí truy xuất không? | S3 Storage Classes | Mục 1.4 | 3 | — | Mục 1.4 nêu thời gian lưu tối thiểu 30 ngày (xóa hoặc ghi đè trước hạn vẫn bị tính đủ 30 ngày) và có phí truy xuất theo GB; đối tượng dưới 128 KB được tính như 128 KB. |
| DS-002 | S3 Glacier Deep Archive có những mức truy xuất nào và thời gian khôi phục tương ứng của từng mức? | S3 Storage Classes | Mục 1.8 | 6 | — | Mục 1.8 nêu Standard khoảng 12 giờ và Bulk khoảng 48 giờ, không có mức Expedited; thời gian lưu tối thiểu 180 ngày. |
| DS-009 | Một subnet trong VPC được coi là public khi hội đủ những điều kiện nào? | VPC Networking | Mục 1.2 | 1 | — | Mục 1.2 nêu ba điều kiện: route 0.0.0.0/0 (hoặc ::/0) trỏ tới IGW hoặc egress-only IGW; tài nguyên có IP public/Elastic IP hoặc địa chỉ IPv6; security group và NACL cho phép lưu lượng. Gắn IGW không tự động làm subnet public. |
| DS-010 | VPC peering có định tuyến bắc cầu giữa ba VPC không, và điều kiện bắt buộc về dải CIDR khi peering là gì? | VPC Networking | Mục 1.5 | 4 | — | Mục 1.5 nêu peering không hỗ trợ định tuyến bắc cầu (A–B và B–C không cho A–C) và yêu cầu dải CIDR không chồng lấn giữa hai VPC. |
| DS-017 | RDS automated backup giữ tối đa bao nhiêu ngày, và point-in-time recovery cho phép khôi phục tới thời điểm gần nhất cách hiện tại bao lâu? | RDS / Aurora | Mục 1.3 | 3 | — | Mục 1.3 nêu thời gian lưu giữ 0–35 ngày (đặt 0 sẽ tắt sao lưu tự động); PITR khôi phục tới thời điểm gần nhất, thường trong vòng 5 phút. |
| DS-018 | Aurora Serverless v2 co giãn theo đơn vị nào, mỗi ACU tương đương bao nhiêu bộ nhớ và phạm vi cấu hình mỗi instance là bao nhiêu? | RDS / Aurora | Mục 1.5 | 4 | — | Mục 1.5 nêu đơn vị ACU (Aurora Capacity Unit), mỗi ACU xấp xỉ 2 GiB; phạm vi 0,5 ACU đến 128 ACU mỗi instance, co giãn theo bước 0,5 ACU và tính phí ACU-giây. |
| DS-023 | Một IAM role gồm hai phần chính nào, và trust policy kiểm soát điều gì? | IAM | Mục 1.3 | 2 | — | Mục 1.3 nêu hai phần là trust policy (ai được assume role) và permission policy (role được làm gì); trust policy không cấp quyền truy cập tài nguyên. |
| DS-024 | Presigned URL của S3 có thời hạn tối đa bao nhiêu ngày khi tạo bằng thông tin xác thực dài hạn, và URL mất hiệu lực khi nào? | IAM | Mục 1.9 | 7 | — | Mục 1.9 nêu thời hạn tối đa 7 ngày với thông tin xác thực dài hạn, ngắn hơn với thông tin tạm thời; URL kế thừa quyền của người tạo nên mất hiệu lực nếu người tạo mất quyền. |
| DS-029 | Khi stop một EC2 instance, thành phần lưu trữ nào vẫn tồn tại và vẫn bị tính phí, còn địa chỉ IP public thì sao? | EC2 / Tính toán | Mục 1.1 | 1 | — | Mục 1.1 nêu stop không tính phí compute, EBS volume vẫn tồn tại và vẫn tính phí, IP public thường bị thu hồi; reboot giữ nguyên IP public và EBS. |
| DS-030 | gp3 có baseline IOPS và throughput bao nhiêu, và có thể tăng tối đa tới mức nào độc lập với dung lượng? | EC2 / Tính toán | Mục 1.4 | 3 | — | Mục 1.4 nêu gp3 baseline 3.000 IOPS và 125 MiB/s, tăng tới 16.000 IOPS và 1.000 MiB/s độc lập với dung lượng; gp2 gắn IOPS với dung lượng. |

### 3.2. So sánh (10 câu)

| ID | Câu hỏi | Tài liệu | Mục | Trang | Mục liên quan | Căn cứ trong mục |
| :--- | :--- | :--- | :--- | ---: | :--- | :--- |
| DS-003 | So sánh ba mức truy xuất Expedited, Standard và Bulk của S3 Glacier Flexible Retrieval về thời gian hoàn thành. | S3 Storage Classes | Mục 1.7 | 5 | — | Mục 1.7 nêu Expedited khoảng 1–5 phút, Standard khoảng 3–5 giờ, Bulk khoảng 5–12 giờ; thời gian lưu tối thiểu 90 ngày. |
| DS-004 | Bên trong S3 Intelligent-Tiering, các tầng truy cập được kích hoạt sau bao lâu không truy cập và khác nhau thế nào về thời gian truy xuất? | S3 Storage Classes | Mục 1.3 | 2 | — | Mục 1.3 nêu Infrequent Access sau 30 ngày; Archive Instant Access sau 90 ngày (vẫn mili giây); Archive Access tùy chọn từ 90 ngày (phút đến giờ); Deep Archive Access tùy chọn từ 180 ngày (giờ). |
| DS-011 | So sánh NAT Gateway và NAT Instance về quản lý vận hành, vá lỗi và chi phí. | VPC Networking | Mục 1.3 | 2 | — | Mục 1.3 nêu NAT Gateway do AWS quản lý, không cần vá, không cần security group, sẵn sàng cao trong AZ; NAT Instance là EC2 tự quản, rẻ hơn với lưu lượng nhỏ nhưng phải tự vá và tự đảm bảo tính sẵn sàng. |
| DS-012 | Security Group và Network ACL khác nhau ở cấp hoạt động và tính stateful như thế nào? | VPC Networking | Mục 1.4 | 3 | — | Mục 1.4 nêu Security Group ở cấp ENI/instance, stateful, chỉ có rule allow và tham chiếu được security group khác; Network ACL ở cấp subnet, stateless, có cả allow và deny, phải mở cả hai chiều. |
| DS-019 | So sánh Multi-AZ và Read Replica của RDS về mục tiêu thiết kế, cơ chế đồng bộ và khả năng phục vụ đọc. | RDS / Aurora | Mục 1.2 | 2 | — | Mục 1.2 nêu Multi-AZ vì mục tiêu sẵn sàng cao, standby đồng bộ, failover tự động, không phục vụ đọc trong mô hình cổ điển; Read Replica vì mục tiêu mở rộng đọc, nhân bản bất đồng bộ, hỗ trợ cross-region, không tự failover. |
| DS-025 | So sánh permission boundary và Service Control Policy (SCP) về phạm vi áp dụng và khả năng cấp quyền. | IAM | Mục 1.7 | 6 | — | Mục 1.7 nêu permission boundary gắn vào user/role, giới hạn quyền tối đa của identity; SCP gắn ở cấp Organizations (account/OU), giới hạn quyền tối đa của tài khoản và không áp dụng cho management account; cả hai chỉ giới hạn, không cấp quyền. |
| DS-031 | So sánh Reserved Instance và Savings Plans về tính linh hoạt và phạm vi áp dụng. | EC2 / Tính toán | Mục 1.3 | 2 | — | Mục 1.3 nêu Reserved Instance cam kết 1 hoặc 3 năm cho một cấu hình, Standard giảm sâu nhưng ít linh hoạt, Convertible đổi được họ instance; Savings Plans cam kết mức chi tiêu theo giờ, Compute Savings Plans áp dụng cho EC2, Lambda và Fargate. |
| DS-032 | So sánh cluster, spread và partition placement group về mục tiêu tối ưu và giới hạn số instance/phân vùng. | EC2 / Tính toán | Mục 1.6 | 5 | — | Mục 1.6 nêu cluster đặt instance gần nhau trong cùng AZ, độ trễ thấp nhưng rủi ro cùng điểm lỗi; spread đặt trên máy chủ vật lý khác nhau, tối đa 7 instance mỗi AZ; partition tối đa 7 phân vùng mỗi AZ, phù hợp HDFS, Cassandra, Kafka. |
| DS-036 | So sánh mục tiêu của kiến trúc loosely coupled (task statement 2.1) và kiến trúc highly available/fault-tolerant (task statement 2.2) theo Exam Guide. | Exam Guide SAA-C03 | Mục 2.1 | 4 | Mục 2.2 | Mục 2.1 nhấn mạnh tách rời thành phần để mở rộng độc lập và chịu thay đổi cục bộ, với hàng đợi/nhắn tin, microservices, serverless; Mục 2.2 nhấn mạnh loại bỏ điểm lỗi đơn, chiến lược DR theo RPO/RTO, tự động hóa và độ bền dữ liệu. |
| DS-037 | Task statement 1.1 và 1.2 trong Domain 1 khác nhau ở phạm vi bảo vệ: cái nào tập trung vào danh tính và quyền, cái nào vào workload và mạng? | Exam Guide SAA-C03 | Mục 1.1 | 2 | Mục 1.2 | Mục 1.1 tập trung vào truy cập an toàn tài nguyên: IAM, IAM Identity Center, MFA, STS, cross-account, SCP, Control Tower; Mục 1.2 tập trung vào bảo vệ workload và ứng dụng: credentials, cổng/giao thức, phân đoạn VPC, WAF/Shield/Secrets Manager, VPN và Direct Connect. |

### 3.3. Nhiều ràng buộc (10 câu)

| ID | Câu hỏi | Tài liệu | Mục | Trang | Mục liên quan | Căn cứ trong mục |
| :--- | :--- | :--- | :--- | ---: | :--- | :--- |
| DS-005 | Công ty phải giữ log kiểm toán 7 năm, gần như không bao giờ đọc lại, nhưng khi bị kiểm toán có thể chờ tối đa hai ngày để lấy dữ liệu. Nên chọn lớp S3 nào để chi phí thấp nhất và cần lưu ý thời gian lưu tối thiểu bao lâu? | S3 Storage Classes | Mục 1.13 | 10 | Mục 1.8 | Mục 1.13 chỉ lớp Glacier Deep Archive cho dữ liệu lưu trữ dài hạn với chi phí thấp nhất; Mục 1.8 xác nhận Bulk khoảng 48 giờ và thời gian lưu tối thiểu 180 ngày. |
| DS-006 | Một nhóm dữ liệu mới cần đọc thường xuyên trong 30 ngày đầu, sau đó chuyển sang lớp ít truy cập nhưng vẫn phải truy xuất tức thời; công ty muốn tự động hóa bằng lifecycle rule. Mốc chuyển tối thiểu sang Standard-IA là bao nhiêu ngày và lớp đích có đặc điểm truy xuất gì? | S3 Storage Classes | Mục 1.10 | 7 | Mục 1.4 | Mục 1.10 nêu chuyển sang Standard-IA hoặc One Zone-IA tối thiểu 30 ngày kể từ khi tạo đối tượng; Mục 1.4 nêu Standard-IA truy xuất trong mili giây, có phí truy xuất và thời gian lưu tối thiểu 30 ngày. |
| DS-013 | Một công ty có khoảng 40 VPC trong nhiều tài khoản, cần nối về data center qua Direct Connect và phân đoạn luồng giữa production với dev. Kiến trúc kết nối tập trung nào phù hợp và dùng gì để kiểm soát luồng giữa các phân đoạn? | VPC Networking | Mục 1.12 | 10 | Mục 1.5, Mục 1.7 | Mục 1.12 nêu hub-and-spoke qua Transit Gateway, kết nối on-premises qua Direct Connect vào Transit Gateway, kiểm soát luồng bằng route table của Transit Gateway và security group, dùng VPC IPAM tránh chồng lấn CIDR; Mục 1.5 nêu Transit Gateway hỗ trợ tới 5.000 attachment; Mục 1.7 nêu Direct Connect Gateway quảng bá tới nhiều VPC ở nhiều Region. |
| DS-014 | Ứng dụng trong private subnet cần gọi S3 và DynamoDB nhưng không được đi qua NAT Gateway, đồng thời phải giới hạn được tài nguyên nào được phép truy cập. Giải pháp nào và cần cấu hình mấy lớp kiểm soát? | VPC Networking | Mục 1.8 | 6 | — | Mục 1.8 nêu dùng gateway endpoint cho S3 và DynamoDB, gắn vào route table; kết hợp endpoint policy, security group và IAM để kiểm soát hai lớp quyền truy cập. |
| DS-020 | Ứng dụng production phải chịu được sự cố mất một AZ, đồng thời có lượng báo cáo đọc rất lớn không được ảnh hưởng giao dịch. Cần cấu hình RDS như thế nào? | RDS / Aurora | Mục 1.13 | 11 | Mục 1.2 | Mục 1.13 nêu production cần chịu lỗi AZ thì bật Multi-AZ và giữ nguyên endpoint DNS khi failover; báo cáo đọc nhiều thì thêm read replica hoặc Aurora Replica; Mục 1.2 xác nhận kết hợp Multi-AZ cho instance chính và read replica cho tải đọc. |
| DS-021 | Hệ thống cần RPO khoảng 1 giây và RTO dưới 1 phút khi mất toàn bộ Region, nhưng Region phụ không được phép ghi trực tiếp. Dịch vụ nào đáp ứng và cơ chế hoạt động ra sao? | RDS / Aurora | Mục 1.6 | 5 | — | Mục 1.6 nêu Aurora Global Database nhân bản từ Region chính sang tối đa 5 Region phụ với RPO khoảng 1 giây và RTO dưới 1 phút; Region phụ chỉ đọc, muốn ghi phải promote. |
| DS-026 | Công ty có nhiều tài khoản AWS, nhân viên đăng nhập một lần bằng Active Directory và nhận quyền theo nhóm trên từng tài khoản. Nên dùng IAM user hay IAM Identity Center, và vì sao? | IAM | Mục 1.5 | 4 | — | Mục 1.5 nêu IAM Identity Center đăng nhập một lần qua nhà cung cấp danh tính doanh nghiệp (SAML 2.0 và SCIM), gán permission set theo nhóm trên từng tài khoản, thu hồi quyền tập trung và không phải tạo IAM user riêng cho từng tài khoản. |
| DS-033 | Một hệ thống chạy ổn định 24/7 trong nhiều tháng, cần giữ quyền kiểm soát hệ điều hành, thỉnh thoảng có đỉnh tải ngắn. Nên kết hợp những tùy chọn mua EC2 nào để tối ưu chi phí? | EC2 / Tính toán | Mục 1.3 | 2 | Mục 1.13 | Mục 1.3 nêu tải ổn định 24/7 dùng Reserved Instance hoặc Savings Plans; đỉnh tải ngắn thì kết hợp On-Demand cho nền tảng và Spot cho phần mở rộng; Mục 1.13 lặp lại cùng khuyến nghị. |
| DS-034 | Cụm HPC cần độ trễ mạng giữa các node cực thấp, khối lượng tính toán lớn và có thể chia thành nhiều job. Nên chọn placement group và họ instance nào? | EC2 / Tính toán | Mục 1.13 | 10 | Mục 1.6 | Mục 1.13 nêu HPC cần độ trễ mạng cực thấp thì dùng cluster placement group với instance compute/accelerated; Mục 1.6 xác nhận cluster đặt instance gần nhau trong cùng AZ, phù hợp HPC và tính toán song song. |
| DS-038 | Một ứng dụng chạy container, tải thay đổi mạnh theo giờ, môi trường non-production cần tiết kiệm chi phí nhưng vẫn phải đảm bảo mức sẵn sàng thấp hơn production. Theo task statement 4.2, cần cân nhắc những nhóm yếu tố nào khi thiết kế giải pháp tính toán tối ưu chi phí? | Exam Guide SAA-C03 | Mục 4.2 | 10 | — | Mục 4.2 nêu các nhóm yếu tố: tùy chọn mua (On-Demand, Reserved, Savings Plans, Spot), họ và kích thước instance, chiến lược mở rộng, mô hình tính toán container/serverless, mức sẵn sàng theo lớp workload production/non-production, công cụ Cost Explorer và Budgets. |

### 3.4. Trộn thuật ngữ tiếng Anh (10 câu)

| ID | Câu hỏi | Tài liệu | Mục | Trang | Mục liên quan | Căn cứ trong mục |
| :--- | :--- | :--- | :--- | ---: | :--- | :--- |
| DS-007 | Khi nào nên chọn S3 Express One Zone thay vì S3 Standard cho workload nhạy cảm latency, và rủi ro chính của lớp này là gì? | S3 Storage Classes | Mục 1.9 | 7 | Mục 1.12 | Mục 1.9 nêu directory bucket trong một AZ, độ trễ một chữ số mili giây, phù hợp huấn luyện/suy luận học máy, phân tích lớn và dữ liệu tạm; không dư thừa xuyên AZ nên không dùng làm nơi lưu duy nhất dữ liệu không thể tái tạo; giá lưu trữ cao hơn Standard. |
| DS-008 | Vì sao bật S3 Intelligent-Tiering cho hàng triệu object nhỏ hơn 128 KB có thể không tiết kiệm chi phí, và khoản phí nào quyết định điều đó? | S3 Storage Classes | Mục 1.11 | 8 | Mục 1.3 | Mục 1.11 nêu phí giám sát và tự động hóa của Intelligent-Tiering có thể vượt khoản tiết kiệm với object nhỏ, cộng phí tính theo kích thước tối thiểu 128 KB ở lớp không thường xuyên; Mục 1.3 xác nhận chi phí đổi lại là phí giám sát và tự động hóa. |
| DS-015 | Với multi-account networking, khi nào nên dùng AWS Transit Gateway thay vì VPC peering, và Transit Gateway khác peering ở khả năng mở rộng ra sao? | VPC Networking | Mục 1.5 | 4 | Mục 1.12 | Mục 1.5 nêu peering phù hợp vài VPC, không transitive, không hỗ trợ edge-to-edge; Transit Gateway theo mô hình hub-and-spoke, hỗ trợ tới 5.000 attachment, phù hợp hàng chục VPC trở lên hoặc kết nối on-premises dùng chung. |
| DS-016 | Route 53 routing policy nào phù hợp cho blue/green deployment và active-passive failover? | VPC Networking | Mục 1.9 | 7 | — | Mục 1.9 nêu Weighted cho blue/green hoặc canary; Failover cho active-passive và cần health check; Latency định tuyến tới Region có độ trễ thấp nhất; Multivalue answer không thay thế load balancer. |
| DS-022 | RDS Proxy giúp gì khi failover Multi-AZ và khi Lambda mở nhiều short-lived connections? | RDS / Aurora | Mục 1.7 | 6 | — | Mục 1.7 nêu RDS Proxy gom và tái sử dụng kết nối, giảm thời gian gián đoạn khi failover, phù hợp Lambda mở nhiều kết nối ngắn, hỗ trợ IAM authentication; proxy không phải load balancer truy vấn. |
| DS-027 | EC2 instance lấy temporary credentials qua dịch vụ nào, và max session duration của IAM role mặc định là bao lâu, tối đa bao lâu? | IAM | Mục 1.3 | 2 | — | Mục 1.3 nêu instance profile và IMDS cấp temporary credentials; thời hạn phiên từ 15 phút đến 12 giờ tùy max session duration, mặc định 1 giờ; role chaining thường giới hạn 1 giờ. |
| DS-028 | KMS key policy có thể chặn một IAM policy đang cho phép truy cập khóa hay không, và vì sao? | IAM | Mục 1.10 | 8 | — | Mục 1.10 nêu key policy là resource policy chính; nếu key policy không cho phép thì IAM policy một mình không đủ, trừ khi key policy ủy quyền cho IAM; key policy mặc định cho tài khoản root quản lý khóa. |
| DS-035 | Burstable performance của họ T hoạt động thế nào với CPU credit, và chế độ unlimited khác standard ở điểm nào? | EC2 / Tính toán | Mục 1.2 | 1 | — | Mục 1.2 nêu họ T có CPU baseline và CPU credit; vượt baseline thì tiêu thụ credit tích lũy; chế độ unlimited cho vượt baseline liên tục với phụ phí, chế độ standard giới hạn để tránh chi phí ngoài dự kiến. |
| DS-039 | Theo Exam Guide, nhóm Networking and Content Delivery trong phạm vi thi gồm những dịch vụ nào? AWS Global Accelerator và AWS Transit Gateway có nằm trong danh sách không? | Exam Guide SAA-C03 | Mục 5.2.13 | 19 | — | Mục 5.2.13 liệt kê AWS Client VPN, CloudFront, Direct Connect, Elastic Load Balancing, Global Accelerator, PrivateLink, Route 53, Site-to-Site VPN, Transit Gateway và Amazon VPC; cả Global Accelerator và Transit Gateway đều có trong danh sách. |
| DS-040 | Amazon Lightsail có nằm trong scope thi SAA-C03 không, và nó thuộc nhóm Compute in-scope hay out-of-scope? Kể tên các dịch vụ Compute in-scope. | Exam Guide SAA-C03 | Mục 5.3.5 | 23 | Mục 5.2.4 | Mục 5.3.5 xếp Amazon Lightsail vào nhóm Compute ngoài phạm vi thi; Mục 5.2.4 liệt kê Compute in-scope gồm AWS Batch, Amazon EC2, EC2 Auto Scaling, Elastic Beanstalk, AWS Outposts, Serverless Application Repository, VMware Cloud on AWS và AWS Wavelength. |

## 4. Cách dùng nhãn khi chấm truy xuất

Một chunk được tính là liên quan khi `metadata["document"]` bằng `expected_document` và `expected_section` nằm trong `metadata["sections"]` (hoặc bằng `metadata["section"]`). Vì chunker gộp nhiều mục vào một chunk cha và cắt chunk con có overlap, một chunk có thể bắt đầu ở mục trước và chứa nội dung của mục sau; khi đó `metadata["section"]` chỉ là nhãn của đơn vị đầu tiên, còn `metadata["sections"]` liệt kê đủ các mục xuất hiện trong chunk. Dùng `sections` sẽ tránh đánh trượt oan, nhưng vì chunk cha trong 5 tài liệu chuyên đề thường phủ 2–4 mục liền kề, cách chấm này có phần rộng tay ở các mục giáp ranh. Nếu cần chấm chặt, yêu cầu thêm `metadata["section"]` bằng đúng `expected_section`; khi đó nên báo cáo cả hai cách để thấy độ nhạy của kết quả.

Kho tri thức còn có ngân hàng 390 câu (`data/raw/aws-saa-question-bank.pdf`). Một số câu trong dev set có thể được giải thích tương đương trong phần giải thích của ngân hàng. Nếu muốn chấm rộng hơn, có thể ghi nhận thêm hit từ ngân hàng câu hỏi như trường hợp chấp nhận được, nhưng phải nhất quán cho cả 40 câu và ghi rõ quy ước trong báo cáo Giai đoạn 2.

## 5. Checklist rà soát

- [ ] Đọc từng câu và xác nhận câu trả lời thực sự nằm trong mục đã gán.
- [ ] Kiểm tra 12 câu có `expected_sections`: các mục phụ có thật sự cần cho câu trả lời không.
- [ ] Nếu sửa `expected_section`, cập nhật luôn `expected_sections` (nếu có) và ghi lại lý do.
- [ ] Không đưa câu từ bộ đề kiểm thử ngoài vào dev set; dev set chỉ dùng để tinh chỉnh tham số.
- [ ] Chốt 40 câu rồi giữ nguyên; mọi thay đổi tham số truy xuất chỉ đo lại trên tệp này.

## 6. Ghi chú về tên tệp

Sổ tay Giai đoạn 2 chỉ định `evaluation/dev_set.jsonl`, nên tệp được đặt đúng vị trí đó. Trong repo còn có `evaluation/build_dev_set.py` sinh `evaluation/data/dev_set.jsonl` từ 6 đề DOCX; tệp đó là dev set dạng đề trắc nghiệm cho Giai đoạn 3–4, khác mục đích với dev set truy xuất 40 câu này. Hai tệp không ghi đè lẫn nhau.
