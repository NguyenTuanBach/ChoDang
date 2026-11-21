-- Hội thoại của trợ lý hỏi đáp: mỗi hội thoại thuộc đúng một người dùng (chủ sở hữu duy nhất).

create table chat_conversation (
    id          bigint generated always as identity primary key,
    user_id     bigint not null references app_user (id),
    title       text,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

create index chat_conversation_user_idx on chat_conversation (user_id, updated_at desc);

create table chat_message (
    id               bigint generated always as identity primary key,
    conversation_id  bigint not null references chat_conversation (id) on delete cascade,
    turn_id          text not null,
    role             text not null check (role in ('user', 'assistant')),
    content          text not null,
    citations        jsonb not null default '[]',
    -- Vết một lượt: bước, tool đã gọi, độ trễ, token, nhà cung cấp, cờ degraded. Đã che PII.
    trace            jsonb not null default '{}',
    degraded         boolean not null default false,
    created_at       timestamptz not null default now()
);

-- Mỗi (hội thoại, lượt, vai trò) chỉ có một dòng: chặn lưu đôi khi FE gửi trùng turn_id.
create unique index chat_message_turn_role_idx on chat_message (conversation_id, turn_id, role);
create index chat_message_conversation_idx on chat_message (conversation_id, id);
create index chat_message_trace_id_idx on chat_message ((trace ->> 'trace_id')) where trace ? 'trace_id';

alter table chat_conversation enable row level security;
alter table chat_message enable row level security;
