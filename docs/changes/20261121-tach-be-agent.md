# Tách BE và agent thành hai module, cấu trúc theo DDDTN

## Mục tiêu
Chuyển repo từ một app `src/` kiểu template sang hai module chạy riêng: `be/` (backend, cổng 8000) và `agent/`
(service AI, cổng 8100), cấu trúc tham chiếu thư mục `DDDTN` cùng cấp. Chỉ dựng khung BE; `agent/` chỉ là khung tối thiểu.

## Đã làm
- **`be/`** (gói `vin15`): `config/` (settings, container DI), `domain/` (exception, model, statemachine README),
  `infrastructure/` (`agent_api` client, `persistence` gồm `Database` + `SqlMigrator`, `security` token HS256, khung `storage/mail/oauth`),
  `service/` (health + 15 gói tính năng rỗng theo `docs/nghiep-vu-thuc-tap.md`), `presentation/` (health, agent, xử lý lỗi, rate limit),
  `resources/db/migration/V1__baseline.sql` (`app_user`, `audit_event` chỉ-thêm, bật RLS).
- **`agent/`** (gói `vin15_agent`): FastAPI `GET /healthz` và `GET /v1/info` (cần service token), `prompts/` chuyển từ gốc repo.
- **Gốc repo**: `docker-compose.yml` (hai service), `Makefile`, `.github/workflows/ci.yml` (hai job), `.env.example` viết lại.
- **Đã bỏ**: `src/`, `tests/`, `eval/`, `requirements.txt`, `pytest.ini`, `ruff.toml`, Dockerfile cũ, SQLAlchemy/SQLite, OIDC Keycloak,
  khung ReAct của template (`graph.py`, nodes, tools, guardrails). Các file này còn nguyên trên nhánh `main`.
- `CLAUDE.md` cập nhật theo cấu trúc mới.

## Cách kiểm tra
- `make test` → BE 43 test (gồm migration chạy trên Postgres nhúng `pgserver`), agent 5 test. `make lint` sạch.
- Chạy cả hai: BE gọi `GET /api/agent/health` → `UP` khi token khớp; `DOWN` (503) khi token sai hoặc agent chưa chạy; BE vẫn sống.
- Test kiến trúc đã thử đột biến: thêm import sai tầng / import `vin15_agent` thì test fail.

## Chưa kiểm tra / còn lưu ý
- **Đã kết nối Supabase thật** qua Session pooler (`aws-0-ap-southeast-2`, IPv4), PostgreSQL 17. Host trực tiếp `db.<ref>.supabase.co` chỉ có IPv6 nên không dùng được từ máy dev.
  Đã áp `V1__baseline` (idempotent), `app_user` và `audit_event` bật RLS, xóa `audit_event` bị trigger chặn, `/api/health/readiness` báo `database: UP`.
- Chưa chạy `docker build` và `docker compose up` (chỉ kiểm `docker compose config`).
- Còn tài liệu cũ nhắc cấu trúc cũ: `README.md`, `ARCHITECTURE.md`, `PROJECT_CONTEXT.md`, `presentation/`, `docs/guide/` (tài liệu khóa học),
  `scripts/check_docs.py`, `deploy/` (Caddy, Keycloak).
- Khung ReAct và guardrail của template chưa được đưa sang `agent/`; sẽ port khi làm agent.
