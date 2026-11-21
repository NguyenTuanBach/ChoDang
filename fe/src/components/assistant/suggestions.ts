import type { Role } from "@/lib/auth";

// Câu hỏi gợi ý ở trạng thái trống của trợ lý, theo vai trò (bấm là gửi luôn).
export const SUGGESTIONS: Record<Role, string[]> = {
  student: ["Hạn nộp đề cương là khi nào?", "Em còn thiếu gì để được công nhận tín chỉ?", "Mở trang mốc và minh chứng giúp em"],
  lecturer: ["Có bao nhiêu sinh viên đang bị chậm thực tập?", "Hôm nay tôi cần duyệt những gì?", "Mở trang cờ rủi ro"],
  admin: ["Có bao nhiêu hồ sơ đang bị chậm thực tập?", "Hàng chờ phê duyệt hôm nay có gì?", "Mở trang quy định"],
};
