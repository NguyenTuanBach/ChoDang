-- Hồ sơ thực tập đầy đủ (A3-A6): doanh nghiệp, người hướng dẫn, mô tả công việc; phiên bản đã nộp (BR-S4); giấy tiếp nhận.

alter table internship add column company_name text not null default '';
alter table internship add column company_tax_code text not null default '';
alter table internship add column company_address text not null default '';
alter table internship add column position text not null default '';
alter table internship add column mentor_name text not null default '';
alter table internship add column mentor_email text not null default '';
alter table internship add column mentor_phone text not null default '';
alter table internship add column job_description text not null default '';
-- Từng trường do AI gợi ý đã được sinh viên xác nhận hay nhập tay: {"company_name": "ai_confirmed", ...}.
alter table internship add column field_confirmations jsonb not null default '{}'::jsonb;
alter table internship add column version int not null default 1;
alter table internship add column submitted_at timestamptz;
alter table internship add column decision_reason text not null default '';
alter table internship add column decided_at timestamptz;

-- Nội dung đã nộp không sửa tại chỗ: mỗi lần nộp chụp một bản (BR-S4).
create table internship_revision (
    id             bigint generated always as identity primary key,
    internship_id  bigint not null references internship (id) on delete cascade,
    version        int not null,
    snapshot       jsonb not null,
    submitted_at   timestamptz not null default now(),
    unique (internship_id, version)
);

create table internship_document (
    id             bigint generated always as identity primary key,
    internship_id  bigint not null references internship (id) on delete cascade,
    kind           text not null default 'receipt_letter' check (kind in ('receipt_letter')),
    filename       text not null,
    mime           text not null,
    size_bytes     bigint not null,
    sha256         text not null,
    storage_key    text not null,
    uploaded_by    bigint references app_user (id),
    uploaded_at    timestamptz not null default now()
);

create index internship_document_idx on internship_document (internship_id);

alter table internship_revision enable row level security;
alter table internship_document enable row level security;
