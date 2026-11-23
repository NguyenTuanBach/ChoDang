-- AI đọc giấy tờ để tự điền: thêm trường của giấy tiếp nhận vào hồ sơ; lưu các trường SV đã xác nhận từ giấy xác nhận / phiếu đánh giá (M5).

alter table internship add column department text not null default '';
alter table internship add column mentor_title text not null default '';
alter table internship add column receipt_letter_number text not null default '';
alter table internship add column receipt_letter_date date;
alter table internship add column receipt_signer_name text not null default '';
alter table internship add column receipt_signer_title text not null default '';

-- Một minh chứng (thường là giấy xác nhận M5) có tối đa một bộ trường đã xác nhận.
-- ``fields``: {"company_name": "...", ...}; ``confirmations``: {"company_name": "ai_confirmed" | "manual"};
-- ``mismatches``: [{"field": "...", "label": "...", "detail": "..."}] do BE tính khi SV xác nhận (đối chiếu với hồ sơ).
create table evidence_extraction (
    evidence_id    bigint primary key references evidence (id) on delete cascade,
    fields         jsonb not null default '{}'::jsonb,
    confirmations  jsonb not null default '{}'::jsonb,
    mismatches     jsonb not null default '[]'::jsonb,
    confirmed_by   bigint references app_user (id),
    confirmed_at   timestamptz not null default now()
);

alter table evidence_extraction enable row level security;
