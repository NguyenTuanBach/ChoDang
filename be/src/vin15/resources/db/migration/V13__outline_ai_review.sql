-- Nhận xét của AI khi nộp đề cương (gợi ý để sinh viên sửa, giảng viên cũng xem được); không thay quyết định của giảng viên.
-- Cấu trúc: {"summary": text, "issues": [{"section": text, "message": text, "level": "error"|"warning"}], "ai": bool}
alter table outline add column ai_review jsonb not null default '{}'::jsonb;
