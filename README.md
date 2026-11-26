# Chatbot RAG luyện thi AWS SAA-C03

Chatbot hỗ trợ tự học và luyện thi chứng chỉ AWS Certified Solutions Architect – Associate (SAA-C03).

Kiến trúc 3 tầng: Next.js (App Router) → FastAPI → Supabase PostgreSQL + pgvector. DeepSeek sinh toàn bộ
văn bản (trả lời, viết lại câu hỏi, tóm tắt, judge); Gemini chỉ cấp embedding 768 chiều.

## Yêu cầu

- Python 3.11+, Node.js 20+, GNU Make
- Một dự án Supabase đã chạy các migration trong `supabase/migrations/`
- Khóa DeepSeek và Gemini

## Cài đặt

1. Tạo tệp cấu hình gốc và điền các biến:

   ```powershell
   cp .env.example .env
   ```

2. Cài phụ thuộc backend và frontend:

   ```powershell
   make install
   ```

3. Tạo tệp `frontend/.env.local` cho giao diện:

   ```dotenv
   NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

   Dùng đúng URL gốc của Supabase (không kèm `/rest/v1`) và khóa `anon`, không dùng
   `service_role` trong biến `NEXT_PUBLIC_*`.

4. Chạy backend (cổng 8000) và frontend (cổng 3000):

   ```powershell
   make dev
   ```

   Giao diện tại http://localhost:3000, kiểm tra backend tại http://localhost:8000/health.

Nếu chỉ cần chạy riêng giao diện:

```powershell
npm --prefix frontend run dev
```

## Biến môi trường

Các biến dùng chung nằm trong `.env` ở thư mục gốc (không commit):

| Biến | Ý nghĩa |
| :--- | :--- |
| `DEEPSEEK_API_KEY` | Khóa API DeepSeek cho mọi tác vụ sinh văn bản |
| `DEEPSEEK_BASE_URL` | Gốc endpoint tương thích OpenAI |
| `DEEPSEEK_MODEL` | Model sinh, mặc định `deepseek-chat` |
| `GEMINI_API_KEY` | Khóa Google AI Studio, chỉ dùng cho embedding 768 chiều |
| `SUPABASE_URL` | URL dự án Supabase |
| `SUPABASE_ANON_KEY` | Khóa công khai cho trình duyệt |
| `SUPABASE_SERVICE_ROLE_KEY` | Khóa máy chủ, chỉ dùng backend và script kiểm thử |
| `DATABASE_URL` | Chuỗi kết nối PostgreSQL |
| `ADMIN_EMAILS` | Danh sách email quản trị, phân tách bằng dấu phẩy; để trống nghĩa là không ai |

Giao diện chỉ đọc ba biến `NEXT_PUBLIC_*` trong `frontend/.env.local` như mục cài đặt ở trên.

Tài khoản đăng nhập dùng Supabase Auth (email + mật khẩu). Mọi tuyến dữ liệu của backend đều yêu cầu
token Supabase; trang `/admin` chỉ mở với email nằm trong `ADMIN_EMAILS`.

## Các màn hình

| Đường dẫn | Chức năng |
| :--- | :--- |
| `/login` | Đăng nhập hoặc đăng ký bằng email và mật khẩu |
| `/chat` | Hỏi đáp có streaming, trích dẫn bấm được, dừng giữa chừng, hai chế độ trả lời |
| `/quiz` | Luyện đề theo lĩnh vực, chấm điểm và xem giải thích |
| `/history` | Tìm kiếm, đổi tên, xóa cuộc trò chuyện và xem lịch sử làm bài |
| `/settings` | Chọn mô hình, chế độ trả lời, ngôn ngữ; xóa toàn bộ dữ liệu cá nhân |
| `/admin` | Thống kê số câu hỏi, chi phí, tỷ lệ từ chối, độ trễ (chỉ quản trị viên) |

## Kiểm thử

```powershell
make lint
```

```powershell
make test
```

```powershell
npm --prefix frontend run build
```

Kiểm thử đầu-cuối bằng Playwright (tự khởi động backend và frontend nếu chưa chạy):

```powershell
cd frontend
npx playwright install chromium firefox webkit
npx playwright test
```

Bộ E2E đọc `.env` ở thư mục gốc để tạo hoặc đặt lại mật khẩu tài khoản thử nghiệm bằng
`SUPABASE_SERVICE_ROLE_KEY`; có thể đặt `E2E_EMAIL` để đổi email mặc định. Thông tin đăng nhập sinh ra
được lưu trong `frontend/e2e/.auth/` và không commit.

Trên Windows nếu Playwright không khởi động được Firefox (lỗi `mozglue.dll`), cài trình duyệt vào một
thư mục riêng và trỏ biến môi trường trước khi chạy:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "D:\playwright-browsers"
npx playwright install chromium firefox webkit
npx playwright test
```

Chi tiết kiến trúc, quy ước và quy tắc bất biến: [CLAUDE.md](CLAUDE.md). Báo cáo từng giai đoạn nằm trong
`docs/`.
