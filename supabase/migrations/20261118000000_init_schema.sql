-- Giai đoạn 0: lược đồ khởi tạo cho Chatbot RAG luyện thi AWS SAA-C03.
-- Bật RLS trên mọi bảng và không tạo policy: mặc định đóng với anon/authenticated.
-- Backend truy cập bằng service_role (bỏ qua RLS) theo quy tắc bất biến số 3 trong CLAUDE.md.

create extension if not exists vector;
create extension if not exists pg_trgm;

-- Tài liệu gốc (PDF hoặc nguồn khác) đã nạp vào kho tri thức.
create table if not exists public.documents (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    source_url text,
    source_type text not null default 'pdf',
    version text not null default 'v1',
    page_count integer,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Chunk cha–con: chunk con nhỏ để truy xuất, parent_id trỏ tới chunk cha (cả mục).
create table if not exists public.chunks (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references public.documents (id) on delete cascade,
    parent_id uuid references public.chunks (id) on delete cascade,
    chunk_index integer not null,
    content text not null,
    embedding vector(768),
    metadata jsonb not null default '{}'::jsonb,
    search_vector tsvector generated always as (to_tsvector('simple', coalesce(content, ''))) stored,
    created_at timestamptz not null default now(),
    constraint chunks_document_chunk_unique unique (document_id, chunk_index)
);

create index if not exists chunks_embedding_hnsw_idx
    on public.chunks using hnsw (embedding vector_cosine_ops);
create index if not exists chunks_search_vector_idx
    on public.chunks using gin (search_vector);
create index if not exists chunks_content_trgm_idx
    on public.chunks using gin (content gin_trgm_ops);
create index if not exists chunks_document_id_idx
    on public.chunks (document_id);
create index if not exists chunks_parent_id_idx
    on public.chunks (parent_id);
create index if not exists chunks_metadata_idx
    on public.chunks using gin (metadata);
create index if not exists documents_metadata_idx
    on public.documents using gin (metadata);

-- Ngân hàng câu hỏi luyện thi (Giai đoạn 2).
create table if not exists public.questions (
    id uuid primary key default gen_random_uuid(),
    question text not null,
    options jsonb not null default '[]'::jsonb,
    correct_answer text,
    explanation text,
    domain text,
    cognitive_level text check (cognitive_level in ('K1', 'K2', 'K3')),
    source text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

-- Phiên hội thoại (Giai đoạn 6).
create table if not exists public.sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid,
    title text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.messages (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.sessions (id) on delete cascade,
    role text not null check (role in ('user', 'assistant', 'system')),
    content text not null,
    citations jsonb not null default '[]'::jsonb,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists messages_session_id_idx
    on public.messages (session_id, created_at);

-- Nhật ký truy vấn phục vụ đánh giá và phân tích lỗi (Giai đoạn 2, 8).
create table if not exists public.query_logs (
    id uuid primary key default gen_random_uuid(),
    session_id uuid references public.sessions (id) on delete set null,
    question text not null,
    rewritten_query text,
    retrieved_chunk_ids uuid[] not null default '{}',
    latency_ms integer,
    prompt_tokens integer,
    completion_tokens integer,
    model text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists query_logs_session_id_idx
    on public.query_logs (session_id);
create index if not exists query_logs_created_at_idx
    on public.query_logs (created_at);

alter table public.documents enable row level security;
alter table public.chunks enable row level security;
alter table public.questions enable row level security;
alter table public.sessions enable row level security;
alter table public.messages enable row level security;
alter table public.query_logs enable row level security;
