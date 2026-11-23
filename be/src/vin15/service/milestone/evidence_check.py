"""Đối chiếu trường trên giấy xác nhận / phiếu đánh giá (M5) với hồ sơ thực tập (hàm thuần, không đụng DB).

Chỉ là **cảnh báo** cho giảng viên (rủi ro giấy giả R7); quyết định chấp nhận mốc vẫn là của giảng viên.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

#: Trường của giấy xác nhận (khớp ``COMPLETION_FIELDS`` phía agent).
COMPLETION_FIELDS = (
    "company_name",
    "company_tax_code",
    "student_name",
    "student_code",
    "position",
    "department",
    "actual_start_date",
    "actual_end_date",
    "mentor_name",
    "result_grade",
    "score",
    "company_comment",
    "signer_name",
    "signer_title",
    "letter_number",
    "letter_date",
    "has_stamp",
)

_COMPANY_NOISE = re.compile(r"\b(cong ty|cty|tnhh|co phan|cp|jsc|ltd|llc|co|mtv|mot thanh vien|tap doan)\b")


def normalize(text: str | None) -> str:
    """Bỏ dấu, chữ thường, gộp khoảng trắng — để so tên không lệ thuộc cách gõ."""
    raw = unicodedata.normalize("NFD", str(text or "")).replace("đ", "d").replace("Đ", "D")
    raw = "".join(c for c in raw if unicodedata.category(c) != "Mn").lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", raw).split())


def _company(text: str | None) -> str:
    return " ".join(_COMPANY_NOISE.sub(" ", normalize(text)).split())


def _digits(text: str | None) -> str:
    return re.sub(r"\D", "", str(text or ""))


def _date(text: str | None) -> date | None:
    try:
        return date.fromisoformat(str(text or "").strip()[:10])
    except ValueError:
        return None


def check_completion(fields: dict[str, str], internship: dict, student_name: str, student_code: str | None) -> list[dict]:
    """Trả danh sách ``{"field", "label", "detail"}`` cho những chỗ lệch với hồ sơ. Trường trống thì không xét."""
    out: list[dict] = []

    def add(field: str, label: str, detail: str) -> None:
        out.append({"field": field, "label": label, "detail": detail})

    def differs(a: str, b: str) -> bool:
        return bool(a and b) and a != b and a not in b and b not in a

    if differs(_company(fields.get("company_name")), _company(internship.get("company_name"))):
        add("company_name", "Tên doanh nghiệp khác hồ sơ", f"Giấy: {fields.get('company_name')} · Hồ sơ: {internship.get('company_name')}")
    tax_doc, tax_profile = _digits(fields.get("company_tax_code")), _digits(internship.get("company_tax_code"))
    if tax_doc and tax_profile and tax_doc != tax_profile:
        add("company_tax_code", "Mã số thuế khác hồ sơ", f"Giấy: {fields.get('company_tax_code')} · Hồ sơ: {internship.get('company_tax_code')}")
    if differs(normalize(fields.get("student_name")), normalize(student_name)):
        add("student_name", "Tên sinh viên trên giấy khác tài khoản", f"Giấy: {fields.get('student_name')} · Tài khoản: {student_name}")
    code_doc = normalize(fields.get("student_code")).replace(" ", "")
    code_me = normalize(student_code).replace(" ", "")
    if code_doc and code_me and code_doc != code_me:
        add("student_code", "Mã sinh viên trên giấy khác tài khoản", f"Giấy: {fields.get('student_code')} · Tài khoản: {student_code}")
    if differs(normalize(fields.get("mentor_name")), normalize(internship.get("mentor_name"))):
        add("mentor_name", "Người hướng dẫn khác hồ sơ", f"Giấy: {fields.get('mentor_name')} · Hồ sơ: {internship.get('mentor_name')}")

    start, end = _date(fields.get("actual_start_date")), _date(fields.get("actual_end_date"))
    if start and end:
        if end < start:
            add("actual_end_date", "Ngày kết thúc trước ngày bắt đầu", f"{start.isoformat()} → {end.isoformat()}")
        else:
            planned_start, planned_end = internship.get("start_date"), internship.get("end_date")
            if isinstance(planned_start, date) and isinstance(planned_end, date) and planned_end > planned_start:
                actual_weeks, planned_weeks = (end - start).days // 7, (planned_end - planned_start).days // 7
                if actual_weeks < planned_weeks:
                    add("actual_end_date", "Thời gian thực tập ngắn hơn đăng ký", f"Thực tế khoảng {actual_weeks} tuần · Đăng ký {planned_weeks} tuần")
    if normalize(fields.get("has_stamp")) in ("no", "khong"):
        add("has_stamp", "Giấy có thể chưa có chữ ký / dấu doanh nghiệp", "AI không thấy dấu hoặc chữ ký; giảng viên cần kiểm tra tệp gốc")
    return out
