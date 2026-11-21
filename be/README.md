# be — backend VIN-15 (FastAPI)

Backend của cổng thực tập. Chạy ở cổng `8000`. Các tác tử AI **không nằm ở đây**: chúng chạy ở service riêng `agent/`
(cổng `8100`) và BE chỉ gọi qua HTTP (`infrastructure/agent_api`). Hai bên không import code của nhau (có test kiểm).

## Chạy
```sh
uv sync --extra dev
uv run python -m vin15            # http://localhost:8000/docs
uv run pytest && uv run ruff check src tests
```
Không có `DATABASE_URL` Postgres thì BE chạy **không database** (chỉ health). Có thì tự áp migration lúc khởi động.

## Cấu trúc `src/vin15/`
```
config/           settings, container DI, CORS, OpenAPI
domain/           lõi: exception/, model/, statemachine/      (không import tầng nào khác)
infrastructure/   nối ra ngoài, chỉ phụ thuộc vào trong
  agent_api/        client gọi agent-api (HTTP + WebSocket, service token)
  persistence/      Database (psycopg pool), SqlMigrator, *_repository.py
  security/         token HS256 (phiên và agent-token có claim scope)
  storage/ mail/ oauth/   R2, Gmail SMTP, Google OAuth   (chưa cài đặt)
service/          nghiệp vụ, chia theo tính năng (auth, user, internship, outline, milestone, progress,
                  exception, credit, policy, monitoring, notification, audit, dashboard, lms, agent)
presentation/     HTTP: controller/, dto/, advice/ (xử lý lỗi), rate_limit.py
resources/db/migration/   V<số>__<mô_tả>.sql  (kiểu Flyway)
```
Hướng phụ thuộc (kiểm bởi `tests/test_architecture.py`):
`presentation → service → domain`, `infrastructure → domain`, `presentation` không import `infrastructure` trực tiếp
(đi qua `Container`), `domain` không import ai.

## Database: Supabase
- Dùng chuỗi **Session pooler** (IPv4) trong `DATABASE_URL`. Host trực tiếp `db.<ref>.supabase.co` chỉ có IPv6.
- Pool tắt prepared statement (`prepare_threshold=None`) vì pooler chế độ transaction không hỗ trợ.
- **Mọi bảng mới phải `enable row level security`**: Supabase mở schema `public` qua khóa anon. Test
  `test_every_table_enables_row_level_security` chặn migration thiếu RLS.
- Sửa migration đã áp dụng là lỗi (checksum lệch): thêm `V<n+1>__...sql` mới.

## API hiện có
| Đường dẫn | Mô tả |
|---|---|
| `GET /api/health` | Liveness |
| `GET /api/health/readiness` | Có kiểm DB. 503 nếu DB không ping được |
| `GET /api/agent/health` | Trạng thái kết nối agent-api: `UP` / `DOWN` (503) / `DISABLED` |
| `POST /api/assistant/ws-ticket` | Vé WebSocket dùng một lần (~30 s). Cần token phiên; ở dev dùng người dùng mặc định |
| `WS /api/assistant/ws` | Chat trợ lý: `auth{ticket}` → `ask`/`cancel`/`ping`; kiểm `Origin`; giới hạn `ask`/phút và số kết nối ngay trong handler |
| `GET /api/assistant/conversations[/{id}]`, `GET /api/assistant/traces/{trace_id}` | Hội thoại của chính mình; vết (chủ sở hữu hoặc quản trị viên) |
| `POST /api/agent-tools/policy/search`, `GET /api/agent-tools/policy/chunks/{id}` | Tool tra quy định đang hiệu lực (agent gọi; service token + `X-On-Behalf-Of`) |
| `GET /api/agent-tools/me/{internship,milestones,progress,credit-checklist,requests}` | Tool cá nhân chỉ-đọc, chủ thể do BE quyết; chỉ sinh viên. Lỗi theo hợp đồng `{"error":{"code","message"}}` |
| `GET/POST /api/admin/policies…` | Quản trị viên: nạp văn bản (tách Điều/Khoản, bản nháp), xem trước, xuất bản |

Hợp đồng chi tiết: `.kiro/specs/agent-hoi-dap/contract.md`. Mọi `/api/agent-tools/*` ghi `audit_event` `actor_kind='agent'`.

## Dev: người dùng mặc định và dữ liệu giả
Chưa có đăng nhập thật. `AGENT_DEV_DEFAULT_USER_EMAIL` (chỉ dev; production **không khởi động** nếu đặt) chọn chủ thể cho tool agent khi
request không có agent-token và cho `ws-ticket` khi không có token phiên. `make seed-dev` (từ chối khi `APP_ENV=production`, chạy lại được) tạo
QTV `qtv@example.test`, GV `gv@example.test`, SV A `sv.a@example.test` (trễ mốc M3, thiếu nhật ký), SV B `sv.b@example.test` (đã nộp báo cáo cuối),
SV C `sv.c@example.test` (chưa có hồ sơ) và bộ quy chế mẫu `is_sample=true` (`resources/seed/policies/*.md`). Có `AGENT_API_URL` và agent chạy thì
seed xin embedding qua agent; không thì quy chế chỉ tìm bằng từ khóa (chạy lại seed khi agent sẵn sàng để bù embedding).

## Test
`uv run pytest`: test đơn vị/HTTP/WebSocket không cần mạng ngoài (agent giả là WebSocket server trên localhost). Test tích hợp V1 dùng Postgres nhúng
(`pgserver`); test V2+ (cần `vector`, `unaccent`, `btree_gist`) chạy trên `DATABASE_URL` trong **schema riêng** `vin15_test_*` rồi xóa, không đụng
dữ liệu có sẵn; không có `DATABASE_URL` thì tự bỏ qua kèm thông báo.

## Thêm tính năng mới
1. Mô hình + lỗi: `domain/`. 2. Bảng: migration mới + `infrastructure/persistence/<x>_repository.py`.
3. Nghiệp vụ: `service/<tính năng>/`. 4. Nối dây: `config/container.py`. 5. HTTP: `presentation/controller/` + `dto/`,
đăng ký router trong `main.py`. Cạnh đổi trạng thái đi qua state machine (`domain/statemachine/README.md`), không viết `update` rời.
