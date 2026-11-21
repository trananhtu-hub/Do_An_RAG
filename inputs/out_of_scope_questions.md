# Câu hỏi ngoài phạm vi — Giai đoạn 3

Tệp này gồm 10 câu hỏi dùng để kiểm tra hành vi từ chối đúng của chatbot ở Giai đoạn 3 (chỉ tiêu "Từ chối đúng ≥ 90%" trong bảng kiểm Giai đoạn 3). Có hai nhóm, mỗi nhóm 5 câu:

- **Nhóm A — Ngoài lĩnh vực AWS:** câu hỏi về kiến thức lập trình, mạng máy tính, cơ sở dữ liệu, công cụ phát triển không thuộc nội dung kho tri thức.
- **Nhóm B — Dịch vụ AWS không có trong kho tri thức:** dịch vụ AWS có thật nhưng không xuất hiện trong 7 tài liệu của `data/raw/`.

## Căn cứ xác định nhóm B

Đã đối chiếu toàn văn 7 tệp PDF trong `data/raw/` ngày 2026-11-21: các tên Amazon Bedrock, AWS CodeWhisperer, AWS HealthImaging, AWS Clean Rooms và AWS Verified Access (kể cả biến thể Health Imaging, Clean Room, Code Whisperer) đều không xuất hiện. Vì vậy kho tri thức không thể mô tả các dịch vụ này.

Không thay bằng các dịch vụ từng được cân nhắc nhưng đã có trong kho: Amazon Comprehend, Amazon Polly, Amazon Rekognition, AWS IoT Core, Amazon Braket. Các tên này xuất hiện trong toàn văn tài liệu (chủ yếu ở ngân hàng câu hỏi và exam guide), nên câu hỏi về chúng không còn là "không có trong kho tri thức".

## Nhóm A — Ngoài lĩnh vực AWS

| ID | Câu hỏi | Vì sao ngoài phạm vi | Lý do từ chối đúng | Dấu hiệu trả lời sai |
| :--- | :--- | :--- | :--- | :--- |
| OOS-A1 | Phân biệt list và tuple trong Python. Khi nào nên dùng tuple thay vì list? | Kiến thức lập trình Python, không thuộc nội dung 7 tài liệu AWS | Ngoài phạm vi | Giải thích tính mutable/immutable, đưa ví dụ code Python |
| OOS-A2 | TCP khác UDP ở những điểm nào và mỗi giao thức phù hợp với loại ứng dụng nào? | Kiến thức mạng máy tính cơ bản, không thuộc nội dung kho tri thức | Ngoài phạm vi | Nêu bắt tay ba bước, đặc điểm giao vận tin cậy, ví dụ ứng dụng |
| OOS-A3 | Phân biệt INNER JOIN và LEFT JOIN trong SQL, cho ví dụ ngắn. | Kiến thức cơ sở dữ liệu quan hệ, không thuộc nội dung kho tri thức | Ngoài phạm vi | Viết truy vấn SQL và giải thích kết quả NULL |
| OOS-A4 | Khi nào nên dùng git rebase thay vì git merge? | Kiến thức công cụ quản lý mã nguồn, không thuộc nội dung kho tri thức | Ngoài phạm vi | Hướng dẫn lệnh git, giải thích lịch sử commit |
| OOS-A5 | Mô hình OSI có bao nhiêu tầng? Nêu chức năng chính của tầng giao vận. | Kiến thức mạng máy tính cơ bản, không thuộc nội dung kho tri thức | Ngoài phạm vi | Liệt kê 7 tầng và chức năng từng tầng |

## Nhóm B — Dịch vụ AWS không có trong kho tri thức

| ID | Câu hỏi | Vì sao ngoài phạm vi | Lý do từ chối đúng | Dấu hiệu trả lời sai |
| :--- | :--- | :--- | :--- | :--- |
| OOS-B1 | Amazon Bedrock là gì và hỗ trợ những mô hình nền tảng (foundation model) nào? | Dịch vụ AWS không xuất hiện trong 7 tài liệu | Không có trong tài liệu | Nêu tên các mô hình nền tảng, giá hoặc tính năng của Bedrock |
| OOS-B2 | AWS CodeWhisperer hoạt động như thế nào và hỗ trợ những ngôn ngữ lập trình nào? | Dịch vụ AWS không xuất hiện trong 7 tài liệu | Không có trong tài liệu | Mô tả tính năng gợi ý mã, danh sách ngôn ngữ hỗ trợ |
| OOS-B3 | AWS HealthImaging là dịch vụ gì và dùng cho những trường hợp nào? | Dịch vụ AWS không xuất hiện trong 7 tài liệu | Không có trong tài liệu | Mô tả lưu trữ ảnh y tế, metadata, tích hợp dịch vụ y tế |
| OOS-B4 | AWS Clean Rooms là gì và giải quyết bài toán gì khi nhiều tổ chức cần phân tích dữ liệu chung? | Dịch vụ AWS không xuất hiện trong 7 tài liệu | Không có trong tài liệu | Mô tả phân tích dữ liệu liên tổ chức, kiểm soát quyền truy cập dữ liệu |
| OOS-B5 | AWS Verified Access là gì và thay thế mô hình VPN truyền thống như thế nào? | Dịch vụ AWS không xuất hiện trong 7 tài liệu | Không có trong tài liệu | Mô tả chính sách truy cập ứng dụng, thay thế VPN |

## Cách chạy và chấm

1. Gửi từng câu độc lập vào chatbot, không kèm ngữ cảnh hội thoại và không gợi ý đáp án.
2. Một câu đạt khi đồng thời: `abstained = true`; câu trả lời nói rõ không có nội dung trong kho tài liệu (nhóm B) hoặc ngoài phạm vi hỗ trợ (nhóm A); không có `citations` trỏ tới chunk không chứa nội dung được nêu; không đưa chi tiết kỹ thuật của dịch vụ hoặc chủ đề được hỏi.
3. Một câu không đạt nếu trả lời bằng kiến thức nền, kể cả khi nội dung đó đúng bên ngoài kho tài liệu, hoặc trích dẫn tài liệu/trang không chứa thông tin tương ứng.
4. Mục tiêu là 10/10 câu đạt. Với câu không đạt, ghi lại ID, câu trả lời và các chunk được truy xuất để phân tích nguyên nhân (retrieval kéo nhầm chunk hay prompt không đủ ràng buộc từ chối).

Lưu ý: 10 câu này chỉ đo "từ chối đúng" (correct refusal). Không dùng chúng để đo "từ chối sai" (wrong refusal); chỉ tiêu từ chối sai ≤ 5% phải đo trên các câu hỏi nằm trong phạm vi kho tri thức.
