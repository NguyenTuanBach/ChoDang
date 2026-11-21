"""Che thông tin cá nhân (email, số điện thoại VN, mã số thuế, mã sinh viên) thành nhãn ``[EMAIL_1]``, ``[SDT_1]``...

Dùng ở BE cho lịch sử hội thoại gửi agent và cho tham số ghi vào audit/trace. Agent che lần nữa trước khi gọi LLM.
Không có thao tác khôi phục nhãn.
"""

from __future__ import annotations

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w])(?:\+84|0)[\s.-]?\d{2,3}[\s.-]?\d{3}[\s.-]?\d{3,4}(?!\d)")
_TAX_ID_BRANCH = re.compile(r"(?<![\w-])\d{10}-\d{3}(?![\w-])")
_TAX_ID = re.compile(r"(?<![\w-])\d{10}(?![\w-])")


class PiiRedactor:
    def __init__(self, student_id_pattern: str = ""):
        pattern = student_id_pattern.strip()
        try:
            self._student_id = re.compile(pattern) if pattern else None
        except re.error:
            self._student_id = None

    def redact(self, text: str) -> tuple[str, dict[str, str]]:
        """Trả ``(văn bản đã che, ánh xạ nhãn -> giá trị gốc)``. Cùng một giá trị luôn nhận cùng một nhãn."""
        mapping: dict[str, str] = {}
        by_value: dict[tuple[str, str], str] = {}
        counters: dict[str, int] = {}

        def label_for(kind: str, value: str) -> str:
            key = (kind, value)
            if key not in by_value:
                counters[kind] = counters.get(kind, 0) + 1
                by_value[key] = f"[{kind}_{counters[kind]}]"
                mapping[by_value[key]] = value
            return by_value[key]

        # MST 13 số (có hậu tố chi nhánh) phải che trước SĐT, nếu không số đầu bị nhận nhầm là SĐT.
        steps = [("EMAIL", _EMAIL), ("MST", _TAX_ID_BRANCH), ("SDT", _PHONE), ("MST", _TAX_ID)]
        if self._student_id is not None:
            steps.append(("MASV", self._student_id))
        for kind, pattern in steps:
            text = pattern.sub(lambda m, k=kind: label_for(k, m.group(0)), text)
        return text, mapping

    def redact_text(self, text: str) -> str:
        return self.redact(text)[0]
