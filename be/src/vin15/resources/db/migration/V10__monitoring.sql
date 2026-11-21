-- Giám sát chủ động (nhóm C): cờ rủi ro, nhật ký nhắc nhở, gợi ý AI (tiền thẩm). Agent chỉ tạo cờ/nhắc; con người xử lý.

create table risk_flag (
    id               bigint generated always as identity primary key,
    internship_id    bigint not null references internship (id) on delete cascade,
    kind             text not null check (kind in (
                         'overdue_milestone', 'missing_journal', 'weak_evidence', 'outcome_mismatch', 'credit_shortfall', 'reminder_escalation')),
    severity         text not null check (severity in ('info', 'warning', 'critical')),
    status           text not null default 'open' check (status in ('open', 'acknowledged', 'resolved', 'dismissed')),
    reason           text not null,
    evidence         jsonb not null default '{}'::jsonb,
    suggestion       text not null default '',
    -- Dấu vân tay của điều kiện gây cờ: cờ không lặp khi chưa đổi, không tái tạo cờ đã bác (C4, C8).
    fingerprint      text not null,
    created_by_kind  text not null default 'system' check (created_by_kind in ('system', 'agent')),
    created_at       timestamptz not null default now(),
    decided_by       bigint references app_user (id),
    decided_at       timestamptz,
    decision_reason  text not null default '',
    unique (internship_id, fingerprint)
);

create index risk_flag_status_idx on risk_flag (status, internship_id);

create table reminder_log (
    id             bigint generated always as identity primary key,
    internship_id  bigint not null references internship (id) on delete cascade,
    milestone_code text not null default '',
    reason         text not null,
    template       text not null,
    sent_at        timestamptz not null default now()
);

create index reminder_log_idx on reminder_log (internship_id, milestone_code, reason, sent_at desc);

create table ai_suggestion (
    id             bigint generated always as identity primary key,
    internship_id  bigint not null references internship (id) on delete cascade,
    subject_kind   text not null check (subject_kind in ('outline', 'milestone')),
    subject_id     bigint not null,
    summary        text not null,
    details        jsonb not null default '{}'::jsonb,
    created_at     timestamptz not null default now()
);

create index ai_suggestion_idx on ai_suggestion (internship_id, subject_kind, subject_id, id desc);

alter table risk_flag enable row level security;
alter table reminder_log enable row level security;
alter table ai_suggestion enable row level security;
