-- Đề cương (có phiên bản), chuẩn đầu ra theo khóa, mẫu mốc do QTV cấu hình, nhật ký có nội dung, minh chứng có tệp.

create table learning_outcome (
    id           bigint generated always as identity primary key,
    cohort       text not null,
    code         text not null,
    description  text not null,
    unique (cohort, code)
);

create table outline (
    id             bigint generated always as identity primary key,
    internship_id  bigint not null references internship (id) on delete cascade,
    version        int not null,
    content        text not null,
    outcome_codes  text[] not null default '{}',
    status         text not null default 'submitted' check (status in ('submitted', 'approved', 'revision_requested', 'rejected')),
    feedback       text not null default '',
    submitted_at   timestamptz not null default now(),
    decided_by     bigint references app_user (id),
    decided_at     timestamptz,
    unique (internship_id, version)
);

-- Mẫu mốc (docs mục 9.1): hạn = mốc neo (start/mid/end) + số ngày lệch.
create table milestone_template (
    code         text primary key check (code in ('M1', 'M2', 'M3', 'M4', 'M5')),
    name         text not null,
    anchor       text not null check (anchor in ('start', 'mid', 'end')),
    offset_days  int not null
);

insert into milestone_template (code, name, anchor, offset_days) values
    ('M1', 'Hồ sơ đăng ký được xác nhận', 'start', -7),
    ('M2', 'Đề cương được duyệt', 'start', 14),
    ('M3', 'Báo cáo giữa kỳ', 'mid', 0),
    ('M4', 'Báo cáo cuối kỳ', 'end', -7),
    ('M5', 'Phiếu đánh giá của doanh nghiệp', 'end', 7);

alter table milestone add column note text not null default '';
alter table milestone add column submitted_at timestamptz;
alter table milestone add column decided_by bigint references app_user (id);
alter table milestone add column decided_at timestamptz;

alter table journal_entry add column content text not null default '';
alter table journal_entry add column lecturer_comment text not null default '';
alter table journal_entry add column commented_at timestamptz;

alter table evidence add column filename text not null default '';
alter table evidence add column mime text not null default '';
alter table evidence add column size_bytes bigint not null default 0;
alter table evidence add column sha256 text not null default '';
alter table evidence add column storage_key text not null default '';
alter table evidence add column uploaded_by bigint references app_user (id);
alter table evidence add column reviewer_comment text not null default '';
alter table evidence add column reviewed_by bigint references app_user (id);
alter table evidence add column reviewed_at timestamptz;

alter table learning_outcome enable row level security;
alter table outline enable row level security;
alter table milestone_template enable row level security;
