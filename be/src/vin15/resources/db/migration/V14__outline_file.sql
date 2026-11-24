-- Tệp đề cương sinh viên đính kèm khi nộp (PDF, ảnh, DOCX); khóa lưu trỏ vào kho tệp, không lộ ra API.
alter table outline add column file_name text;
alter table outline add column file_mime text;
alter table outline add column file_size integer;
alter table outline add column file_key text;
