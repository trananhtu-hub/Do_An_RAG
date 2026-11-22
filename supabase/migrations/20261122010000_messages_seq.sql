-- Thứ tự tin nhắn ổn định trong một phiên.
-- created_at lấy now() của transaction nên hai tin nhắn ghi cùng một transaction
-- có thể trùng thời điểm; seq (identity) bảo đảm thứ tự xác định.

alter table public.messages
    add column if not exists seq bigint generated always as identity;

create index if not exists messages_session_seq_idx
    on public.messages (session_id, seq);
