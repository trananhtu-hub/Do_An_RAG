-- Giai đoạn 1: bổ sung cột phục vụ nạp dữ liệu có kiểm soát trùng lặp.
-- Không đổi quyền RLS: các bảng vẫn bật RLS và mặc định đóng.

alter table public.documents
    add column if not exists source_key text,
    add column if not exists checksum text,
    add column if not exists language text;

create unique index if not exists documents_source_key_key
    on public.documents (source_key);

alter table public.chunks
    add column if not exists token_count integer,
    add column if not exists content_type text not null default 'text',
    add column if not exists checksum text,
    add column if not exists embedding_model text;

create index if not exists chunks_content_type_idx
    on public.chunks (content_type);

alter table public.questions
    add column if not exists document_id uuid references public.documents (id) on delete cascade,
    add column if not exists external_id text,
    add column if not exists question_number integer,
    add column if not exists topic text,
    add column if not exists source_page integer,
    add column if not exists page_end integer,
    add column if not exists language text,
    add column if not exists checksum text;

create unique index if not exists questions_document_number_key
    on public.questions (document_id, question_number);

create index if not exists questions_domain_idx
    on public.questions (domain);

create index if not exists questions_external_id_idx
    on public.questions (external_id);

-- Chỉ mục bắt buộc của Giai đoạn 1 (tạo lại nếu chưa có).
create index if not exists chunks_embedding_hnsw_idx
    on public.chunks using hnsw (embedding vector_cosine_ops);

create index if not exists chunks_search_vector_idx
    on public.chunks using gin (search_vector);
