# Chatbot RAG luyện thi AWS SAA-C03

Chatbot hỗ trợ tự học và luyện thi chứng chỉ AWS Certified Solutions Architect – Associate (SAA-C03).
Kiến trúc 3 tầng: Next.js (App Router) → FastAPI → Supabase PostgreSQL + pgvector, sinh câu trả lời bằng Gemini.

## Chạy nhanh

Yêu cầu: Python 3.11+, Node.js 20+, GNU Make.

```powershell
cp .env.example .env
```

```powershell
make install
```

```powershell
make dev
```

Giao diện tại http://localhost:3000; kiểm tra backend tại http://localhost:8000/health.

Chi tiết kiến trúc, quy ước và quy tắc bất biến: [CLAUDE.md](CLAUDE.md).
