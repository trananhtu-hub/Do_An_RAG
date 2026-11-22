# Kịch bản hội thoại — bộ dev (10 kịch bản mới)

Tệp này là bộ dev đi kèm bộ nghiệm thu `inputs/conversations.md`: gồm 10 kịch bản mới, cùng sáu loại hành vi và cùng phân bố 3 – 2 – 2 – 1 – 1 – 1, mỗi kịch bản 4 lượt (tổng 40 lượt). Mã `DV-*` tách khỏi mã `KB-*` để không trộn bộ dev với bộ nghiệm thu đã đóng băng.

Bộ dev dùng để phát triển, phân tích lỗi và kiểm tra hồi quy trong lúc tinh chỉnh. Kết quả của bộ dev không thay thế kết quả của bộ nghiệm thu `inputs/conversations.md`; không dùng bộ nghiệm thu để tinh chỉnh.

Các kịch bản chỉ dùng nội dung có trong 7 tài liệu của kho tri thức. Cột "Căn cứ" ghi tên tài liệu (trường `document_title`) và mục/trang để đối chiếu với trích dẫn của chatbot; mọi trích dẫn cuối phải trỏ đúng tài liệu và mục, đồng thời nằm trong khoảng trang tương ứng của chunk.

Bộ dev tập trung vào các phần ít được bộ nghiệm thu cũ phủ: Route 53, Auto Scaling và cân bằng tải, RDS Proxy, VPC peering và Transit Gateway, CloudFront và Global Accelerator, loại volume EBS, kết nối lai, Aurora Serverless v2, loại policy IAM và placement group.

## Quy ước chạy và chấm

- Mỗi kịch bản chạy trong một phiên riêng, cùng một tài khoản test; không dùng lại phiên giữa các kịch bản.
- Chỉ gửi cột "Câu hỏi người dùng" cho chatbot. Các cột còn lại là tiêu chí chấm, không đưa vào prompt.
- Cột "Câu viết lại kỳ vọng" là đầu ra mong đợi của bước query condensation: câu độc lập, giữ nguyên ý, không thêm dữ kiện. Với lượt đã độc lập, ghi "Giữ nguyên".
- Kịch bản đạt khi tất cả lượt đạt. Kết quả bộ dev dùng để phân tích lỗi và so sánh cấu hình; ngưỡng nghiệm thu ≥ 8/10 chỉ áp dụng cho bộ `inputs/conversations.md`.
- Khi một lượt không đạt, ghi mã kịch bản, số lượt và lỗi thuộc tầng nào: condensation, retrieval, generation hay streaming/SSE.
- Khi so sánh hai cấu hình, không sửa kịch bản giữa các lần chạy; nếu buộc phải sửa, ghi phiên bản kịch bản và chạy lại cả hai cấu hình.

## Phân bố 10 kịch bản

| Loại | Mã kịch bản | Số lượng |
| :--- | :--- | :---: |
| Tra cứu nối tiếp | DV-01, DV-02, DV-03 | 3 |
| So sánh | DV-04, DV-05 | 2 |
| Nhiều ràng buộc | DV-06, DV-07 | 2 |
| Đổi chủ đề giữa chừng | DV-08 | 1 |
| Người dùng hỏi lại làm rõ | DV-09 | 1 |
| Hỏi ngoài phạm vi | DV-10 | 1 |
| **Tổng** | | **10** |

| Mã | Chủ đề | Số lượt |
| :--- | :--- | :---: |
| DV-01 | Route 53: DNS, chính sách định tuyến và failover | 4 |
| DV-02 | Auto Scaling group và cân bằng tải | 4 |
| DV-03 | RDS Proxy và quản lý kết nối | 4 |
| DV-04 | VPC peering và Transit Gateway | 4 |
| DV-05 | CloudFront và Global Accelerator | 4 |
| DV-06 | Chọn loại EBS volume theo ràng buộc | 4 |
| DV-07 | Kết nối hybrid on-premises – VPC | 4 |
| DV-08 | Đổi chủ đề từ VPC endpoint sang Aurora Serverless v2 | 4 |
| DV-09 | Người dùng hỏi lại về permission boundary | 4 |
| DV-10 | Ngoài phạm vi giữa hội thoại EC2 | 4 |

## DV-01 — Tra cứu nối tiếp: Route 53 từ DNS đến failover

- **Mã kịch bản:** DV-01
- **Loại:** Tra cứu nối tiếp
- **Mục tiêu:** Kiểm tra chuỗi khái niệm Route 53: hosted zone và bản ghi → chính sách định tuyến → failover dựa trên health check → alias record; kiểm tra đại từ "nó" và "cái nào" ở các lượt sau.
- **Số lượt:** 4
- **Tài liệu:** VPC Networking — Mục 1.9 (tr.7–8)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | Amazon Route 53 là gì và hosted zone dùng để làm gì? | Giữ nguyên | Trả lời Route 53 là dịch vụ DNS có tính sẵn sàng cao và là registrar tên miền; hosted zone public hoặc private, private zone chỉ phân giải trong VPC được liên kết; nêu các bản ghi A, AAAA, CNAME, MX, TXT, NS, SOA; CNAME không dùng được ở đỉnh tên miền. | VPC Networking — Mục 1.9 (tr.7–8) |
| 2 | Vậy nó có những chính sách định tuyến nào? | Route 53 có những chính sách định tuyến nào? | Liệt kê Simple, Weighted, Latency, Failover, Geolocation/Geoproximity, Multivalue answer và IP-based; nêu ngắn mục đích từng loại; nói Simple không hỗ trợ health check và multivalue không thay thế load balancer. | VPC Networking — Mục 1.9 (tr.7–8) |
| 3 | Muốn tự chuyển sang Region dự phòng khi Region chính lỗi thì dùng cái nào? | Muốn tự động chuyển sang Region dự phòng khi Region chính gặp sự cố thì nên dùng chính sách định tuyến nào của Route 53? | Trả lời Failover (active-passive) và phải gắn health check; nói DNS failover chỉ hoạt động khi bản ghi có health check; health check dùng HTTP/HTTPS/TCP với chu kỳ 30 giây mặc định hoặc 10 giây fast; không nhầm sang Global Accelerator. | VPC Networking — Mục 1.9 (tr.7–8) |
| 4 | Alias record khác CNAME ở điểm nào? | Alias record của Route 53 khác CNAME ở điểm nào? | Trả lời Alias trỏ tới tài nguyên AWS như ALB, CloudFront, S3 website, API Gateway; dùng được ở đỉnh tên miền và không tính phí truy vấn tới tài nguyên AWS; CNAME không dùng được ở đỉnh tên miền; TTL quyết định thời gian cache. | VPC Networking — Mục 1.9 (tr.7–8) |

**Tiêu chí đạt:**

- 4/4 lượt đúng; lượt 2 giữ "Route 53" trong câu viết lại và nêu đủ các chính sách Simple, Weighted, Latency, Failover, Geolocation/Geoproximity, Multivalue answer, IP-based.
- Lượt 3 nêu Failover gắn với health check; không trả lời bằng Global Accelerator hoặc lái sang dịch vụ khác.
- Lượt 4 nêu đúng hai khác biệt: tài nguyên AWS và đỉnh tên miền; không nói CNAME dùng được ở zone apex.
- Trích đúng VPC Networking Mục 1.9 ở cả bốn lượt; không bịa thêm loại bản ghi hoặc chính sách ngoài tài liệu.

## DV-02 — Tra cứu nối tiếp: Auto Scaling group và cân bằng tải

- **Mã kịch bản:** DV-02
- **Loại:** Tra cứu nối tiếp
- **Mục tiêu:** Kiểm tra chuỗi Auto Scaling: thành phần → loại health check → scaling policy → tích hợp target group và deregistration delay; kiểm tra việc không đồng nhất Auto Scaling với load balancer.
- **Số lượt:** 4
- **Tài liệu:** EC2 Tinh toan — Mục 1.7 (tr.5–6), Mục 1.8 (tr.6–7)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | Auto Scaling group là gì và gồm những thành phần nào? | Giữ nguyên | Trả lời Auto Scaling duy trì số lượng instance mong muốn, tự thêm khi tải tăng và giảm khi tải giảm, trải instance trên nhiều AZ và thay thế instance lỗi; nêu launch template mô tả AMI, instance type, security group, user data, role; Auto Scaling group đặt min/max/desired capacity; scaling policy; cooldown và warm-up; health check EC2 hoặc ELB; lifecycle hook; Auto Scaling không phải load balancer. | EC2 Tinh toan — Mục 1.7 (tr.5–6) |
| 2 | Health check của nó có mấy loại và khác nhau thế nào? | Auto Scaling group có những loại health check nào và health check EC2 khác health check ELB ở điểm nào? | Trả lời có health check EC2 và health check ELB; instance không khỏe bị thay thế tự động; nêu việc bật health check loại ELB để Auto Scaling thay thế instance bị load balancer đánh dấu không khỏe. | EC2 Tinh toan — Mục 1.7 (tr.5–6); Mục 1.8 (tr.6–7) |
| 3 | Vậy muốn giữ CPU quanh 50% thì dùng scaling policy nào? | Muốn giữ mức CPU quanh 50% thì nên dùng loại scaling policy nào của Auto Scaling? | Trả lời target tracking giữ metric ở mức mục tiêu; nêu thêm step scaling, simple scaling, scheduled scaling và predictive scaling; nhắc cooldown/warm-up; đặt min capacity đủ cho tải nền và max capacity đủ cho đỉnh. | EC2 Tinh toan — Mục 1.7 (tr.5–6) |
| 4 | Kết hợp với load balancer thì instance mới đăng ký vào đâu? | Khi kết hợp Auto Scaling với Elastic Load Balancing, instance mới đăng ký vào đâu và cần cấu hình gì để gỡ instance an toàn? | Trả lời instance mới tự động đăng ký vào target group của load balancer khi khỏe; cấu hình deregistration delay để hoàn tất yêu cầu đang xử lý trước khi gỡ instance; load balancer cần ít nhất hai subnet ở hai AZ và Auto Scaling group nên trải trên các subnet đó. | EC2 Tinh toan — Mục 1.7 (tr.5–6); Mục 1.8 (tr.6–7) |

**Tiêu chí đạt:**

- 4/4 lượt đúng; lượt 1 nói rõ Auto Scaling không phải load balancer.
- Lượt 2 phân biệt health check EC2 và health check ELB; nêu instance không khỏe bị thay thế.
- Lượt 3 chọn target tracking cho CPU quanh 50%; nêu cooldown/warm-up.
- Lượt 4 nêu target group, tự đăng ký khi khỏe và deregistration delay; nêu yêu cầu ít nhất hai subnet ở hai AZ.
- Trích đúng Mục 1.7 và Mục 1.8 theo từng lượt.

## DV-03 — Tra cứu nối tiếp: RDS Proxy và quản lý kết nối

- **Mã kịch bản:** DV-03
- **Loại:** Tra cứu nối tiếp
- **Mục tiêu:** Kiểm tra chuỗi RDS Proxy: định nghĩa và pooling → giới hạn (không tăng tốc truy vấn) → tình huống Lambda/serverless → xác thực IAM và failover; chống việc phóng đại khả năng của proxy.
- **Số lượt:** 4
- **Tài liệu:** RDS Aurora — Mục 1.7 (tr.6)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | RDS Proxy là gì và giải quyết vấn đề gì? | Giữ nguyên | Trả lời RDS Proxy là proxy được quản lý đứng giữa ứng dụng và cơ sở dữ liệu, gom và tái sử dụng kết nối; giúp giảm số kết nối mở đồng thời và rút ngắn thời gian failover nhờ giữ kết nối ổn định phía ứng dụng. | RDS Aurora — Mục 1.7 (tr.6) |
| 2 | Nó có làm truy vấn nhanh hơn không? | RDS Proxy có làm từng truy vấn nhanh hơn không? | Trả lời không: RDS Proxy không phải load balancer truy vấn và không tăng tốc từng truy vấn; lợi ích nằm ở connection pooling và failover; một số thao tác đặc biệt có thể khiến proxy ghim kết nối về một instance, giảm hiệu quả pooling. | RDS Aurora — Mục 1.7 (tr.6) |
| 3 | Lambda mở nhiều kết nối ngắn thì proxy giúp thế nào? | RDS Proxy giúp gì khi Lambda mở nhiều kết nối ngắn tới cơ sở dữ liệu? | Trả lời nhờ connection pooling và multiplexing, nhiều kết nối ứng dụng chia sẻ ít kết nối cơ sở dữ liệu; phù hợp với Lambda và ứng dụng serverless; giúp tránh làm cạn connection pool của cơ sở dữ liệu. | RDS Aurora — Mục 1.7 (tr.6) |
| 4 | Xác thực qua proxy dùng IAM được không và failover nhanh hơn bao nhiêu? | RDS Proxy có hỗ trợ xác thực bằng IAM và giảm thời gian failover bao nhiêu? | Trả lời có xác thực bằng IAM hoặc Secrets Manager, giảm việc nhúng mật khẩu trong ứng dụng; failover nhanh hơn tới khoảng 66%; hỗ trợ TLS, kiểm soát truy cập theo người dùng proxy và endpoint riêng cho reader/writer; tính phí theo giờ và theo số vCPU của cơ sở dữ liệu. | RDS Aurora — Mục 1.7 (tr.6) |

**Tiêu chí đạt:**

- 4/4 lượt đúng; lượt 2 trả lời "không" với việc tăng tốc từng truy vấn và nêu proxy không phải load balancer truy vấn.
- Lượt 3 nêu multiplexing, nhiều kết nối ứng dụng chia sẻ ít kết nối cơ sở dữ liệu, phù hợp Lambda/serverless.
- Lượt 4 nêu IAM hoặc Secrets Manager, failover nhanh hơn tới khoảng 66%, TLS và endpoint reader/writer.
- Trích đúng RDS Aurora Mục 1.7; không nói proxy tăng tốc truy vấn hoặc thay thế load balancer.
- Không bịa thêm mức giảm failover khác 66%.

## DV-04 — So sánh: VPC peering và Transit Gateway

- **Mã kịch bản:** DV-04
- **Loại:** So sánh
- **Mục tiêu:** Kiểm tra so sánh xuyên lượt VPC peering và Transit Gateway; các lượt sau dùng "cái nào" nên phải giữ đúng hai đối tượng so sánh; kiểm tra quy tắc chọn theo số lượng VPC và nhu cầu kết nối lai.
- **Số lượt:** 4
- **Tài liệu:** VPC Networking — Mục 1.5 (tr.4–5)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | VPC peering và Transit Gateway khác nhau thế nào? | Giữ nguyên | Lập bảng so sánh tối thiểu 5 tiêu chí: mô hình kết nối (một-một vs hub-and-spoke), định tuyến bắc cầu (không vs có), quy mô (vài VPC vs tới 5.000 attachment), quản lý tài khoản và Region (từng cặp peering vs một Transit Gateway mỗi Region, peering giữa các Transit Gateway, chia sẻ qua AWS RAM), chi phí (truyền dữ liệu, không phí cố định theo giờ vs phí giờ và phí xử lý theo GB), kết nối lai (peering không tập trung vs Transit Gateway nối VPC, VPN, Direct Connect); nêu peering yêu cầu CIDR không chồng lấn và cập nhật route table hai phía. | VPC Networking — Mục 1.5 (tr.4–5) |
| 2 | Cái nào hỗ trợ định tuyến bắc cầu? | VPC peering hay Transit Gateway hỗ trợ định tuyến bắc cầu? | Trả lời Transit Gateway; VPC peering không bắc cầu: nếu A peering B và B peering C thì A không tự động kết nối C; peering chỉ phù hợp kết nối trực tiếp từng cặp. | VPC Networking — Mục 1.5 (tr.4–5) |
| 3 | Tôi có 3 VPC muốn kết nối full mesh thì nên dùng cái nào? | Với 3 VPC cần kết nối full mesh, nên dùng VPC peering hay Transit Gateway? | Trả lời với khoảng 3 VPC và nhu cầu đơn giản, peering tiết kiệm hơn; cần 3 kết nối peering giữa từng cặp và cập nhật route table hai phía; nếu dự kiến tăng số VPC, nhiều tài khoản hoặc cần kết nối lai tập trung thì Transit Gateway giảm độ phức tạp quản lý; không khẳng định peering là lựa chọn duy nhất. | VPC Networking — Mục 1.5 (tr.4–5) |
| 4 | Nếu cần nối on-premises qua Direct Connect cho nhiều VPC thì sao? | Nếu cần nối mạng on-premises qua Direct Connect cho nhiều VPC thì nên dùng VPC peering hay Transit Gateway? | Trả lời Transit Gateway theo mô hình hub-and-spoke, nối VPC, VPN và Direct Connect qua một điểm quản lý; hỗ trợ tới 5.000 attachment mỗi gateway; có route table riêng để tách môi trường production và development; chia sẻ qua AWS RAM; peering một-một không phù hợp làm điểm tập trung cho nhiều VPC và kết nối lai. | VPC Networking — Mục 1.5 (tr.4–5) |

**Tiêu chí đạt:**

- Lượt 1 có bảng so sánh tối thiểu 5 tiêu chí; 4/4 lượt không mâu thuẫn với bảng.
- Lượt 2 nói Transit Gateway bắc cầu, peering không bắc cầu; không nói peering chuyển tiếp qua VPC trung gian.
- Lượt 3 chọn peering cho 3 VPC nhưng nêu điều kiện chuyển sang Transit Gateway khi tăng quy mô; không bỏ ràng buộc chi phí.
- Lượt 4 chọn Transit Gateway cho kết nối lai tập trung; không nói peering nối được Direct Connect cho nhiều VPC.
- Trích đúng VPC Networking Mục 1.5.

## DV-05 — So sánh: CloudFront và Global Accelerator

- **Mã kịch bản:** DV-05
- **Loại:** So sánh
- **Mục tiêu:** Kiểm tra so sánh CDN và tăng tốc mạng; các lượt sau dùng "cái nào" nên phải giữ đúng hai đối tượng; phân biệt cache nội dung với tối ưu tuyến TCP/UDP.
- **Số lượt:** 4
- **Tài liệu:** VPC Networking — Mục 1.10 (tr.8–9)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | CloudFront và Global Accelerator khác nhau ở đâu? | Giữ nguyên | Lập bảng so sánh tối thiểu 4 tiêu chí: bản chất (CDN cache tại hơn 600 điểm hiện diện vs tối ưu tuyến mạng), giao thức (HTTP/HTTPS vs TCP/UDP), địa chỉ IP (không có IP anycast tĩnh vs hai IP anycast tĩnh), cache (có vs không), trường hợp sử dụng (nội dung tĩnh, video, tệp tải về vs game, VoIP, ứng dụng cần IP tĩnh và failover nhanh); nêu có thể kết hợp hai dịch vụ. | VPC Networking — Mục 1.10 (tr.8–9) |
| 2 | Cái nào cache nội dung? | CloudFront hay Global Accelerator có cache nội dung tại biên? | Trả lời CloudFront; Global Accelerator không cache nội dung, chỉ tối ưu tuyến mạng; CloudFront cache nội dung tĩnh và động tại POP gần người dùng. | VPC Networking — Mục 1.10 (tr.8–9) |
| 3 | Ứng dụng game dùng UDP cần IP tĩnh thì chọn cái nào? | Ứng dụng game dùng UDP cần IP tĩnh toàn cầu nên chọn CloudFront hay Global Accelerator? | Trả lời Global Accelerator: hai địa chỉ IP anycast tĩnh, không phụ thuộc Region, xử lý TCP/UDP, health check và failover giữa các endpoint group, điều chỉnh lưu lượng bằng traffic dial; endpoint có thể là ALB, NLB, EC2, Elastic IP; không cache nội dung; CloudFront là CDN HTTP/HTTPS nên không phù hợp với UDP. | VPC Networking — Mục 1.10 (tr.8–9) |
| 4 | Có thể dùng cả hai cùng lúc không? | Có thể kết hợp CloudFront và Global Accelerator trong cùng một kiến trúc không? | Trả lời có; CloudFront cho nội dung tĩnh, video, tệp tải về và giảm tải origin, Global Accelerator cho API hoặc lưu lượng không phải HTTP; hai dịch vụ giải quyết hai bài toán khác nhau, không thay thế nhau. | VPC Networking — Mục 1.10 (tr.8–9) |

**Tiêu chí đạt:**

- Bảng lượt 1 đúng tối thiểu 4 tiêu chí; 4/4 lượt nhất quán.
- Lượt 2 chỉ CloudFront cache; không nói Global Accelerator cache nội dung.
- Lượt 3 chọn Global Accelerator và nêu IP anycast tĩnh cùng TCP/UDP; không chọn CloudFront cho UDP.
- Lượt 4 nêu kết hợp đúng vai trò từng dịch vụ.
- Trích đúng VPC Networking Mục 1.10.

## DV-06 — Nhiều ràng buộc: chọn loại EBS volume

- **Mã kịch bản:** DV-06
- **Loại:** Nhiều ràng buộc
- **Mục tiêu:** Kiểm tra lập bảng ràng buộc trước khi kết luận và cập nhật khi ràng buộc thay đổi; chống W1 (nhảy cóc) và việc bỏ qua giới hạn IOPS của gp3.
- **Số lượt:** 4
- **Tài liệu:** EC2 Tinh toan — Mục 1.4 (tr.3–4), Mục 1.12 (tr.9–10)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | Tôi chạy cơ sở dữ liệu tự quản trên một EC2, cần volume 2 TB đạt 20.000 IOPS, độ trễ thấp, dữ liệu phải còn khi instance stop/start, sao lưu định kỳ và chi phí hợp lý; không cần chia sẻ volume cho nhiều instance. Chọn loại EBS nào? | Giữ nguyên | Lập bảng ràng buộc (IOPS, độ trễ, dung lượng, độ bền dữ liệu, sao lưu, chia sẻ, chi phí); chọn io2 vì yêu cầu 20.000 IOPS vượt mức tối đa 16.000 IOPS của gp3 và cần độ trễ thấp; nêu io2 Block Express đạt tới 256.000 IOPS và 4.000 MiB/s nếu cần cao hơn; EBS tồn tại độc lập với vòng đời instance và sao lưu bằng snapshot lên S3; không cần Multi-Attach. | EC2 Tinh toan — Mục 1.4 (tr.3–4) |
| 2 | Nếu chỉ cần 10.000 IOPS và ngân sách chặt thì sao? | Nếu chỉ cần 10.000 IOPS và ngân sách chặt thì nên chọn loại EBS volume nào? | Cập nhật bảng: gp3 có baseline 3.000 IOPS và 125 MiB/s, tăng tới 16.000 IOPS và 1.000 MiB/s độc lập với dung lượng nên đáp ứng 10.000 IOPS; gp3 là lựa chọn mặc định cho hầu hết khối lượng công việc; chỉ dùng io2 khi cần IOPS rất cao hoặc độ trễ rất thấp; nêu đánh đổi giữa mức IOPS cấp thêm và chi phí, không khẳng định con số giá. | EC2 Tinh toan — Mục 1.4 (tr.3–4) |
| 3 | Volume có tự mất khi stop instance không và có đổi loại khi đang chạy được không? | EBS volume có tự mất khi stop instance không và có thể đổi loại khi đang chạy không? | Trả lời EBS tồn tại độc lập với vòng đời instance, stop/start giữ nguyên EBS; elastic volumes cho phép đổi loại và kích thước khi đang chạy mà không cần dừng instance; volume gắn với một AZ và chỉ gắn được cho instance cùng AZ; snapshot là bản sao tăng dần lưu trong S3, không tự xóa cùng instance, cần Data Lifecycle Manager. | EC2 Tinh toan — Mục 1.4 (tr.3–4); Mục 1.12 (tr.9–10) |
| 4 | Nếu cần gắn cùng volume cho nhiều instance trong cùng AZ thì sao? | Nếu cần gắn cùng một EBS volume cho nhiều instance trong cùng AZ thì dùng tính năng nào và loại volume nào? | Nhận ra ràng buộc "không cần chia sẻ" đã thay đổi; trả lời Multi-Attach cho volume io1/io2 gắn tối đa 16 instance trong cùng AZ, dùng cho ứng dụng cluster cần truy cập khối chia sẻ; không dùng được khác AZ. | EC2 Tinh toan — Mục 1.4 (tr.3–4) |

**Tiêu chí đạt:**

- Lượt 1 có bảng ràng buộc; chọn io2 và nêu đúng giới hạn 16.000 IOPS của gp3.
- Lượt 2 chuyển sang gp3 khi chỉ cần 10.000 IOPS; nêu baseline và mức tối đa; không quay lại io2 vô điều kiện.
- Lượt 3 nêu EBS tồn tại độc lập với instance, elastic volumes, một AZ và snapshot tăng dần.
- Lượt 4 nêu Multi-Attach cho io1/io2, tối đa 16 instance cùng AZ; không nói Multi-Attach xuyên AZ.
- Trích đúng Mục 1.4; lượt 3 có thể thêm Mục 1.12.

## DV-07 — Nhiều ràng buộc: kết nối hybrid on-premises – VPC

- **Mã kịch bản:** DV-07
- **Loại:** Nhiều ràng buộc
- **Mục tiêu:** Kiểm tra lập bảng ràng buộc cho kết nối lai (băng thông, độ trễ, đường truyền, dự phòng, thời gian triển khai, chi phí) và cập nhật khi ràng buộc thay đổi; chống việc chọn Site-to-Site VPN cho yêu cầu 10 Gbps.
- **Số lượt:** 4
- **Tài liệu:** VPC Networking — Mục 1.6 (tr.5), Mục 1.7 (tr.6)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | Công ty có data center cần kết nối tới VPC: băng thông khoảng 10 Gbps, độ trễ thấp và ổn định, không đi qua internet công cộng, phải chịu lỗi khi một đường hỏng, có thể chờ vài tuần để triển khai. Nên chọn giải pháp nào? | Giữ nguyên | Lập bảng ràng buộc; chọn Direct Connect với cổng 10 Gbps (cổng vật lý 1, 10 hoặc 100 Gbps; có thể thuê hosted connection dung lượng nhỏ hơn từ đối tác); nêu đường truyền riêng không qua internet công cộng, băng thông ổn định, độ trễ thấp; thời gian thiết lập vài tuần do kéo cáp vật lý; Site-to-Site VPN mỗi đường hầm tối đa khoảng 1,25 Gbps nên không đủ 10 Gbps; thiết kế hai kết nối ở hai địa điểm để dự phòng. | VPC Networking — Mục 1.7 (tr.6) |
| 2 | Nếu chưa kịp kéo Direct Connect thì tạm dùng gì? | Nếu chưa triển khai được Direct Connect thì tạm thời dùng giải pháp kết nối nào? | Trả lời Site-to-Site VPN qua IPsec trên internet; triển khai trong vài giờ; mỗi kết nối có hai đường hầm tới hai thiết bị biên khác nhau của AWS, nên cấu hình cả hai; băng thông tối đa khoảng 1,25 Gbps mỗi đường hầm; nối tới virtual private gateway hoặc Transit Gateway; định tuyến tĩnh hoặc BGP; phù hợp làm tạm thời hoặc dự phòng cho Direct Connect. | VPC Networking — Mục 1.6 (tr.5); Mục 1.7 (tr.6) |
| 3 | Làm sao thiết kế để không có điểm lỗi đơn? | Thiết kế kết nối Direct Connect chịu lỗi thế nào để tránh điểm lỗi đơn? | Trả lời khuyến nghị tối thiểu hai kết nối Direct Connect tại hai địa điểm khác nhau; nếu chưa có hai kết nối vật lý, dùng Site-to-Site VPN làm đường dự phòng, AWS khuyến nghị mô hình kết hợp này cho hầu hết khách hàng; dùng BGP để tự động chuyển tuyến; LAG gộp nhiều cổng để tăng băng thông; yêu cầu rất cao dùng nhiều kết nối đa địa điểm kèm nhiều VPN dự phòng. | VPC Networking — Mục 1.7 (tr.6) |
| 4 | Direct Connect có mã hóa mặc định không? | Direct Connect có mã hóa dữ liệu mặc định không? | Trả lời không: Direct Connect không được mã hóa mặc định; dùng MACsec lớp 2 trên cổng 10 Gbps và 100 Gbps tại một số địa điểm hoặc VPN trên Direct Connect nếu cần mã hóa; nêu chi phí gồm phí cổng theo giờ, phí truyền dữ liệu ra ngoài và phí đối tác; MTU tới 9001 byte với jumbo frame cần cấu hình thiết bị on-premises. | VPC Networking — Mục 1.7 (tr.6) |

**Tiêu chí đạt:**

- Lượt 1 có bảng ràng buộc; chọn Direct Connect 10 Gbps, không chọn Site-to-Site VPN làm giải pháp chính cho 10 Gbps.
- Lượt 2 nêu VPN triển khai trong vài giờ, tối đa khoảng 1,25 Gbps mỗi đường hầm và hai đường hầm.
- Lượt 3 nêu hai kết nối ở hai địa điểm, VPN dự phòng và BGP; không nói LAG thay thế dự phòng đa địa điểm.
- Lượt 4 nói Direct Connect không mã hóa mặc định; nêu MACsec hoặc VPN trên Direct Connect.
- Trích đúng Mục 1.7; lượt 2 có thể thêm Mục 1.6.

## DV-08 — Đổi chủ đề giữa chừng: từ VPC endpoint sang Aurora Serverless v2

- **Mã kịch bản:** DV-08
- **Loại:** Đổi chủ đề giữa chừng
- **Mục tiêu:** Kiểm tra phát hiện đổi chủ đề và reset ngữ cảnh; câu hỏi mới về Aurora Serverless v2 không được viết lại bằng từ khóa VPC, endpoint, S3 hay NAT.
- **Số lượt:** 4
- **Tài liệu:** VPC Networking — Mục 1.8 (tr.6–7); RDS Aurora — Mục 1.5 (tr.4–5)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | Gateway endpoint khác interface endpoint ở điểm nào? | Giữ nguyên | So sánh: gateway endpoint chỉ hỗ trợ S3 và DynamoDB, gắn vào route table, không tính phí theo giờ và không tính phí xử lý dữ liệu; interface endpoint dựa trên PrivateLink, tạo ENI trong subnet, hỗ trợ hầu hết dịch vụ AWS và dịch vụ bên thứ ba, tính phí theo giờ và theo GB, có thể bật Private DNS; endpoint không có tính bắc cầu. | VPC Networking — Mục 1.8 (tr.6–7) |
| 2 | Truy cập S3 từ subnet private nên dùng loại nào để tiết kiệm? | Truy cập Amazon S3 từ subnet private nên dùng gateway endpoint hay interface endpoint để tiết kiệm chi phí? | Trả lời gateway endpoint: chỉ hỗ trợ S3/DynamoDB, không phí theo giờ, không phí xử lý dữ liệu, lưu lượng đi theo tuyến endpoint thay vì NAT gateway; interface endpoint tính phí theo giờ và theo GB; có thể dùng endpoint policy giới hạn bucket. | VPC Networking — Mục 1.8 (tr.6–7) |
| 3 | Đổi chủ đề: Aurora Serverless v2 tính phí thế nào? | Aurora Serverless v2 tính phí như thế nào? | Phát hiện đổi chủ đề; trả lời tính theo ACU-giây trong khoảng min/max, mỗi ACU xấp xỉ 2 GiB bộ nhớ kèm CPU và mạng, min 0,5 ACU và max 128 ACU mỗi instance, co giãn theo bước 0,5 ACU dựa trên CPU, bộ nhớ và tải kết nối, không cần dừng cụm; phù hợp môi trường phát triển, thử nghiệm và tải biến động; không nhắc VPC, endpoint, S3 hay NAT. | RDS Aurora — Mục 1.5 (tr.4–5) |
| 4 | Vậy tải đều 24/7 thì có nên dùng không? | Với tải đều chạy 24/7, có nên dùng Aurora Serverless v2 không? | Trả lời Serverless v2 không phải lựa chọn mặc định cho tải ổn định cao; với tải đều, instance provisioned kèm Reserved Instance thường rẻ hơn; vẫn cần đặt max ACU đủ cao cho đỉnh tải; Serverless v2 phù hợp môi trường không chạy 24/7 hoặc tải dao động mạnh; có thể nêu các đòn bẩy chi phí Aurora. | RDS Aurora — Mục 1.5 (tr.4–5) |

**Tiêu chí đạt:**

- Lượt 3 nhận diện đổi chủ đề; câu viết lại không chứa "VPC", "endpoint", "S3", "NAT", "PrivateLink".
- Trích dẫn lượt 3–4 chỉ từ RDS Aurora Mục 1.5; không có VPC Networking.
- Lượt 3 nêu ACU, phạm vi 0,5–128, bước 0,5 ACU và tính phí theo ACU-giây.
- Lượt 4 nói provisioned + Reserved Instance thường rẻ hơn cho tải đều 24/7; không nói Serverless v2 luôn rẻ hơn.
- 4/4 lượt đúng; hai lượt đầu trả lời đúng VPC endpoint và có trích dẫn Mục 1.8.

## DV-09 — Người dùng hỏi lại làm rõ: permission boundary và Service Control Policy

- **Mã kịch bản:** DV-09
- **Loại:** Người dùng hỏi lại làm rõ
- **Mục tiêu:** Kiểm tra người dùng hỏi lại để làm rõ câu trả lời trước; chatbot phải giải thích lại đúng trọng tâm permission boundary, giữ ngữ cảnh và phân biệt với SCP.
- **Số lượt:** 4
- **Tài liệu:** IAM — Mục 1.7 (tr.6)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | Permission boundary là gì? | Giữ nguyên | Trả lời boundary đặt giới hạn tối đa cho quyền của user hoặc role; quyền hiệu lực là giao của identity policy và boundary; boundary không cấp quyền, chỉ giới hạn; không áp dụng cho resource-based policy hoặc tài khoản root; hữu ích khi cho phép đội ngũ tự tạo role nhưng không vượt quá giới hạn. | IAM — Mục 1.7 (tr.6) |
| 2 | Ý bạn là nó không cấp quyền mà chỉ giới hạn? Vậy khác SCP ở đâu? | Permission boundary chỉ giới hạn quyền còn Service Control Policy khác ở điểm nào? | Xác nhận đúng: boundary không cấp quyền, chỉ giới hạn; boundary gắn với user hoặc role; SCP áp dụng ở cấp Organizations, gắn với account hoặc OU, giới hạn quyền tối đa cho mọi principal trong tài khoản thành viên; SCP không áp dụng cho management account và không cấp quyền; nêu ví dụ SCP chặn xóa CloudTrail, chặn Region ngoài danh sách hoặc chặn tài nguyên không mã hóa. | IAM — Mục 1.7 (tr.6) |
| 3 | Vậy nếu cả hai cùng áp thì quyền hiệu lực tính sao? | Khi permission boundary và SCP cùng áp dụng, quyền hiệu lực được xác định thế nào? | Trả lời identity policy phải cho phép; permission boundary giới hạn bằng giao với identity policy; SCP giới hạn trần quyền ở cấp tài khoản/OU; một hành động chỉ được phép khi không vượt qua bất kỳ lớp nào; nêu mẫu kết hợp SCP, boundary và identity policy để kiểm soát nhiều lớp; nhắc boundary không áp dụng cho resource-based policy. | IAM — Mục 1.7 (tr.6) |
| 4 | Có thể dùng boundary để chặn root của tài khoản thành viên không? | Permission boundary có chặn được tài khoản root của tài khoản thành viên không? | Trả lời không: permission boundary không áp dụng cho tài khoản root; SCP áp dụng cho tài khoản thành viên và không áp dụng cho management account; dùng SCP để chặn hành động như xóa CloudTrail, dùng Region ngoài danh sách hoặc tạo tài nguyên không mã hóa. | IAM — Mục 1.7 (tr.6) |

**Tiêu chí đạt:**

- Lượt 2 là câu hỏi lại làm rõ; chatbot xác nhận "đúng, boundary không cấp quyền" và phân biệt phạm vi boundary với SCP, không lái sang dịch vụ khác.
- Không nói permission boundary cấp quyền hoặc áp dụng cho tài khoản root.
- Lượt 3 nêu nhiều lớp kiểm soát và giao quyền; không bịa thứ tự ưu tiên ngoài tài liệu.
- Lượt 4 phân biệt boundary không áp dụng cho root, SCP áp dụng cho tài khoản thành viên và không áp dụng cho management account.
- Trích đúng IAM Mục 1.7.

## DV-10 — Hỏi ngoài phạm vi giữa hội thoại EC2

- **Mã kịch bản:** DV-10
- **Loại:** Hỏi ngoài phạm vi
- **Mục tiêu:** Kiểm tra từ chối đúng hai loại ngoài phạm vi (ngoài lĩnh vực AWS và dịch vụ AWS không có trong kho) giữa một hội thoại đang đúng chủ đề; sau đó quay lại được.
- **Số lượt:** 4
- **Tài liệu:** EC2 Tinh toan — Mục 1.6 (tr.5); đối chiếu `inputs/out_of_scope_questions.md` (OOS-A3, OOS-B4)

| Lượt | Câu hỏi người dùng | Câu viết lại kỳ vọng | Hành vi mong đợi | Căn cứ |
| :---: | :--- | :--- | :--- | :--- |
| 1 | Cluster placement group phù hợp với loại workload nào? | Giữ nguyên | Trả lời cluster đặt các instance gần nhau trong cùng AZ, độ trễ mạng thấp và thông lượng cao; phù hợp HPC và tính toán song song; rủi ro là cùng một điểm lỗi; không thể di chuyển instance đang chạy vào placement group, phải stop rồi chỉnh hoặc tạo lại. | EC2 Tinh toan — Mục 1.6 (tr.5) |
| 2 | Phân biệt INNER JOIN và LEFT JOIN trong SQL, cho ví dụ ngắn. | Giữ nguyên | Từ chối: ngoài phạm vi hỗ trợ vì không phải nội dung ôn thi SAA trong kho; không viết truy vấn SQL, không giải thích NULL hay kết quả join; có thể mời quay lại câu hỏi AWS SAA. | Không trích dẫn |
| 3 | Vậy AWS Clean Rooms là gì? | AWS Clean Rooms là dịch vụ gì? | Từ chối đúng loại "không có trong tài liệu": nói 7 tài liệu không chứa Clean Rooms; không mô tả phân tích dữ liệu liên tổ chức, cộng tác dữ liệu, kiểm soát quyền riêng tư hay tính năng của dịch vụ; không trích dẫn. | Không trích dẫn |
| 4 | Quay lại EC2: spread placement group tối đa bao nhiêu instance mỗi AZ? | Spread placement group cho phép tối đa bao nhiêu instance mỗi AZ? | Trả lời tối đa 7 instance mỗi AZ, đặt trên các máy chủ vật lý khác nhau; phù hợp ứng dụng nhỏ cần độ sẵn sàng cao; không nhầm với partition placement group tối đa 7 phân vùng mỗi AZ; trả lời đúng ngữ cảnh EC2 sau hai lượt ngoài phạm vi. | EC2 Tinh toan — Mục 1.6 (tr.5) |

**Tiêu chí đạt:**

- Lượt 2 không có truy vấn SQL, không có từ khóa INNER JOIN, LEFT JOIN, NULL; `abstained = true`, lý do ngoài phạm vi.
- Lượt 3 không có mô tả tính năng Clean Rooms; `abstained = true`, lý do không có trong tài liệu.
- Lượt 2–3 không có citations.
- Lượt 4 trả lời đúng 7 instance mỗi AZ và có trích dẫn; chứng minh hội thoại phục hồi sau khi từ chối.
- Không dùng các dịch vụ đã có trong kho (Comprehend, Polly, Rekognition, IoT Core, Braket) làm câu ngoài phạm vi.

## Bảng tổng hợp chấm điểm

| Mã | Loại | Số lượt | Đạt | Lỗi chính (condensation / retrieval / generation / streaming) |
| :--- | :--- | :---: | :---: | :--- |
| DV-01 | Tra cứu nối tiếp | 4 | | |
| DV-02 | Tra cứu nối tiếp | 4 | | |
| DV-03 | Tra cứu nối tiếp | 4 | | |
| DV-04 | So sánh | 4 | | |
| DV-05 | So sánh | 4 | | |
| DV-06 | Nhiều ràng buộc | 4 | | |
| DV-07 | Nhiều ràng buộc | 4 | | |
| DV-08 | Đổi chủ đề giữa chừng | 4 | | |
| DV-09 | Người dùng hỏi lại làm rõ | 4 | | |
| DV-10 | Hỏi ngoài phạm vi | 4 | | |

**Tổng số kịch bản đạt:** ___ / 10.

## Ghi chú khi sử dụng

- Đây là kịch bản kiểm thử hành vi hội thoại, không phải prompt huấn luyện. Không đưa nội dung cột "Hành vi mong đợi" vào ngữ cảnh gửi mô hình.
- Bộ dev dùng mã `DV-*`; script chấm hiện tại đọc `inputs/conversations.md` và mã `KB-*`, nên khi chạy bộ dev cần trỏ script sang tệp này, cho phép mã `DV-*` và bổ sung kiểm tra tự động riêng nếu muốn.
- Không sửa kịch bản giữa các lần chạy khi đang so sánh cấu hình; nếu sửa, ghi phiên bản và chạy lại cả hai cấu hình.
- Với mỗi lượt không đạt, lưu `session_id`, số lượt, `rewritten_query`, danh sách chunk truy xuất và câu trả lời để phân tích nguyên nhân.
- Các kịch bản này không thay thế bộ test ngoại kho ≥ 150 câu của Giai đoạn 6; chúng chỉ đo hành vi nhiều lượt, condensation và từ chối ở giai đoạn phát triển.
