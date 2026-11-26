# BÁO CÁO GIAI ĐOẠN 5

Trạng thái: MỘT PHẦN

- **Ngày hoàn tất kiểm thử:** 2026-11-24
- **Nhánh làm việc:** `phase4-fix`
- **Phạm vi:** giao diện MVP 5 màn hình, xác thực Supabase, kiểm thử E2E và tài liệu chạy frontend.
- **Quy ước đánh số:** báo cáo dùng cách đánh số của đề bài đồ án, theo đó Giai đoạn 5 là giao diện MVP. Trong `CLAUDE.md`, phần này tương ứng với mục “Giai đoạn 7 — giao diện chat hoàn chỉnh”.
- **Bằng chứng thô:** toàn bộ log, báo cáo Lighthouse và ảnh chụp màn hình nằm trong `docs/evidence/phase-5/`.

Lý do trạng thái MỘT PHẦN: toàn bộ hạng mục kỹ thuật và kiểm thử tự động đã đạt, nhưng UAT với 3–5 người chưa được tổ chức. Không có điểm UAT nào được ghi nhận hay suy diễn trong báo cáo này.

## 1. Việc đã làm

### 1.1. Nguyên tắc thực hiện

- Giữ nguyên hợp đồng API đã có cho chat, phiên hội thoại và `/health`; chỉ bổ sung endpoint mới cho quiz, quản trị và tài liệu theo phương án “mở rộng backend tối thiểu” đã được duyệt.
- Không dùng thư viện UI nặng; giao diện dựng bằng Tailwind CSS 4 và component nội bộ.
- Phiên đăng nhập dùng cookie của `@supabase/ssr`; không lưu token Supabase trong `localStorage`.
- Toàn bộ chuỗi giao diện bằng tiếng Việt có dấu; bố cục dùng được trên máy tính và màn hình nhỏ.
- Logo lấy từ `frontend/public/logo.png`; màu chính `#1F4E79`, màu phụ `#F2F2F2`; phông Inter có bộ ký tự tiếng Việt.

### 1.2. Backend

Bổ sung các router mới, có xác thực Supabase cho mọi tuyến:

| Nhóm | Endpoint | Chức năng |
| :--- | :--- | :--- |
| Quiz | `GET /quiz/domains` | Số câu khả dụng theo 4 lĩnh vực blueprint |
| Quiz | `POST /quiz/questions` | Lấy ngẫu nhiên 5/10/15/20 câu, không trả đáp án |
| Quiz | `POST /quiz/submit` | Chấm điểm, trả đáp án đúng và giải thích, lưu lượt làm bài |
| Quiz | `GET /quiz/attempts` | Lịch sử làm bài của người dùng hiện tại |
| Quiz | `DELETE /quiz/attempts` | Xóa toàn bộ lịch sử làm bài của người dùng hiện tại |
| Quản trị | `GET /admin/stats` | Thống kê tổng hợp và theo ngày, chỉ quản trị viên |
| Tài liệu | `GET /documents` | Danh mục tài liệu trong kho tri thức |
| Tài liệu | `GET /documents/{id}/file` | Trả PDF gốc để mở đúng trang trích dẫn |

Chi tiết chính:

- **Quiz:** chỉ chọn câu có đủ 4 phương án và `correct_answer` xác định; phương án được xáo trộn trước khi trả về; đáp án đúng không xuất hiện trong `POST /quiz/questions`. Lĩnh vực lấy từ bảng `questions`; nhãn tiếng Việt cho Secure, Resilient, High-Performing, Cost-Optimized.
- **Lưu lịch sử làm bài:** migration `supabase/migrations/20261124000000_quiz_phase5.sql` tạo bảng `public.quiz_attempts`, bật RLS và mặc định đóng; backend truy cập bằng khóa máy chủ theo quy tắc bất biến số 3.
- **Quản trị:** `ADMIN_EMAILS` là danh sách email phân tách bằng dấu phẩy; `GET /admin/stats` trả 403 `admin_required` với tài khoản học viên. Số liệu gồm số câu hỏi, tài liệu, chunk, phiên, lượt hỏi, chi phí ước tính, tỷ lệ từ chối, tỷ lệ lỗi, độ trễ p50/p95 và TTFT p95; kèm chuỗi điểm theo ngày.
- **Tài liệu:** danh mục dùng cho chip trích dẫn; endpoint tệp trả `application/pdf` dạng inline, có kiểm tra UUID và trả 404 khi không tìm thấy.
- **Ổn định kết nối:** bổ sung kiểm tra `SELECT 1` sau 30 giây nhàn rỗi trong `backend/app/services/sessions/pool.py` để thay kết nối PostgreSQL đã bị máy chủ đóng. Đây là sửa lỗi nội bộ, không đổi hợp đồng API; có 3 unit test mới trong `backend/tests/test_session_pool.py`.
- **Kiểm thử backend mới:** `backend/tests/test_quiz.py`, `backend/tests/test_admin_access.py`, `backend/tests/test_session_pool.py`.

Không thay đổi cấu trúc phản hồi của các endpoint chat/session hiện có.

### 1.3. Frontend

Khung và xác thực:

- Next.js App Router + TypeScript strict, Tailwind CSS 4, PostCSS, Inter bằng `next/font` với subset `latin` và `vietnamese`.
- Supabase Auth email/mật khẩu qua `@supabase/ssr`; `proxy.ts` làm mới phiên và chuyển người chưa đăng nhập về `/login?next=...`.
- `AuthProvider` giữ trạng thái đăng nhập; email và vai trò hiển thị ở góc trên bên phải (“Quản trị viên” hoặc “Đã đăng nhập”).
- Không có token Supabase trong `localStorage`; chỉ tùy chọn giao diện (chế độ trả lời, ngôn ngữ, mô hình) được lưu cục bộ.

Năm màn hình:

| Màn hình | Chức năng đã làm |
| :--- | :--- |
| `/chat` | Khung chat, gửi câu hỏi, streaming SSE, nút dừng tạo câu trả lời, chip trích dẫn bấm được, xem PDF đúng trang, hai chế độ “Trả lời nhanh” và “Giải thích từng bước”, chọn ngôn ngữ trả lời, trạng thái tải/rỗng/lỗi |
| `/quiz` | Chọn lĩnh vực và số câu (5/10/15/20), tiến độ trả lời, nộp bài có xác nhận, điểm và giải thích từng câu, lịch sử làm bài |
| `/history` | Danh sách phiên, tìm theo tiêu đề, đổi tên, xóa có xác nhận, trạng thái rỗng, liên kết mở lại phiên |
| `/settings` | Mô hình, chế độ trả lời, ngôn ngữ; lưu tùy chọn; xóa toàn bộ phiên, tin nhắn, lịch sử làm bài và tùy chọn với hộp thoại xác nhận |
| `/admin` | Chặn tài khoản học viên; hiển thị số câu hỏi, lượt hỏi, chi phí ước tính, tỷ lệ từ chối, độ trễ p95, TTFT p95 và hoạt động theo ngày |

Nội dung và an toàn:

- Markdown dùng `react-markdown` + `remark-gfm` + `rehype-sanitize`; không bật `rehype-raw`, không render HTML thô. Liên kết nguy hiểm và thẻ `script` bị vô hiệu hóa.
- Chip trích dẫn tải PDF qua endpoint tài liệu, mở bằng blob URL kèm `#page=N`. Nếu trích dẫn chỉ có nguồn mà không có đoạn trích, hộp thoại hiển thị thông báo thay vì khối trích rỗng.
- Nút dừng hủy luồng SSE và giữ phần câu trả lời đã nhận.
- Biểu mẫu, hộp thoại và điều hướng có nhãn tiếng Việt; điều hướng đáy màn hình cho di động.

Kiểm thử giao diện:

- `frontend/e2e/global-setup.ts` tạo hoặc đặt lại tài khoản thử nghiệm bằng `SUPABASE_SERVICE_ROLE_KEY`, lưu phiên vào `frontend/e2e/.auth/` (không commit).
- `frontend/e2e/phase5.spec.ts` kiểm tra đăng nhập, hỏi đáp có streaming và trích dẫn, luyện đề 5 câu, tìm/đổi tên/xóa phiên, chặn quyền quản trị.
- `frontend/e2e/sanitize.spec.ts` kiểm tra Markdown chứa thẻ `script` và liên kết nguy hiểm.
- `frontend/playwright.config.ts` chạy setup, Chromium, Firefox, WebKit; một worker; lưu bằng chứng ngoài thư mục bị Playwright xóa.

Tài liệu:

- `README.md` mô tả kiến trúc, yêu cầu, cài đặt, biến môi trường, các màn hình, lệnh lint/test/build/E2E và cách xử lý lỗi Firefox trên Windows bằng `PLAYWRIGHT_BROWSERS_PATH`.

### 1.4. Đối chiếu 13 nhược điểm W1–W13

| Mã | Trạng thái sau Giai đoạn 5 | Ghi chú |
| :--- | :--- | :--- |
| W1 | Đang xử lý | Giao diện có chế độ “Giải thích từng bước”, nhưng chất lượng suy luận K3 vẫn thuộc tầng sinh và đánh giá Giai đoạn 8 |
| W2 | Chưa xử lý | Không thuộc phạm vi giao diện |
| W3 | Chưa xử lý | Top-k thích ứng thuộc tầng truy xuất |
| W4 | Đang xử lý | UI đã nối session và hiển thị lịch sử; chất lượng viết lại câu hỏi vẫn là hạng mục riêng |
| W5 | Một phần | Đã có streaming SSE và nút dừng; độ trễ TTFT/tổng vẫn chưa đạt chỉ tiêu Giai đoạn 4 |
| W6 | Chưa xử lý | Bộ đánh giá và độ đo thuộc Giai đoạn 2/8 |
| W7 | Chưa xử lý | Tìm kiếm Việt–Anh và reranker thuộc tầng truy xuất |
| W8 | Một phần | Trang quản trị có tỷ lệ từ chối, tỷ lệ lỗi và độ trễ; chưa có phân tích nhóm lỗi |
| W9 | Một phần | Có danh mục và trình xem tài liệu gốc; chưa có version index |
| W10 | Chưa xử lý | Cấu hình vector-only và ablation thuộc Giai đoạn 4 |
| W11 | Chưa xử lý | Kiểm định thống kê thuộc Giai đoạn 8 |
| W12 | Chưa xử lý | Cách gọi `ts_rank` thuộc tầng truy xuất |
| W13 | Chưa xử lý | Câu hỏi tự biên soạn và đóng băng tập test thuộc Giai đoạn 2/8 |

## 2. Kết quả kiểm thử (Hạng mục | Lệnh | Kỳ vọng | Thực tế | Đạt)

| Hạng mục | Lệnh | Kỳ vọng | Thực tế | Đạt |
| :--- | :--- | :--- | :--- | :---: |
| Kiểm thử backend | `make -f ./Makefile test` | Toàn bộ pytest đạt | 305 passed, 1 warning, 7,82 giây | Đạt |
| Lint backend và frontend | `make -f ./Makefile lint` | ruff, black và ESLint sạch | ruff passed; black 146 tệp không đổi; ESLint không lỗi | Đạt |
| Build production | `npm --prefix frontend run build` | Build thành công, không lỗi TypeScript | Compiled 622 ms; TypeScript 1.938 ms; 8 tuyến static; có Proxy middleware | Đạt |
| E2E ba trình duyệt | `PLAYWRIGHT_BROWSERS_PATH=D:/playwright-browsers npx playwright test` | Toàn bộ kịch bản đạt trên Chromium, Firefox, WebKit | 16 passed, 1,1 phút | Đạt |
| Sanitize Markdown | nằm trong lệnh E2E trên | Thẻ `script` không chạy; liên kết `javascript:` không bấm được | Đạt trên cả 3 trình duyệt | Đạt |
| Kiểm tra thủ công 5 màn hình | Kịch bản thủ công, ảnh tại `docs/evidence/phase-5/manual/` | 5 màn hình có đủ trạng thái và chức năng MVP | 23/23 PASS; `TẤT CẢ ĐẠT` | Đạt |
| Tràn ngang trên di động | Kiểm tra thủ công 5 màn hình ở cửa sổ hẹp | `overflow = 0` | 5/5 màn hình `overflow = 0` | Đạt |
| Lighthouse `/login` lần đầu | `npx -y lighthouse http://localhost:3000/login ...` | Performance ≥ 80; Accessibility ≥ 90 | Performance 93; Accessibility 100; LCP 3,2 giây; CLS 0 | Đạt |
| Lighthouse `/login` lần lặp | Lặp lệnh trên sau khi máy chủ ấm | Performance ≥ 80; Accessibility ≥ 90 | Performance 93; Accessibility 100; LCP 3,2 giây; CLS 0 | Đạt |
| Lighthouse `/chat` có đăng nhập | Lighthouse với cookie phiên thử nghiệm | Performance ≥ 80; Accessibility ≥ 90 | Performance 88; Accessibility 100; LCP 3,9 giây; CLS 0 | Đạt |
| Sức khỏe backend | `curl http://localhost:8000/health` | HTTP 200 | HTTP 200 | Đạt |

Ghi chú về lệnh: trong Git Bash của máy kiểm thử, `make test` và `make lint` không tìm thấy Makefile nếu không chỉ định `-f ./Makefile`; lệnh có `-f` cho kết quả đúng. Đây là khác biệt môi trường, không phải lỗi mã nguồn.

### 2.1. Kiểm tra thủ công 5 màn hình

| Màn hình | Kỳ vọng | Thực tế | Đạt |
| :--- | :--- | :--- | :---: |
| `/chat` | Hai chế độ trả lời, ô câu hỏi, gửi, streaming, dừng, trích dẫn, trạng thái lỗi khi thiếu tùy chọn | Đủ các thành phần; streaming và dừng hoạt động; chip trích dẫn mở PDF | Đạt |
| `/quiz` | Chọn lĩnh vực, chọn 5 câu, bắt đầu làm bài, nộp bài, xem điểm và giải thích | Chọn được 5 câu và bắt đầu; nộp bài lưu lịch sử | Đạt |
| `/history` | Ô tìm kiếm, danh sách phiên, đổi tên, xóa, trạng thái rỗng | Tìm, đổi tên và xóa hoạt động; trạng thái rỗng sau khi xóa dữ liệu | Đạt |
| `/settings` | Mô hình, chế độ, ngôn ngữ; lưu sau khi tải lại; xóa toàn bộ dữ liệu có xác nhận | Tùy chọn được giữ; xóa dữ liệu đưa về mặc định | Đạt |
| `/admin` | Chỉ quản trị viên; đủ thẻ số liệu và hoạt động theo ngày; học viên bị chặn | Thẻ “Câu hỏi trong kho”, “Chi phí ước tính”, “Tỷ lệ từ chối”, “Độ trễ phản hồi p95”, “TTFT p95” hiển thị; học viên thấy thông báo không có quyền | Đạt |

Kiểm tra quản trị viên dương tính được thực hiện bằng cách tạm thêm email thử nghiệm vào `ADMIN_EMAILS`, sau đó khôi phục cấu hình ban đầu. Không có tài khoản quản trị thường trực nào được tạo trong mã nguồn hay trong bộ E2E.

## 3. Kết quả E2E (Kịch bản | Chromium | Firefox | WebKit)

| Kịch bản | Chromium | Firefox | WebKit |
| :--- | :--- | :--- | :--- |
| Đăng nhập tài khoản thử nghiệm và lưu phiên | Đạt (setup, 2,2 giây) | Đạt (dùng phiên setup) | Đạt (dùng phiên setup) |
| Hỏi đáp: nhận câu trả lời trực tiếp và mở trích dẫn PDF | Đạt (12,5 giây) | Đạt (15,6 giây) | Đạt (12,8 giây) |
| Luyện đề: làm 5 câu, nhận kết quả và lưu lịch sử | Đạt (2,8 giây) | Đạt (3,1 giây) | Đạt (3,6 giây) |
| Lịch sử: tìm, đổi tên và xóa cuộc trò chuyện vừa tạo | Đạt (1,6 giây) | Đạt (1,6 giây) | Đạt (2,5 giây) |
| Quản trị: tài khoản học viên không vào được trang quản trị | Đạt (442 ms) | Đạt (585 ms) | Đạt (774 ms) |
| Sanitize: Markdown chứa thẻ `script` và liên kết nguy hiểm không được thực thi | Đạt (501 ms) | Đạt (739 ms) | Đạt (1,0 giây) |

Tổng: **16 passed (1,1 phút)**, gồm 1 test setup dùng chung và 5 kịch bản × 3 trình duyệt. Log tại `docs/evidence/phase-5/e2e-full.log`.

## 4. Kết quả UAT (Tiêu chí | Điểm trung bình | Ghi chú)

Chưa tổ chức UAT. Số người tham gia: **0/3–5**. Không có điểm trung bình nào được tính hoặc suy diễn. Biểu mẫu sẵn sàng tại `docs/phase-5-uat-form.md`.

| Tiêu chí | Điểm trung bình | Ghi chú |
| :--- | :---: | :--- |
| C1. Đăng nhập và điều hướng rõ ràng, dễ làm theo | Chưa có dữ liệu | Chưa có người tham gia |
| C2. Bố cục màn hình chat dễ nhìn, không rối | Chưa có dữ liệu | Chưa có người tham gia |
| C3. Câu trả lời hữu ích cho việc ôn thi SAA-C03 | Chưa có dữ liệu | Chưa có người tham gia |
| C4. Trích dẫn giúp kiểm chứng câu trả lời dễ dàng | Chưa có dữ liệu | Chưa có người tham gia |
| C5. Chế độ “Giải thích từng bước” hữu ích với câu hỏi vận dụng | Chưa có dữ liệu | Chưa có người tham gia |
| C6. Màn hình luyện đề dễ dùng và kết quả dễ hiểu | Chưa có dữ liệu | Chưa có người tham gia |
| C7. Lịch sử cho phép tìm, đổi tên và xóa thuận tiện | Chưa có dữ liệu | Chưa có người tham gia |
| C8. Cài đặt mô hình, chế độ, ngôn ngữ dễ hiểu | Chưa có dữ liệu | Chưa có người tham gia |
| C9. Giao diện dùng tốt trên màn hình nhỏ | Chưa có dữ liệu | Chưa có người tham gia |
| C10. Tổng thể đáng tin cậy, ít lỗi trong quá trình dùng | Chưa có dữ liệu | Chưa có người tham gia |

Kết luận UAT: **chưa đánh giá**. Không đủ cơ sở để coi Definition of Done về UAT là đạt.

## 5. Vấn đề và rủi ro

| Vấn đề / rủi ro | Mức độ | Ảnh hưởng | Hướng xử lý |
| :--- | :--- | :--- | :--- |
| Chưa tổ chức UAT 3–5 người | Cao | Không xác nhận được mức độ dễ dùng và mức độ hài lòng; báo cáo chỉ có thể ở trạng thái MỘT PHẦN | Tổ chức theo `docs/phase-5-uat-form.md`, ghi điểm và lỗi thực tế, cập nhật báo cáo |
| Chỉ tiêu TTFT và độ trễ Giai đoạn 4 chưa đạt | Cao | Người dùng thấy câu trả lời xuất hiện chậm dù đã có streaming; TTFT p95 một lượt 10.836,8 ms và đa lượt 6.905,0–8.125,2 ms so với ngưỡng ≤ 2.000 ms; tổng p95 19.887,6 ms so với ngưỡng ≤ 10.000 ms | Giữ nguyên phạm vi Giai đoạn 5; đo lại và tối ưu ở giai đoạn hiệu năng; không che giấu số liệu |
| Kết quả đa lượt Giai đoạn 4 mới đạt 3/10 và 2/10 | Cao | Chất lượng hội thoại nhiều lượt chưa đạt ngưỡng ≥ 8/10 | Xử lý ở giai đoạn đánh giá/tối ưu; giao diện không tự che lỗi này |
| Phụ thuộc độ trễ và độ sẵn sàng của DeepSeek | Trung bình | Streaming có thể chậm hoặc lỗi khi nhà cung cấp quá tải; UI hiển thị lỗi nhưng không khắc phục được phía dịch vụ | Theo dõi qua thống kê quản trị; thêm timeout/hiển thị lỗi rõ; không đổi nhà cung cấp sinh văn bản ngoài quy định |
| E2E phụ thuộc Supabase và DeepSeek thật | Trung bình | Bộ test không hermetic; có thể chậm hoặc không ổn định khi mạng/dịch vụ bên ngoài có sự cố | Ghi nhận thời gian chờ lớn cho streaming; cân nhắc môi trường test riêng trong CI |
| Firefox trên Windows cần `PLAYWRIGHT_BROWSERS_PATH` | Trung bình | Nếu không đặt biến, Firefox không khởi động do lỗi `mozglue.dll` | Đã ghi trong README; CI Linux không gặp lỗi này |
| `make test`/`make lint` cần `-f ./Makefile` trong Git Bash | Thấp | Người mới có thể tưởng lệnh hỏng | Ghi rõ trong báo cáo; giữ nguyên Makefile |
| Kiểm tra quản trị dương tính chưa tự động hóa | Trung bình | E2E chỉ kiểm tra học viên bị chặn; giao diện quản trị dương tính mới được kiểm tra thủ công | Thêm tài khoản quản trị riêng cho E2E hoặc test tích hợp có kiểm soát |
| Lighthouse `/chat` đạt 88 điểm hiệu năng | Thấp | Vẫn trên ngưỡng 80 nhưng gần ngưỡng; LCP 3,9 giây | Theo dõi khi thêm tính năng; tối ưu ảnh/phông và nội dung above-the-fold |
| Trình xem PDF dùng iframe và blob URL | Trung bình | Một số trình duyệt hoặc cài đặt tải PDF có thể không hiển thị trong iframe | Đã có liên kết mở tab mới và tải PDF; cân nhắc PDF.js nếu cần đồng nhất |
| Kho quiz chỉ gồm câu đủ 4 phương án và có đáp án xác định | Thấp | Một số câu trong kho không xuất hiện trong bài luyện | Hiển thị số câu khả dụng theo lĩnh vực; bổ sung dữ liệu ở giai đoạn nạp liệu |
| Kết nối PostgreSQL nhàn rỗi có thể bị đóng | Thấp | Trước khi sửa, yêu cầu đầu tiên sau thời gian nghỉ có thể trả 503 | Đã thêm kiểm tra `SELECT 1` sau 30 giây và 3 unit test; rủi ro còn lại là kết nối mới chậm ở lần đầu |

Không có khóa, mật khẩu hay chuỗi kết nối nào xuất hiện trong log, báo cáo hoặc hội thoại. `git status` không có `.env` hay tệp khóa bí mật.

## 6. Đề xuất cho giai đoạn 6

1. **Tổ chức UAT trước tiên:** 3–5 người theo `docs/phase-5-uat-form.md`; ghi điểm C1–C10, nhật ký lỗi và câu hỏi mở; chỉ kết luận Đạt khi điểm tổng thể ≥ 4,0, không tiêu chí nào dưới 3,5 và không còn lỗi chặn.
2. **Đo lại và tối ưu độ trễ:** TTFT và tổng thời gian vẫn là rủi ro lớn nhất với trải nghiệm chat. Ưu tiên giảm ngữ cảnh gửi vào mô hình, kiểm tra cấu hình streaming, bộ nhớ đệm truy xuất và thời gian xử lý tiền xử lý; giữ DeepSeek là nhà cung cấp sinh văn bản duy nhất.
3. **Đưa E2E vào CI:** chạy lint, test, build và Playwright trên Chromium/Firefox/WebKit với Supabase test riêng; lưu log và ảnh khi lỗi.
4. **Tự động hóa kiểm tra quản trị dương tính:** tạo tài khoản test được cấp quyền qua biến môi trường của môi trường CI, không hard-code email quản trị trong mã nguồn.
5. **Bổ sung kiểm tra trợ năng tự động:** dùng axe-core cho 5 màn hình; giữ Accessibility 100 như hiện tại khi thêm thành phần mới.
6. **Phân trang hoặc ảo hóa lịch sử:** hiện `/sessions` lấy tối đa 100 phiên và `/quiz/attempts` mặc định 20; cần xử lý khi dữ liệu người dùng tăng.
7. **Thêm giới hạn tần suất và chi phí:** dùng số liệu quản trị để đặt cảnh báo chi phí, tỷ lệ từ chối và tỷ lệ lỗi; tránh lạm dụng endpoint sinh văn bản.
8. **Cải thiện phân tích lỗi:** trang quản trị mới có tỷ lệ từ chối/lỗi; cần phân nhóm lỗi để trả lời nhược điểm W8, không chỉ hiển thị tổng.
9. **Đồng nhất trình xem PDF:** nếu iframe không ổn định trên một số trình duyệt, cân nhắc PDF.js; vẫn ưu tiên thành phần nội bộ, không thêm thư viện UI nặng.
10. **Giữ kỷ luật phạm vi:** không bắt đầu Giai đoạn 6 trong báo cáo này; các đề xuất trên là đầu vào cho giai đoạn kế tiếp.

## 7. Xác nhận Definition of Done

| Hạng mục Definition of Done | Trạng thái | Bằng chứng / ghi chú |
| :--- | :---: | :--- |
| 5 màn hình `/chat`, `/quiz`, `/history`, `/settings`, `/admin` | Đạt | Build liệt kê đủ 5 tuyến; kiểm tra thủ công và E2E |
| Đăng nhập Supabase Auth và bảo vệ tuyến | Đạt | `proxy.ts`, `AuthProvider`, E2E setup; chuyển về `/login` khi chưa đăng nhập |
| Không lưu token trong `localStorage` | Đạt | Phiên dùng cookie `@supabase/ssr`; chỉ tùy chọn giao diện lưu cục bộ |
| Streaming, dừng tạo câu trả lời | Đạt | E2E hỏi đáp trên 3 trình duyệt; nút dừng có nhãn trợ năng |
| Chip trích dẫn mở đúng tài liệu và trang | Đạt | E2E mở PDF trong hộp thoại; endpoint tài liệu trả PDF gốc |
| Hai chế độ trả lời nhanh và từng bước | Đạt | Kiểm tra thủ công; chế độ lưu trong tùy chọn |
| Markdown an toàn, không render script | Đạt | `rehype-sanitize`; E2E sanitize trên 3 trình duyệt |
| Quiz: chọn lĩnh vực, 5 câu, chấm điểm, giải thích, lưu lịch sử | Đạt | E2E luyện đề; bảng `quiz_attempts` có RLS |
| History: tìm, đổi tên, xóa | Đạt | E2E và kiểm tra thủ công |
| Settings: mô hình, chế độ, ngôn ngữ, xóa toàn bộ dữ liệu | Đạt | Kiểm tra thủ công 23 bước; xóa có xác nhận |
| Admin: số câu hỏi, chi phí, độ trễ, tỷ lệ từ chối; chỉ quản trị viên | Đạt | Thẻ số liệu thủ công; backend 403 với học viên; E2E chặn quyền |
| Giao diện tiếng Việt, trạng thái tải/rỗng/lỗi | Đạt | Ảnh và kiểm tra thủ công 5 màn hình |
| Responsive máy tính và di động | Đạt | 5/5 màn hình `overflow = 0`; điều hướng đáy |
| Playwright E2E trên Chromium/Firefox/WebKit | Đạt | 16 passed, 1,1 phút |
| Lighthouse Performance ≥ 80, Accessibility ≥ 90 | Đạt | Login 93/100 (hai lần), Chat 88/100; không còn audit trợ năng lỗi |
| README hướng dẫn chạy frontend và biến môi trường | Đạt | `README.md` đã cập nhật |
| UAT 3–5 người, thang 5 mức, điểm trung bình | Chưa đạt | Chưa có người tham gia; biểu mẫu đã sẵn sàng |
| Báo cáo Giai đoạn 5 đúng mẫu | Đạt | Tệp này |

**Kết luận Definition of Done:** các hạng mục kỹ thuật, kiểm thử tự động, kiểm tra thủ công, hiệu năng và tài liệu đã đạt. Hạng mục UAT chưa đạt vì chưa có người tham gia, nên toàn bộ Giai đoạn 5 được xác nhận ở trạng thái **MỘT PHẦN**.

Đã dừng tại đây theo yêu cầu; không bắt đầu Giai đoạn 6.
