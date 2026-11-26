-- Giai đoạn 5: lịch sử làm bài quiz của từng người dùng.
-- Bảng mới bật RLS và mặc định đóng; backend truy cập bằng service_role
-- theo quy tắc bất biến số 3 trong CLAUDE.md.

create table if not exists public.quiz_attempts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    domain text,
    total_questions integer not null check (total_questions > 0),
    correct_count integer not null check (correct_count >= 0),
    duration_seconds integer,
    details jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists quiz_attempts_user_created_idx
    on public.quiz_attempts (user_id, created_at desc);

alter table public.quiz_attempts enable row level security;

comment on table public.quiz_attempts is
    'Lịch sử làm bài quiz; chỉ backend dùng khóa máy chủ đọc/ghi.';
