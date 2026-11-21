"""``PolicyAssistant``: nối PII → prompt → vòng lặp agent → hậu kiểm → ``final`` (kèm ``token`` đã kiểm).

Câu trả lời chỉ được phát sau khi hậu kiểm xong (không để người dùng thấy văn bản chưa kiểm); các khung ``token`` là
phần văn bản ĐÃ kiểm, cắt theo từ (không cắt giữa thẻ ``[cite:...]``), nối lại đúng bằng ``final.answer``.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from vin15_agent.core.agent_loop import LoopConfig, LoopEvent, LoopOutcome, PlanningEvent, ToolCallEvent, ToolResultEvent, run_agent_loop
from vin15_agent.core.ai_client import AiClient, LlmUnavailableError
from vin15_agent.core.pii import PiiRedactor
from vin15_agent.core.prompts import PromptLoader
from vin15_agent.core.tools import TurnContext
from vin15_agent.core.tracing import TurnTrace
from vin15_agent.policy_assistant.be_client import BeClientFactory, BeToolsClient
from vin15_agent.policy_assistant.degraded import degraded_answer, render_chunk_listing
from vin15_agent.policy_assistant.protocol import (
    Citation,
    ErrorFrame,
    FinalFrame,
    OutboundFrame,
    StartFrame,
    StatusFrame,
    TokenFrame,
    ToolCallFrame,
    ToolResultFrame,
    Usage,
    Verdict,
)
from vin15_agent.policy_assistant.registry import POLICY_TOOL_NAMES, build_registry
from vin15_agent.policy_assistant.verify import (
    CITE_RE,
    build_citations,
    check_numbers,
    guard_commitments,
    number_sources,
    sample_warning_needed,
    verify_citations,
)
from vin15_agent.shared.settings import Settings

logger = logging.getLogger(__name__)

Emit = Callable[[OutboundFrame], Awaitable[None]]

ROLE_LABELS = {"student": "sinh viên", "lecturer": "giảng viên", "admin": "quản trị viên"}
_MARKER = re.compile(r"\[\[\s*(refuse:(\w+)|no_basis|needs_human)\s*\]\]")
_TOKEN_PIECE = re.compile(r"\S+\s*")
_WORDS_PER_TOKEN = 3
_INTERNAL_ERROR = "Trợ lý gặp sự cố, vui lòng thử lại sau."


@dataclass
class _Answer:
    text: str
    verdict: Verdict
    citations: list[Citation]


class PolicyAssistant:
    def __init__(self, ai: AiClient, be_factory: BeClientFactory, settings: Settings, loader: PromptLoader | None = None) -> None:
        self._ai = ai
        self._be_factory = be_factory
        self._settings = settings
        self._loader = loader or PromptLoader(settings.agent_prompts_dir or None)
        self._templates = self._loader.sections("refusals")
        PiiRedactor(settings.pii_student_id_pattern)  # báo lỗi cấu hình regex ngay khi khởi động, không đợi lượt hỏi đầu tiên

    # ------------------------------------------------------------------ vào chính

    async def run(self, start: StartFrame, emit: Emit) -> None:
        """Chạy một lượt hỏi, phát khung qua ``emit``. Kết thúc bằng ``final`` hoặc ``error``. Hủy bằng ``task.cancel()``."""
        redactor = PiiRedactor(self._settings.pii_student_id_pattern)
        trace = TurnTrace(redactor=redactor)
        ctx = TurnContext(actor_role=start.actor.role, today=start.today, agent_token=start.actor.agent_token, redactor=redactor, trace=trace)
        be = self._be_factory(start.actor.agent_token)
        try:
            await self._run(start, ctx, be, emit)
        finally:
            await be.aclose()

    async def _run(self, start: StartFrame, ctx: TurnContext, be: BeToolsClient, emit: Emit) -> None:
        redactor, trace = ctx.redactor, ctx.trace
        question = redactor.redact_text(start.question)
        history = [{"role": h.role, "content": redactor.redact_text(h.content)} for h in start.history]
        trace.step("start")
        await emit(StatusFrame(step="planning", text="Đang phân tích câu hỏi…"))

        registry = build_registry(start.actor.role, be, self._ai)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt(start)},
            *history,
            {"role": "user", "content": question},
        ]
        s = self._settings
        config = LoopConfig(
            max_rounds=s.agent_max_rounds,
            max_tool_calls=s.agent_max_tool_calls,
            turn_seconds=s.agent_turn_seconds,
            tool_timeout_seconds=s.agent_tool_timeout_seconds,
            temperature=s.assistant_temperature,
        )

        async def on_event(event: LoopEvent) -> None:
            if isinstance(event, PlanningEvent):
                await emit(StatusFrame(step="planning", text=event.text))
            elif isinstance(event, ToolCallEvent):
                step = "searching" if event.name == "search_policy" else "reading"
                await emit(StatusFrame(step=step, text=event.label))
                await emit(ToolCallFrame(name=event.name, label=event.label))
            elif isinstance(event, ToolResultEvent):
                await emit(ToolResultFrame(name=event.name, ok=event.ok, summary=event.summary))

        try:
            outcome = await run_agent_loop(
                ai=self._ai, registry=registry, messages=messages, ctx=ctx, config=config, emit=on_event,
                limit_message=self._loader.raw("loop_limit"), before_answer=_policy_lookup_nudge,
            )  # fmt: skip
        except LlmUnavailableError:
            logger.warning("LLM không khả dụng, chuyển chế độ suy giảm (trace=%s)", trace.trace_id)
            await self._degraded(question, ctx, be, emit)
            return
        except Exception as exc:  # lỗi cấu hình/yêu cầu LLM (401, 400...) hoặc lỗi phát khung: không che bằng suy giảm
            logger.error("Lượt hỏi lỗi (trace=%s): %s %s", trace.trace_id, type(exc).__name__, redactor.redact_text(str(exc))[:300])
            await emit(ErrorFrame(code="internal", message=_INTERNAL_ERROR))
            return

        if outcome.finish != "answer":
            await self._unfinished(outcome, ctx, emit)
            return
        await emit(StatusFrame(step="verifying", text="Đang kiểm tra trích dẫn và số liệu…"))
        answer = self._postprocess(outcome.text, start, question, ctx)
        await self._emit_final(answer, ctx, emit, degraded=False)

    # ------------------------------------------------------------------ prompt

    def _system_prompt(self, start: StartFrame) -> str:
        loader = self._loader
        return loader.render(
            "policy_assistant.system",
            today=start.today,
            user_role=ROLE_LABELS.get(start.actor.role, start.actor.role),
            school_name=self._settings.school_name,
            sample_notice=self._templates.get("sample_notice", "") if self._settings.assistant_sample_notice else "",
            citation_rules=loader.raw("citation_rules"),
            safeguards=loader.raw("safeguards"),
            refusals=loader.without_sections("refusals"),
        )

    # ------------------------------------------------------------------ hậu kiểm

    def _postprocess(self, text: str, start: StartFrame, question: str, ctx: TurnContext) -> _Answer:
        t = self._templates
        needs_human = False
        verdict: Verdict = "answered"

        markers = list(_MARKER.finditer(text))
        for m in markers:
            if m.group(2):  # refuse:<id>: thay toàn bộ bằng mẫu cố định
                template = t.get(m.group(2)) or t["out_of_scope"]
                return _Answer(template, "refused", [])
        needs_human = any(m.group(1) == "needs_human" for m in markers)
        no_basis = any(m.group(1) == "no_basis" for m in markers)
        text = _MARKER.sub("", text).strip()
        if no_basis and len(text) < 40:
            return _Answer(t["no_basis"], "no_match", [])
        if no_basis:
            text += "\n\n" + t["no_basis_partial"]

        cites = verify_citations(text, ctx.seen_chunks.keys(), no_basis_partial=t["no_basis_partial"])
        text = guard_commitments(cites.text, t["no_commitment"]).text
        extra_sources = [question, start.today, *(h.content for h in start.history)]
        text = check_numbers(text, number_sources(ctx.seen_chunks, ctx.tool_texts, extra_sources), t["number_mismatch"]).text

        cited_ids = list(dict.fromkeys(CITE_RE.findall(text)))
        used_policy_tool = any(c["name"] in POLICY_TOOL_NAMES for c in ctx.trace.tool_calls)
        used_personal_ok = any(c["name"].startswith("get_my_") and c["ok"] for c in ctx.trace.tool_calls)
        substantive = text
        for key in ("no_basis_partial", "number_mismatch", "no_commitment"):
            substantive = substantive.replace(t[key], "")
        if not substantive.strip() or (used_policy_tool and not cited_ids and not used_personal_ok):
            return _Answer(t["no_basis"], "no_match", [])

        if sample_warning_needed(ctx.seen_chunks, cited_ids) and t["sample_warning"] not in text:
            text += "\n\n" + t["sample_warning"]
        if needs_human:
            verdict = "needs_human"
        return _Answer(text, verdict, build_citations(ctx.seen_chunks, cited_ids))

    # ------------------------------------------------------------------ các nhánh kết thúc khác

    async def _degraded(self, question: str, ctx: TurnContext, be: BeToolsClient, emit: Emit) -> None:
        ctx.trace.degraded = True
        await emit(StatusFrame(step="searching", text="Đang tra cứu điều khoản bằng từ khóa…"))
        text, chunks = await degraded_answer(be, question, notice=self._templates["degraded_notice"], empty_notice=self._templates["degraded_empty"])
        ctx.seen_chunks.update(chunks)
        answer = _Answer(text, "degraded", build_citations(ctx.seen_chunks, list(chunks)))
        await self._emit_final(answer, ctx, emit, degraded=True)

    async def _unfinished(self, outcome: LoopOutcome, ctx: TurnContext, emit: Emit) -> None:
        """Hết vòng/ngân sách/thời gian mà chưa có câu trả lời: dựng từ chunk đã có, hoặc mẫu "chưa xử lý được"."""
        t = self._templates
        if not ctx.seen_chunks:
            if outcome.finish == "timeout":
                await emit(ErrorFrame(code="timeout", message="Trợ lý xử lý quá thời gian cho phép, vui lòng thử lại."))
                return
            await self._emit_final(_Answer(t["unfinished_empty"], "error_fallback", []), ctx, emit, degraded=False)
            return
        listing = render_chunk_listing(list(ctx.seen_chunks.values())[:3])
        answer = _Answer(f"{t['unfinished']}\n\n{listing.text}", "error_fallback", build_citations(ctx.seen_chunks, listing.cited_ids))
        await self._emit_final(answer, ctx, emit, degraded=False)

    async def _emit_final(self, answer: _Answer, ctx: TurnContext, emit: Emit, *, degraded: bool) -> None:
        trace = ctx.trace
        await emit(StatusFrame(step="answering", text="Đang soạn câu trả lời…"))
        for piece in token_pieces(answer.text):
            await emit(TokenFrame(delta=piece))
        usage = Usage(prompt_tokens=trace.prompt_tokens or None, completion_tokens=trace.completion_tokens or None, provider=trace.provider, model=trace.model)
        await emit(
            FinalFrame(
                answer=answer.text, citations=answer.citations, verdict=answer.verdict, degraded=degraded, usage=usage, trace_id=trace.trace_id,
            )
        )  # fmt: skip
        trace.step("final", answer.verdict)
        logger.info(
            "Lượt hỏi xong trace=%s verdict=%s degraded=%s llm_calls=%d tools=%d ms=%d",
            trace.trace_id, answer.verdict, degraded, trace.llm_calls, len(trace.tool_calls), trace.elapsed_ms(),
        )  # fmt: skip


def token_pieces(text: str, words_per_piece: int = _WORDS_PER_TOKEN) -> list[str]:
    """Cắt văn bản thành các mảnh theo từ (giữ nguyên khoảng trắng/xuống dòng); nối lại đúng bằng ``text``."""
    words = _TOKEN_PIECE.findall(text)
    pieces = ["".join(words[i : i + words_per_piece]) for i in range(0, len(words), words_per_piece)]
    leading = text[: len(text) - len(text.lstrip())]
    if leading and pieces:
        pieces[0] = leading + pieces[0]
    return pieces


_POLICY_NUDGE = (
    "Bạn đã xem hồ sơ của người hỏi nhưng CHƯA tra quy định. Hãy gọi search_policy ngay để lấy điều kiện/thời hạn làm căn cứ, "
    "rồi đối chiếu với số liệu trong hồ sơ và trích dẫn [cite:chunk_id] của quy định. Chưa tra thì chưa được trả lời."
)


def _policy_lookup_nudge(ctx: TurnContext) -> str | None:
    """Câu hỏi cá nhân mà mới gọi get_my_* (chưa search_policy): nhắc tra quy định một lần trước khi trả lời."""
    names = [call["name"] for call in ctx.trace.tool_calls]
    if any(n.startswith("get_my_") for n in names) and "search_policy" not in names and "get_policy_clause" not in names:
        return _POLICY_NUDGE
    return None
