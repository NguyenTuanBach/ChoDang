-- Schema nghiệp vụ thực tập TỐI THIỂU, đủ cho các tool `get_my_*` của trợ lý hỏi đáp đọc.
-- Tên bảng/cột và trạng thái theo docs/nghiep-vu-thuc-tap.md mục 6 và 9 để sau này mở rộng, không phải bảng tạm.
-- Chỉ chứa schema; dữ liệu giả nằm ở `make seed-dev`.

create table internship (
    id           bigint generated always as identity primary key,
    user_id      bigint not null references app_user (id),
    cohort       text not null,
    status       text not null default 'draft' check (status in (
                     'draft', 'submitted', 'revision_requested', 'rejected', 'confirmed',
                     'in_progress', 'pending_credit', 'credit_review', 'completed', 'closed_no_credit')),
    start_date   date,
    end_date     date,
    mode         text not null default 'onsite' check (mode in ('onsite', 'remote', 'hybrid')),
    lecturer_id  bigint references app_user (id),
    created_at   timestamptz not null default now(),
    unique (user_id, cohort),
    check (end_date is null or start_date is null or end_date >= start_date)
);

create index internship_user_idx on internship (user_id);

create table milestone (
    id             bigint generated always as identity primary key,
    internship_id  bigint not null references internship (id) on delete cascade,
    code           text not null check (code in ('M1', 'M2', 'M3', 'M4', 'M5')),
    name           text not null,
    due_date       date not null,
    status         text not null default 'pending' check (status in ('pending', 'submitted', 'accepted', 'rejected', 'overdue')),
    unique (internship_id, code)
);

create table journal_entry (
    id             bigint generated always as identity primary key,
    internship_id  bigint not null references internship (id) on delete cascade,
    week_start     date not null,
    submitted_at   timestamptz not null default now(),
    unique (internship_id, week_start)
);

create table evidence (
    id             bigint generated always as identity primary key,
    milestone_id   bigint not null references milestone (id) on delete cascade,
    title          text not null default '',
    status         text not null default 'submitted' check (status in ('submitted', 'accepted', 'rejected')),
    submitted_at   timestamptz not null default now()
);

create table request (
    id             bigint generated always as identity primary key,
    internship_id  bigint not null references internship (id) on delete cascade,
    kind           text not null check (kind in ('milestone_extension', 'exception')),
    status         text not null default 'open' check (status in ('open', 'approved', 'rejected', 'cancelled')),
    created_at     timestamptz not null default now()
);

alter table internship enable row level security;
alter table milestone enable row level security;
alter table journal_entry enable row level security;
alter table evidence enable row level security;
alter table request enable row level security;
