# Yêu cầu ngoại lệ có lưu vết (HITL)

## Mục tiêu
Phần nâng cao của đề bài: luồng phê duyệt ngoại lệ có lưu vết. Mọi quyết định ngoại lệ bắt buộc do
giảng viên phụ trách (con người) đưa ra; agent/hệ thống không thể tự duyệt.

## Đã làm
- **Model** `ExceptionRequest` (`src/models/orm.py`, bảng `exception_request`, tạo qua `init_db`/`create_all`).
  Hai loại: `late_extension` (gia hạn quá hạn, tối đa 30 ngày) và `credit_recognition` (công nhận/quy đổi tín chỉ).
- **State machine**: entity `exception` (`open → approved | rejected | cancelled`) trong `src/workflow/state_machine.py`.
  Duyệt/từ chối là cạnh quyết định → chỉ `human` + GV phụ trách + bắt buộc lý do (P1).
- **Service** `src/services/exceptions.py`: kiểm tra payload theo loại, chặn trùng yêu cầu đang mở,
  AI tóm tắt (`reviewer.summarize_exception`, chỉ gợi ý, che PII), hệ quả khi duyệt:
  `late_extension` dời hạn + gỡ overdue + đóng cờ (audit `due_date_changed` có `exception_id`);
  `credit_recognition` chỉ ghi nhận quyết định.
- **API** (`src/api/vin15/exception_routes.py`): `GET/POST /internships/{id}/exceptions`, `GET /exceptions`,
  `POST /exceptions/{id}/cancel`, `POST /exceptions/{id}/decision`. Hàng chờ `/approvals/queue` có thêm nhóm
  `exceptions` (có điểm ưu tiên, `priority.py`); timeline `/internships/{id}/audit` gồm cả sự kiện ngoại lệ.
- **Frontend**: `ExceptionPanel.jsx` (SV gửi/theo dõi/hủy), `ExceptionCard` trong `LecturerQueue.jsx`,
  `DecisionBox` thêm `kind="exception"`; lịch sử audit hiển thị ở trang hồ sơ của GV.

## Kiểm tra
- `pytest tests` → 229 passed (có `tests/test_vin15/test_exceptions.py`, P1 trong `test_state_machine.py` đã phủ cạnh mới).
- `npx vitest run` (frontend) → 342 passed.
- `ruff check src tests` sạch.

## Chưa làm / lưu ý
- Chưa chạy thử giao diện trên trình duyệt (chỉ test tự động).
- Mặc định: chỉ GV phụ trách được quyết định (kể cả `credit_recognition`); admin chỉ xem qua `GET /exceptions`.
  Cần đổi nếu quy chế yêu cầu Hội đồng Khoa/admin duyệt tín chỉ.
- Chưa có loại `waive_requirement`, `change_company`; chưa có màn admin riêng và chưa có UI timeline cho sinh viên.
- Bảng mới tạo bằng `create_all`, không có migration (dự án chưa dùng Alembic).
