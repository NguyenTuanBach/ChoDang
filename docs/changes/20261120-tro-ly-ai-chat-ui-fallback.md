# Trợ lý AI: giao diện chat toàn trang, lời chào, đường dự phòng, làm cứng guardrail, minh bạch thời gian

## Vấn đề
- Trang trợ lý có 2 thanh cuộn, ô nhập phải cuộn mới thấy.
- Gõ "hello" nhận "không tìm thấy quy định" (cứng).
- `gpt-4o` trả `KHONG_TIM_THAY` quá thận trọng dù truy hồi đã tìm đúng đoạn (ví dụ "Nhật ký thực tập phải nộp thế nào?").

## Đã làm
- **Giao diện** (`frontend/src/features/shared/Assistant.jsx`, `styles/layout.css`, `styles/components.css`, `AppShell.jsx`):
  khung `shell--chat` cao đúng màn hình, chỉ danh sách tin nhắn cuộn, ô nhập + gợi ý ở đáy; cuộn tới tin mới bằng
  `scrollTop` (không dùng `scrollIntoView` vì kéo cả trang). Hội thoại vẫn chỉ giữ trong bộ nhớ.
- **Small talk** (`src/agents/policy_graph.py`, `smalltalk_reply`): lời chào/cảm ơn/"bạn là ai" → trả lời cố định, không
  tra cứu, không gọi LLM, outcome `smalltalk`. Chỉ nhận khi cả câu là lời chào (không nhận nhầm câu hỏi thật).
- **Prompt** (`prompts/policy_assistant.md`): cho phép trả lời từng phần khi có đoạn cùng chủ đề; chỉ `KHONG_TIM_THAY`
  khi không đoạn nào nói về chủ đề.
- **Đường dự phòng** (`verify` trong `policy_graph.py`): LLM từ chối nhưng đoạn truy hồi điểm ≥
  `extractive_on_refusal_min_score` (mặc định 11.0, `src/config.py`) → trích nguyên văn kèm nguồn, mode
  `extractive_refused`. Dưới ngưỡng vẫn "không tìm thấy".

- **Làm cứng guard đầu vào** (`src/agents/policy_guard.py`): ngoài regex gốc, thêm bước chuẩn hóa (NFKC, bỏ ký tự vô hình,
  bỏ dấu, hạ chữ thường, gom ký tự rời "i g n o r e") rồi khớp mẫu injection tiếng Việt/Anh (quên/bỏ qua/vượt qua hướng dẫn,
  dịch/tóm tắt/in system prompt, đóng vai không bị ràng buộc, developer mode, "đừng tra cứu quy định") và hỏi dữ liệu SV khác
  (theo họ tên, "danh sách tất cả sinh viên"). "Đóng vai trò", "bỏ qua mốc", "quên nộp nhật ký" không bị chặn nhầm.
- **Guard đầu ra riêng cho trợ lý chính sách** (`Guardrails.check_policy_output` trong `src/agents/guardrails.py`, dùng ở
  `finalize`): chặn email/SĐT/MSSV trong câu trả lời và câu cam kết/quyết định thay giảng viên ("chắc chắn được duyệt", "tôi đã
  duyệt cho bạn"). Tách riêng khỏi `check_output_text` vì agent ReAct của template có thể hợp lệ trả email từ tool.
  Lớp đầu vẫn là `verify_citations` (loại câu không bám nguồn); guard đầu ra là lớp dự phòng thứ hai.
- **Minh bạch thời gian**: mỗi câu trả lời kèm `timing {llm_called, llm_ms, total_ms, model}` (SSE `done` và `/assistant/chat`);
  giao diện hiện dòng "Đã gọi gpt-4o · LLM 1.2s · tổng 2.4s" hoặc "Không gọi LLM (lý do) · tổng 0.1s".

- **Nhánh trò chuyện do LLM** (`src/agents/chitchat.py`, `prompts/policy_chitchat.md`, node `chitchat` trong `policy_graph.py`):
  sau `retrieve`, nếu điểm truy hồi cao nhất < `chat_max_retrieval_score` (mặc định 4.0; tin nhắn trò chuyện ≤ ~3.6, câu quy
  chế thật ≥ ~4.6) và có LLM → `gpt-4o-mini` trả lời tự nhiên (chào, "thanh kiu", hỏi thăm, ngoài lề, tâm sự…). Prompt cấm nêu
  số liệu/cam kết và cấm trả lời câu quy chế bằng kiến thức riêng; đầu ra qua `check_policy_output`, bỏ ký hiệu trích dẫn,
  cắt ≤ 600 ký tự; lỗi/quá 6s → rơi về lời chào cố định (`smalltalk_reply`) hoặc "không tìm thấy". Guard đầu vào vẫn chạy
  TRƯỚC nên injection không tới được LLM trò chuyện. Không có API key (mock-first) → giữ lời chào cố định bằng regex.

## Kiểm tra
- `pytest tests` → 292 passed; `ruff check` sạch; vitest frontend toàn bộ qua.
- Chạy thật với `gpt-4o` trên Docker: "Nhật ký…" → `extractive_refused`; "Doanh nghiệp tiếp nhận cần giấy tờ gì?" →
  `generated`; lạc đề (giá vàng, lịch thi, đổi giảng viên) → `not_found`; injection và hỏi hồ sơ SV khác → `refused`.

- Đo thực (Docker, gpt-4o): câu không gọi LLM (chào, bị guard chặn, không có đoạn phù hợp) xử lý ~0.1–0.2s ở server; câu có
  gọi LLM ~0.9–2.3s (bật LangSmith tracing cộng thêm ~1s so với tắt). Truy hồi + guard chỉ ~0.05s.
- Script đo trên Windows qua `localhost` thấy thêm ~2s do độ trễ kết nối IPv6→IPv4, không phải do server.

## Lưu ý
- Ngưỡng 11.0 hiệu chỉnh theo kho 33 đoạn hiện tại (đúng chủ đề ≥ ~11.8, lạc đề ≤ ~10.8); đổi kho quy định hoặc bật
  embedding thì cần hiệu chỉnh lại.
- Chưa kiểm tra giao diện chat trên màn điện thoại; embedding của 33 đoạn chưa được tạo (cần `POST /policies/reindex`).
