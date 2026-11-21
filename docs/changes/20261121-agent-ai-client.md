# AiClient cho agent: OpenAI trực tiếp, proxy AiClient làm dự phòng

## Mục tiêu
Agent có một cửa duy nhất để gọi LLM. Đường chính gọi thẳng OpenAI; proxy `AiClient` (tương thích OpenAI) chỉ là đường dự phòng.
BE không giữ khóa LLM.

## Đã làm
- `agent/src/vin15_agent/core/ai_client.py`: `AiClient.complete(messages) -> ChatResult`. Thử đường chính, chuyển sang dự phòng
  **chỉ khi lỗi tạm thời** (mất kết nối, timeout, 429, 5xx). Lỗi 400/401/403 ném lại nguyên vẹn để không che lỗi cấu hình.
  Chưa cấu hình đường nào thì ném `LlmUnavailableError`.
- `shared/settings.py`: thêm `OPENAI_*` (khóa dùng `SecretStr`, không lộ trong repr/log) và `AICLIENT_*` (trống `AICLIENT_BASE_URL` = tắt dự phòng).
- `runtime/http/app.py`: tạo `AiClient` khi khởi động; `GET /v1/info` trả thêm `llm_providers` (tên đường đã cấu hình, không lộ khóa).
- `runtime/llm_check.py` + `make agent-llm-check`: gọi thử một câu để xác nhận khóa.
- `pyproject.toml`: thêm `openai`. `.env.example`: thêm `OPENAI_MODEL`, `OPENAI_TIMEOUT_SECONDS`, `AICLIENT_*`.
- Test kiến trúc mới: SDK `openai` chỉ được import trong `core/`.

## Cách kiểm tra
- `make agent-test` (14 test, gồm 7 test AiClient bằng client giả: dùng đường chính, fallback khi 429/mất kết nối, không fallback khi 401,
  hết đường thì `LlmUnavailableError`, chưa cấu hình, không lộ khóa) và `make agent-lint`.
- `make agent-llm-check` đã gọi thật OpenAI: `OK qua 'openai' (gpt-4o-mini-2024-07-18)`.

## Chưa kiểm tra / còn lưu ý
- **Đường dự phòng chưa chạy thật**: chưa có `AICLIENT_BASE_URL`/khóa của proxy; mới kiểm bằng client giả.
  Với proxy dùng tham số `max_tokens` (OpenAI trực tiếp dùng `max_completion_tokens`); nếu proxy khác thì sửa ở `from_settings`.
- Model mặc định `gpt-4o-mini` đặt tạm, chỉnh bằng `OPENAI_MODEL`. Chưa có streaming, tool calling, embedding.
- **Chưa che PII trước khi gửi LLM** (ràng buộc trong `CLAUDE.md`): phải làm trước khi agent nhận dữ liệu sinh viên thật.
- Mỗi lần gọi chưa ghi nhật ký chi phí/token ra đâu ngoài giá trị trả về.
