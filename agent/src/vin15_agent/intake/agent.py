"""``IntakeExtractor``: PDF có chữ → trích văn bản → **che PII** (email, SĐT, MST) → LLM → khôi phục nhãn cục bộ.

LLM chỉ thấy nhãn ``[EMAIL_1]``, ``[SDT_1]``, ``[MST_1]``; agent tự thay lại giá trị gốc trong kết quả nên PII không rời khỏi hệ thống.
Ảnh/PDF quét **không** gửi LLM (không che được thông tin cá nhân trên ảnh): trả ghi chú để sinh viên nhập tay.
Kết quả chỉ là gợi ý có nguồn và độ tin cậy; không lưu, sinh viên xác nhận từng trường.
"""

from __future__ import annotations

import io
import logging
import re
from typing import Any

from vin15_agent.core.ai_client import AiClient
from vin15_agent.core.pii import PiiRedactor
from vin15_agent.core.prompts import PromptLoader
from vin15_agent.core.structured import StructuredOutputError, ask_json
from vin15_agent.shared.settings import Settings

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 12000
MIN_TEXT_CHARS = 30
_LABEL = re.compile(r"\[[A-Z]+_\d+\]")

FIELD_HINTS = {
    "company_name": "tên doanh nghiệp",
    "company_tax_code": "mã số thuế",
    "company_address": "địa chỉ doanh nghiệp",
    "position": "vị trí thực tập",
    "mentor_name": "họ tên người hướng dẫn tại doanh nghiệp",
    "mentor_email": "email người hướng dẫn",
    "mentor_phone": "số điện thoại người hướng dẫn",
    "job_description": "mô tả công việc",
    "start_date": "ngày bắt đầu (định dạng YYYY-MM-DD)",
    "end_date": "ngày kết thúc (định dạng YYYY-MM-DD)",
}


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages[:10])


class IntakeExtractor:
    def __init__(self, ai: AiClient, prompts: PromptLoader, settings: Settings):
        self._ai = ai
        self._prompts = prompts
        self._student_pattern = settings.pii_student_id_pattern

    async def extract(self, mime: str, data: bytes, fields: list[str]) -> dict[str, Any]:
        wanted = [f for f in fields if f in FIELD_HINTS]
        if mime != "application/pdf":
            return {"fields": {}, "notes": "Chỉ trích tự động từ PDF có chữ. Ảnh không được gửi cho AI vì chứa thông tin cá nhân; hãy nhập tay."}
        try:
            text = pdf_text(data)
        except Exception:
            logger.warning("Không đọc được PDF", exc_info=True)
            return {"fields": {}, "notes": "Không đọc được tệp PDF; hãy nhập tay."}
        if len(text.strip()) < MIN_TEXT_CHARS:
            return {"fields": {}, "notes": "PDF không có lớp chữ (có thể là ảnh quét); hãy nhập tay."}
        redactor = PiiRedactor(self._student_pattern)
        redaction = redactor.redact(text[:MAX_TEXT_CHARS])
        system = self._prompts.render("intake.system", fields="\n".join(f"- {name}: {FIELD_HINTS[name]}" for name in wanted))
        try:
            parsed = await ask_json(self._ai, system, redaction.text, max_tokens=1200)
        except StructuredOutputError:
            return {"fields": {}, "notes": "AI không trả kết quả đọc được; hãy nhập tay."}
        out: dict[str, Any] = {}
        for name, item in (parsed.get("fields") or {}).items():
            if name not in wanted or not isinstance(item, dict) or not item.get("value"):
                continue
            out[name] = {
                "value": self._restore(str(item["value"]), redaction.mapping),
                "confidence": item.get("confidence", 0),
                "source": self._restore(str(item.get("source", "")), redaction.mapping),
            }
        return {"fields": out, "notes": str(parsed.get("notes", ""))[:300]}

    @staticmethod
    def _restore(text: str, mapping: dict[str, str]) -> str:
        return _LABEL.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)
