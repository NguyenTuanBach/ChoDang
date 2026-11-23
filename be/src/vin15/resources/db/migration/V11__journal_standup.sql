-- Nhật ký tuần kiểu standup: kế hoạch tuần tới dạng danh sách việc có đánh dấu hoàn thành, mục "đang vướng" và gợi ý lịch của AI.
-- Vẫn một dòng cho mỗi tuần (quy tắc thiếu nhật ký, điều kiện tín chỉ không đổi). RLS đã bật ở V7.

alter table journal_entry add column plan_items jsonb not null default '[]'::jsonb;
alter table journal_entry add column blockers text not null default '';
alter table journal_entry add column ai_advice text not null default '';
