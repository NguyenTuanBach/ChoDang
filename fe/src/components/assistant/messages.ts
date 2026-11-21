// Văn bản tiếng Việt cho lỗi, cảnh báo và kết luận của trợ lý.
import type { Verdict } from "@/lib/assistant-protocol";
import type { UiErrorCode } from "@/lib/assistant/reducer";

export const ERROR_TEXT: Record<UiErrorCode, string> = {
  busy: "Trợ lý đang xử lý một câu hỏi khác của bạn. Hãy đợi câu đó xong rồi hỏi lại.",
  rate_limited: "Bạn hỏi quá nhanh hoặc mở quá nhiều kết nối. Vui lòng chờ một lúc rồi thử lại.",
  timeout: "Trợ lý trả lời quá lâu nên đã dừng. Hãy thử lại hoặc đặt câu hỏi ngắn gọn hơn.",
  llm_unavailable: "Dịch vụ AI tạm thời không khả dụng. Hãy thử lại sau ít phút.",
  cancelled: "Bạn đã dừng câu trả lời này.",
  internal: "Hệ thống gặp lỗi khi xử lý câu hỏi. Hãy thử lại sau.",
  invalid_frame: "Yêu cầu gửi lên không hợp lệ. Hãy tải lại trang rồi thử lại.",
  ticket_failed: "Không lấy được quyền kết nối tới trợ lý (có thể chưa đăng nhập hoặc BE chưa sẵn sàng).",
  auth_failed: "Phiên kết nối không hợp lệ hoặc đã hết hạn. Hãy thử lại.",
  connection_failed: "Không kết nối được tới trợ lý. Kiểm tra mạng rồi thử lại.",
  connection_lost: "Mất kết nối trước khi hệ thống nhận được câu hỏi. Hãy gửi lại.",
};

export const SAMPLE_WARNING =
  "Căn cứ có văn bản mẫu, chưa phải quy chế chính thức của trường. Chỉ dùng để tham khảo, không dùng để ra quyết định.";

export const DEGRADED_WARNING =
  "Chế độ hạn chế: dịch vụ AI gặp sự cố tạm thời nên câu trả lời có thể chưa đầy đủ. Hãy đối chiếu với nguyên văn quy chế.";

export const VERDICT_NOTE: Partial<Record<Verdict, string>> = {
  no_match: "Không tìm thấy căn cứ phù hợp trong quy chế hiện hành.",
  refused: "Trợ lý không trả lời câu hỏi này.",
  needs_human:
    "Vấn đề này cần giảng viên hoặc quản trị viên xem xét. Trợ lý chỉ cung cấp thông tin, không tự quyết định.",
};

export const STEP_LABEL = {
  planning: "Đang phân tích câu hỏi",
  searching: "Đang tra cứu quy chế",
  reading: "Đang đọc văn bản",
  answering: "Đang soạn câu trả lời",
  verifying: "Đang kiểm tra trích dẫn",
} as const;
