-- Nền tảng: tài khoản (đăng nhập theo lời mời) và nhật ký kiểm toán chỉ-thêm.
-- Chuỗi mời: QTV mời GV, GV mời SV. Email chưa được mời thì không đăng nhập được.

create table app_user (
    id            bigint generated always as identity primary key,
    email         text not null unique check (email = lower(email)),
    full_name     text not null default '',
    role          text not null check (role in ('student', 'lecturer', 'admin')),
    status        text not null default 'invited' check (status in ('invited', 'active', 'revoked')),
    invited_by    bigint references app_user (id),
    invited_at    timestamptz not null default now(),
    activated_at  timestamptz
);

create table audit_event (
    id          bigint generated always as identity primary key,
    at          timestamptz not null default now(),
    actor_id    bigint,
    actor_kind  text not null check (actor_kind in ('human', 'system', 'agent')),
    actor_role  text not null default '',
    entity      text not null,
    entity_id   bigint,
    action      text not null,
    before      jsonb,
    after       jsonb,
    reason      text not null default ''
);

-- Chỉ-thêm: chặn UPDATE và DELETE (BR-S3, nguyên tắc N4).
create function audit_event_append_only() returns trigger as $$
begin
    raise exception 'audit_event is append-only';
end;
$$ language plpgsql;

create trigger audit_event_no_change
    before update or delete on audit_event
    for each row execute function audit_event_append_only();

-- Supabase mở bảng schema public qua PostgREST bằng khóa anon. Bật RLS và không tạo policy nào
-- để khóa đó không đọc được gì; BE kết nối bằng role chủ sở hữu nên không bị RLS chặn.
alter table app_user enable row level security;
alter table audit_event enable row level security;
