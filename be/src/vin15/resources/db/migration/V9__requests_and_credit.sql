-- Gia hạn, ngoại lệ (D1-D3), thẩm định công nhận tín chỉ (D4), hàng đợi đồng bộ LMS (D6).

create table exception_type (
    code            text primary key,
    name            text not null,
    affects_credit  boolean not null default false,
    active          boolean not null default true
);

-- Danh mục mặc định (docs mục 13.2, Q2); QTV chỉnh được.
insert into exception_type (code, name, affects_credit) values
    ('mentor_change', 'Đổi người hướng dẫn', false),
    ('company_change', 'Đổi doanh nghiệp', true),
    ('long_pause', 'Tạm dừng thực tập dài ngày', true),
    ('shorten_duration', 'Rút ngắn thời lượng thực tập', true);

alter table request add column exception_type_code text references exception_type (code);
alter table request add column milestone_code text check (milestone_code in ('M1', 'M2', 'M3', 'M4', 'M5'));
alter table request add column reason text not null default '';
alter table request add column new_due_date date;
alter table request add column decision_reason text not null default '';
alter table request add column decided_by bigint references app_user (id);
alter table request add column decided_at timestamptz;
alter table request add column affects_credit boolean not null default false;

create table request_attachment (
    id           bigint generated always as identity primary key,
    request_id   bigint not null references request (id) on delete cascade,
    filename     text not null,
    mime         text not null,
    size_bytes   bigint not null,
    sha256       text not null,
    storage_key  text not null,
    uploaded_at  timestamptz not null default now()
);

create table credit_assessment (
    id               bigint generated always as identity primary key,
    internship_id    bigint not null references internship (id) on delete cascade,
    status           text not null default 'pending' check (status in ('pending', 'lecturer_passed', 'lecturer_returned', 'approved', 'denied')),
    checklist        jsonb not null default '[]'::jsonb,
    lecturer_id      bigint references app_user (id),
    lecturer_note    text not null default '',
    lecturer_at      timestamptz,
    admin_id         bigint references app_user (id),
    admin_reason     text not null default '',
    admin_at         timestamptz,
    created_at       timestamptz not null default now()
);

create index credit_assessment_idx on credit_assessment (internship_id, id desc);

-- Hàng đợi ghi kết quả sang LMS: tạo cùng transaction với quyết định phê duyệt, worker gửi và thử lại.
create table credit_sync_job (
    id               bigint generated always as identity primary key,
    internship_id    bigint not null unique references internship (id) on delete cascade,
    student_code     text not null,
    course_code      text not null,
    credits          int not null,
    status           text not null default 'pending' check (status in ('pending', 'synced', 'failed')),
    attempts         int not null default 0,
    last_error       text not null default '',
    next_attempt_at  timestamptz not null default now(),
    created_at       timestamptz not null default now(),
    synced_at        timestamptz
);

alter table exception_type enable row level security;
alter table request_attachment enable row level security;
alter table credit_assessment enable row level security;
alter table credit_sync_job enable row level security;
