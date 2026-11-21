# CLAUDE.md — Project context cho Claude Code (C4/C5)

> Inspire team 001 (PROJECT_CONTEXT Quick Rehydrate) + team 008 (CLAUDE.md structure).

## Quick Rehydrate (≤ 60s)

Đọc nhanh khi mất context:
- **Đây là**: VIN-15 — hệ thống hỗ trợ thực tập bằng AI cho một trường (sản phẩm thật, đang làm lại nghiệp vụ từ đầu).
- **Đề tài**: `docs/problem-statement.md`. Nghiệp vụ đã phân tích: `docs/nghiep-vu-thuc-tap.md` (bản nháp 0.1).
- **Cấu trúc**: `be/` (FastAPI, cổng 8000) + `agent/` (service AI riêng, cổng 8100). Đọc `be/README.md`, `agent/README.md`.
- **Stack**: Python 3.12, uv, FastAPI, Pydantic v2, Postgres (Supabase) qua psycopg, migration SQL kiểu Flyway.
- **Chạy**: `make install`, `make be-run` (BE), `make agent-run` (agent). Test: `make test`. Lint: `make lint`.
- **Cấu hình**: `.env` ở gốc repo (mẫu `.env.example`). BE không giữ khóa LLM, chỉ agent dùng.

## Current Invariants (để không drift)

- **Source of truth kỹ thuật**: code trong `be/src/` và `agent/src/`. File `.md` (kể cả file này) chỉ là
  tóm tắt — khi mâu thuẫn, CODE WINS.
- **BE và agent chỉ nói chuyện qua HTTP** (`be/.../infrastructure/agent_api`, kèm service token). BE không import
  `vin15_agent`, agent không import `vin15`. Hai test `test_architecture.py` kiểm điều này.
- **Hướng phụ thuộc trong BE**: `presentation → service → domain`, `infrastructure → domain`, `presentation` đi qua `Container`.
- **Agent không có công cụ quyết định**: không duyệt, chấp nhận, công nhận, ghi LMS. Quyền quyết định nằm ở BE (state machine).
- **Mọi bảng mới phải bật RLS** (Supabase mở schema `public` qua khóa anon) — có test chặn.
- **Prompts**: nằm ở `agent/prompts/*.md` (external file, `{{placeholder}}`). KHÔNG nhúng prompt dài trong Python string.
- **Ràng buộc đề tài** (chi tiết ở `docs/problem-statement.md`):
  - Phê duyệt đề cương thực tập, xử lý ngoại lệ, công nhận quy đổi tín chỉ BẮT BUỘC có
    giảng viên/quản trị viên phê duyệt (HITL) — agent không được tự quyết.
  - Câu trả lời về chính sách phải trích dẫn đúng văn bản quy định hiện hành.
  - Bảo mật thông tin sinh viên và doanh nghiệp (che PII trước khi gửi LLM ngoài).
- **Logging hooks**: `.claude/.cursor/.codex/.gemini/.github` auto-log prompt vào
  `.ai-log/`. KHÔNG disable, KHÔNG bypass `--no-verify`. Đừng dán khóa/mật khẩu vào prompt (sẽ bị ghi log).

## Quy tắc viết tài liệu (docs)

- **Làm xong một chức năng/refactor thì viết tài liệu** vào `docs/changes/`, một file `.md`. Có thể viết
  ngay khi vừa xong hoặc ngay trước khi commit — miễn là có trước khi kết thúc công việc.
- **Tên file**: `YYYYMMDD-<làm-cái-gì>.md` (kebab-case, ngày là ngày làm), ví dụ
  `docs/changes/20261114-refactor-fe.md`.
- **Nội dung**: vấn đề/mục tiêu, đã làm gì (cấu trúc, file chính), cách kiểm tra, và những gì
  chưa kiểm tra hoặc còn lưu ý.
- **Người dùng yêu cầu chỉnh sửa lại tính năng đã có tài liệu → SỬA file docs đó**, không tạo file
  `.md` mới cho cùng tính năng. Cập nhật nội dung cho khớp code; chỉ tạo file mới khi là tính năng khác.

## Quy tắc commit / PR

- **KHÔNG** thêm `Co-Authored-By: Claude ...` vào commit message và **KHÔNG** thêm dòng
  "Generated with Claude Code" vào mô tả PR. Viết message thuần, không kèm trailer attribution nào.
- **Khi sửa theo review/CI (Auto-fix)**: chỉ sửa code, chạy kiểm tra, commit và push. **KHÔNG** đăng comment
  hay reply trên PR/thread review, và không cần resolve thread (kể cả dòng "Addressed by Claude Code").
  Giải thích gì thêm thì nói với người dùng trong phiên làm việc.

## Quyết định kỹ thuật (ADR ngắn)

- **Tách agent thành service riêng**: cổng riêng, vòng đời riêng, khóa LLM chỉ nằm ở agent → BE nhỏ, dễ kiểm, ranh giới HITL rõ.
- **Postgres (Supabase) + migration SQL**: không dùng ORM; mỗi thực thể một repository, schema nằm trong `resources/db/migration`.
- **Defence-in-depth cho HITL**: agent không được cấp công cụ quyết định, và state machine từ chối actor không phải người.
