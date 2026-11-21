-- Kho văn bản quy định: văn bản -> phiên bản (có hiệu lực) -> đoạn (chunk) để tìm kiếm lai (từ khóa + vector).
-- Chỉ chứa schema. Dữ liệu mẫu nằm ở `make seed-dev`, không nằm trong migration (migration chạy cả ở production).

create extension if not exists vector;
create extension if not exists unaccent;
create extension if not exists btree_gist;

-- `unaccent()` của Postgres chỉ STABLE nên không dùng được trong cột sinh ra. Bọc lại thành hàm IMMUTABLE
-- (từ điển `unaccent` cố định). `search_path` có `extensions` vì Supabase hay đặt extension ở schema đó.
create function f_unaccent(text) returns text
    language sql immutable parallel safe strict
    set search_path = public, extensions, pg_catalog
as $$ select unaccent('unaccent'::regdictionary, $1) $$;

create table policy_document (
    id          bigint generated always as identity primary key,
    code        text not null unique check (code = btrim(code) and code <> ''),
    title       text not null,
    issuer      text not null default '',
    created_at  timestamptz not null default now()
);

create table policy_version (
    id             bigint generated always as identity primary key,
    document_id    bigint not null references policy_document (id),
    version_label  text not null check (version_label = btrim(version_label) and version_label <> ''),
    effective_from date not null,
    effective_to   date,
    status         text not null default 'draft' check (status in ('draft', 'published', 'superseded')),
    is_sample      boolean not null default false,
    published_by   bigint references app_user (id),
    published_at   timestamptz,
    created_at     timestamptz not null default now(),
    unique (document_id, version_label),
    check (effective_to is null or effective_to >= effective_from),
    -- Khoảng hiệu lực của các bản đang `published` cùng một văn bản không được chồng nhau (BR: một ngày chỉ có một bản hiện hành).
    constraint policy_version_no_overlap exclude using gist (
        document_id with =,
        daterange(effective_from, effective_to, '[]') with &&
    ) where (status = 'published')
);

create table policy_chunk (
    id               bigint generated always as identity primary key,
    version_id       bigint not null references policy_version (id) on delete cascade,
    ordinal          integer not null,
    article_no       text not null,
    clause_no        text,
    heading          text not null default '',
    text             text not null,
    tsv              tsvector generated always as (to_tsvector('simple', f_unaccent(coalesce(heading, '') || ' ' || text))) stored,
    embedding        vector(1536),
    embedding_model  text,
    unique (version_id, ordinal)
);

create index policy_chunk_tsv_idx on policy_chunk using gin (tsv);
-- Chưa tạo chỉ mục vector: vài trăm đoạn thì quét tuần tự đủ nhanh. Thêm HNSW khi cần.

alter table policy_document enable row level security;
alter table policy_version enable row level security;
alter table policy_chunk enable row level security;
