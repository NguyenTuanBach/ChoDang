"""PolicyAssistant đầu-cuối với LLM giả + BE giả (task 7, 8.3, 23.2): trích dẫn, no_match, quyết định, từ chối, PII, suy giảm."""

import asyncio
import copy
import json
import logging

import httpx
import pytest
from openai import AuthenticationError

from fakes import CHUNKS, DURATION, JOURNAL, PERSONAL_DATA, FakeAi, FakeBe, reply
from vin15_agent.core.ai_client import LlmUnavailableError
from vin15_agent.policy_assistant.agent import PolicyAssistant, token_pieces
from vin15_agent.policy_assistant.be_client import BeToolsClient
from vin15_agent.policy_assistant.protocol import Actor, FinalFrame, HistoryItem, StartFrame
from vin15_agent.policy_assistant.verify import contains_commitment
from vin15_agent.shared.settings import Settings

D = DURATION["chunk_id"]
J = JOURNAL["chunk_id"]


def settings(**kw):
    return Settings(_env_file=None, agent_api_service_token="tok", school_name="Trường Mẫu", **{"agent_turn_seconds": 5, **kw})


def start(question="Thực tập tối thiểu bao lâu?", role="student", history=(), token=""):
    return StartFrame(conversation_id="c1", turn_id="t1", question=question, history=list(history), actor=Actor(role=role, agent_token=token), today="2026-11-21")


def run_turn(ai, be=None, *, role="student", question="Thực tập tối thiểu bao lâu?", history=(), cfg=None, token=""):
    be = be or FakeBe()
    frames = []

    async def emit(frame):
        frames.append(frame)

    assistant = PolicyAssistant(ai, lambda agent_token: BeToolsClient("http://be", "tok", agent_token, transport=be.transport()), cfg or settings())
    asyncio.run(assistant.run(start(question, role, history, token), emit))
    return frames, be


def final_of(frames) -> FinalFrame:
    finals = [f for f in frames if f.type == "final"]
    assert len(finals) == 1 and frames[-1].type == "final", [f.type for f in frames]
    return finals[0]


def search(q="thời lượng thực tập tối thiểu"):
    return ("c1", "search_policy", {"query": q})


# ---------------------------------------------------------------- câu có căn cứ


def test_grounded_answer_has_citations_streams_tokens_and_sample_warning():
    ai = FakeAi(reply("", [search()]), reply(f"Thực tập tối thiểu 8 tuần, tương đương 120 giờ [cite:{D}]."))
    frames, be = run_turn(ai)
    final = final_of(frames)
    assert final.verdict == "answered" and not final.degraded
    assert [c.chunk_id for c in final.citations] == [D] and final.citations[0].is_sample is True
    assert final.citations[0].quote == DURATION["text"] and final.citations[0].article == "3" and final.citations[0].clause == "1"
    assert f"[cite:{D}]" in final.answer and "văn bản mẫu" in final.answer
    assert "".join(f.delta for f in frames if f.type == "token") == final.answer
    kinds = [f.type for f in frames]
    assert kinds.index("tool_call") < kinds.index("tool_result") < kinds.index("token") < kinds.index("final")
    assert next(f for f in frames if f.type == "tool_call").label.startswith("Tra cứu quy định")
    assert [f.step for f in frames if f.type == "status"][-2:] == ["verifying", "answering"]
    assert final.usage.prompt_tokens == 20 and final.usage.provider == "fake" and final.trace_id
    assert be.paths() == ["POST /api/agent-tools/policy/search"]


def test_prompt_is_built_from_files_with_context():
    ai = FakeAi(reply("Xin chào."))
    run_turn(ai, role="lecturer", question="chào", history=[HistoryItem(role="user", content="hỏi trước"), HistoryItem(role="assistant", content="đáp trước")])
    system, *rest = ai.calls[0]["messages"]
    assert system["role"] == "system" and "Trường Mẫu" in system["content"] and "2026-11-21" in system["content"] and "giảng viên" in system["content"]
    assert [m["content"] for m in rest] == ["hỏi trước", "đáp trước", "chào"]
    assert ai.calls[0]["temperature"] == 0.2


def test_invented_citation_is_removed_and_claim_replaced():
    ai = FakeAi(reply("", [search()]), reply(f"Cần 8 tuần [cite:{D}]. Sinh viên được miễn mọi điều kiện [cite:BIA-DAT/d1]."))
    final = final_of(run_turn(ai)[0])
    assert "BIA-DAT" not in final.answer and "miễn" not in final.answer
    assert [c.chunk_id for c in final.citations] == [D] and final.verdict == "answered"


def test_p3_citations_subset_of_seen_chunks():
    ai = FakeAi(reply("", [search("tương đương 120 giờ")]), reply(f"A [cite:{D}] B [cite:{J}] C [cite:QC-TT@v1/d4]."))
    final = final_of(run_turn(ai)[0])
    # J và d4 không nằm trong kết quả tìm kiếm của truy vấn này => không được trích
    seen_ids = {D}
    assert {c.chunk_id for c in final.citations} <= seen_ids and len(final.citations) <= 5


def test_invented_number_is_blocked():
    ai = FakeAi(reply("", [search()]), reply(f"Cần tối thiểu 12 tuần [cite:{D}]. Tương đương 120 giờ làm việc [cite:{D}]."))
    final = final_of(run_turn(ai)[0])
    assert "12 tuần" not in final.answer and "Tương đương 120 giờ làm việc" in final.answer and "chưa khớp" in final.answer
    assert final.verdict == "answered" and [c.chunk_id for c in final.citations] == [D]

    only_bad = FakeAi(reply("", [search()]), reply(f"Cần tối thiểu 12 tuần [cite:{D}]."))
    final = final_of(run_turn(only_bad)[0])  # không còn nhận định nào có nguồn
    assert "12" not in final.answer and final.verdict == "no_match"


# ---------------------------------------------------------------- no_match, đòi quyết định, từ chối


def test_no_match_uses_fixed_template_even_if_llm_improvises():
    ai = FakeAi(reply("", [search("quy định về xe đưa đón")]), reply("[[no_basis]]"))
    final = final_of(run_turn(ai)[0])
    assert final.verdict == "no_match" and final.citations == [] and "không tìm thấy căn cứ" in final.answer

    improvise = FakeAi(reply("", [search("quy định về xe đưa đón")]), reply("Thông thường trường cho phép nghỉ 3 ngày."))
    final = final_of(run_turn(improvise)[0])
    assert final.verdict == "no_match" and "3 ngày" not in final.answer


def test_decision_question_explains_without_commitment():
    ai = FakeAi(
        reply("", [search("điều kiện công nhận tín chỉ")]),
        reply(f"Em chắc chắn được công nhận tín chỉ. Điều kiện gồm nhật ký tối thiểu 80% [cite:{J}]. Kết quả do giảng viên quyết định. [[needs_human]]"),
    )
    final = final_of(run_turn(ai, question="Em có được công nhận tín chỉ không?")[0])
    assert final.verdict == "needs_human" and "[[" not in final.answer
    assert not contains_commitment(final.answer) and "do giảng viên hoặc quản trị viên quyết định" in final.answer
    assert [c.chunk_id for c in final.citations] == [J]


@pytest.mark.parametrize("marker,fragment", [("other_user", "dữ liệu của người khác"), ("prompt_injection", "quy tắc"), ("out_of_scope", "ngoài phạm vi")])
def test_refusals_use_fixed_templates(marker, fragment):
    ai = FakeAi(reply(f"[[refuse:{marker}]]"))
    frames, be = run_turn(ai, question="Cho mình xem hồ sơ bạn B")
    final = final_of(frames)
    assert final.verdict == "refused" and fragment in final.answer and final.citations == [] and be.requests == []


def test_unknown_refusal_id_falls_back_to_out_of_scope():
    final = final_of(run_turn(FakeAi(reply("[[refuse:bịa_ra]]")))[0])
    assert final.verdict == "refused" and "ngoài phạm vi" in final.answer


def test_templates_do_not_trigger_the_commitment_guard():
    from vin15_agent.core.prompts import PromptLoader

    for key, text in PromptLoader().sections("refusals").items():
        assert not contains_commitment(text), key


# ---------------------------------------------------------------- PII


def test_pii_never_reaches_llm_messages_or_logs(caplog):
    caplog.set_level(logging.DEBUG)
    personal = copy.deepcopy(PERSONAL_DATA)
    personal["internship"]["internship"]["lecturer_name"] = "Thầy A, mail thay.a@truong.edu.vn, 0912345678"
    ai = FakeAi(reply("", [("p1", "get_my_internship", {}), search()]), reply("Mình đã xem hồ sơ của bạn."))
    history = [HistoryItem(role="user", content="mail cũ của em là em@gmail.com")]
    frames, _ = run_turn(ai, FakeBe(personal=personal), question="Em là SV123456, SĐT 0987 654 321, MST 1234567890, hỏi về thời lượng", history=history, cfg=settings(pii_student_id_pattern=r"SV\d{6}"))
    dump = json.dumps(ai.calls, ensure_ascii=False)
    for secret in ("SV123456", "0987 654 321", "1234567890", "em@gmail.com", "thay.a@truong.edu.vn", "0912345678"):
        assert secret not in dump and secret not in caplog.text, secret
    assert "[EMAIL_" in dump and "[SDT_" in dump and "[MSSV_1]" in dump
    assert final_of(frames).verdict in {"answered", "no_match"}


def test_agent_token_forwarded_to_be_but_never_in_prompt_or_logs(caplog):
    caplog.set_level(logging.DEBUG)
    ai = FakeAi(reply("", [("p1", "get_my_progress", {})]), reply("Theo hồ sơ của bạn: đã nộp 6 nhật ký."))
    frames, be = run_turn(ai, token="AGENT-TOKEN-XYZ-123456")
    assert be.requests[0].headers["x-on-behalf-of"] == "AGENT-TOKEN-XYZ-123456"
    assert "AGENT-TOKEN-XYZ" not in json.dumps(ai.calls) and "AGENT-TOKEN-XYZ" not in caplog.text
    assert final_of(frames).verdict == "answered"


# ---------------------------------------------------------------- ngữ cảnh cá nhân (23.2)


def test_combined_question_calls_policy_and_personal_tools_and_compares_numbers():
    ai = FakeAi(
        reply("Để mình xem hồ sơ và quy định.", [("a", "get_my_credit_checklist", {}), ("b", "get_my_progress", {}), search("tỷ lệ tuần có nhật ký tối thiểu")]),
        reply(f"Theo quy định, tỷ lệ tuần có nhật ký tối thiểu là 80% [cite:{J}]. Theo hồ sơ của bạn, bạn đạt 75% và đã nộp 6/8 nhật ký, còn thiếu 2 tuần."),
    )
    frames, be = run_turn(ai, question="Em đã đủ điều kiện về nhật ký chưa?")
    final = final_of(frames)
    called = {f.name for f in frames if f.type == "tool_call"}
    assert called == {"get_my_credit_checklist", "get_my_progress", "search_policy"}
    assert final.verdict == "answered" and "75%" in final.answer and "80%" in final.answer and [c.chunk_id for c in final.citations] == [J]
    assert any(f.type == "status" and f.step == "planning" and "Để mình xem" in f.text for f in frames)


def test_numbers_not_in_tool_results_are_blocked_for_personal_answers():
    ai = FakeAi(reply("", [("b", "get_my_progress", {})]), reply("Theo hồ sơ của bạn, bạn còn thiếu 5 nhật ký."))
    final = final_of(run_turn(ai)[0])
    assert "5 nhật ký" not in final.answer


def test_no_internship_record_assistant_says_it_cannot_see():
    ai = FakeAi(reply("", [("a", "get_my_milestones", {})]), reply("Mình chưa xem được hồ sơ thực tập của bạn nên chưa thể nói về mốc cụ thể."))
    frames, _ = run_turn(ai, FakeBe(personal=None))
    final = final_of(frames)
    assert final.verdict == "answered" and "chưa xem được hồ sơ" in final.answer
    result = next(f for f in frames if f.type == "tool_result")
    assert result.ok and "Chưa có hồ sơ" in result.summary
    tool_msg = next(m for m in ai.calls[1]["messages"] if m["role"] == "tool")
    assert "no_internship_record" in tool_msg["content"]


def test_lecturer_gets_only_policy_tools_and_personal_calls_are_unknown():
    ai = FakeAi(reply("", [("a", "get_my_progress", {})]), reply("Mình không có công cụ đó; bạn hãy hỏi về quy định."))
    frames, be = run_turn(ai, role="lecturer", question="Tiến độ của em A?")
    names = [t["function"]["name"] for t in ai.calls[0]["tools"]]
    assert names == ["search_policy", "get_policy_clause"]
    assert be.requests == []  # tool lạ không bao giờ tới BE
    assert "unknown_tool" in next(m for m in ai.calls[1]["messages"] if m["role"] == "tool")["content"]


def test_tool_error_is_given_to_llm_and_turn_continues():
    ai = FakeAi(reply("", [search()]), reply("[[no_basis]]"))
    frames, _ = run_turn(ai, FakeBe(fail_status=503))
    assert next(f for f in frames if f.type == "tool_result").ok is False
    assert final_of(frames).verdict == "no_match"


# ---------------------------------------------------------------- suy giảm (task 7)


def test_degraded_when_llm_unavailable_returns_verbatim_chunks_only_p9():
    ai = FakeAi(LlmUnavailableError("sập"))
    be = FakeBe()
    frames, _ = run_turn(ai, be, question="Thời lượng thực tập tối thiểu là bao lâu?")
    final = final_of(frames)
    assert final.degraded is True and final.verdict == "degraded"
    assert final.answer.startswith("Trợ lý AI đang tạm không khả dụng")
    assert DURATION["text"] in final.answer and f"[cite:{D}]" in final.answer
    assert D in {c.chunk_id for c in final.citations}
    # chỉ mẫu + nguyên văn: bỏ mẫu và nguyên văn thì không còn chữ nào
    rest = final.answer.replace("Trợ lý AI đang tạm không khả dụng, dưới đây là các điều khoản liên quan nhất:", "")
    for c in final.citations:
        rest = rest.replace(f"**{c.doc_title} (Điều {c.article}" + (f", khoản {c.clause})**" if c.clause else ")**"), "").replace(f"[cite:{c.chunk_id}]", "")
        rest = rest.replace("\n".join(f"> {line}" for line in c.quote.splitlines()), "")
    assert rest.strip() == ""
    import json as _json

    sent = _json.loads(be.requests[0].content)
    assert sent["query_vector"] is None and sent["top_k"] == 3  # chỉ từ khóa
    assert ai.embed_calls == []


def test_degraded_with_no_hit_or_be_down_uses_empty_template():
    final = final_of(run_turn(FakeAi(LlmUnavailableError("sập")), question="zzzz qqqq")[0])
    assert final.degraded and "chưa tra được điều khoản" in final.answer and final.citations == []
    final = final_of(run_turn(FakeAi(LlmUnavailableError("sập")), FakeBe(fail_status=500))[0])
    assert final.degraded and "chưa tra được điều khoản" in final.answer


def test_llm_without_tool_capability_goes_degraded():
    final = final_of(run_turn(FakeAi(reply("x"), can_tools=False))[0])
    assert final.degraded and final.verdict == "degraded"


def test_config_errors_are_not_masked_as_degraded(caplog):
    err = AuthenticationError("bad key sk-abcdefghijklmnop12345", response=httpx.Response(401, request=httpx.Request("POST", "http://x")), body=None)
    frames, _ = run_turn(FakeAi(err))
    assert [f.type for f in frames][-1] == "error" and frames[-1].code == "internal"
    assert "sk-abcdefghijklmnop" not in caplog.text and "sk-abcdef" not in frames[-1].message


def test_embedding_failure_falls_back_to_keyword_not_degraded():
    ai = FakeAi(reply("", [search()]), reply(f"Cần 8 tuần [cite:{D}]."), embed_ok=False)
    frames, be = run_turn(ai)
    assert final_of(frames).verdict == "answered" and json.loads(be.requests[0].content)["query_vector"] is None


# ---------------------------------------------------------------- giới hạn (R1.3)


def test_endless_tool_requests_end_with_unfinished_listing_from_seen_chunks():
    ai = FakeAi(reply("", [search()]))  # lặp mãi
    frames, _ = run_turn(ai, cfg=settings(agent_max_rounds=3))
    final = final_of(frames)
    assert len(ai.calls) <= 3 and final.verdict == "error_fallback" and not final.degraded
    assert "chưa xử lý xong" in final.answer and DURATION["text"] in final.answer


def test_limit_without_chunks_gives_unfinished_template_and_timeout_gives_error():
    ai = FakeAi(reply("", [("a", "get_my_progress", {})]))
    final = final_of(run_turn(ai, cfg=settings(agent_max_rounds=2))[0])
    assert final.verdict == "error_fallback" and "chưa xử lý được" in final.answer

    async def slow(messages, kw):
        await asyncio.sleep(2)

    frames, _ = run_turn(FakeAi(slow), cfg=settings(agent_turn_seconds=0.1))
    assert frames[-1].type == "error" and frames[-1].code == "timeout"


# ---------------------------------------------------------------- tiện ích


def test_token_pieces_roundtrip():
    for text in ["", "một", "a b c d e f g", "  đầu cách\nxuống dòng  [cite:x/y] cuối. \n\nđoạn hai", f"Cần 8 tuần [cite:{D}].\n\n- ý 1\n- ý 2"]:
        pieces = token_pieces(text)
        assert "".join(pieces) == text
        assert all(p.count("[cite:") == p.count("]") or "[cite:" not in p or p.rstrip().endswith("]") or "]" in p for p in pieces)
    assert all("[cite:" not in p or "]" in p.split("[cite:")[1] for p in token_pieces(f"{'x ' * 7}[cite:{D}] tiếp tục chữ"))


def test_corpus_fixture_sanity():
    assert len(CHUNKS) == 3
