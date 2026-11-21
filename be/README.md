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
  agent_api/        client gọi agent-api (HTTP + service token)
  persistence/      Database (psycopg pool), SqlMigrator, *_repository.py
  security/         token phiên HS256
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

## Thêm tính năng mới
1. Mô hình + lỗi: `domain/`. 2. Bảng: migration mới + `infrastructure/persistence/<x>_repository.py`.
3. Nghiệp vụ: `service/<tính năng>/`. 4. Nối dây: `config/container.py`. 5. HTTP: `presentation/controller/` + `dto/`,
đăng ký router trong `main.py`. Cạnh đổi trạng thái đi qua state machine (`domain/statemachine/README.md`), không viết `update` rời.
