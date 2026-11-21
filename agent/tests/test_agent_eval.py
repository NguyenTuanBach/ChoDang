"""Runner đánh giá (task 24.3): bộ câu hợp lệ + chỉ số tính đúng trên kết quả mẫu (tất định, LLM giả)."""

import asyncio

import pytest

from fakes import DURATION, FakeAi, FakeBe, reply
from vin15_agent.policy_assistant.agent import PolicyAssistant
from vin15_agent.policy_assistant.be_client import BeToolsClient
from vin15_agent.runtime.agent_eval import (
    CASES_PATH,
    Case,
    CaseResult,
    compute_metrics,
    evaluate,
    execute_case,
    format_report,
    load_cases,
    select_cases,
)
from vin15_agent.shared.settings import Settings

D = DURATION["chunk_id"]


def case(**kw) -> Case:
    base = {"id": "x", "group": "grounded", "question": "q", "expect": {}}
    return Case.model_validate({**base, **kw})


def result(c: Case, **kw) -> CaseResult:
    base = dict(case=c, verdict="answered", answer="Cần 8 tuần.", citations=[{"chunk_id": D, "quote": DURATION["text"], "effective_from": "2026-01-01"}], tools_called=["search_policy"], latency_ms=1000, prompt_tokens=100, completion_tokens=50)  # noqa: E501
    base.update(kw)
    return CaseResult(**base)


# ---- bộ câu ----


def test_cases_file_has_40_to_60_cases_in_six_groups_with_unique_ids():
    cases = load_cases(CASES_PATH)
    assert 40 <= len(cases) <= 60
    assert {c.group for c in cases} == {"grounded", "personal", "decision", "no_basis", "validity", "adversarial"}
    assert len({c.id for c in cases}) == len(cases)
    for c in cases:
        assert c.question.strip() and c.expect.verdict, c.id
        if c.group == "personal":
            assert c.persona in {"sv_a", "sv_b"}, c.id
        if c.group == "adversarial":
            assert set(c.expect.verdict) <= {"refused", "needs_human"} or c.id in {"a09", "a10"}, c.id


def test_select_cases_by_persona_group_and_limit():
    cases = load_cases(CASES_PATH)
    only_a = select_cases(cases, persona="sv_a")
    assert all(c.persona in (None, "sv_a") for c in only_a) and not any(c.persona == "sv_b" for c in only_a)
    assert all(c.persona is None for c in select_cases(cases, persona=None))
    assert {c.group for c in select_cases(cases, persona="sv_a", groups=["adversarial"])} == {"adversarial"}
    assert len(select_cases(cases, persona="sv_a", limit=3)) == 3


def test_invalid_case_file_is_rejected(tmp_path):
    bad = tmp_path / "c.yaml"
    bad.write_text("- {id: a, group: khong_co, question: q, expect: {verdict: [answered]}}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_cases(bad)


# ---- evaluate: kiểm tra từng câu ----


def test_evaluate_passes_when_expectations_met():
    c = case(expect={"verdict": ["answered"], "cited_any": ["thời lượng"], "tools_called": ["search_policy"], "answer_contains": ["8 tuần"]})
    assert evaluate(c, result(c), today="2026-11-21") == []


def test_evaluate_reports_each_kind_of_failure():
    c = case(expect={"verdict": ["refused"], "cited_any": ["không có cụm này"], "tools_called": ["get_my_progress"], "tools_not_called": ["search_policy"], "answer_not_contains": ["8 tuần"]})
    failures = " | ".join(evaluate(c, result(c), today="2026-11-21"))
    for fragment in ("verdict", "cited_any", "tools_called", "tools_not_called", "answer_not_contains"):
        assert fragment in failures


def test_evaluate_general_checks_write_tools_commitment_leak_citations():
    c = case(expect={"verdict": ["answered"]})
    assert any("tool ghi" in f for f in evaluate(c, result(c, tools_called=["search_policy", "approve_credit"]), today="2026-11-21"))
    assert any("cam kết" in f for f in evaluate(c, result(c, answer="Em chắc chắn được công nhận."), today="2026-11-21"))
    assert any("[[" in f for f in evaluate(c, result(c, answer="[[refuse:other_user]]"), today="2026-11-21"))
    assert any("hiệu lực" in f for f in evaluate(c, result(c, citations=[{"chunk_id": D, "quote": "x", "effective_from": "2027-01-01"}]), today="2026-11-21"))
    assert any("không có trong citations" in f for f in evaluate(c, result(c, answer=f"Cần 8 tuần [cite:{D}] [cite:bia]."), today="2026-11-21"))
    assert any("lỗi" in f for f in evaluate(c, result(c, verdict=None, error_code="internal"), today="2026-11-21"))


# ---- chỉ số R14.3 ----


def test_compute_metrics_on_sample_results():
    g1 = case(id="g1", expect={"verdict": ["answered"], "cited_any": ["thời lượng"]})
    g2 = case(id="g2", expect={"verdict": ["answered"], "cited_any": ["không có"]})
    a1 = case(id="a1", group="adversarial", expect={"verdict": ["refused"]})
    a2 = case(id="a2", group="adversarial", expect={"verdict": ["refused"]})
    d1 = case(id="d1", group="decision", expect={"verdict": ["needs_human"]})
    results = [
        result(g1),
        result(g2),
        result(a1, verdict="refused", answer="Mình không thể.", citations=[], tools_called=[]),
        result(a2, verdict="answered", answer="Dạ đây ạ.", citations=[], tools_called=[], latency_ms=3000, prompt_tokens=300, completion_tokens=150),
        result(d1, verdict="needs_human", answer="Em đã được công nhận rồi.", tools_called=["search_policy", "update_internship"]),
    ]
    m = compute_metrics(results, today="2026-11-21")
    assert m.total == 5 and m.citation_accuracy == pytest.approx(0.5)  # g1 đúng, g2 sai (2 câu có kỳ vọng trích dẫn)
    assert m.adversarial_refusal_rate == pytest.approx(0.5) and m.adversarial_total == 2
    assert m.commitment_count == 1 and m.write_tool_calls == 1
    assert m.avg_latency_ms == pytest.approx((1000 * 4 + 3000) / 5) and m.avg_tokens == pytest.approx((150 * 4 + 450) / 5)
    assert m.passed == 2  # g1, a1 đạt; g2 (cụm), a2 (verdict), d1 (cam kết + tool ghi) hỏng
    assert not m.targets_met


def test_targets_met_when_all_goals_reached():
    g = case(id="g", expect={"verdict": ["answered"], "cited_any": ["thời lượng"]})
    a = case(id="a", group="adversarial", expect={"verdict": ["refused"]})
    m = compute_metrics([result(g), result(a, verdict="refused", answer="Không.", citations=[], tools_called=[])], today="2026-11-21")
    assert m.citation_accuracy == 1.0 and m.adversarial_refusal_rate == 1.0 and m.commitment_count == 0 and m.write_tool_calls == 0 and m.targets_met
    assert "ĐẠT" in format_report([result(g)], m) or "đạt" in format_report([result(g)], m).lower()


def test_metrics_with_no_applicable_cases_do_not_crash():
    c = case(expect={"verdict": ["answered"]})
    m = compute_metrics([result(c)], today="2026-11-21")
    assert m.citation_accuracy is None and m.adversarial_refusal_rate is None


# ---- execute_case với LLM giả + BE giả (khung → CaseResult) ----


def _assistant(ai, be):
    settings = Settings(_env_file=None, agent_api_service_token="tok", agent_turn_seconds=5)
    return PolicyAssistant(ai, lambda t: BeToolsClient("http://be", "tok", t, transport=be.transport()), settings)


def test_execute_case_collects_frames_into_result():
    c = case(id="g1", question="Thời lượng thực tập tối thiểu?", expect={"verdict": ["answered"], "cited_any": ["thời lượng"]})
    ai = FakeAi(reply("", [("c1", "search_policy", {"query": "thời lượng thực tập"})]), reply(f"Cần 8 tuần [cite:{D}]."))
    res = asyncio.run(execute_case(_assistant(ai, FakeBe()), c, today="2026-11-21"))
    assert res.verdict == "answered" and res.tools_called == ["search_policy"] and res.citations[0]["chunk_id"] == D
    assert res.prompt_tokens == 20 and res.latency_ms >= 0 and res.error_code is None
    assert evaluate(c, res, today="2026-11-21") == []


def test_execute_case_records_error_frames():
    c = case(question="q", expect={"verdict": ["answered"]})
    res = asyncio.run(execute_case(_assistant(FakeAi(RuntimeError("hỏng")), FakeBe()), c, today="2026-11-21"))
    assert res.verdict is None and res.error_code == "internal"
