// Nhãn tiếng Việt cho các trạng thái và loại.

export const INTERNSHIP_STATUS: Record<string, string> = {
  draft: "Nháp",
  submitted: "Chờ GV xác nhận",
  revision_requested: "Cần sửa hồ sơ",
  rejected: "Bị từ chối",
  confirmed: "Đã xác nhận, chờ đề cương",
  in_progress: "Đang thực tập",
  pending_credit: "Chờ thẩm định tín chỉ",
  credit_review: "Chờ QTV phê duyệt",
  completed: "Hoàn thành",
  closed_no_credit: "Kết thúc, không công nhận",
};

export const MILESTONE_STATUS: Record<string, string> = {
  pending: "Chờ nộp",
  submitted: "Đã nộp, chờ duyệt",
  accepted: "Đã chấp nhận",
  rejected: "Bị trả lại",
  overdue: "Quá hạn",
};

export const OUTLINE_STATUS: Record<string, string> = {
  submitted: "Chờ duyệt",
  approved: "Đã duyệt",
  revision_requested: "Cần sửa",
  rejected: "Bị từ chối",
};

export const REQUEST_STATUS: Record<string, string> = {
  open: "Đang chờ",
  approved: "Đã duyệt",
  rejected: "Bị từ chối",
  cancelled: "Đã hủy",
};

export const FLAG_STATUS: Record<string, string> = {
  open: "Mới",
  acknowledged: "Đã ghi nhận",
  resolved: "Đã giải quyết",
  dismissed: "Đã bác bỏ",
};

export const FLAG_KIND: Record<string, string> = {
  overdue_milestone: "Quá hạn mốc",
  missing_journal: "Thiếu nhật ký",
  weak_evidence: "Minh chứng yếu",
  outcome_mismatch: "Lệch chuẩn đầu ra",
  credit_shortfall: "Thiếu điều kiện tín chỉ",
  reminder_escalation: "Nhắc nhiều lần chưa phản hồi",
};

export const SEVERITY: Record<string, string> = { info: "Thông tin", warning: "Cảnh báo", critical: "Nghiêm trọng" };

export const ACCOUNT_STATUS: Record<string, string> = { invited: "Đã mời, chưa đăng nhập", active: "Đang hoạt động", revoked: "Đã thu hồi / khóa" };

export const QUEUE_KIND: Record<string, string> = {
  internship_submitted: "Hồ sơ",
  outline_submitted: "Đề cương",
  milestone_submitted: "Mốc",
  credit_assessment: "Thẩm định tín chỉ",
  credit_approval: "Phê duyệt tín chỉ",
  request: "Yêu cầu",
  risk_flag: "Cờ rủi ro",
};

export const MODE_LABEL: Record<string, string> = { onsite: "Tại doanh nghiệp", remote: "Từ xa", hybrid: "Kết hợp" };

export const ANCHOR_LABEL: Record<string, string> = { start: "ngày bắt đầu", mid: "giữa kỳ", end: "ngày kết thúc" };

export function fmtDate(value: string | null | undefined): string {
  if (!value) return "—";
  const [y, m, d] = value.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

export function fmtDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return `${date.toLocaleDateString("vi-VN")} ${date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}`;
}
