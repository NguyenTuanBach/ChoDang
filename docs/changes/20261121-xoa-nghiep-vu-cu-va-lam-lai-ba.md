# Xóa nghiệp vụ cũ và làm lại phân tích nghiệp vụ (nhánh `konan`)

> Cấu trúc code ở file này đã đổi tiếp: xem `20261121-tach-be-agent.md` (không còn `src/`, `tests/`, `eval/` ở gốc).

## Mục tiêu
Bỏ toàn bộ nghiệp vụ VIN-15 cũ để phân tích lại từ đề bài (`docs/problem-statement.md`) như một BA, chốt nghiệp vụ chuẩn và phạm vi trước khi viết lại code.

## Đã làm
- **Xóa 253 file** bằng `git rm` (khôi phục được từ `main`):
  - Tài liệu: PRD, BRIEF, `docs/changes/*` cũ, wireframe, `.kiro/specs`, WORKLOG, JOURNAL, hai file đề xuất/phân công.
  - Backend: `src/api/vin15`, `src/workflow`, `src/seed.py`, `policy_graph/policy_guard/chitchat`, toàn bộ `src/services` trừ `llm.py`, `config/cohort.yaml`, `seed/policies`, 5 prompt nghiệp vụ, 3 script nghiệp vụ.
  - Frontend: `frontend/`, `web/`, `_legacy/`.
  - Eval/test: `policy_guard_eval.py`, `policy_adversarial.jsonl`, `tests/test_vin15`, `tests/samples`.
- **Giữ lại**: đề bài, `docs/guide/`, khung agent `graph.py` + nodes + guardrails + tools mẫu, `core/`, `db.py`, `services/llm.py`, `models/schemas.py`, Docker/deploy, hook ghi log, CLAUDE.md.
- **Sửa để không vỡ**: `src/models/orm.py` chỉ còn `User` + `AuditEvent`; `src/main.py` bỏ router VIN-15, seed, monitor, file tĩnh; `Dockerfile` bỏ stage frontend; `.dockerignore` bỏ dòng frontend.
- **Viết mới**: `docs/nghiep-vu-thuc-tap.md` (phân tích nghiệp vụ, phạm vi, vai trò, quy trình, trạng thái, yêu cầu, agent, rủi ro, câu hỏi mở).

## Cách kiểm tra
- `pytest tests -q` → 58 passed (khung template).
- `ruff check src tests eval scripts` → 8 lỗi, đều nằm trong `scripts/log_*.py`, `submit_log.py` (có từ trước, không liên quan).

## Chưa kiểm tra / còn lưu ý
- `ARCHITECTURE.md`, `PROJECT_CONTEXT.md`, `README.md`, `CLAUDE.md`, `presentation/` vẫn mô tả hệ thống cũ (còn nhắc `policy_graph.py` đã xóa).
- `src/config.py`, `.env.example` còn cấu hình nghiệp vụ cũ (monitor, OCR, seed, SSO).
- Chưa chạy thử `docker build` sau khi bỏ stage frontend.
- Tài liệu nghiệp vụ còn các câu hỏi mở Q1–Q8 (mục 13.2) và số liệu mẫu `[GIẢ LẬP]` ở mục 9.
