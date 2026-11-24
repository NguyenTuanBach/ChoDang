"""IntakeExtractor đọc đề cương (kind=outline): tách bốn phần từ văn bản thuần; có trong chế độ phân loại tự động của Trợ lý."""

from __future__ import annotations

import asyncio
import json

from fakes import FakeAi, reply
from vin15_agent.core.prompts import PromptLoader
from vin15_agent.intake import IntakeExtractor
from vin15_agent.intake.agent import AUTO_KINDS, FIELDS_BY_KIND, OUTLINE_FIELDS
from vin15_agent.shared.settings import Settings

OUTLINE_TEXT = (
    "Mục tiêu: Nắm quy trình phát triển web tại doanh nghiệp.\n"
    "Nhiệm vụ: Phát triển API và kiểm thử.\n"
    "Kế hoạch: Tuần 1-2 làm quen; tuần 3-12 phát triển.\n"
    "Kết quả dự kiến: Hoàn thành ba chức năng kèm kiểm thử."
)


def extractor(ai: FakeAi) -> IntakeExtractor:
    return IntakeExtractor(ai, PromptLoader(None), Settings(_env_file=None))


def run(coro):
    return asyncio.run(coro)


def test_outline_has_the_four_section_fields_and_is_auto_classified():
    assert set(OUTLINE_FIELDS) == {"objective", "tasks", "plan", "results"}
    assert "outline" in FIELDS_BY_KIND and "outline" in AUTO_KINDS


def test_text_outline_is_split_into_fields_and_unknown_fields_are_dropped():
    answer = {
        "kind": "outline",
        "fields": {
            "objective": {"value": "Nắm quy trình phát triển web.", "confidence": 0.9, "source": "Mục tiêu: ..."},
            "plan": {"value": "Tuần 1-2 làm quen; tuần 3-12 phát triển.", "confidence": 0.8, "source": ""},
            "company_name": {"value": "Không được phép", "confidence": 1, "source": ""},
            "tasks": {"value": "", "confidence": 0.5, "source": ""},
        },
        "notes": "",
    }
    ai = FakeAi(reply(json.dumps(answer, ensure_ascii=False)))
    result = run(extractor(ai).extract("text/plain", OUTLINE_TEXT.encode(), list(OUTLINE_FIELDS), "outline"))
    assert result["kind"] == "outline"
    assert set(result["fields"]) == {"objective", "plan"}  # trường lạ và giá trị rỗng bị bỏ
    assert result["fields"]["plan"]["value"].startswith("Tuần 1-2")
    # prompt gửi đi có đủ bốn phần và dùng đường chữ (không đòi vision)
    system = ai.calls[0]["messages"][0]["content"]
    assert all(name in system for name in OUTLINE_FIELDS)
    assert ai.calls[0].get("capability") != "vision"
    assert ai.calls[0]["max_tokens"] >= 3000


def test_long_outline_values_are_kept_up_to_4000_chars():
    long_value = "a" * 3500
    answer = {"fields": {"tasks": {"value": long_value, "confidence": 0.9, "source": ""}}}
    result = run(extractor(FakeAi(reply(json.dumps(answer)))).extract("text/plain", OUTLINE_TEXT.encode(), [], "outline"))
    assert len(result["fields"]["tasks"]["value"]) == 3500


def test_empty_text_file_is_rejected_without_calling_ai():
    ai = FakeAi(reply("{}"))
    result = run(extractor(ai).extract("text/plain", b"ngan", list(OUTLINE_FIELDS), "outline"))
    assert result["fields"] == {} and ai.calls == []
