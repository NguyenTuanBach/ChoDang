-- LMS mini nằm trong hệ thống. Chỉ `infrastructure/lms` được đụng các bảng `lms_*`; phần còn lại đi qua `LmsPort`.
-- Sinh viên được nhận diện bằng mã sinh viên (student_code), không dùng id nội bộ, để thay LMS thật không phải đổi nghiệp vụ.

create table lms_student (
    student_code  text primary key,
    full_name     text not null default ''
);

create table lms_course (
    code     text primary key,
    name     text not null,
    credits  int not null check (credits > 0),
    kind     text not null default 'regular' check (kind in ('regular', 'internship'))
);

create table lms_grade (
    student_code  text not null references lms_student (student_code) on delete cascade,
    course_code   text not null references lms_course (code) on delete cascade,
    score         numeric(4, 2) not null check (score >= 0 and score <= 10),
    term          text not null default '',
    primary key (student_code, course_code)
);

-- Học phần tiên quyết của một học phần (ở đây là học phần thực tập), kèm điểm tối thiểu.
create table lms_prerequisite (
    course_code           text not null references lms_course (code) on delete cascade,
    required_course_code  text not null references lms_course (code) on delete cascade,
    min_score             numeric(4, 2) not null default 5.0,
    primary key (course_code, required_course_code)
);

-- Sổ tín chỉ tích lũy: nơi nhận kết quả quy đổi tín chỉ thực tập sau khi QTV phê duyệt.
create table lms_credit_ledger (
    id            bigint generated always as identity primary key,
    student_code  text not null references lms_student (student_code) on delete cascade,
    course_code   text not null references lms_course (code),
    credits       int not null check (credits > 0),
    source        text not null default 'internship',
    external_ref  text not null unique,
    posted_at     timestamptz not null default now()
);

alter table lms_student enable row level security;
alter table lms_course enable row level security;
alter table lms_grade enable row level security;
alter table lms_prerequisite enable row level security;
alter table lms_credit_ledger enable row level security;
