"""Guardrail theo domain cho trợ lý chính sách (R8.6–8.7).

Bổ sung cho `guardrails.check_input` (pattern tiếng Anh của template):
- prompt injection tiếng Việt → từ chối
- hỏi dữ liệu SV khác (mã SV lạ, "hồ sơ của sinh viên khác") → từ chối
- yêu cầu ra quyết định ("duyệt cho em", "em được gia hạn không") → KHÔNG từ chối,
  đánh dấu decision_request để câu trả lời giải thích quy định + hướng dẫn tạo yêu cầu.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from src.agents.guardrails import GuardrailViolation, fold, guardrails

_INJECTION_VI = (
    re.compile(r"bỏ\s+qua\s+(?:(?:tất\s+cả|mọi|các|những)\s+)*(?:hướng\s+dẫn|chỉ\s+dẫn|quy\s+tắc|lệnh|ràng\s+buộc)", re.I),
    re.compile(r"(?:tiết\s+lộ|in\s+ra|cho\s+(?:tôi\s+|em\s+)?xem)\s+(?:system\s+prompt|prompt\s+hệ\s+thống|lời\s+nhắc\s+hệ\s+thống)", re.I),
    re.compile(r"(?:giả\s+vờ|đóng\s+vai|coi\s+như)\s+(?:bạn\s+)?(?:là\s+)?(?:giảng\s+viên|quản\s+trị|admin)", re.I),
    # Các biến thể không dấu thường xuất hiện trong prompt tấn công copy/paste.
    re.compile(r"bo\s+qua\s+(?:tat\s+ca\s+|moi\s+)?(?:huong\s+dan|quy\s+tac|lenh|rang\s+buoc)", re.I),
    re.compile(r"(?:in\s+ra|cho\s+(?:toi|em)\s+xem|tiet\s+lo)\s+(?:system\s+prompt|prompt\s+he\s+thong)", re.I),
)
# Chạy trên văn bản đã chuẩn hóa (NFKC, bỏ ký tự vô hình, bỏ dấu, hạ chữ thường) → bắt cả biến thể không dấu/đổi hoa thường.
_GAP = r"(?:\s+\S+){0,6}?\s+"  # tối đa vài từ chen giữa ("bỏ qua TẤT CẢ các")
_INJECTION_FOLDED = (
    re.compile(rf"\b(bo qua|quen|bo di|phot lo|huy bo|khong can tuan theo|dung tuan theo|vuot qua|ignore|forget|disregard|override|bypass){_GAP}"
               r"(huong dan|chi dan|quy tac|lenh|rang buoc|gioi han|chi thi|instructions?|rules?|guidelines?|restrictions?|"
               r"duoc dan|da duoc dan|da duoc cho|truoc do|ban dau)"),
    re.compile(r"(tiet lo|in ra|hien thi|cho .{0,20}xem|lap lai|doc lai|dich|translate|tom tat|viet lai|cho biet|reveal|show|print|repeat|leak|dump)"
               r".{0,25}(system prompt|prompt he thong|loi nhac he thong|chi dan he thong|huong dan (ban dau|he thong|noi bo)|"
               r"developer (prompt|message)|initial (prompt|instructions))"),
    re.compile(r"(dong vai(?! tro)|gia vo|gia lap|hay hanh dong nhu|tu gio (ban|may) la|ban bay gio la|act as|pretend (to be|you are)|"
               r"you are now|roleplay as).{0,30}(giang vien|admin|quan tri|khong (bi )?(gioi han|rang buoc|kiem duyet)|"
               r"unrestricted|jailbr|developer|dan\b|root)"),
    re.compile(r"\b(developer mode|che do (nha phat trien|lap trinh vien|admin)|jailbreak|dan mode|do anything now)\b"),
    re.compile(r"(khong can|dung can|dung|dung co) (tra cuu|dan nguon|trich dan|doi chieu) .{0,20}(quy dinh|van ban|nguon)"),
)
# Chuỗi liền (bỏ hết khoảng trắng/dấu câu) — chống chèn ký tự: "i g n o r e  p r e v i o u s"
_INJECTION_COMPACT = re.compile(r"(ignore|disregard|forget)(all|any)?(the)?(previous|prior|above|your)(instructions?|rules?|prompts?)"
                                r"|(reveal|show|print|repeat|leak)(your|the|me)?(system|developer)(prompt|instructions?)")
_SURNAME = r"(nguyen|tran|le|pham|hoang|huynh|phan|vu|vo|dang|bui|do|ngo|duong|ly)"
_OTHER_STUDENT_FOLDED = (
    re.compile(rf"(ho so|diem|thong tin|nhat ky|ket qua|email|so dien thoai|sdt|bai lam)\s+cua\s+(ban|sinh vien|sv|anh|chi)?\s*{_SURNAME}\s+[a-z]+"),
    re.compile(r"(danh sach|toan bo|tat ca)\s+(sinh vien|sv|ho so|diem|email|sdt|so dien thoai)"),
)
_STUDENT_CODE = re.compile(r"\b[Ss][Vv]\d{4,}\b|(?<!\d)\d{8}(?!\d)")
_OTHER_STUDENT = (
    re.compile(r"(?:hồ\s+sơ|điểm|thông\s+tin|nhật\s+ký|kết\s+quả|số\s+điện\s+thoại|email|địa\s+chỉ)\s+"
               r"(?:của\s+)?(?:sinh\s+viên|bạn|sv|học\s+viên)\s+(?:khác|tên)", re.I),
    re.compile(r"(?:hồ\s+sơ|điểm|thông\s+tin|nhật\s+ký|kết\s+quả)\s+của\s+(?:bạn\s+)?[A-ZĐ][a-zà-ỹ]+\s+[A-ZĐ]"),
)
_DECISION = (
    re.compile(r"(?:duyệt|phê\s+duyệt|chấp\s+thuận|đồng\s+ý|cho\s+phép|công\s+nhận)\s+(?:giúp\s+|cho\s+)?(?:em|tôi|mình)\b", re.I),
    re.compile(r"(?:em|tôi|mình)\s+(?:có\s+)?được\s+(?:gia\s+hạn|duyệt|công\s+nhận|miễn|hoãn|lùi)", re.I),
    re.compile(r"(?:cho|xin)\s+(?:em|tôi|mình)\s+(?:được\s+)?(?:gia\s+hạn|hoãn|lùi|dời)", re.I),
)


@dataclass
class GuardResult:
    refusal_reason: str = ""
    violation_type: str = ""
    decision_request: bool = False


_INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060\ufeff\u00ad]")


def _canon(text: str) -> str:
    """NFKC (đổi chữ full-width/biến thể) + bỏ ký tự vô hình + bỏ dấu + hạ chữ thường + gom khoảng trắng."""
    text = _INVISIBLE.sub("", unicodedata.normalize("NFKC", text))
    return re.sub(r"\s+", " ", fold(text)).strip()


def check_policy_query(query: str, own_student_code: str | None) -> GuardResult:
    # Thứ tự: pattern gốc (loại vi phạm cụ thể) → biến thể đã chuẩn hóa → dữ liệu sinh viên khác
    try:
        guardrails.check_input(query)
    except GuardrailViolation as exc:
        return GuardResult("Yêu cầu chứa nội dung tìm cách vượt qua quy tắc của trợ lý.", exc.violation_type)
    for pattern in _INJECTION_VI:
        if pattern.search(query):
            return GuardResult("Yêu cầu chứa nội dung tìm cách vượt qua quy tắc của trợ lý.", "prompt_injection_vi")
    canon = _canon(query)
    compact = re.sub(r"[\W_]+", "", canon)
    if any(p.search(canon) for p in _INJECTION_FOLDED) or _INJECTION_COMPACT.search(compact):
        return GuardResult("Yêu cầu chứa nội dung tìm cách vượt qua quy tắc của trợ lý.", "prompt_injection_vi")
    if any(p.search(canon) for p in _OTHER_STUDENT_FOLDED):
        return GuardResult("Trợ lý không cung cấp thông tin của sinh viên khác.", "other_student_data")
    own = (own_student_code or "").lower()
    if any(code.lower() != own for code in _STUDENT_CODE.findall(query)):
        return GuardResult("Trợ lý không cung cấp thông tin của sinh viên khác.", "other_student_data")
    for pattern in _OTHER_STUDENT:
        if pattern.search(query):
            return GuardResult("Trợ lý không cung cấp thông tin của sinh viên khác.", "other_student_data")
    return GuardResult(decision_request=any(p.search(query) for p in _DECISION))
