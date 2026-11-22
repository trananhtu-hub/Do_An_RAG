# Phiếu chấm thủ công — câu trả lời hội thoại

- Nguồn: `conversation_bench_stream_20261123-042635.json` (stream, 20261123-042635)
- Số lượt cần chấm: 24
- Thang chấm: ĐẠT (trả lời đúng, đủ ý quan trọng, trích dẫn hợp lệ) / MỘT PHẦN (đúng hướng nhưng thiếu ý hoặc trích dẫn chưa chuẩn) / SAI (sai nội dung, bịa, hoặc từ chối sai).
- Chấm độc lập trước khi xem phần "Đáp án máy chấm" ở cuối tệp.

## Phần chấm

### 1. KB-01 · lượt 1

**Hỏi:** Amazon S3 là gì?

**Đáp:** Theo ngữ cảnh tài liệu, Amazon S3 là dịch vụ lưu trữ đối tượng: S3 cung cấp nhiều lớp lưu trữ (storage class) trên cùng một không gian tên đối tượng, mỗi lớp được thiết kế cho một mẫu truy cập và một mức chi phí khác nhau, và lớp được gán khi tải đối tượng lên hoặc khi chuyển lớp bằng quy tắc vòng đời [S3 Storage Classes – Mục 1.1]. Nếu không chỉ định lớp, S3 dùng lớp Standard [S3 Storage Classes – Mục 1.1]. Mọi lớp đều truy cập qua API S3; có thể chuyển lớp mà không đổi khóa đối tượng và không cần thay đổi ứng dụng đọc dữ liệu [S3 Storage Classes – Mục 1.1]. S3 cũng là dịch vụ lưu trữ có mô hình quyền kết hợp identity policy, bucket policy, ACL (đang lỗi thời) và presigned URL [IAM – Mục 1.9].

**Trích dẫn:** S3 Storage Classes – Mục 1.1 — Amazon S3 cung cấp nhiều lớp lưu trữ (storage class) trên cùng một không gian tên đối tượn; S3 Storage Classes – Mục 1.1 — Nếu không chỉ định, S3 dùng lớp Standard.; S3 Storage Classes – Mục 1.1 — Mọi lớp đều truy cập qua API S3; có thể chuyển lớp mà không đổi khóa đối tượng và không cầ; IAM – Mục 1.9 — S3 là dịch vụ lưu trữ có mô hình quyền kết hợp identity policy, bucket policy, ACL (đang l

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 2. KB-01 · lượt 2

**Hỏi:** So với EBS thì khác ở đâu?

**Đáp:** **Tóm tắt:** EBS là ổ đĩa khối gắn với một instance trong cùng một Availability Zone, còn S3 là dịch vụ lưu trữ đối tượng với nhiều lớp lưu trữ trên cùng không gian tên đối tượng và được truy cập qua API [EC2 Tinh toan – Mục 1.4] [S3 Storage Classes – Mục 1.1].

| Tiêu chí | Amazon EBS | Amazon S3 |
| :--- | :--- | :--- |
| Kiểu lưu trữ | Ổ đĩa khối (block) gắn với instance [EC2 Tinh toan – Mục 1.4]; tài liệu exam guide liệt kê object, file, block là các kiểu lưu trữ cần phân biệt [aws-saa-exam-guide – Mục 3.1] | Nhiều lớp lưu trữ (storage class) trên cùng một không gian tên đối tượng [S3 Storage Classes – Mục 1.1] |
| Phạm vi Availability Zone | Volume gắn với một AZ; chỉ gắn được cho instance trong cùng AZ [EC2 Tinh toan – Mục 1.4] | Các lớp đa AZ lưu dữ liệu trên tối thiểu ba Availability Zone [S3 Storage Classes – Mục 1.1]; riêng các lớp một AZ chỉ lưu trong một AZ và dữ liệu mất nếu AZ đó bị phá hủy [S3 Storage Classes – Mục 1.1] |
| Độ bền | Không có trong tài liệu (chỉ nêu dữ liệu tồn tại độc lập với vòng đời instance) [EC2 Tinh toan – Mục 1.4] | Các lớp đa AZ được thiết kế cho độ bền 99,999999999% (11 số 9) [S3 Storage Classes – Mục 1.1] |
| Cách truy cập | Gắn trực tiếp như ổ đĩa của instance; EBS có độ trễ thấp vừa phải [EC2 Tinh toan – Mục 1.5] | Mọi lớp đều truy cập qua API S3; có thể chuyển lớp mà không đổi khóa đối tượng và không cần thay đổi ứng dụng đọc dữ liệu [S3 Storage Classes – Mục 1.1] |
| Sao lưu / bảo vệ dữ liệu | Snapshot là bản sao lưu tăng dần, lưu trong S3 do AWS quản lý [EC2 Tinh toan – Mục 1.4] | Hỗ trợ đầy đủ tính năng S3: phiên bản đối tượng, nhân bản, vòng đời, Object Lock, sao chép nhiều vùng [S3 Storage Classes – Mục 1.2] |
| Thay đổi cấu hình khi đang chạy | Có thể thay đổi loại và kích thước volume khi đang chạy (elastic volumes) mà không cần dừng instance [EC2 Tinh toan – Mục 1.4] | Không có trong tài liệu |
| Chi phí | Không có trong tài liệu (ngữ cảnh không nêu giá volume EBS) | Mỗi lớp có mức chi phí khác nhau; cần tính cả phí truy xuất, phí request, phí xóa sớm và phí chuyển lớp, không chỉ giá lưu trữ mỗi GB [S3 Storage Classes – Mục 1.1] |

**Khi nào chọn EBS:** Khi cần ổ đĩa khối gắn với instance trong cùng AZ, dữ liệu tồn tại độc lập với vòng đời instance và có thể sao lưu bằng snapshot lên S3 [EC2 Tinh toan – Mục 1.4]; EBS phù hợp làm nơi đặt dữ liệu chính với đặc tính bền vững, snapshot được, gắn lại được, độ trễ thấp vừa phải [EC2 Tinh toan – Mục 1.5].

**Khi nào chọn S3:** Khi cần lưu trữ đối tượng và chọn lớp theo tần suất truy cập, thời gian truy xuất chấp nhận được, thời gian lưu dự kiến, khả năng tái tạo dữ liệu và chi phí đầy đủ [S3 Storage Classes – Mục 1.1]; dữ liệu không thể tái tạo phải dùng lớp đa AZ [S3 Storage Classes – Mục 1.1].

**Trích dẫn:** EC2 Tinh toan – Mục 1.4 — Amazon Elastic Block Store (EBS) cung cấp ổ đĩa khối gắn với instance trong cùng Availabil; EC2 Tinh toan – Mục 1.4 — EBS gắn với một AZ; volume chỉ gắn được cho instance trong cùng AZ.; EC2 Tinh toan – Mục 1.4 — Dữ liệu EBS tồn tại độc lập với vòng đời instance và có thể sao lưu bằng snapshot lên S3.; EC2 Tinh toan – Mục 1.4 — Snapshot là bản sao lưu tăng dần, lưu trong S3 do AWS quản lý; lần đầu đầy đủ, các lần sau; EC2 Tinh toan – Mục 1.4 — Có thể thay đổi loại và kích thước volume khi đang chạy (elastic volumes) mà không cần dừn; EC2 Tinh toan – Mục 1.5 — EBS: bền vững, snapshot được, gắn lại được, độ trễ thấp vừa phải.; S3 Storage Classes – Mục 1.1 — Amazon S3 cung cấp nhiều lớp lưu trữ (storage class) trên cùng một không gian tên đối tượn; S3 Storage Classes – Mục 1.1 — Các lớp đa Availability Zone (Standard, Intelligent-Tiering, Standard-IA, Glacier Instant ; S3 Storage Classes – Mục 1.1 — Các lớp một Availability Zone (One Zone-IA, Express One Zone) chỉ lưu dữ liệu trong một AZ; S3 Storage Classes – Mục 1.1 — Mọi lớp đều truy cập qua API S3; có thể chuyển lớp mà không đổi khóa đối tượng và không cầ; S3 Storage Classes – Mục 1.1 — Chi phí đầy đủ: không chỉ giá lưu trữ mỗi GB mà còn phí truy xuất, phí request, phí xóa sớ; S3 Storage Classes – Mục 1.2 — Hỗ trợ đầy đủ tính năng S3: phiên bản đối tượng, nhân bản, vòng đời, Object Lock, sao chép; aws-saa-exam-guide – Mục 3.1 — Các kiểu lưu trữ kèm đặc điểm, ví dụ object, file, block.

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 3. KB-02 · lượt 1

**Hỏi:** RDS sao lưu tự động giữ bao lâu?

**Đáp:** Sao lưu tự động (automated backup) của RDS có thời gian lưu giữ từ 0 đến 35 ngày; đặt 0 sẽ tắt sao lưu tự động [RDS Aurora – Mục 1.3]. Trong khoảng lưu giữ đó, phục hồi theo thời điểm (point-in-time recovery) có thể đưa dữ liệu về bất kỳ giây nào, thường trong vòng 5 phút kể từ thời điểm gần nhất [RDS Aurora – Mục 1.3].

**Trích dẫn:** RDS Aurora – Mục 1.3 — Thời gian lưu giữ 0-35 ngày; đặt 0 sẽ tắt sao lưu tự động.; RDS Aurora – Mục 1.3 — Phục hồi theo thời điểm (point-in-time recovery) tới bất kỳ giây nào trong khoảng lưu giữ,

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 4. KB-02 · lượt 2

**Hỏi:** Có khôi phục được về một giờ trước không?

**Đáp:** Có. Sao lưu tự động của RDS hỗ trợ phục hồi theo thời điểm (point-in-time recovery) tới bất kỳ giây nào trong khoảng lưu giữ, thường trong vòng 5 phút kể từ thời điểm gần nhất [RDS Aurora – Mục 1.3]. Vì thời gian lưu giữ sao lưu tự động là 0-35 ngày [RDS Aurora – Mục 1.3], nên thời điểm một giờ trước nằm trong khoảng lưu giữ (miễn là sao lưu tự động đang được bật, tức thời gian lưu giữ khác 0) và có thể khôi phục về đó. Lưu ý: mọi bản khôi phục đều tạo ra một DB instance mới [RDS Aurora – Mục 1.3], nên cần cập nhật DNS hoặc endpoint để chuyển hướng ứng dụng [RDS Aurora – Mục 1.3].

**Trích dẫn:** RDS Aurora – Mục 1.3 — Phục hồi theo thời điểm (point-in-time recovery) tới bất kỳ giây nào trong khoảng lưu giữ,; RDS Aurora – Mục 1.3 — Thời gian lưu giữ 0-35 ngày; đặt 0 sẽ tắt sao lưu tự động.; RDS Aurora – Mục 1.3 — Mọi bản khôi phục đều tạo ra một DB instance mới.; RDS Aurora – Mục 1.3 — Khôi phục luôn tạo tài nguyên mới, không ghi đè instance hiện có; cần thay đổi DNS hoặc en

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 5. KB-03 · lượt 1

**Hỏi:** IAM role là gì?

**Đáp:** IAM role là một danh tính tạm thời được giả định bởi người dùng, ứng dụng hoặc dịch vụ; role không có mật khẩu hay access key cố định [IAM – Mục 1.1]. Đây là cách chuẩn để cấp quyền tạm thời cho ứng dụng, dịch vụ AWS và người dùng từ tài khoản khác mà không cần lưu thông tin xác thực dài hạn [IAM – Mục 1.3]. Mỗi role có hai phần: trust policy (ai được giả định role) và permission policy (role được làm gì) [IAM – Mục 1.3]. Lưu ý trust policy không cấp quyền truy cập tài nguyên; nó chỉ xác định ai có thể assume role [IAM – Mục 1.3].

**Trích dẫn:** IAM – Mục 1.1 — Vai trò (role): danh tính tạm thời được giả định bởi người dùng, ứng dụng hoặc dịch vụ; kh; IAM – Mục 1.3 — IAM role là cách chuẩn để cấp quyền tạm thời cho ứng dụng, dịch vụ AWS và người dùng từ tà; IAM – Mục 1.3 — Mỗi role có hai phần: trust policy (ai được giả định role) và permission policy (role được; IAM – Mục 1.3 — Trust policy không cấp quyền truy cập tài nguyên; nó chỉ xác định ai có thể assume role.

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 6. KB-03 · lượt 2

**Hỏi:** Trust policy của nó dùng để làm gì?

**Đáp:** Trust policy của IAM role là phần xác định **ai được phép giả định (assume) role** — tức kiểm soát danh tính nào có thể nhận role đó [IAM – Mục 1.3]. Trust policy **không cấp quyền truy cập tài nguyên**; nó chỉ xác định ai có thể assume role, còn việc role được làm gì do permission policy quyết định [IAM – Mục 1.3]. Cùng nguyên tắc đó, tài liệu nhấn mạnh trong phần bẫy thường gặp: trust policy chỉ kiểm soát ai được assume role, không kiểm soát role được làm gì [IAM – Mục 1.12].

**Trích dẫn:** IAM – Mục 1.3 — Mỗi role có hai phần: trust policy (ai được giả định role) và permission policy (role được; IAM – Mục 1.3 — Trust policy không cấp quyền truy cập tài nguyên; nó chỉ xác định ai có thể assume role.; IAM – Mục 1.12 — Trust policy chỉ kiểm soát ai được assume role, không kiểm soát role được làm gì.

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 7. KB-04 · lượt 1

**Hỏi:** Multi-AZ và Read Replica khác nhau thế nào?

**Đáp:** **Tóm tắt:** Multi-AZ là cơ chế **sẵn sàng cao** (bản sao đồng bộ, failover tự động), còn Read Replica là cơ chế **mở rộng khả năng đọc** (bản sao bất đồng bộ, không tự failover) [RDS Aurora – Mục 1.2].

| Tiêu chí | Multi-AZ | Read Replica |
| :--- | :--- | :--- |
| Mục tiêu | Sẵn sàng cao: duy trì bản sao đồng bộ ở Availability Zone khác, tự động chuyển đổi khi instance chính gặp sự cố [RDS Aurora – Mục 1.2] | Mở rộng khả năng đọc: bản sao bất đồng bộ phục vụ truy vấn đọc [RDS Aurora – Mục 1.2] |
| Cơ chế sao chép | Cập nhật **đồng bộ** [RDS Aurora – Mục 1.2] | Sao chép **bất đồng bộ**, có độ trễ nhất định [RDS Aurora – Mục 1.2] |
| Phục vụ truy vấn đọc | Standby **không** phục vụ truy vấn đọc trong mô hình Multi-AZ cổ điển [RDS Aurora – Mục 1.2] | Phục vụ truy vấn đọc; phù hợp cho báo cáo, tìm kiếm, đọc phân tán [RDS Aurora – Mục 1.2] |
| Failover | Tự động, thường mất khoảng 60-120 giây, phụ thuộc thời gian phát hiện sự cố [RDS Aurora – Mục 1.2] | Không tự động failover; khi instance chính lỗi, replica vẫn chạy nhưng ứng dụng phải chuyển endpoint thủ công [RDS Aurora – Mục 1.2] |
| Endpoint | Endpoint DNS giữ nguyên khi failover nên ứng dụng không cần đổi cấu hình [RDS Aurora – Mục 1.2] | Ứng dụng phải chuyển endpoint thủ công khi instance chính lỗi [RDS Aurora – Mục 1.2] |
| Phạm vi triển khai | Bản sao ở Availability Zone khác; với RDS MySQL, PostgreSQL, MariaDB có thêm mô hình Multi-AZ DB cluster: một writer và hai instance đọc được, trải trên ba AZ [RDS Aurora – Mục 1.2] | Cùng Region hoặc khác Region (cross-region read replica) tùy engine [RDS Aurora – Mục 1.2] |
| Nâng cấp thành instance độc lập | Không có trong tài liệu | Có thể nâng cấp replica thành instance độc lập (promote) để phục vụ kịch bản phục hồi hoặc tách môi trường [RDS Aurora – Mục 1.2] |
| Chi phí | Không có trong tài liệu | Tăng chi phí do thêm instance và lưu trữ; cần cân nhắc số lượng replica theo tải đọc thực tế [RDS Aurora – Mục 1.2] |

**Khi nào chọn Multi-AZ:** nên bật cho môi trường production của mọi ứng dụng quan trọng, kể cả khi chưa cần đọc mở rộng [RDS Aurora – Mục 1.2]; tình huống ứng dụng production cần chịu lỗi AZ thì bật Multi-AZ và giữ nguyên endpoint DNS khi failover [RDS Aurora – Mục 1.13].

**Khi nào chọn Read Replica:** khi báo cáo đọc nhiều và không được ảnh hưởng giao dịch, thêm read replica hoặc Aurora Replica và trỏ báo cáo vào reader endpoint [RDS Aurora – Mục 1.13].

**Cách phối hợp:** production cần chịu lỗi và tải đọc cao thì bật Multi-AZ cho instance chính và thêm read replica [RDS Aurora – Mục 1.2].

**Trích dẫn:** RDS Aurora – Mục 1.2 — Multi-AZ nhằm mục tiêu sẵn sàng cao: RDS duy trì một bản sao đồng bộ ở Availability Zone k; RDS Aurora – Mục 1.2 — Read replica nhằm mục tiêu mở rộng khả năng đọc: bản sao bất đồng bộ có thể phục vụ truy v; RDS Aurora – Mục 1.2 — Standby không phục vụ truy vấn đọc trong mô hình Multi-AZ cổ điển.; RDS Aurora – Mục 1.2 — Failover tự động thường mất khoảng 60-120 giây, phụ thuộc thời gian phát hiện sự cố.; RDS Aurora – Mục 1.2 — Bản sao standby được cập nhật đồng bộ; endpoint DNS giữ nguyên khi failover nên ứng dụng k; RDS Aurora – Mục 1.2 — Với RDS MySQL, PostgreSQL, MariaDB có thêm mô hình Multi-AZ DB cluster: một writer và hai ; RDS Aurora – Mục 1.2 — Sao chép bất đồng bộ, có độ trễ nhất định; phù hợp cho báo cáo, tìm kiếm, đọc phân tán.; RDS Aurora – Mục 1.2 — Hỗ trợ cùng Region hoặc khác Region (cross-region read replica) tùy engine.; RDS Aurora – Mục 1.2 — Không tự động failover; khi instance chính lỗi, replica vẫn chạy nhưng ứng dụng phải chuyể; RDS Aurora – Mục 1.2 — Tăng chi phí do thêm instance và lưu trữ; cần cân nhắc số lượng replica theo tải đọc thực ; RDS Aurora – Mục 1.2 — Production cần chịu lỗi và tải đọc cao: bật Multi-AZ cho instance chính và thêm read repli; RDS Aurora – Mục 1.13 — Ứng dụng production cần chịu lỗi AZ: bật Multi-AZ, giữ nguyên endpoint DNS khi failover.; RDS Aurora – Mục 1.13 — Báo cáo đọc nhiều, không được ảnh hưởng giao dịch: thêm read replica hoặc Aurora Replica, 

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 8. KB-04 · lượt 2

**Hỏi:** Cái nào giúp tăng khả năng đọc?

**Đáp:** **Read Replica** là cơ chế giúp tăng khả năng đọc: bản sao bất đồng bộ có thể phục vụ truy vấn đọc và có thể nâng cấp thành instance độc lập [RDS Aurora – Mục 1.2]. Replica phù hợp cho báo cáo, tìm kiếm, đọc phân tán [RDS Aurora – Mục 1.2], và khi báo cáo đọc nhiều mà không được ảnh hưởng giao dịch thì thêm read replica hoặc Aurora Replica và trỏ báo cáo vào reader endpoint [RDS Aurora – Mục 1.13].

Ngược lại, Multi-AZ phục vụ mục tiêu sẵn sàng cao, và standby không phục vụ truy vấn đọc trong mô hình Multi-AZ cổ điển [RDS Aurora – Mục 1.2]. Lưu ý: với RDS MySQL, PostgreSQL, MariaDB có thêm mô hình Multi-AZ DB cluster gồm một writer và hai instance đọc được, trải trên ba AZ [RDS Aurora – Mục 1.2].

**Trích dẫn:** RDS Aurora – Mục 1.2 — Read replica nhằm mục tiêu mở rộng khả năng đọc: bản sao bất đồng bộ có thể phục vụ truy v; RDS Aurora – Mục 1.2 — Sao chép bất đồng bộ, có độ trễ nhất định; phù hợp cho báo cáo, tìm kiếm, đọc phân tán.; RDS Aurora – Mục 1.2 — Standby không phục vụ truy vấn đọc trong mô hình Multi-AZ cổ điển.; RDS Aurora – Mục 1.2 — Với RDS MySQL, PostgreSQL, MariaDB có thêm mô hình Multi-AZ DB cluster: một writer và hai ; RDS Aurora – Mục 1.13 — Báo cáo đọc nhiều, không được ảnh hưởng giao dịch: thêm read replica hoặc Aurora Replica, 

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 9. KB-05 · lượt 1

**Hỏi:** Security group và network ACL khác nhau ở điểm nào?

**Đáp:** **Tóm tắt:** Security group là tường lửa **có trạng thái (stateful)** ở cấp ENI/instance, chỉ có rule allow; Network ACL là tường lửa **không có trạng thái (stateless)** ở cấp subnet, có cả rule allow và deny [VPC Networking – Mục 1.4].

| Tiêu chí | Security Group | Network ACL |
| :--- | :--- | :--- |
| Cấp hoạt động | Cấp ENI/instance, là một trong hai lớp tường lửa ở cấp tài nguyên [VPC Networking – Mục 1.4]; [VPC Networking – Mục 1.1] | Cấp subnet, lớp tường lửa ở cấp subnet [VPC Networking – Mục 1.4]; [VPC Networking – Mục 1.1] |
| Trạng thái | Có trạng thái (stateful): lưu lượng phản hồi của một kết nối được phép tự động, không cần mở chiều ngược lại [VPC Networking – Mục 1.4] | Không có trạng thái (stateless): phải mở cả chiều vào và chiều ra, kể cả cổng tạm thời [VPC Networking – Mục 1.4] |
| Loại rule | Chỉ có rule cho phép (allow); mọi lưu lượng không khớp bị từ chối ngầm định [VPC Networking – Mục 1.4] | Có cả rule allow và deny [VPC Networking – Mục 1.4] |
| Cách đánh giá | Mọi rule được đánh giá trước khi quyết định, không theo thứ tự [VPC Networking – Mục 1.4] | Đánh giá theo số thứ tự từ thấp đến cao, dừng ở rule khớp đầu tiên [VPC Networking – Mục 1.4] |
| Tham chiếu nguồn | Có thể tham chiếu security group khác làm nguồn thay vì dải CIDR, ví dụ chỉ cho phép security group của ALB truy cập EC2 [VPC Networking – Mục 1.4] | Không có trong tài liệu |
| Hành vi mặc định | Security group mặc định của VPC từ chối toàn bộ inbound và cho phép toàn bộ outbound; có thể xóa rule outbound mặc định để siết chặt [VPC Networking – Mục 1.4] | NACL mặc định của VPC cho phép toàn bộ vào và ra; NACL tự tạo từ chối toàn bộ cho đến khi thêm rule [VPC Networking – Mục 1.4] |
| Cách gắn | Một ENI có thể gắn nhiều security group (tối đa 5 theo hạn mức mặc định); quyền hạn là hợp của các rule [VPC Networking – Mục 1.4] | Một subnet gắn với đúng một NACL; một NACL có thể gắn với nhiều subnet [VPC Networking – Mục 1.4] |
| Yêu cầu mở cổng tạm thời | Không cần mở chiều ngược lại nhờ tính stateful [VPC Networking – Mục 1.4] | Vì stateless, khi mở inbound cổng 443 phải mở outbound dải cổng tạm thời 1024-65535 (và ngược lại) [VPC Networking – Mục 1.4] |

**Khi nào dùng Security Group:** dùng làm lớp kiểm soát chính ở cấp tài nguyên, và có thể tham chiếu security group khác làm nguồn thay vì dải CIDR [VPC Networking – Mục 1.4].

**Khi nào dùng Network ACL:** dùng làm lớp phòng thủ bổ sung ở cấp subnet khi cần chặn theo dải IP cụ thể [VPC Networking – Mục 1.4]. Khi gỡ lỗi kết nối, kiểm tra lần lượt: security group của nguồn và đích, NACL hai chiều, route table, rồi DNS [VPC Networking – Mục 1.4].

**Trích dẫn:** VPC Networking – Mục 1.4 — Security group hoạt động ở cấp ENI/instance và có trạng thái (stateful): lưu lượng phản hồ; VPC Networking – Mục 1.4 — Network ACL hoạt động ở cấp subnet và không có trạng thái (stateless): phải mở cả chiều và; VPC Networking – Mục 1.4 — Chỉ có rule cho phép (allow); mọi lưu lượng không khớp bị từ chối ngầm định.; VPC Networking – Mục 1.4 — Mọi rule được đánh giá trước khi quyết định, không theo thứ tự.; VPC Networking – Mục 1.4 — Có thể tham chiếu security group khác làm nguồn thay vì dải CIDR, ví dụ chỉ cho phép secur; VPC Networking – Mục 1.4 — Security group mặc định của VPC từ chối toàn bộ inbound và cho phép toàn bộ outbound; có t; VPC Networking – Mục 1.4 — Một ENI có thể gắn nhiều security group (tối đa 5 theo hạn mức mặc định); quyền hạn là hợp; VPC Networking – Mục 1.4 — Có cả rule allow và deny; đánh giá theo số thứ tự từ thấp đến cao, dừng ở rule khớp đầu ti; VPC Networking – Mục 1.4 — NACL mặc định của VPC cho phép toàn bộ vào và ra; NACL tự tạo từ chối toàn bộ cho đến khi ; VPC Networking – Mục 1.4 — Vì stateless, khi mở inbound cổng 443 phải mở outbound dải cổng tạm thời 1024-65535 (và ng; VPC Networking – Mục 1.4 — Một subnet gắn với đúng một NACL; một NACL có thể gắn với nhiều subnet.; VPC Networking – Mục 1.4 — Dùng security group làm lớp kiểm soát chính ở cấp tài nguyên; NACL làm lớp phòng thủ bổ su; VPC Networking – Mục 1.4 — Khi gỡ lỗi kết nối, kiểm tra lần lượt: security group của nguồn và đích, NACL hai chiều, r; VPC Networking – Mục 1.1 — Security Group và Network ACL: hai lớp tường lửa ở cấp tài nguyên và cấp subnet.

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 10. KB-05 · lượt 2

**Hỏi:** Cái nào có trạng thái?

**Đáp:** **Security group** là lớp có trạng thái (stateful): nó hoạt động ở cấp ENI/instance và lưu lượng phản hồi của một kết nối được phép sẽ tự động được cho qua, không cần mở chiều ngược lại [VPC Networking – Mục 1.4]. Ngược lại, **Network ACL** là stateless — hoạt động ở cấp subnet và phải mở cả chiều vào lẫn chiều ra, kể cả cổng tạm thời [VPC Networking – Mục 1.4].

**Trích dẫn:** VPC Networking – Mục 1.4 — Security group hoạt động ở cấp ENI/instance và có trạng thái (stateful): lưu lượng phản hồ; VPC Networking – Mục 1.4 — Network ACL hoạt động ở cấp subnet và không có trạng thái (stateless): phải mở cả chiều và

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 11. KB-06 · lượt 1

**Hỏi:** Tôi có 80 TB ảnh thumbnail có thể tạo lại từ nguồn gốc, chỉ đọc vài lần mỗi tháng nhưng cần truy xuất trong mili giây, lưu 6 tháng, chi phí thấp nhất. Chọn lớp S3 nào?

**Đáp:** **Tóm tắt:** Chọn **S3 One Zone-IA** — lớp dành cho dữ liệu ít truy cập nhưng cần truy xuất tức thời, phù hợp với dữ liệu có thể tái tạo và cần chi phí thấp.

**Bảng kiểm ràng buộc**

| # | Ràng buộc | Phương án đáp ứng | Căn cứ |
| :--- | :--- | :--- | :--- |
| 1 | Dữ liệu có thể tạo lại từ nguồn gốc (nên không bắt buộc đa AZ) | S3 One Zone-IA chỉ lưu trong một AZ, "chỉ dùng cho dữ liệu có thể tái tạo" | [S3 Storage Classes – Mục 1.1] |
| 2 | Chỉ đọc vài lần mỗi tháng (ít truy cập) | One Zone-IA thuộc nhóm không thường xuyên; tài liệu nêu đúng tình huống "Bản sao thứ cấp của dữ liệu có thể tái tạo, cần chi phí thấp: S3 One Zone-IA" | [S3 Storage Classes – Mục 1.1], [S3 Storage Classes – Mục 1.13] |
| 3 | Cần truy xuất trong mili giây | Loại các lớp Glacier phải khôi phục tạm thời; One Zone-IA là lớp không thường xuyên, dữ liệu truy xuất ngay (như Standard-IA "truy xuất trong mili giây, không cần chờ khôi phục") | [S3 Storage Classes – Mục 1.12], [S3 Storage Classes – Mục 1.4] |
| 4 | Lưu 6 tháng (khoảng 180 ngày) | Dài hơn mốc thời gian lưu tối thiểu 30 ngày của Standard-IA cùng nhóm và 90 ngày của Glacier Flexible Retrieval, bằng mốc 180 ngày của Deep Archive → không bị tính phí xóa sớm | [S3 Storage Classes – Mục 1.4], [S3 Storage Classes – Mục 1.7], [S3 Storage Classes – Mục 1.9] |
| 5 | Chi phí thấp nhất | Nhóm không thường xuyên có "chi phí lưu trữ thấp hơn nhưng có phí truy xuất hoặc thời gian lưu tối thiểu"; One Zone-IA là lựa chọn tài liệu gắn với "cần chi phí thấp" | [S3 Storage Classes – Mục 1.1], [S3 Storage Classes – Mục 1.13] |

**Vì sao không chọn phương án khác**
- **S3 Standard:** giá lưu trữ mỗi GB cao nhất trong nhóm lớp phổ thông, đắt hơn cần thiết cho dữ liệu ít truy cập [S3 Storage Classes – Mục 1.2].
- **S3 Standard-IA:** thoả truy xuất mili giây và ít truy cập, nhưng lưu đa AZ nên không tận dụng được đặc tính dữ liệu có thể tái tạo để giảm chi phí [S3 Storage Classes – Mục 1.4].
- **S3 Intelligent-Tiering:** dành cho trường hợp chưa biết mẫu truy cập, đồng thời phát sinh phí giám sát và tự động hóa tính trên mỗi 1.000 đối tượng — bất lợi với tập nhiều ảnh thumbnail nhỏ [S3 Storage Classes – Mục 1.3], [S3 Storage Classes – Mục 1.13].
- **S3 Glacier Instant Retrieval:** cũng truy xuất trong mili giây nhưng thuộc nhóm lưu trữ lạnh, nhóm này "đổi lại thời gian truy xuất lâu hơn hoặc phí truy xuất cao hơn"; không phải lựa chọn tài liệu gắn với tình huống "dữ liệu có thể tái tạo, cần chi phí thấp" [S3 Storage Classes – Mục 1.1], [S3 Storage Classes – Mục 1.6], [S3 Storage Classes – Mục 1.13].
- **S3 Glacier Flexible Retrieval / Deep Archive:** đối tượng không đọc trực tiếp được, phải gửi yêu cầu khôi phục và chờ từ phút đến giờ (Deep Archive 12–48 giờ) → vi phạm ràng buộc truy xuất mili giây [S3 Storage Classes – Mục 1.7], [S3 Storage Classes – Mục 1.9], [S3 Storage Classes – Mục 1.12].

**Kết luận:** Dùng **S3 One Zone-IA** cho 80 TB thumbnail. Lưu ý khi tính chi phí: ngoài giá lưu trữ mỗi GB cần tính cả phí truy xuất, phí request, phí chuyển lớp và phí xóa sớm, vì "chọn lớp rẻ nhất theo giá lưu trữ mỗi GB có thể làm tăng tổng chi phí" [S3 Storage Classes – Mục 1.1], [S3 Storage Classes – Mục 1.13]. Vì One Zone-IA chỉ nằm trong một AZ, dữ liệu mất nếu AZ đó bị phá hủy — chấp nhận được ở đây vì ảnh có thể tạo lại từ nguồn gốc [S3 Storage Classes – Mục 1.1].

**Trích dẫn:** S3 Storage Classes – Mục 1.1 — Các lớp một Availability Zone (One Zone-IA, Express One Zone) chỉ lưu dữ liệu trong một AZ; S3 Storage Classes – Mục 1.1 — Nhóm không thường xuyên: S3 Intelligent-Tiering, S3 Standard-IA và S3 One Zone-IA, chi phí; S3 Storage Classes – Mục 1.1 — Chọn lớp rẻ nhất theo giá lưu trữ mỗi GB có thể làm tăng tổng chi phí nếu dữ liệu được tru; S3 Storage Classes – Mục 1.13 — Bản sao thứ cấp của dữ liệu có thể tái tạo, cần chi phí thấp: S3 One Zone-IA.; S3 Storage Classes – Mục 1.13 — Dữ liệu lạnh cần truy xuất trong mili giây: S3 Glacier Instant Retrieval.; S3 Storage Classes – Mục 1.12 — Các lớp Glacier không cho đọc trực tiếp; phải khôi phục tạm thời và chờ theo mức đã chọn.; S3 Storage Classes – Mục 1.4 — Truy xuất trong mili giây, không cần chờ khôi phục.; S3 Storage Classes – Mục 1.4 — Lớp này có giá lưu trữ thấp hơn S3 Standard, bù lại là phí truy xuất theo GB và thời gian ; S3 Storage Classes – Mục 1.7 — Thời gian lưu tối thiểu 90 ngày; xóa sớm vẫn bị tính đủ 90 ngày.; S3 Storage Classes – Mục 1.9 — Truy xuất Standard khoảng 12 giờ, Bulk khoảng 48 giờ; không có mức Expedited.; S3 Storage Classes – Mục 1.9 — Thời gian lưu tối thiểu 180 ngày; xóa sớm vẫn bị tính đủ 180 ngày.; S3 Storage Classes – Mục 1.2 — Giá lưu trữ mỗi GB cao nhất trong nhóm các lớp phổ thông; dữ liệu ít truy cập nên được chu; S3 Storage Classes – Mục 1.3 — Phí giám sát và tự động hóa tính trên mỗi 1.000 đối tượng được theo dõi, nên cần ước tính 

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 12. KB-06 · lượt 2

**Hỏi:** Nếu ảnh gốc không thể tạo lại thì sao?

**Đáp:** **Tóm tắt:** Chọn **S3 Glacier Instant Retrieval** — lớp lưu trữ lạnh nhưng vẫn truy xuất trong mili giây, dữ liệu trên tối thiểu ba Availability Zone, có giá lưu trữ thấp hơn Standard-IA.

**Bảng kiểm ràng buộc**

| # | Ràng buộc | Phương án đáp ứng | Căn cứ |
| :--- | :--- | :--- | :--- |
| 1 | Dữ liệu **không thể tạo lại** → phải dùng lớp đa Availability Zone, loại bỏ One Zone-IA | Glacier Instant Retrieval là lớp đa AZ: "dữ liệu trên tối thiểu ba Availability Zone" | [S3 Storage Classes – Mục 1.1], [S3 Storage Classes – Mục 1.6] |
| 2 | Chỉ đọc vài lần mỗi tháng (ít truy cập) | Tài liệu xếp đúng tình huống "Dữ liệu lạnh cần truy xuất trong mili giây: S3 Glacier Instant Retrieval" | [S3 Storage Classes – Mục 1.13] |
| 3 | Cần truy xuất trong mili giây | "Truy xuất trong mili giây, không cần tạo yêu cầu khôi phục" | [S3 Storage Classes – Mục 1.6] |
| 4 | Lưu 6 tháng (~180 ngày) | Thời gian lưu tối thiểu 90 ngày của Glacier Instant Retrieval; 180 ngày dài hơn mốc này nên không bị tính phí xóa sớm | [S3 Storage Classes – Mục 1.6] |
| 5 | Chi phí thấp nhất | "giá lưu trữ thấp hơn Standard-IA", đổi lại phí truy xuất cao hơn | [S3 Storage Classes – Mục 1.6] |

**Vì sao không chọn phương án khác**
- **S3 One Zone-IA:** bị loại vì ràng buộc 1 thay đổi — lớp này "chỉ lưu dữ liệu trong một AZ; dữ liệu mất nếu AZ đó bị phá hủy, nên chỉ dùng cho dữ liệu có thể tái tạo" [S3 Storage Classes – Mục 1.1], trong khi tài liệu yêu cầu "dữ liệu không thể tạo lại phải dùng lớp đa AZ" [S3 Storage Classes – Mục 1.1].
- **S3 Standard-IA:** thỏa đa AZ, ít truy cập, truy xuất tức thời, thời gian lưu tối thiểu 30 ngày (6 tháng vượt mốc này) [S3 Storage Classes – Mục 1.4], [S3 Storage Classes – Mục 1.13]; nhưng giá lưu trữ cao hơn Glacier Instant Retrieval nên không phải lựa chọn chi phí thấp nhất [S3 Storage Classes – Mục 1.6].
- **S3 Standard:** đa AZ và truy xuất mili giây nhưng "không có thời gian lưu tối thiểu, không có phí truy xuất dữ liệu" với mức giá dành cho dữ liệu truy cập thường xuyên — đắt hơn cần thiết cho dữ liệu chỉ đọc vài lần mỗi tháng [S3 Storage Classes – Mục 1.2], [S3 Storage Classes – Mục 1.1].
- **S3 Intelligent-Tiering:** tài liệu gắn lớp này với trường hợp "Chưa biết mẫu truy cập, muốn tự động tối ưu mà không quản lý quy tắc", trong khi ở đây mẫu truy cập đã rõ (vài lần mỗi tháng) [S3 Storage Classes – Mục 1.13].
- **S3 Glacier Flexible Retrieval / Deep Archive:** thuộc nhóm lưu trữ lạnh có thời gian truy xuất lâu hơn, và các lớp Glacier "không cho đọc trực tiếp; phải khôi phục tạm thời và chờ theo mức đã chọn" → vi phạm ràng buộc truy xuất mili giây [S3 Storage Classes – Mục 1.1], [S3 Storage Classes – Mục 1.12].

**Kết luận:** Dùng **S3 Glacier Instant Retrieval** cho 80 TB thumbnail không thể tái tạo. Hai lưu ý khi tính chi phí: (1) lớp này có "phí truy xuất theo GB cao hơn Standard-IA; đối tượng nhỏ hơn 128 KB tính như 128 KB" — với ảnh thumbnail nhỏ, phí truy xuất có thể bị tính theo mức 128 KB mỗi đối tượng [S3 Storage Classes – Mục 1.6]; (2) phải tính "chi phí đầy đủ: không chỉ giá lưu trữ mỗi GB mà còn phí truy xuất, phí request, phí xóa sớm và phí chuyển lớp" [S3 Storage Classes – Mục 1.1]. Nếu khối lượng đọc tăng đột biến làm phí truy xuất vượt lợi ích giá lưu trữ, **S3 Standard-IA** là phương án thay thế đa AZ với phí truy xuất thấp hơn [S3 Storage Classes – Mục 1.4], [S3 Storage Classes – Mục 1.6].

**Trích dẫn:** S3 Storage Classes – Mục 1.1 — Khả năng tái tạo dữ liệu: dữ liệu không thể tạo lại phải dùng lớp đa AZ.; S3 Storage Classes – Mục 1.1 — Các lớp một Availability Zone (One Zone-IA, Express One Zone) chỉ lưu dữ liệu trong một AZ; S3 Storage Classes – Mục 1.6 — S3 Glacier Instant Retrieval dành cho dữ liệu lưu trữ lạnh nhưng vẫn cần truy xuất tức thờ; S3 Storage Classes – Mục 1.6 — Lớp này có giá lưu trữ thấp hơn Standard-IA, đổi lại là phí truy xuất cao hơn và thời gian; S3 Storage Classes – Mục 1.6 — Truy xuất trong mili giây, không cần tạo yêu cầu khôi phục.; S3 Storage Classes – Mục 1.6 — Có phí truy xuất theo GB cao hơn Standard-IA; đối tượng nhỏ hơn 128 KB tính như 128 KB.; S3 Storage Classes – Mục 1.4 — Thời gian lưu tối thiểu 30 ngày; xóa hoặc ghi đè trước hạn vẫn bị tính đủ 30 ngày.; S3 Storage Classes – Mục 1.13 — Dữ liệu lạnh cần truy xuất trong mili giây: S3 Glacier Instant Retrieval.; S3 Storage Classes – Mục 1.13 — Chưa biết mẫu truy cập, muốn tự động tối ưu mà không quản lý quy tắc: S3 IntelligentTierin; S3 Storage Classes – Mục 1.12 — Các lớp Glacier không cho đọc trực tiếp; phải khôi phục tạm thời và chờ theo mức đã chọn.; S3 Storage Classes – Mục 1.2 — Không có thời gian lưu tối thiểu, không có phí truy xuất dữ liệu.

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 13. KB-07 · lượt 1

**Hỏi:** Website chạy 24/7 ổn định 12 tháng, không thể gián đoạn, muốn giảm chi phí tối đa và có thể cam kết 1 năm. Nên mua instance thế nào?

**Đáp:** **Tóm tắt:** Với website chạy 24/7 ổn định 12 tháng, không thể gián đoạn và cam kết được 1 năm, nên mua **Reserved Instance (Standard) kỳ hạn 1 năm** — hoặc **Savings Plans 1 năm** nếu muốn linh hoạt hơn — thay vì On-Demand hay Spot.

**Bảng kiểm ràng buộc**

| # | Ràng buộc | Phương án đáp ứng | Căn cứ |
| :--- | :--- | :--- | :--- |
| 1 | Tải ổn định 24/7 trong nhiều tháng | Reserved Instance hoặc Savings Plans | [EC2 Tinh toan – Mục 1.3] |
| 2 | Có thể cam kết 1 năm, muốn giảm chi phí tối đa | Reserved Instance cam kết 1 hoặc 3 năm, Standard giảm giá sâu; Savings Plans cam kết mức chi tiêu theo giờ trong 1 hoặc 3 năm | [EC2 Tinh toan – Mục 1.3] |
| 3 | Không thể gián đoạn | Loại Spot — chỉ phù hợp khối lượng công việc chịu lỗi, stateless; không dùng cho ứng dụng không thể gián đoạn | [EC2 Tinh toan – Mục 1.3] |
| 4 | Tải đã dự đoán được (ổn định), không phải tải bất thường | Loại On-Demand — chỉ phù hợp tải không dự đoán được hoặc thử nghiệm ngắn hạn | [EC2 Tinh toan – Mục 1.3] |
| 5 | Không có yêu cầu license theo máy chủ vật lý | Loại Dedicated Hosts — chỉ dùng khi có yêu cầu license theo socket/core | [EC2 Tinh toan – Mục 1.3] |

**Vì sao không chọn phương án khác**
- **Spot Instance:** có thể bị thu hồi với thông báo 2 phút và không dùng cho ứng dụng không thể gián đoạn — vi phạm ràng buộc 3 [EC2 Tinh toan – Mục 1.3].
- **On-Demand:** không cam kết nên không đạt mục tiêu giảm chi phí tối đa cho tải ổn định dài hạn; chỉ phù hợp tải không dự đoán được hoặc thử nghiệm ngắn hạn [EC2 Tinh toan – Mục 1.3].
- **Dedicated Hosts:** dành cho yêu cầu license phần mềm theo máy chủ vật lý, không liên quan đến mục tiêu giảm chi phí ở đây [EC2 Tinh toan – Mục 1.3].
- **Capacity Reservation:** đặt trước năng lực cho một AZ cụ thể và không bắt buộc cam kết dài hạn, nên không phải lựa chọn tối ưu chi phí dài hạn [EC2 Tinh toan – Mục 1.3].

**Kết luận:** Chọn **Reserved Instance Standard kỳ hạn 1 năm** để giảm giá sâu nhất; nếu dự kiến nhu cầu có thể thay đổi họ instance thì dùng **Convertible Reserved Instance**, hoặc **Compute Savings Plans 1 năm** nếu muốn linh hoạt áp dụng cho EC2, Lambda, Fargate [EC2 Tinh toan – Mục 1.3]. Với ứng dụng web truyền thống chạy 24/7, mô hình tham chiếu là EC2 + Auto Scaling + ELB kèm Reserved Instance hoặc Savings Plans [EC2 Tinh toan – Mục 1.13]. Trước khi cam kết, nên theo dõi mức sử dụng thực tế để tránh trả tiền cho năng lực không dùng [EC2 Tinh toan – Mục 1.3].

**Trích dẫn:** EC2 Tinh toan – Mục 1.3 — Tải ổn định 24/7 trong nhiều tháng: Reserved Instance hoặc Savings Plans.; EC2 Tinh toan – Mục 1.3 — Reserved Instance: cam kết 1 hoặc 3 năm cho một cấu hình; Standard giảm giá sâu nhưng ít l; EC2 Tinh toan – Mục 1.3 — Savings Plans: cam kết mức chi tiêu theo giờ trong 1 hoặc 3 năm; Compute Savings Plans lin; EC2 Tinh toan – Mục 1.3 — Spot phù hợp cho khối lượng công việc chịu lỗi, stateless; không dùng cho cơ sở dữ liệu ch; EC2 Tinh toan – Mục 1.3 — On-Demand: trả theo giây/giờ, không cam kết; linh hoạt nhất, phù hợp tải không dự đoán đượ; EC2 Tinh toan – Mục 1.3 — Yêu cầu license phần mềm theo máy chủ vật lý: Dedicated Hosts.; EC2 Tinh toan – Mục 1.3 — Capacity Reservation: đặt trước năng lực cho một AZ cụ thể, đảm bảo có instance khi cần, k; EC2 Tinh toan – Mục 1.3 — Theo dõi mức sử dụng thực tế trước khi cam kết dài hạn để tránh trả tiền cho năng lực khôn; EC2 Tinh toan – Mục 1.13 — Ứng dụng web truyền thống chạy 24/7: EC2 + Auto Scaling + ELB, mua Reserved Instance hoặc 

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 14. KB-07 · lượt 2

**Hỏi:** Sao không dùng Spot cho web cho rẻ?

**Đáp:** Không nên dùng Spot Instance cho website chạy 24/7 không thể gián đoạn vì Spot có thể bị thu hồi bất cứ lúc nào với thông báo trước chỉ 2 phút [EC2 Tinh toan – Mục 1.3], và tài liệu nêu rõ Spot phù hợp cho khối lượng công việc chịu lỗi, stateless; không dùng cho cơ sở dữ liệu chính hoặc ứng dụng không thể gián đoạn [EC2 Tinh toan – Mục 1.3]. Với sự cố Spot, ứng dụng cần xử lý tín hiệu ngắt và thoát an toàn, đồng thời không lưu dữ liệu quan trọng trên instance store của Spot mà phải dùng S3, EBS hoặc hàng đợi để bền vững hóa công việc [EC2 Tinh toan – Mục 1.12] — những yêu cầu này không phù hợp với một website cần chạy liên tục, không thể gián đoạn. Đổi lại, Spot chỉ tận dụng năng lực dư với giá giảm tới khoảng 90% [EC2 Tinh toan – Mục 1.3], nên tiết kiệm chi phí không bù được rủi ro gián đoạn. Với tải ổn định 24/7 trong nhiều tháng, tài liệu khuyến nghị dùng Reserved Instance hoặc Savings Plans [EC2 Tinh toan – Mục 1.3].

**Trích dẫn:** EC2 Tinh toan – Mục 1.3 — Spot Instance: tận dụng năng lực dư với giá giảm tới khoảng 90%; có thể bị thu hồi với thô; EC2 Tinh toan – Mục 1.3 — Spot phù hợp cho khối lượng công việc chịu lỗi, stateless; không dùng cho cơ sở dữ liệu ch; EC2 Tinh toan – Mục 1.3 — Tải ổn định 24/7 trong nhiều tháng: Reserved Instance hoặc Savings Plans.; EC2 Tinh toan – Mục 1.12 — Spot có thể bị thu hồi với thông báo trước 2 phút; ứng dụng cần xử lý tín hiệu ngắt và tho; EC2 Tinh toan – Mục 1.12 — Không lưu dữ liệu quan trọng trên instance store của Spot; dùng S3, EBS hoặc hàng đợi để b

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 15. KB-08 · lượt 1

**Hỏi:** Làm sao giảm chi phí lưu log cũ trên S3?

**Đáp:** Để giảm chi phí lưu log cũ trên S3, tài liệu gợi ý dùng **quy tắc vòng đời (lifecycle rule)** để tự động chuyển đối tượng sang lớp lưu trữ rẻ hơn theo thời gian, nhờ đó giữ dữ liệu mới ở lớp nhanh và đẩy dần dữ liệu cũ sang lớp rẻ hơn [S3 Storage Classes – Mục 1.10]. Cụ thể:

- **Mốc thời gian tối thiểu khi chuyển lớp:** sang S3 Standard-IA hoặc S3 One Zone-IA tối thiểu 30 ngày kể từ khi tạo đối tượng; sang S3 Glacier Instant Retrieval hoặc S3 Glacier Flexible Retrieval tối thiểu 90 ngày; sang S3 Glacier Deep Archive tối thiểu 180 ngày [S3 Storage Classes – Mục 1.10].
- **Có thể kết hợp nhiều bước**, ví dụ Standard sau 30 ngày chuyển Standard-IA, sau 90 ngày chuyển Glacier Flexible Retrieval, sau 365 ngày chuyển Deep Archive [S3 Storage Classes – Mục 1.10].
- **Lưu ý về chi phí:** mỗi lần chuyển lớp phát sinh phí request; với số lượng lớn đối tượng nhỏ, chi phí chuyển lớp có thể đáng kể [S3 Storage Classes – Mục 1.10]. Quy tắc vòng đời chạy bất đồng bộ, có thể mất đến 48 giờ để áp dụng, không dùng để đáp ứng yêu cầu tức thời [S3 Storage Classes – Mục 1.10]. Xóa đối tượng trước thời gian lưu tối thiểu của lớp đích vẫn bị tính đủ thời gian tối thiểu [S3 Storage Classes – Mục 1.10]. Nên dùng S3 Storage Lens và báo cáo chi phí để kiểm tra hiệu quả của quy tắc sau khi triển khai [S3 Storage Classes – Mục 1.10].

Ngoài ra, với dữ liệu ít truy cập, tài liệu khuyến nghị chuyển sang lớp thấp hơn bằng quy tắc vòng đời thay vì giữ ở S3 Standard vì giá lưu trữ mỗi GB của Standard cao nhất trong nhóm các lớp phổ thông [S3 Storage Classes – Mục 1.2].

**Trích dẫn:** S3 Storage Classes – Mục 1.10 — Quy tắc vòng đời (lifecycle rule) cho phép S3 tự động chuyển đối tượng sang lớp lưu trữ kh; S3 Storage Classes – Mục 1.10 — Sang S3 Standard-IA hoặc S3 One Zone-IA: tối thiểu 30 ngày kể từ khi tạo đối tượng.; S3 Storage Classes – Mục 1.10 — Sang S3 Glacier Instant Retrieval hoặc S3 Glacier Flexible Retrieval: tối thiểu 90 ngày.; S3 Storage Classes – Mục 1.10 — Sang S3 Glacier Deep Archive: tối thiểu 180 ngày.; S3 Storage Classes – Mục 1.10 — Có thể kết hợp nhiều bước, ví dụ Standard sau 30 ngày chuyển Standard-IA, sau 90 ngày chuy; S3 Storage Classes – Mục 1.10 — Mỗi lần chuyển lớp phát sinh phí request; với số lượng lớn đối tượng nhỏ, chi phí chuyển l; S3 Storage Classes – Mục 1.10 — Quy tắc vòng đời chạy bất đồng bộ, có thể mất đến 48 giờ để áp dụng; không dùng để đáp ứng; S3 Storage Classes – Mục 1.10 — Xóa đối tượng trước thời gian lưu tối thiểu của lớp đích vẫn bị tính đủ thời gian tối thiể; S3 Storage Classes – Mục 1.10 — Nên dùng S3 Storage Lens và báo cáo chi phí để kiểm tra hiệu quả của quy tắc sau khi triển; S3 Storage Classes – Mục 1.2 — Giá lưu trữ mỗi GB cao nhất trong nhóm các lớp phổ thông; dữ liệu ít truy cập nên được chu

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 16. KB-08 · lượt 2

**Hỏi:** Vậy log nên chuyển sang Deep Archive sau bao lâu?

**Đáp:** Theo tài liệu, mốc thời gian tối thiểu khi chuyển lớp sang S3 Glacier Deep Archive bằng quy tắc vòng đời là **180 ngày** kể từ khi đối tượng được tạo [S3 Storage Classes – Mục 1.10]. Tài liệu cũng nêu ví dụ kết hợp nhiều bước: Standard sau 30 ngày chuyển Standard-IA, sau 90 ngày chuyển Glacier Flexible Retrieval, sau 365 ngày chuyển Deep Archive [S3 Storage Classes – Mục 1.10]. Lưu ý thêm: mỗi lần chuyển lớp phát sinh phí request, và với số lượng lớn đối tượng nhỏ thì chi phí chuyển lớp có thể đáng kể [S3 Storage Classes – Mục 1.10].

**Trích dẫn:** S3 Storage Classes – Mục 1.10 — Sang S3 Glacier Deep Archive: tối thiểu 180 ngày.; S3 Storage Classes – Mục 1.10 — Có thể kết hợp nhiều bước, ví dụ Standard sau 30 ngày chuyển Standard-IA, sau 90 ngày chuy; S3 Storage Classes – Mục 1.10 — Mỗi lần chuyển lớp phát sinh phí request; với số lượng lớn đối tượng nhỏ, chi phí chuyển l

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 17. KB-09 · lượt 1

**Hỏi:** NAT Gateway có cần gắn security group không?

**Đáp:** Không. NAT gateway không gắn security group; bạn kiểm soát lưu lượng bằng security group của tài nguyên và NACL của subnet [VPC Networking – Mục 1.3]. Đây cũng là một đặc điểm của NAT gateway do AWS quản lý: không cần vá lỗi, không cần security group, có tính sẵn sàng trong AZ [VPC Networking – Mục 1.3].

**Trích dẫn:** VPC Networking – Mục 1.3 — NAT gateway không gắn security group; kiểm soát lưu lượng bằng security group của tài nguy; VPC Networking – Mục 1.3 — NAT gateway do AWS quản lý: không cần vá lỗi, không cần security group, có tính sẵn sàng t

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 18. KB-09 · lượt 2

**Hỏi:** Ý bạn là NAT Gateway không có security group, vậy tôi bảo vệ nó bằng cách nào?

**Đáp:** Vì NAT gateway không gắn security group, bạn kiểm soát lưu lượng bằng security group của tài nguyên và NACL của subnet [VPC Networking – Mục 1.3]. Cụ thể, security group hoạt động ở cấp ENI/instance và có trạng thái (stateful), còn Network ACL hoạt động ở cấp subnet và không có trạng thái (stateless) [VPC Networking – Mục 1.4]. Khi phối hợp, nên dùng security group làm lớp kiểm soát chính ở cấp tài nguyên và NACL làm lớp phòng thủ bổ sung ở cấp subnet khi cần chặn theo dải IP cụ thể [VPC Networking – Mục 1.4]. Lưu ý thêm: NAT gateway không hỗ trợ IPv6 và không thể dùng làm bastion host [VPC Networking – Mục 1.3].

**Trích dẫn:** VPC Networking – Mục 1.3 — NAT gateway không gắn security group; kiểm soát lưu lượng bằng security group của tài nguy; VPC Networking – Mục 1.4 — Security group hoạt động ở cấp ENI/instance và có trạng thái (stateful); VPC Networking – Mục 1.4 — Network ACL hoạt động ở cấp subnet và không có trạng thái (stateless); VPC Networking – Mục 1.4 — Dùng security group làm lớp kiểm soát chính ở cấp tài nguyên; NACL làm lớp phòng thủ bổ su; VPC Networking – Mục 1.3 — NAT gateway không hỗ trợ IPv6 và không thể dùng làm bastion host.

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 19. KB-10 · lượt 1

**Hỏi:** S3 Standard-IA khác Standard ở điểm nào?

**Đáp:** **Tóm tắt:** Standard-IA có giá lưu trữ thấp hơn Standard nhưng đổi lại phải chịu phí truy xuất theo GB và ràng buộc thời gian lưu tối thiểu 30 ngày, trong khi Standard không có cả hai khoản này [S3 Storage Classes – Mục 1.4] [S3 Storage Classes – Mục 1.2].

| Tiêu chí | S3 Standard | S3 Standard-IA |
| :--- | :--- | :--- |
| Giá lưu trữ | Cao nhất trong nhóm các lớp phổ thông; dữ liệu ít truy cập nên chuyển sang lớp thấp hơn bằng quy tắc vòng đời [S3 Storage Classes – Mục 1.2] | Giá lưu trữ thấp hơn S3 Standard [S3 Storage Classes – Mục 1.4] |
| Phí truy xuất dữ liệu | Không có phí truy xuất dữ liệu [S3 Storage Classes – Mục 1.2] | Có phí truy xuất theo GB [S3 Storage Classes – Mục 1.4] |
| Thời gian lưu tối thiểu | Không có thời gian lưu tối thiểu [S3 Storage Classes – Mục 1.2] | Tối thiểu 30 ngày [S3 Storage Classes – Mục 1.4] |
| Phí xóa sớm | Không có thời gian lưu tối thiểu nên không phát sinh ràng buộc lưu tối thiểu [S3 Storage Classes – Mục 1.2] | Xóa hoặc ghi đè trước hạn vẫn bị tính đủ 30 ngày; cần cân nhắc phí xóa sớm khi dữ liệu chỉ được lưu trong thời gian ngắn [S3 Storage Classes – Mục 1.4] |
| Độ trễ truy xuất | Độ trễ mili giây cho mọi yêu cầu đọc [S3 Storage Classes – Mục 1.2] | Truy xuất trong mili giây, không cần chờ khôi phục [S3 Storage Classes – Mục 1.4] |
| Độ bền / Availability | Độ bền thiết kế 99,999999999%, khả năng sẵn sàng 99,99%, lưu trên tối thiểu ba Availability Zone [S3 Storage Classes – Mục 1.2] | Độ bền thiết kế 11 số 9, khả năng sẵn sàng 99,9%, dữ liệu trên tối thiểu ba Availability Zone [S3 Storage Classes – Mục 1.4] |
| Tính năng S3 | Hỗ trợ đầy đủ tính năng S3: phiên bản đối tượng, nhân bản, vòng đời, Object Lock, sao chép nhiều vùng [S3 Storage Classes – Mục 1.2] | Không có trong tài liệu |
| Đối tượng nhỏ | Không có trong tài liệu | Đối tượng nhỏ hơn 128 KB được tính như 128 KB [S3 Storage Classes – Mục 1.4] |
| Trường hợp sử dụng | Dữ liệu truy cập thường xuyên, cần truy xuất ngay và thường xuyên, không chấp nhận phí truy xuất [S3 Storage Classes – Mục 1.2] | Dữ liệu ít được truy cập nhưng phải truy xuất ngay khi cần: bản sao lưu, ảnh chụp, dữ liệu phục hồi sau thảm họa, dữ liệu cũ ít truy cập, tệp phương tiện ít dùng, nhật ký cũ, dữ liệu tuân thủ thỉnh thoảng mới tra cứu [S3 Storage Classes – Mục 1.4] |

**Khi nào chọn Standard:** dữ liệu được đọc thường xuyên, cần truy xuất ngay và không chấp nhận phí truy xuất, hoặc cần thời gian lưu không ràng buộc tối thiểu [S3 Storage Classes – Mục 1.2].
**Khi nào chọn Standard-IA:** dữ liệu ít được truy cập nhưng phải truy xuất tức thời khi có nhu cầu [S3 Storage Classes – Mục 1.4].

**Lưu ý:** nếu dữ liệu thực tế được truy cập thường xuyên, phí truy xuất có thể làm tổng chi phí cao hơn S3 Standard [S3 Storage Classes – Mục 1.4]; nguyên tắc chung là phải tính chi phí đầy đủ gồm giá lưu trữ mỗi GB, phí truy xuất, phí request, phí xóa sớm và phí chuyển lớp [S3 Storage Classes – Mục 1.1].

**Trích dẫn:** S3 Storage Classes – Mục 1.2 — Lớp này không có phí truy xuất, không có thời gian lưu tối thiểu và hỗ trợ đầy đủ các tính; S3 Storage Classes – Mục 1.2 — Giá lưu trữ mỗi GB cao nhất trong nhóm các lớp phổ thông; S3 Storage Classes – Mục 1.4 — Lớp này có giá lưu trữ thấp hơn S3 Standard, bù lại là phí truy xuất theo GB và thời gian ; S3 Storage Classes – Mục 1.4 — Thời gian lưu tối thiểu 30 ngày; xóa hoặc ghi đè trước hạn vẫn bị tính đủ 30 ngày.; S3 Storage Classes – Mục 1.4 — Nếu dữ liệu thực tế được truy cập thường xuyên, phí truy xuất có thể làm tổng chi phí cao ; S3 Storage Classes – Mục 1.1 — Chi phí đầy đủ: không chỉ giá lưu trữ mỗi GB mà còn phí truy xuất, phí request, phí xóa sớ

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 20. KB-10 · lượt 2

**Hỏi:** Viết cho tôi đoạn Python để upload file lên S3.

**Đáp:** Câu hỏi này nằm ngoài phạm vi tài liệu SAA-C03 hiện có, nên mình không trả lời để tránh cung cấp thông tin không có căn cứ. Bạn có thể hỏi về các chủ đề đang có như S3 Storage Classes, vòng đời đối tượng S3 hoặc thiết kế giải pháp lưu trữ tối ưu chi phí.

**Trích dẫn:** (không có)

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 21. KB-01 · lượt 3

**Hỏi:** Vậy khi nào dùng cái nào?

**Đáp:** **Tóm tắt:** Trong ngữ cảnh hiện có, EBS được mô tả là lưu trữ khối gắn với instance trong cùng Availability Zone, còn S3 được nhắc đến như dịch vụ lưu trữ đối tượng có quản lý vòng đời đối tượng; tài liệu chưa có đoạn so sánh trực tiếp đầy đủ giữa hai dịch vụ.

| Tiêu chí | Amazon S3 | Amazon EBS |
| :--- | :--- | :--- |
| Kiểu lưu trữ | Lưu trữ đối tượng — tài liệu nêu “đối tượng S3” và “lưu trữ đối tượng” [aws-saa-exam-guide – Mục 4.1] | Ổ đĩa khối — “cung cấp ổ đĩa khối gắn với instance” [EC2 Tinh toan – Mục 1.4] |
| Phạm vi gắn kết | Không có trong tài liệu | Gắn với instance trong cùng Availability Zone; volume chỉ gắn được cho instance trong cùng AZ [EC2 Tinh toan – Mục 1.4] |
| Tồn tại dữ liệu | Không có trong tài liệu (chỉ nêu quản lý vòng đời đối tượng) [aws-saa-exam-guide – Mục 4.1] | Dữ liệu tồn tại độc lập với vòng đời instance [EC2 Tinh toan – Mục 1.4] |
| Sao lưu | Không có trong tài liệu | Có thể sao lưu bằng snapshot lên S3; snapshot là bản sao lưu tăng dần, lưu trong S3 do AWS quản lý [EC2 Tinh toan – Mục 1.4] |
| Trường hợp sử dụng | Quản lý vòng đời đối tượng S3; phân tầng lạnh (cold tiering) cho lưu trữ đối tượng [aws-saa-exam-guide – Mục 4.1] | Không có trong tài liệu hướng dẫn lựa chọn EBS theo trường hợp sử dụng |
| Chi phí | Không có trong tài liệu | Không có trong tài liệu |

**Khi nào chọn S3:** Khi nhu cầu là lưu trữ đối tượng và quản lý vòng đời đối tượng, hoặc áp dụng phân tầng lạnh cho lưu trữ đối tượng [aws-saa-exam-guide – Mục 4.1].

**Khi nào chọn EBS:** Khi cần ổ đĩa khối gắn với instance trong cùng Availability Zone, dữ liệu tồn tại độc lập với vòng đời instance và có thể sao lưu bằng snapshot [EC2 Tinh toan – Mục 1.4].

**Giới hạn:** Tài liệu hiện có chưa nêu tiêu chí so sánh trực tiếp giữa S3 và EBS về chi phí, hiệu năng hay hướng dẫn chọn dịch vụ theo từng khối lượng công việc, nên các ô tương ứng được ghi “không có trong tài liệu”.

**Trích dẫn:** EC2 Tinh toan – Mục 1.4 — Amazon Elastic Block Store (EBS) cung cấp ổ đĩa khối gắn với instance trong cùng Availabil; EC2 Tinh toan – Mục 1.4 — Dữ liệu EBS tồn tại độc lập với vòng đời instance và có thể sao lưu bằng snapshot lên S3.; EC2 Tinh toan – Mục 1.4 — EBS gắn với một AZ; volume chỉ gắn được cho instance trong cùng AZ.; EC2 Tinh toan – Mục 1.4 — Snapshot là bản sao lưu tăng dần, lưu trong S3 do AWS quản lý; aws-saa-exam-guide – Mục 4.1 — Quản lý vòng đời đối tượng S3.; aws-saa-exam-guide – Mục 4.1 — Phân tầng lưu trữ, ví dụ phân tầng lạnh (cold tiering) cho lưu trữ đối tượng.; aws-saa-exam-guide – Mục 3.1 — Các kiểu lưu trữ kèm đặc điểm, ví dụ object, file, block.

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 22. KB-01 · lượt 4

**Hỏi:** EBS có tự nhân bản qua nhiều AZ không?

**Đáp:** Không. EBS gắn với một AZ và volume chỉ gắn được cho instance trong cùng AZ [EC2 Tinh toan – Mục 1.4]. Tài liệu không nêu cơ chế EBS tự nhân bản qua nhiều AZ; điểm liên quan đến AZ khác là có thể tạo volume mới từ snapshot ở AZ khác hoặc Region khác (sau khi copy snapshot) [EC2 Tinh toan – Mục 1.4].

**Trích dẫn:** EC2 Tinh toan – Mục 1.4 — EBS gắn với một AZ; volume chỉ gắn được cho instance trong cùng AZ.; EC2 Tinh toan – Mục 1.4 — Có thể tạo volume mới từ snapshot ở AZ khác hoặc Region khác (sau khi copy snapshot).

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 23. KB-02 · lượt 3

**Hỏi:** Khôi phục xong nó ghi đè DB cũ hay tạo cái mới?

**Đáp:** Bản khôi phục tạo ra một DB instance mới, không ghi đè lên DB instance cũ. Tài liệu nêu rõ: "Mọi bản khôi phục đều tạo ra một DB instance mới" [RDS Aurora – Mục 1.3], và "Khôi phục luôn tạo tài nguyên mới, không ghi đè instance hiện có; cần thay đổi DNS hoặc endpoint để chuyển hướng ứng dụng" [RDS Aurora – Mục 1.3]. Vì vậy sau khi phục hồi theo thời điểm, bạn cần cập nhật cấu hình ứng dụng/DNS trỏ sang endpoint mới [RDS Aurora – Mục 1.3].

**Trích dẫn:** RDS Aurora – Mục 1.3 — Mọi bản khôi phục đều tạo ra một DB instance mới.; RDS Aurora – Mục 1.3 — Khôi phục luôn tạo tài nguyên mới, không ghi đè instance hiện có; cần thay đổi DNS hoặc en; RDS Aurora – Mục 1.3 — Khôi phục snapshot tạo instance mới với endpoint mới; cần cập nhật cấu hình ứng dụng.

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

### 24. KB-02 · lượt 4

**Hỏi:** Vậy snapshot thủ công khác gì?

**Đáp:** **Tóm tắt:** Sao lưu tự động gắn với vòng đời DB instance và chỉ giữ 0-35 ngày để phục hồi theo thời điểm, còn snapshot thủ công tồn tại cho đến khi bạn xóa và có thêm khả năng sao chép sang Region khác, xuất sang S3 [RDS Aurora – Mục 1.3].

| Tiêu chí | Sao lưu tự động (automated backup) | Snapshot thủ công (manual snapshot) |
| :--- | :--- | :--- |
| Thời gian lưu giữ | 0-35 ngày; đặt 0 sẽ tắt sao lưu tự động [RDS Aurora – Mục 1.3] | Tồn tại đến khi bị xóa, kể cả sau khi xóa DB instance [RDS Aurora – Mục 1.3] |
| Phục hồi theo thời điểm | Hỗ trợ phục hồi theo thời điểm tới bất kỳ giây nào trong khoảng lưu giữ, thường trong vòng 5 phút kể từ thời điểm gần nhất [RDS Aurora – Mục 1.3] | Không có trong tài liệu |
| Thời điểm chạy | Diễn ra trong backup window; nên đặt vào giờ thấp điểm [RDS Aurora – Mục 1.3] | Không có trong tài liệu |
| Khi xóa DB instance | Giữ snapshot cuối cùng một thời gian nếu tùy chọn này được bật khi xóa [RDS Aurora – Mục 1.3] | Vẫn tồn tại kể cả sau khi xóa DB instance [RDS Aurora – Mục 1.3] |
| Sao chép sang Region khác | Không có trong tài liệu | Có thể sao chép sang Region khác [RDS Aurora – Mục 1.3] |
| Chia sẻ và mã hóa | Không có trong tài liệu | Snapshot của DB đã mã hóa chỉ có thể chia sẻ nếu nguồn cho phép; snapshot mã hóa không chia sẻ công khai [RDS Aurora – Mục 1.3] |
| Xuất dữ liệu để phân tích | Không có trong tài liệu | Có thể xuất snapshot sang S3 dưới định dạng Parquet để phân tích bằng Athena [RDS Aurora – Mục 1.3] |
| Khôi phục | Mọi bản khôi phục đều tạo ra một DB instance mới [RDS Aurora – Mục 1.3] | Khôi phục snapshot tạo instance mới với endpoint mới; cần cập nhật cấu hình ứng dụng [RDS Aurora – Mục 1.3] |

**Khi nào dùng sao lưu tự động:** khi cần phục hồi theo thời điểm trong khoảng lưu giữ (0-35 ngày) [RDS Aurora – Mục 1.3].
**Khi nào dùng snapshot thủ công:** khi cần bản sao giữ lâu dài đến khi tự xóa, sao chép sang Region khác hoặc xuất sang S3 để phân tích [RDS Aurora – Mục 1.3].

**Lưu ý chung:** khôi phục luôn tạo tài nguyên mới, không ghi đè instance hiện có; cần thay đổi DNS hoặc endpoint để chuyển hướng ứng dụng [RDS Aurora – Mục 1.3].

**Trích dẫn:** RDS Aurora – Mục 1.3 — Sao lưu tự động • Thời gian lưu giữ 0-35 ngày; đặt 0 sẽ tắt sao lưu tự động.; RDS Aurora – Mục 1.3 — Phục hồi theo thời điểm (point-in-time recovery) tới bất kỳ giây nào trong khoảng lưu giữ,; RDS Aurora – Mục 1.3 — Tồn tại đến khi bị xóa, kể cả sau khi xóa DB instance; có thể sao chép sang Region khác.; RDS Aurora – Mục 1.3 — Có thể xuất snapshot sang S3 dưới định dạng Parquet để phân tích bằng Athena.; RDS Aurora – Mục 1.3 — Khôi phục snapshot tạo instance mới với endpoint mới; cần cập nhật cấu hình ứng dụng.

**Chấm tay:** ☐ ĐẠT / ☐ MỘT PHẦN / ☐ SAI

**Ghi chú:** 

---

## Đáp án máy chấm (chỉ xem sau khi chấm tay)

| # | Kịch bản | Lượt | Judge | Lý do tóm tắt |
| ---: | :--- | :---: | ---: | :--- |
| 1 | KB-01 | 1 | 0.5 | Câu viết lại giữ nguyên và câu trả lời đúng phần lớn: nêu S3 là lưu trữ đối tượng, nhiều lớp trên cùng không gian tên, gán lớp khi tải lên hoặc bằng lifecycle, mặc định Standard; k |
| 2 | KB-01 | 2 | 1.0 | Đáp ứng đầy đủ: câu viết lại chứa cả S3 và EBS; có bảng so sánh rõ giữa S3 và EBS; nêu đúng S3 là lưu trữ đối tượng, truy cập qua API, nhiều lớp, có lớp đa AZ và một AZ; EBS là ổ đ |
| 3 | KB-02 | 1 | 0.5 | Trả lời đúng thời gian lưu giữ 0–35 ngày và đặt 0 là tắt, trích dẫn phù hợp Mục 1.3; không nói khôi phục ghi đè instance. Tuy nhiên thiếu ý backup chạy trong backup window nên đặt  |
| 4 | KB-02 | 2 | 1.0 | Câu trả lời đáp ứng đầy đủ hành vi mong đợi: khẳng định có thể khôi phục về một giờ trước bằng PITR trong khoảng lưu giữ 0-35 ngày, nêu đúng khả năng khôi phục tới bất kỳ giây nào  |
| 5 | KB-03 | 1 | 0.5 | Trả lời đúng định nghĩa IAM role, nêu đúng trust policy và permission policy, nói rõ trust policy không cấp quyền tài nguyên. Tuy nhiên thiếu thông tin thời hạn credential tạm thời |
| 6 | KB-03 | 2 | 1.0 | Câu trả lời xác định đúng trust policy dùng để xác định ai được assume role; nêu rõ không cấp quyền truy cập tài nguyên và permission policy mới quy định role được làm gì. Trích dẫ |
| 7 | KB-04 | 1 | 1.0 | Đáp ứng đầy đủ hành vi mong đợi: có bảng so sánh vượt 5 tiêu chí (mục tiêu, cơ chế đồng bộ/bất đồng bộ, khả năng đọc, failover, endpoint, phạm vi, chi phí), kết luận hai cơ chế bổ  |
| 8 | KB-04 | 2 | 1.0 | Câu trả lời xác định đúng Read Replica giúp tăng khả năng đọc, nêu standby Multi-AZ cổ điển không phục vụ đọc và có nêu ngoại lệ Multi-AZ DB cluster (1 writer + 2 instance đọc được |
| 9 | KB-05 | 1 | 1.0 | Câu trả lời so sánh đầy đủ 5 tiêu chí chính: cấp áp dụng, stateful/stateless, loại rule, cách đánh giá, hành vi mặc định; không nói NACL stateful hay security group có rule deny. C |
| 10 | KB-05 | 2 | 1.0 | Trả lời đúng: security group là stateful và phản hồi được phép tự động; Network ACL là stateless và phải mở cả hai chiều kể cả cổng tạm thời. Câu viết lại giữ đúng ý, đủ thực thể;  |
| 11 | KB-06 | 1 | 1.0 | Đáp ứng đầy đủ: bảng 5 ràng buộc, chọn One Zone-IA, nêu phí truy xuất và xóa sớm, giải thích hợp lý, trích dẫn phù hợp. |
| 12 | KB-06 | 2 | 1.0 | Đạt đầy đủ: lượt 2 chuyển khỏi One Zone-IA sang S3 Glacier Instant Retrieval là lớp đa AZ, truy xuất mili giây, nêu đúng phí truy xuất cao hơn và mốc lưu tối thiểu 90 ngày; có bảng |
| 13 | KB-07 | 1 | 1.0 | Đáp ứng đầy đủ: có bảng ràng buộc, chọn Reserved Instance/Savings Plans 1 năm cho tải web 24/7 ổn định, loại Spot cho web không thể gián đoạn, loại On-Demand cho tải dài hạn ổn địn |
| 14 | KB-07 | 2 | 1.0 | Đạt đầy đủ: nêu đúng Spot có thể bị thu hồi với thông báo 2 phút, chỉ phù hợp workload chịu lỗi/stateless, không dùng cho cơ sở dữ liệu chính hoặc ứng dụng không thể gián đoạn; giả |
| 15 | KB-08 | 1 | 1.0 | Câu trả lời đáp ứng đầy đủ hành vi mong đợi: dùng lifecycle chuyển log cũ sang Standard-IA/Glacier/Deep Archive theo mốc thời gian, nêu lifecycle chạy bất đồng bộ (tối đa 48 giờ) v |
| 16 | KB-08 | 2 | 0.5 | Trả lời đúng mốc tối thiểu 180 ngày và có nêu phí request khi chuyển lớp, nhưng thiếu các ý quan trọng theo hành vi mong đợi: chỉ nên dùng khi gần như không đọc, phí truy xuất/khôi |
| 17 | KB-09 | 1 | 1.0 | Câu trả lời đúng trọng tâm: NAT Gateway không gắn security group; kiểm soát bằng security group của tài nguyên và NACL của subnet. Trích dẫn đúng VPC Networking – Mục 1.3, không mâ |
| 18 | KB-09 | 2 | 0.5 | Câu trả lời đúng hướng: xác nhận gián tiếp NAT Gateway không gắn security group và giải thích kiểm soát bằng security group của tài nguyên, NACL của subnet; trích đúng Mục 1.3 và t |
| 19 | KB-10 | 1 | 1.0 | Câu trả lời so sánh đúng và đầy đủ S3 Standard-IA với S3 Standard theo hành vi mong đợi: giá lưu trữ thấp hơn, có phí truy xuất, tối thiểu 30 ngày, truy xuất mili giây, đa AZ; Stan |
| 20 | KB-10 | 2 | 1.0 | Câu trả lời từ chối rõ ràng vì ngoài phạm vi tài liệu SAA-C03, không viết code, không nêu thư viện hay chi tiết kỹ thuật để trả lời câu hỏi; chỉ nêu chủ đề S3 liên quan để mời quay |
| 21 | KB-01 | 3 | 0.5 | Câu viết lại đúng và có bảng so sánh, không gán sai đặc điểm EBS cho S3 hay bịa IOPS/dung lượng; có nêu snapshot EBS lưu trong S3. Tuy nhiên câu trả lời thiếu các ý quan trọng theo |
| 22 | KB-01 | 4 | 1.0 | Câu trả lời đúng: EBS không tự nhân bản qua nhiều AZ; EBS gắn với một AZ và chỉ gắn được cho instance trong cùng AZ. Câu trả lời cũng nêu đúng việc có thể tạo volume từ snapshot ở  |
| 23 | KB-02 | 3 | 1.0 | Lượt 3 trả lời đúng: khôi phục tạo DB instance mới, không ghi đè instance cũ, và cần cập nhật DNS/endpoint ứng dụng. Câu viết lại thực tế giải quyết đúng đại từ 'nó', giữ đủ ý và t |
| 24 | KB-02 | 4 | 1.0 | Câu trả lời phân biệt rõ sao lưu tự động và snapshot thủ công: thời gian lưu giữ, PITR, hành vi sau khi xóa DB instance, sao chép Region, chia sẻ/mã hóa, xuất S3 và việc khôi phục  |

