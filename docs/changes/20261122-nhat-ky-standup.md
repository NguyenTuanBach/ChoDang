# Nhật ký tuần kiểu standup (trang `/student/journal`)

## Mục tiêu
Thiết kế lại trang nhật ký theo mẫu "Daily standup" người dùng gửi, nhưng **giữ nhịp theo tuần** (đã hỏi và được chọn): quy tắc
"thiếu nhật ký ≥ 2 tuần" (monitoring) và điều kiện tín chỉ vẫn tính theo tuần, không đổi.

## Đã làm
- **DB** `V11__journal_standup.sql`: `journal_entry` thêm `plan_items jsonb` (danh sách việc `{text, done}`), `blockers text`, `ai_advice text`.
- **BE**:
  - `POST /api/student/journal` nhận thêm `plan_items`, `blockers`, `ai_advice` (chuẩn hóa ở `normalize_plan_items`: bỏ dòng trống, tối đa 20 việc, 300 ký tự/việc).
  - `PUT /api/student/journal/{id}/items`: sinh viên chủ nhật ký tích/bỏ tích việc sau khi nộp (ghi audit); nội dung đã nộp không đổi.
  - `POST /api/student/journal/ai-advice` (`JournalAdviceService`): BE che PII rồi gọi agent `POST /v1/journal/advice`; không ghi DB.
- **Agent**: gói `journal_advice` (`JournalAdvisor`), prompt `agent/prompts/journal_advice.system.md`, endpoint `/v1/journal/advice`
  (một-lượt, không công cụ ghi, che PII lần nữa); `/v1/info` thêm `journal_advice`.
- **FE** `student/JournalPage.tsx`: khung giới thiệu "Weekly standup"; form có "Tuần này: bạn đã làm gì?" (đếm n/20), danh sách việc
  có ô tích (`ui/check-box.tsx`), "Đang vướng (nếu có)", ô "Gợi ý lịch từ AI" (nhãn "AI gợi ý", nút "Hỏi AI lịch đã ổn chưa", để trống nếu không hỏi);
  danh sách "Các tuần gần nhất" gập/mở được, tích việc ngay trong lịch sử.
  Trang chi tiết hồ sơ của giảng viên hiển thị thêm việc, mục vướng và gợi ý AI (có ghi rõ sinh viên tự hỏi).

## Cách hoạt động của danh sách việc
Việc chưa tích ở nhật ký gần nhất tự xuất hiện ở form tuần sau (nhãn "Từ tuần trước"). Sinh viên tích việc đã xong, thêm việc mới cho tuần tới.

## Kiểm tra
- `tsc`, `eslint` (FE) sạch; `ruff` (các file đã sửa) sạch; agent `pytest` 198 đạt (không tính `test_agent_eval.py`, lỗi thiếu tzdata trên Windows có từ trước).
- Có test cho `normalize_plan_items` (`be/tests/service/test_journal_items.py`); chưa có test cho `update_journal_items`, `JournalAdviceService`, `JournalAdvisor` và FE. Đã gọi thử `POST /api/student/journal/ai-advice` với LLM thật: trả gợi ý đúng ngữ cảnh.

## Chưa kiểm tra / lưu ý
- Chưa xem trang trên trình duyệt; chưa nộp thử nhật ký thật (tránh ghi dữ liệu vào DB dùng chung); đã gọi LLM thật một lần cho gợi ý (chỉ đọc).
- `ai_advice` do trình duyệt gửi lại khi nộp nên về kỹ thuật sinh viên có thể sửa chữ trước khi nộp; BE chỉ giới hạn độ dài. Giảng viên thấy dòng ghi chú "sinh viên tự hỏi".
- Nhật ký cũ (trước V11) hiển thị không có danh sách việc.
