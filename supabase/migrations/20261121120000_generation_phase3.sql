-- Giai đoạn 3: bổ sung cột nhật ký sinh câu trả lời.
-- Giữ nguyên RLS đang bật và mặc định đóng; backend ghi bằng service_role.

alter table public.query_logs
    add column if not exists prompt_version text,
    add column if not exists cost_usd numeric(14, 8),
    add column if not exists fallback_used text;

comment on column public.query_logs.prompt_version is
    'Phiên bản prompt sinh câu trả lời, ví dụ v1 (kèm prompt_mode trong metadata).';
comment on column public.query_logs.cost_usd is
    'Chi phí ước tính theo bảng giá cấu hình tại config/generation.yaml.';
comment on column public.query_logs.fallback_used is
    'Tên provider dự phòng đã trả lời; null nếu provider chính trả lời.';
