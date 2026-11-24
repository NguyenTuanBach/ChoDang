"""Nộp đề cương có kiểm tra: lỗi chắc chắn thì không lưu và báo đúng phần; đạt thì lưu kèm chuẩn đầu ra do AI nhận diện và nhận xét AI."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from tests.fakes import make_user
from vin15.domain.exception import AgentUnavailableError
from vin15.domain.model.user import Role
from vin15.service.outline.outline_check import check_outline
from vin15.service.outline.outline_review_service import OutlineReviewService

STUDENT = make_user(3, "sv.a@example.test", Role.STUDENT)

FULL = (
    "Mục tiêu: vận dụng kiến thức lập trình web vào dự án thực tế.\n"
    "Nhiệm vụ: phát triển và kiểm thử module quản lý đơn hàng.\n"
    "Kế hoạch: tuần 1-2 làm quen hệ thống, tuần 3-10 phát triển, tuần 11-12 báo cáo.\n"
    "Kết quả dự kiến: hoàn thành ba tính năng kèm kiểm thử."
)


def sections(issues):
    return [i["section"] for i in issues]


def test_full_outline_passes_rule_check():
    assert check_outline(FULL) == []


def test_missing_sections_are_reported_by_name():
    text = "Mục tiêu: học hỏi thêm về lập trình web và làm việc nhóm trong doanh nghiệp thực tế."
    assert sections(check_outline(text)) == ["Nhiệm vụ", "Kế hoạch", "Kết quả dự kiến"]


def test_too_short_outline_is_reported():
    issues = check_outline("Mục tiêu")
    assert issues[0]["section"] == "Nội dung" and issues[0]["level"] == "error"


def test_section_names_match_without_vietnamese_accents():
    text = FULL.lower().replace("ế", "e").replace("ụ", "u").replace("ạ", "a").replace("ả", "a")
    assert check_outline(text) == []


class FakeCases:
    def student_internship(self, user_id):
        return {"id": 1, "status": "confirmed", "cohort": "2026-K1", "lecturer_id": 2}


class FakeOutlines:
    def __init__(self):
        self.saved: list[dict] = []

    def outcomes_for(self, cohort):
        return [{"code": "LO1", "description": "Lập trình web"}, {"code": "LO2", "description": "Làm việc nhóm"}]

    def submit(self, student, text, codes, ai_review=None):
        self.saved.append({"text": text, "codes": codes, "review": ai_review})
        return 42


class FakeAgent:
    def __init__(self, body=None, fail=False):
        self.body, self.fail, self.calls = body or {}, fail, []

    async def call(self, path, payload, **_):
        self.calls.append((path, payload))
        if self.fail:
            raise AgentUnavailableError("agent tắt")
        return self.body


class FakeRedactor:
    def redact_text(self, text):
        return text


def run(coro):
    return asyncio.run(coro)


def service(agent, outlines=None):
    outlines = outlines or FakeOutlines()
    return OutlineReviewService(outlines, FakeCases(), agent, FakeRedactor()), outlines


def test_rule_errors_block_saving_but_still_return_ai_comments():
    agent = FakeAgent({"summary": "Cần bổ sung.", "issues": [{"section": "Kế hoạch", "message": "Thêm mốc thời gian."}], "outcome_codes": ["LO1"]})
    svc, outlines = service(agent)
    result = run(svc.submit(STUDENT, "Mục tiêu: học hỏi thêm về lập trình web và làm việc nhóm trong doanh nghiệp thực tế."))
    assert result["saved"] is False and result["id"] is None
    assert "Nhiệm vụ" in sections(result["issues"]) and "Kế hoạch" in sections(result["issues"])
    assert result["summary"] == "Cần bổ sung." and outlines.saved == []


def test_valid_outline_is_saved_with_ai_detected_outcomes_and_review():
    agent = FakeAgent({"summary": "Đề cương rõ ràng.", "issues": [{"section": "Kế hoạch", "message": "Nên chia mốc theo tháng."}], "outcome_codes": ["LO1", "LO9", "LO1"]})
    svc, outlines = service(agent)
    result = run(svc.submit(STUDENT, FULL))
    assert result["saved"] is True and result["id"] == 42
    # LO9 không có trong khóa nên bị loại; trùng được gộp.
    assert result["outcome_codes"] == ["LO1"] and outlines.saved[0]["codes"] == ["LO1"]
    assert outlines.saved[0]["review"]["summary"] == "Đề cương rõ ràng."
    assert agent.calls[0][0] == "/v1/outline/review"


def test_agent_down_still_saves_when_rules_pass():
    svc, outlines = service(FakeAgent(fail=True))
    result = run(svc.submit(STUDENT, FULL))
    assert result["saved"] is True and result["ai"] is False and result["outcome_codes"] == []
    assert len(outlines.saved) == 1


def test_warning_when_ai_finds_no_outcome_covered():
    svc, _ = service(FakeAgent({"summary": "", "issues": [], "outcome_codes": []}))
    result = run(svc.submit(STUDENT, FULL))
    assert result["saved"] is True and "Chuẩn đầu ra" in sections(result["issues"])


def test_not_confirmed_internship_cannot_submit():
    cases = SimpleNamespace(student_internship=lambda user_id: {"id": 1, "status": "in_progress", "cohort": "2026-K1", "lecturer_id": 2})
    svc = OutlineReviewService(FakeOutlines(), cases, FakeAgent(), FakeRedactor())
    try:
        run(svc.submit(STUDENT, FULL))
    except Exception as error:  # noqa: BLE001
        assert type(error).__name__ == "StateConflictError"
    else:
        raise AssertionError("phải ném StateConflictError")


# ---- Tải tệp đề cương: AI đọc và gợi ý bốn phần ----
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def test_text_file_is_sent_to_agent_as_plain_text_and_fields_are_cleaned():
    agent = FakeAgent({
        "kind": "outline",
        "fields": {
            "objective": {"value": "  Nắm quy trình web.  ", "confidence": 0.9},
            "plan": {"value": "Tuần 1-12", "confidence": 0.8},
            "company_name": {"value": "không thuộc đề cương"},
            "tasks": {"value": "   "},
        },
        "notes": "ok",
    })
    svc, _ = service(agent)
    result = run(svc.extract_file(STUDENT, "dc.txt", FULL.encode()))
    path, payload = agent.calls[0]
    assert path == "/v1/intake/extract" and payload["kind"] == "outline" and payload["mime"] == "text/plain"
    assert set(payload["fields"]) == {"objective", "tasks", "plan", "results"}
    assert result["fields"] == {"objective": {"value": "Nắm quy trình web."}, "plan": {"value": "Tuần 1-12"}}
    assert result["notes"] == "ok"


def test_image_is_sent_unchanged_with_its_real_mime():
    agent = FakeAgent({"fields": {}})
    svc, _ = service(agent)
    run(svc.extract_file(STUDENT, "dc.png", PNG))
    assert agent.calls[0][1]["mime"] == "image/png"


def test_unsupported_or_empty_file_is_rejected_before_calling_the_agent():
    agent = FakeAgent({"fields": {}})
    svc, _ = service(agent)
    for name, data in (("dc.exe", b"MZ\x90\x00xxxx"), ("dc.txt", b"")):
        try:
            run(svc.extract_file(STUDENT, name, data))
        except Exception as error:  # noqa: BLE001
            assert type(error).__name__ == "InvalidInputError"
        else:
            raise AssertionError("phải ném InvalidInputError")
    assert agent.calls == []


def test_extract_requires_confirmed_internship():
    cases = SimpleNamespace(student_internship=lambda user_id: {"id": 1, "status": "in_progress", "cohort": "2026-K1", "lecturer_id": 2})
    svc = OutlineReviewService(FakeOutlines(), cases, FakeAgent({"fields": {}}), FakeRedactor())
    try:
        run(svc.extract_file(STUDENT, "dc.txt", FULL.encode()))
    except Exception as error:  # noqa: BLE001
        assert type(error).__name__ == "StateConflictError"
    else:
        raise AssertionError("phải ném StateConflictError")
