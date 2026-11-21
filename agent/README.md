# agent — service AI của VIN-15

Module **riêng**, chạy ở **cổng riêng** (mặc định `8100`). Backend (`be/`) gọi agent qua HTTP kèm service token
(`be/src/vin15/infrastructure/agent_api`). Hai bên **không import code của nhau** (có test kiểm: `tests/test_architecture.py`).

## Trạng thái
Chỉ có khung: `GET /healthz` (không token) và `GET /v1/info` (cần token). Chưa có agent nào.
Ba agent theo `docs/nghiep-vu-thuc-tap.md` mục 8: tác tử giám sát, trợ lý chính sách, tiền thẩm.

## Chạy
```sh
uv sync --extra dev
uv run vin15-agent-api            # http://localhost:8100/healthz
uv run pytest && uv run ruff check src tests
```

## Cấu hình (`.env` ở gốc repo)
| Biến | Ý nghĩa |
|---|---|
| `AGENT_API_PORT` | Cổng (mặc định 8100) |
| `AGENT_API_SERVICE_TOKEN` | Token BE phải gửi. Phải khớp giá trị bên BE |
| `APP_ENV=production` | Bật kiểm tra token không dùng giá trị mặc định |

## Cấu trúc dự kiến
```
src/vin15_agent/
  runtime/    điểm vào: HTTP app, nối các agent        (tầng trên cùng)
  <agent>/    mỗi agent một gói: domain, features, adapters
  core/       gọi LLM (proxy AiClient), prompt, bộ nhớ, tracing
  shared/     cấu hình, kiểu cơ bản                    (tầng dưới cùng)
prompts/      prompt dạng file .md (không nhúng prompt dài trong Python)
```
Quy tắc: `runtime → agent → core → shared`; SDK của nhà cung cấp LLM chỉ import trong `core`.

## Nguyên tắc nghiệp vụ (bất biến)
- Agent **không có công cụ quyết định**: không duyệt, chấp nhận, công nhận, ghi LMS. Agent chỉ đọc, gợi ý, soạn nháp,
  tự gửi nhắc nhở cho chính sinh viên và gắn cờ rủi ro. Quyền quyết định nằm ở BE (state machine).
- PII phải được che trước khi gửi LLM ngoài.
