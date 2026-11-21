-- Giai đoạn 2: chỉ mục phục vụ truy hồi lai.
-- Bổ sung full-text không dấu (unaccent) và trigram cho thuật ngữ tiếng Anh.
-- Không đổi quyền RLS: các bảng vẫn bật RLS và mặc định đóng.

create extension if not exists unaccent;

-- unaccent() là STABLE (phụ thuộc dictionary); bọc thành IMMUTABLE để dùng
-- trong cột sinh và chỉ mục biểu thức.
create or replace function public.immutable_unaccent(value text)
returns text
language sql
immutable
parallel safe
strict
as $$
    select public.unaccent('public.unaccent', value)
$$;

alter table public.chunks
    add column if not exists search_text text
        generated always as (public.immutable_unaccent(coalesce(content, ''))) stored;

alter table public.chunks
    add column if not exists search_vector_unaccented tsvector
        generated always as (
            to_tsvector('simple', public.immutable_unaccent(coalesce(content, '')))
        ) stored;

create index if not exists chunks_search_vector_unaccented_idx
    on public.chunks using gin (search_vector_unaccented);

create index if not exists chunks_search_text_trgm_idx
    on public.chunks using gin (search_text gin_trgm_ops);
