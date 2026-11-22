-- Giai đoạn 4: hội thoại đa lượt, tóm tắt ngữ cảnh và streaming.
-- Bổ sung cột còn thiếu, khóa ngoại người dùng và chính sách RLS theo chủ sở hữu.
-- Bảng sessions/messages hiện đang rỗng nên có thể đặt user_id NOT NULL an toàn.

-- ---------------------------------------------------------------------------
-- 1. sessions: tóm tắt, đếm token, đếm lượt
-- ---------------------------------------------------------------------------
alter table public.sessions
    add column if not exists summary text,
    add column if not exists summary_updated_at timestamptz,
    add column if not exists summary_message_count integer not null default 0,
    add column if not exists token_count integer not null default 0,
    add column if not exists message_count integer not null default 0;

alter table public.sessions
    alter column user_id set not null;

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conname = 'sessions_user_id_fkey'
          and conrelid = 'public.sessions'::regclass
    ) then
        alter table public.sessions
            add constraint sessions_user_id_fkey
            foreign key (user_id) references auth.users (id) on delete cascade;
    end if;
end
$$;

create index if not exists sessions_user_updated_idx
    on public.sessions (user_id, updated_at desc);

-- ---------------------------------------------------------------------------
-- 2. messages: token, câu hỏi đã viết lại, request_id chống trùng khi nối lại
-- ---------------------------------------------------------------------------
alter table public.messages
    add column if not exists token_count integer not null default 0,
    add column if not exists rewritten_query text,
    add column if not exists request_id uuid;

create index if not exists messages_session_created_idx
    on public.messages (session_id, created_at, id);

create unique index if not exists messages_session_request_uidx
    on public.messages (session_id, request_id)
    where request_id is not null;

-- ---------------------------------------------------------------------------
-- 3. query_logs: TTFT, tổng thời gian, cờ streaming, người dùng
-- ---------------------------------------------------------------------------
alter table public.query_logs
    add column if not exists ttft_ms integer,
    add column if not exists total_latency_ms integer,
    add column if not exists streaming boolean not null default false,
    add column if not exists user_id uuid,
    add column if not exists status text,
    add column if not exists conversation_tokens integer;

create index if not exists query_logs_user_created_idx
    on public.query_logs (user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- 4. RLS: mỗi người chỉ đọc/ghi phiên của mình
-- ---------------------------------------------------------------------------
alter table public.sessions enable row level security;
alter table public.messages enable row level security;

drop policy if exists sessions_select_own on public.sessions;
create policy sessions_select_own on public.sessions
    for select to authenticated
    using (user_id = auth.uid());

drop policy if exists sessions_insert_own on public.sessions;
create policy sessions_insert_own on public.sessions
    for insert to authenticated
    with check (user_id = auth.uid());

drop policy if exists sessions_update_own on public.sessions;
create policy sessions_update_own on public.sessions
    for update to authenticated
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

drop policy if exists sessions_delete_own on public.sessions;
create policy sessions_delete_own on public.sessions
    for delete to authenticated
    using (user_id = auth.uid());

drop policy if exists messages_select_own on public.messages;
create policy messages_select_own on public.messages
    for select to authenticated
    using (
        exists (
            select 1 from public.sessions s
            where s.id = messages.session_id and s.user_id = auth.uid()
        )
    );

drop policy if exists messages_insert_own on public.messages;
create policy messages_insert_own on public.messages
    for insert to authenticated
    with check (
        exists (
            select 1 from public.sessions s
            where s.id = messages.session_id and s.user_id = auth.uid()
        )
    );

drop policy if exists messages_update_own on public.messages;
create policy messages_update_own on public.messages
    for update to authenticated
    using (
        exists (
            select 1 from public.sessions s
            where s.id = messages.session_id and s.user_id = auth.uid()
        )
    )
    with check (
        exists (
            select 1 from public.sessions s
            where s.id = messages.session_id and s.user_id = auth.uid()
        )
    );

drop policy if exists messages_delete_own on public.messages;
create policy messages_delete_own on public.messages
    for delete to authenticated
    using (
        exists (
            select 1 from public.sessions s
            where s.id = messages.session_id and s.user_id = auth.uid()
        )
    );

-- query_logs giữ RLS đóng hoàn toàn: chỉ backend dùng khóa máy chủ ghi/đọc.

-- ---------------------------------------------------------------------------
-- 5. Quyền bảng cho PostgREST
-- Supabase không tự cấp DML cho role authenticated khi bảng được tạo bằng SQL.
-- Chỉ cấp cho authenticated; RLS phía trên vẫn giới hạn từng dòng theo auth.uid().
-- anon không được cấp quyền nào.
-- ---------------------------------------------------------------------------
grant select, insert, update, delete on public.sessions to authenticated;
grant select, insert, update, delete on public.messages to authenticated;
