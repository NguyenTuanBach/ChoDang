# Time budget cho `summarize_outline`

## Vấn đề
`POST /internships/{id}/outline` gọi `summarize_outline` đồng bộ; khi có API key, request nộp đề cương phải chờ
LLM tóm tắt. Model chậm hoặc treo thì sinh viên chờ theo.

## Đã làm (`src/services/reviewer.py`)
- `_llm_summary_within(text, purpose, budget)`: chạy `_llm_summary` trong `ThreadPoolExecutor` (tối đa 4 thread),
  chờ tối đa `OUTLINE_SUMMARY_BUDGET_SECONDS` (5 giây; `<=0` = không giới hạn).
- Quá hạn hoặc LLM lỗi → dùng bản tóm tắt theo luật (`_first_sentences`), `source="rules"`. Trước đây lỗi LLM
  trả `None` và UI ẩn hẳn gợi ý; nay GV vẫn thấy "CĐR chưa nhắc tới" (tính xác định, không cần LLM).
- Chỉ đổi `summarize_outline`; không đụng `summarize_extension` (thuộc nhóm 2). Bản tóm tắt chỉ là gợi ý,
  không ảnh hưởng quyết định duyệt (HITL giữ nguyên).
- Ngân sách là hằng số trong `reviewer.py` (không thêm vào `config.py` để tránh sửa file dùng chung).
- Test mới: `tests/test_vin15/test_outline_summary_budget.py` (LLM chậm, LLM lỗi, LLM nhanh).

## Kiểm tra
- `pytest tests/ -q`: 179 passed, 1 skipped. `ruff check src tests`: sạch.

## Chưa kiểm tra / lưu ý
- Chưa chạy với model thật. Thread LLM quá hạn không hủy được, vẫn chạy nốt ở nền (có chặn bởi pool 4 thread;
  nếu pool đầy thì lời gọi sau phải xếp hàng và cũng sẽ hết hạn → dùng bản theo luật).
- Nếu cần chỉnh ngân sách theo môi trường, chuyển hằng số sang `Settings` (file dùng chung → cần review).
- `summarize_extension` có cùng rủi ro chậm; báo nhóm 2 có thể dùng lại `_llm_summary_within`.
