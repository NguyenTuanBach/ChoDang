-- Tài khoản: mã sinh viên (khóa ánh xạ sang LMS), giảng viên phụ trách; hạ tầng dùng chung: thông báo, hộp thư email, trạng thái job.

alter table app_user add column student_code text unique;
alter table app_user add column advisor_id bigint references app_user (id);

create table notification (
    id          bigint generated always as identity primary key,
    user_id     bigint not null references app_user (id) on delete cascade,
    kind        text not null default 'info',
    title       text not null,
    body        text not null default '',
    link        text not null default '',
    created_at  timestamptz not null default now(),
    read_at     timestamptz
);

create index notification_user_idx on notification (user_id, created_at desc);

create table email_outbox (
    id          bigint generated always as identity primary key,
    to_email    text not null,
    subject     text not null,
    body        text not null,
    status      text not null default 'pending' check (status in ('pending', 'sent', 'failed')),
    attempts    int not null default 0,
    last_error  text not null default '',
    created_at  timestamptz not null default now(),
    sent_at     timestamptz
);

create index email_outbox_pending_idx on email_outbox (status, id);

-- Mỗi job chạy theo ngày (email tổng hợp, giám sát) ghi ngày chạy cuối để không chạy lặp.
create table job_state (
    name         text primary key,
    last_run_on  date,
    detail       text not null default ''
);

alter table notification enable row level security;
alter table email_outbox enable row level security;
alter table job_state enable row level security;
