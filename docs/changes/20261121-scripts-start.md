# scripts/start.sh: chạy BE, agent và FE cùng lúc

## Mục tiêu
Một lệnh bật BE (cổng 8000), agent-api (cổng 8100) và FE Next.js (cổng 3000), gom log về một terminal. Dựa trên `DDDTN/scripts/start.sh`,
bỏ các phần dự án này không có (worker, runner, Postgres trong Docker vì DB là Supabase).

## Đã làm
- `scripts/start.sh`: đọc `.env` (từng dòng, không `source`), kiểm cổng (hỏi kill nếu bị chiếm), `uv sync` khi `uv.lock`/`pyproject.toml` đổi
  (dấu vết `.venv/.vin15-synced`), bật agent, BE rồi FE, chờ health, in log có tiền tố `[AG]`/`[BE]`.
- Dùng chung `AGENT_API_SERVICE_TOKEN`; nếu `.env` chưa đặt `AGENT_API_URL` thì script trỏ tới agent local để BE gọi được `/api/agent/health`.
- BE hoặc FE chết thì dừng tất cả; agent chết thì BE/FE vẫn chạy (khớp quy ước BE sống khi agent DOWN).
- FE: `npm ci` khi `package-lock.json` đổi, `npm run dev` ở `NEXT_PORT`, script export `BE_URL` để Next proxy đúng BE.
- Cờ: `--skip-be`, `--skip-agent`, `--skip-fe`, `-h`. Log từng tiến trình ở `/tmp/vin15-start-<pid>/`.

## Cách kiểm tra
- `NEXT_PORT=3100 scripts/start.sh`: cả ba lên; `/api/health`, `/healthz`, `/api/agent/health` (cả qua proxy của FE) đều `UP`; sau khi dừng, các cổng đóng, không còn tiến trình.

## Chưa kiểm tra / còn lưu ý
- Cổng 3000 đang bị FE của DDDTN chiếm trên máy dev nên đã thử bằng `NEXT_PORT=3100`. Script không tự kill tiến trình lạ khi không có terminal tương tác.
- Mới thử dừng bằng SIGTERM (chung trap với Ctrl+C); chưa thử Ctrl+C trong terminal tương tác, `--skip-be`/`--skip-agent`, và nhánh "cổng bị chiếm".
- Chỉ dành cho Linux (cần `ss`, `setsid`). Chưa có bản Windows.

## Bổ sung: chạy được chat khi chưa có đăng nhập (dev)
- `start.sh` tự đặt `AGENT_DEV_DEFAULT_USER_EMAIL=sv.a@example.test` khi `APP_ENV` khác production và biến chưa đặt; cần `make seed-dev` một lần để có user và quy chế mẫu.
- Lỗi đã gặp: `start.sh` export cả biến trống trong `.env`, trong đó `OPENAI_BASE_URL=` rỗng làm SDK `openai` lỗi kết nối (`APIConnectionError`),
  agent rơi vào chế độ suy giảm. Đã sửa ở `agent/src/vin15_agent/core/ai_client.py`: đặt `base_url` tường minh (`OPENAI_DEFAULT_BASE_URL`) khi cấu hình trống.
