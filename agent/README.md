# agent — service AI của VIN-15

Module **riêng**, chạy ở **cổng riêng** (mặc định `8100`). Backend (`be/`) gọi agent qua HTTP kèm service token
(`be/src/vin15/infrastructure/agent_api`). Hai bên **không import code của nhau** (có test kiểm: `tests/test_architecture.py`).

## Trạng thái
Có: `GET /healthz` (không token), `GET /v1/info` (cần token), `POST /v1/embeddings` (cần token, cho BE nạp chunk) và
**trợ lý chính sách** (`WS /v1/policy-assistant/ws`, cần token ở bắt tay). `core/ai_client.py` gọi LLM: OpenAI trực tiếp, proxy AiClient dự phòng
(chat có tool, streaming, embedding; đường dự phòng khai báo khả năng qua `AICLIENT_CAPABILITIES`, mặc định chỉ chat thường).
Có thêm ba agent **một lượt, đầu ra cấu trúc, không có công cụ ghi** (`runtime/http/structured_agents.py`, đều cần token): chuẩn hóa hồ sơ
`POST /v1/intake/extract` (PDF có chữ → che PII → LLM → khôi phục nhãn cục bộ), giám sát `POST /v1/monitor/review` (lệch chuẩn đầu ra, minh chứng yếu) và
tiền thẩm `POST /v1/pre-review`. BE gửi dữ liệu đã che PII, nhận kết luận rồi **tự kiểm và tự ghi** (cờ rủi ro ghi `actor_kind=agent`); agent không đổi trạng thái nào.
Prompt: `prompts/{intake,monitor_review,pre_review}.system.md`.
Hợp đồng khung WebSocket: `.kiro/specs/agent-hoi-dap/contract.md`; bản mã: `policy_assistant/protocol.py`.

Trợ lý chính sách (ReAct, mọi tool chỉ-đọc, gọi ngược BE `/api/agent-tools/*`): `search_policy`, `get_policy_clause` (mọi vai trò) và
`get_my_*` (chỉ sinh viên, không tham số chủ thể); giảng viên/quản trị viên có `get_staff_queue`, `list_risk_flags`, `get_dashboard_summary`,
`list_internships` (chỉ tham số lọc; phạm vi do BE quyết từ agent-token). **Prompt và văn phong theo vai trò**: `prompts/policy_assistant.system.md` (phần chung)
+ `prompts/persona.{student,lecturer,admin}.md` (khối `<part id="persona">` giọng/cấu trúc và `<part id="workflow">` cách phân loại câu hỏi); câu từ chối
cố định có biến thể `*_staff` cho giảng viên/quản trị viên (`prompts/refusals.md`). Hậu kiểm bằng code: trích dẫn `[cite:id]` ⊆ chunk đã thấy (≤ 5), số liệu phải có trong nguồn,
viết lại cụm cam kết, che PII trước khi vào LLM/log, chế độ suy giảm (`degraded`) khi LLM sập.

## Chạy
```sh
uv sync --extra dev
uv run vin15-agent-api            # http://localhost:8100/healthz
uv run pytest && uv run ruff check src tests
make agent-llm-check              # gọi thử LLM một câu (từ gốc repo)
make agent-eval ARGS="--persona sv_a"   # đánh giá bằng LLM THẬT + BE đã seed (tests/eval/cases.yaml); không chạy trong CI
```

## Cấu hình (`.env` ở gốc repo)
| Biến | Ý nghĩa |
|---|---|
| `AGENT_API_PORT` | Cổng (mặc định 8100) |
| `AGENT_API_SERVICE_TOKEN` | Token BE phải gửi. Phải khớp giá trị bên BE |
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL` | LLM chính (trống base URL = api.openai.com) |
| `AICLIENT_BASE_URL`, `AICLIENT_API_KEY` | LLM dự phòng; trống base URL = tắt |
| `AICLIENT_CAPABILITIES` | Khả năng đường dự phòng hỗ trợ (`tools,stream,embed`, cách nhau dấu phẩy); trống = chỉ chat thường |
| `OPENAI_EMBEDDING_MODEL`, `ASSISTANT_TEMPERATURE` | Model embedding; nhiệt độ riêng của trợ lý (mặc định 0.2; model suy luận bỏ qua) |
| `AGENT_MAX_ROUNDS`, `AGENT_MAX_TOOL_CALLS`, `AGENT_TURN_SECONDS` | Giới hạn mỗi lượt: vòng LLM (6), lần gọi tool (8), giây (25) |
| `AGENT_TOOL_TIMEOUT_SECONDS`, `ASSISTANT_MAX_CONCURRENT_TURNS` | Hạn một lời gọi tool tới BE (8 s); số lượt đồng thời tối đa (50, vượt thì `error: busy`) |
| `BE_API_URL` | Địa chỉ BE để agent gọi tool (cùng `AGENT_API_SERVICE_TOKEN`) |
| `PII_STUDENT_ID_PATTERN`, `SCHOOL_NAME`, `ASSISTANT_SAMPLE_NOTICE`, `AGENT_PROMPTS_DIR` | Regex mã SV để che PII; tên trường trong prompt; cảnh báo quy chế mẫu; thư mục prompt |
| `APP_ENV=production` | Bật kiểm tra token không dùng giá trị mặc định |

## Cấu trúc dự kiến
```
src/vin15_agent/
  runtime/    điểm vào: HTTP app, nối các agent        (tầng trên cùng)
  <agent>/    mỗi agent một gói (policy_assistant: agent, be_client, tools/, verify, degraded, protocol)
  core/       AiClient, tools, agent_loop, pii, prompts, tracing
  shared/     cấu hình, kiểu cơ bản                    (tầng dưới cùng)
prompts/      prompt dạng file .md (không nhúng prompt dài trong Python)
```
Quy tắc: `runtime → agent → core → shared`; SDK của nhà cung cấp LLM chỉ import trong `core`.

## Nguyên tắc nghiệp vụ (bất biến)
- Agent **không có công cụ quyết định**: không duyệt, chấp nhận, công nhận, ghi LMS. Agent chỉ đọc, gợi ý, soạn nháp,
  tự gửi nhắc nhở cho chính sinh viên và gắn cờ rủi ro. Quyền quyết định nằm ở BE (state machine).
- PII phải được che trước khi gửi LLM ngoài.
