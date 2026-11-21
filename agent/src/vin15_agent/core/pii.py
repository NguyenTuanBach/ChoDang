"""Che PII trước khi nội dung đi ra LLM bên ngoài, vào log hoặc trace.

Mẫu phủ: email, số điện thoại VN, mã số thuế, mã sinh viên (regex cấu hình) và khóa/token. Che bằng regex không phủ hết
(đặc biệt họ tên tự do) nên BE còn phải chỉ trả trường tối thiểu ở tool cá nhân. Mặc định KHÔNG khôi phục nhãn.
"""

from __future__ import annotations

import re
from typing import NamedTuple

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# 0xxxxxxxxx hoặc +84xxxxxxxxx (9 số sau đầu số), cho phép dấu cách, chấm, gạch ngang giữa các số.
_PHONE = re.compile(r"(?<![\w+])(?:\+84|0)(?:[\s.-]?\d){9}(?!\d)")
# Mã số thuế: 10 số, hoặc 13 số (10-3).
_TAX13 = re.compile(r"(?<![\w.-])\d{10}-\d{3}(?![\w-]|\.\d)")
_TAX10 = re.compile(r"(?<![\w.-])\d{10}(?![\w-]|\.\d)")
_SECRET = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}|\bBearer\s+[A-Za-z0-9._~+/=-]{16,}")


class Redaction(NamedTuple):
    text: str
    #: nhãn → giá trị gốc (chỉ phục vụ kiểm thử/đối soát cục bộ, KHÔNG ghi log).
    mapping: dict[str, str]


class PiiRedactor:
    """Mỗi lượt hỏi dùng một thể hiện để nhãn nhất quán giữa câu hỏi, lịch sử và kết quả tool."""

    def __init__(self, student_id_pattern: str = "") -> None:
        pattern = student_id_pattern.strip()
        try:
            self._student = re.compile(pattern) if pattern else None
        except re.error as exc:
            raise ValueError(f"PII_STUDENT_ID_PATTERN không phải regex hợp lệ: {exc}") from exc
        self._labels: dict[tuple[str, str], str] = {}
        self._counters: dict[str, int] = {}
        self._mapping: dict[str, str] = {}

    def _label(self, kind: str, value: str) -> str:
        key = (kind, value)
        if key not in self._labels:
            self._counters[kind] = self._counters.get(kind, 0) + 1
            label = f"[{kind}_{self._counters[kind]}]"
            self._labels[key] = label
            self._mapping[label] = value
        return self._labels[key]

    def redact(self, text: str) -> Redaction:
        """Trả văn bản đã che và ánh xạ nhãn → giá trị gốc của các nhãn xuất hiện trong ``text``."""
        used: dict[str, str] = {}

        def sub(kind: str):
            def repl(match: re.Match[str]) -> str:
                label = self._label(kind, match.group(0))
                used[label] = match.group(0)
                return label

            return repl

        text = _SECRET.sub("[KHOA_BI_MAT]", text)
        text = _EMAIL.sub(sub("EMAIL"), text)
        text = _TAX13.sub(sub("MST"), text)
        text = _PHONE.sub(sub("SDT"), text)  # 10 số bắt đầu bằng 0 coi là SĐT (mơ hồ với MST, cùng là PII)
        text = _TAX10.sub(sub("MST"), text)
        if self._student is not None:
            text = self._student.sub(sub("MSSV"), text)
        return Redaction(text, used)

    def redact_text(self, text: str) -> str:
        return self.redact(text).text
