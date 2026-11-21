# Hợp đồng giao tiếp — Agent hỏi đáp

> Nguồn sự thật chung cho ba luồng làm song song (agent / BE / FE). Bản mã: `agent/src/vin15_agent/policy_assistant/protocol.py` (Pydantic) và `fe/src/lib/assistant-protocol.ts` (TypeScript). Đổi hợp đồng phải sửa cả ba chỗ + báo người điều phối.

## 1. Xác thực giữa các bên
- BE → agent (HTTP và WS): `Authorization: Bearer <AGENT_API_SERVICE_TOKEN>`.
- agent → BE (`/api/agent-tools/*`): `Authorization: Bearer <AGENT_API_SERVICE_TOKEN>` + `X-On-Behalf-Of: <agent_token>` nếu `start.actor.agent_token` không rỗng. Rỗng (dev) → BE dùng người dùng mặc định `AGENT_DEV_DEFAULT_USER_EMAIL`. Công cụ **không** nhận tham số chủ thể.
- Lỗi BE trả `{"error": {"code": "...", "message": "..."}}` (theo `global_exception_handler`); agent ánh xạ 401/403/404/429/5xx thành `ToolResult(ok=False, error{code,message})`.

## 2. Agent HTTP
- `POST /v1/embeddings` (service token): `{"texts": ["..."]}` → `{"model": "...", "dimensions": 1536, "vectors": [[...]]}`. Lỗi LLM → 503 `{"error":{"code":"llm_unavailable"}}`.
- `GET /v1/info`: `agents` gồm `"policy_assistant"`.

## 3. Agent WebSocket `WS /v1/policy-assistant/ws`
Bắt tay kiểm service token (sai → từ chối/đóng 4401). Khung đầu tiên phải là `start`; sau đó chỉ nhận `cancel`/`ping`. Một lượt mỗi kết nối. Kết thúc lượt: agent phát `final` hoặc `error` rồi đóng 1000. Khung quá 256 KiB → đóng 1009; JSON/`type` sai → 1003.

Khung (JSON, có `type`):
| type | hướng | trường |
|---|---|---|
| `start` | BE→agent | `conversation_id, turn_id, question, history[{role,content}], actor{role, agent_token}, today(YYYY-MM-DD)` |
| `cancel` | →agent | `{}` |
| `ping` / `pong` | hai chiều | `{}` |
| `ready` | agent→BE | `{}` (sau khi nhận `start` hợp lệ) |
| `status` | agent→ | `step` (`planning\|searching\|reading\|answering\|verifying`), `text` |
| `tool_call` | agent→ | `name, label` |
| `tool_result` | agent→ | `name, ok, summary` |
| `token` | agent→ | `delta` |
| `final` | agent→ | `answer, citations[], verdict, degraded, usage{prompt_tokens,completion_tokens,provider,model}, trace_id` |
| `error` | agent→ | `code` (`busy\|rate_limited\|timeout\|cancelled\|llm_unavailable\|internal`), `message` |

`verdict`: `answered | no_match | refused | needs_human | degraded | error_fallback`.
`citations[i]`: `chunk_id, doc_code, doc_title, version, article, clause, effective_from, is_sample, quote` (`quote` = nguyên văn điều/khoản, ≤ 1200 ký tự).
`answer`: Markdown, trích dẫn nội tuyến dạng `[cite:<chunk_id>]` — phía FE thay bằng chip bấm xem; `citations` do **code** dựng từ kết quả tool, không do LLM.

## 4. FE ↔ BE
- `POST /api/assistant/ws-ticket` (cần người dùng; dev: người dùng mặc định) → `{"ticket":"...","expires_in":30}`; vé dùng một lần.
- `WS /api/assistant/ws`: kiểm `Origin` ∈ `CORS_ORIGINS`. Khung FE→BE: `auth{ticket}` (≤ 5 s sau khi mở), `ask{conversation_id|null, turn_id, question}`, `cancel{turn_id}`, `ping{}`. BE→FE: `ready{}` sau `auth` đúng; mọi khung của lượt như bảng trên, **BE thêm** `turn_id` và `conversation_id` vào mỗi khung; `final` thêm `message_id`. `error` thêm các mã `busy` (đang có lượt), `rate_limited`, `invalid_frame`. Đóng: 1000 xong, 4401 xác thực, 4408 im lặng quá hạn, 4429 giới hạn kết nối.
- BE tự: cắt lịch sử (≤ `ASSISTANT_HISTORY_TURNS` lượt cuối) và che PII lịch sử trước khi gửi agent (agent che lần nữa); nếu FE rớt giữa lượt, BE chạy hết và lưu `final`.
- REST (người chủ): `GET /api/assistant/conversations` → `[{id,title,created_at,updated_at}]`; `GET /api/assistant/conversations/{id}` → `{id,title,messages:[{id,turn_id,role,content,citations,degraded,created_at}]}`; `GET /api/assistant/traces/{trace_id}` (chủ hoặc admin).

## 5. BE `/api/agent-tools/*` (chỉ-đọc; mỗi lời gọi ghi `audit_event actor_kind='agent'`)
`Chunk` = `{chunk_id, doc_code, doc_title, version, article_no, clause_no|null, heading, text, effective_from, effective_to|null, is_sample, score|null}`.

- `POST /api/agent-tools/policy/search` — body `{query, query_vector: number[]|null, top_k: 1..8 (mặc định 5)}` → `{status:"ok"|"no_match", mode:"hybrid"|"keyword", chunks: Chunk[]}`. Chỉ phiên bản `published` hiệu lực hôm nay (`Asia/Ho_Chi_Minh`).
- `GET /api/agent-tools/policy/chunks/{chunk_id:path}?with_neighbors=false` → `{chunk: Chunk, neighbors: Chunk[]}`; không có → 404 `not_found`.
- `GET /api/agent-tools/me/internship` → `{available, reason?, internship?: {cohort, status, start_date, end_date, mode, lecturer_name}}`
- `GET /api/agent-tools/me/milestones` → `{available, reason?, milestones: [{code, name, due_date, status, days_left, next_action}]}`
- `GET /api/agent-tools/me/progress` → `{available, reason?, journal: {submitted, expected, missing_weeks: [date]}, evidence: {submitted, required}}`
- `GET /api/agent-tools/me/credit-checklist` → `{available, reason?, items: [{code:"T1".."T6", label, met, value, threshold}], all_met}`
- `GET /api/agent-tools/me/requests` → `{available, reason?, requests: [{kind, status, created_at}]}`
- `available=false` + `reason="no_internship_record"` khi chưa có hồ sơ; vai trò giảng viên/quản trị gọi `me/*` → 403 `forbidden_role`. Không trả email/SĐT/MST/mã SV.

## 6. Cấu hình (đã có trong `.env.example`)
`OPENAI_EMBEDDING_MODEL, ASSISTANT_TEMPERATURE, AGENT_MAX_ROUNDS, AGENT_MAX_TOOL_CALLS, AGENT_TURN_SECONDS, BE_API_URL (agent→BE), PII_STUDENT_ID_PATTERN, SCHOOL_NAME, POLICY_NO_MATCH_THRESHOLD, AGENT_DEV_DEFAULT_USER_EMAIL, ASSISTANT_ASK_PER_MINUTE, ASSISTANT_MAX_CONNECTIONS_PER_USER, ASSISTANT_MAX_FRAME_BYTES, ASSISTANT_HISTORY_TURNS, ASSISTANT_WS_AUTH_SECONDS, NEXT_PUBLIC_BE_WS_URL`.
