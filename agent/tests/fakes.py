"""Đồ giả dùng chung cho test: BE giả (httpx.MockTransport) và LLM giả. Không cần mạng, không cần khóa."""

from __future__ import annotations

import json
from typing import Any

import httpx

from vin15_agent.core.ai_client import ChatResult, LlmUnavailableError, ToolCall


def make_chunk(chunk_id: str, article: str, clause: str | None, text: str, *, is_sample: bool = True, heading: str = "") -> dict[str, Any]:
    return {
        "chunk_id": chunk_id, "doc_code": "QC-TT", "doc_title": "Quy chế thực tập", "version": "v1", "article_no": article,
        "clause_no": clause, "heading": heading, "text": text, "effective_from": "2026-01-01", "effective_to": None,
        "is_sample": is_sample, "score": 0.5,
    }  # fmt: skip


DURATION = make_chunk(
    "QC-TT@v1/d3/k1", "3", "1", "Thời lượng thực tập tối thiểu để quy đổi tín chỉ là 8 tuần, tương đương 120 giờ làm việc thực tế.", heading="Thời lượng"
)
REPORT = make_chunk(
    "QC-TT@v1/d4", "4", None, "Báo cáo cuối kỳ nộp trong tuần cuối. Phiếu đánh giá của doanh nghiệp nộp trong 5 ngày làm việc sau khi kết thúc thực tập.",
    heading="Báo cáo",
)  # fmt: skip
JOURNAL = make_chunk(
    "QC-TT@v1/d5/k1", "5", "1", "Tỷ lệ tuần có nhật ký phải đạt tối thiểu 80% số tuần thực tập mới đủ điều kiện công nhận tín chỉ.", heading="Nhật ký"
)
CHUNKS = [DURATION, REPORT, JOURNAL]

PERSONAL_DATA: dict[str, dict[str, Any]] = {
    "internship": {"available": True, "internship": {"cohort": "K2026", "status": "in_progress", "start_date": "2026-09-01", "end_date": "2026-11-30", "mode": "onsite", "lecturer_name": "Thầy A"}},
    "milestones": {"available": True, "milestones": [{"code": "M3", "name": "Báo cáo giữa kỳ", "due_date": "2026-11-25", "status": "pending", "days_left": 4, "next_action": "Nộp báo cáo"}]},
    "progress": {"available": True, "journal": {"submitted": 6, "expected": 8, "missing_weeks": ["2026-10-12", "2026-10-19"]}, "evidence": {"submitted": 1, "required": 2}},
    "credit-checklist": {"available": True, "items": [{"code": "T4", "label": "Tỷ lệ tuần có nhật ký", "met": False, "value": "75%", "threshold": "80%"}], "all_met": False},
    "requests": {"available": True, "requests": []},
}  # fmt: skip


class FakeBe:
    """BE giả: kho quy định nhỏ + dữ liệu cá nhân. ``requests`` ghi lại mọi lời gọi (đã nhận qua transport)."""

    def __init__(self, chunks=None, personal="default", service_token="tok", *, forbidden_personal=False, fail_status: int | None = None) -> None:
        self.chunks = list(CHUNKS if chunks is None else chunks)
        self.personal = PERSONAL_DATA if personal == "default" else personal
        self.service_token = service_token
        self.forbidden_personal = forbidden_personal
        self.fail_status = fail_status
        self.requests: list[httpx.Request] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    @staticmethod
    def _err(status: int, code: str, message: str = "lỗi") -> httpx.Response:
        return httpx.Response(status, json={"error": {"code": code, "message": message}})

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.headers.get("authorization") != f"Bearer {self.service_token}":
            return self._err(401, "unauthorized")
        if self.fail_status:
            return self._err(self.fail_status, "be_error")
        path = request.url.path
        if request.method == "POST" and path == "/api/agent-tools/policy/search":
            body = json.loads(request.content)
            words = [w for w in body["query"].lower().replace("?", " ").split() if len(w) >= 3]
            scored = sorted(((sum(w in c["text"].lower() or w in c["heading"].lower() for w in words), c) for c in self.chunks), key=lambda x: -x[0])
            hits = [c for s, c in scored if s > 0][: body.get("top_k", 5)]
            return httpx.Response(200, json={"status": "ok" if hits else "no_match", "mode": "hybrid" if body.get("query_vector") else "keyword", "chunks": hits})
        if request.method == "GET" and path.startswith("/api/agent-tools/policy/chunks/"):
            cid = path.removeprefix("/api/agent-tools/policy/chunks/")
            for i, c in enumerate(self.chunks):
                if c["chunk_id"] == cid:
                    neighbors = [self.chunks[j] for j in (i - 1, i + 1) if 0 <= j < len(self.chunks)] if request.url.params.get("with_neighbors") == "true" else []
                    return httpx.Response(200, json={"chunk": c, "neighbors": neighbors})
            return self._err(404, "not_found", "Không có đoạn này")
        if request.method == "GET" and path.startswith("/api/agent-tools/me/"):
            if self.forbidden_personal:
                return self._err(403, "forbidden_role", "Vai trò này không dùng được công cụ cá nhân")
            if self.personal is None:
                return httpx.Response(200, json={"available": False, "reason": "no_internship_record"})
            return httpx.Response(200, json=self.personal[path.rsplit("/", 1)[1]])
        return self._err(404, "not_found")

    def paths(self) -> list[str]:
        return [f"{r.method} {r.url.path}" for r in self.requests]


def reply(text: str = "", calls: list[tuple[str, str, dict]] | tuple = (), *, provider: str = "fake", prompt_tokens: int = 10, completion_tokens: int = 5) -> ChatResult:
    return ChatResult(
        text=text, provider=provider, model="fake-1", prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        tool_calls=tuple(ToolCall(i, n, json.dumps(a, ensure_ascii=False)) for i, n, a in calls),
    )  # fmt: skip


class FakeAi:
    """LLM giả: phát lần lượt các phản hồi đã định (hết thì lặp phản hồi cuối). ``Exception`` trong danh sách sẽ được ném ra."""

    def __init__(self, *responses, embed_ok: bool = True, can_tools: bool = True) -> None:
        self.responses, self.calls, self.embed_calls = list(responses), [], []
        self.embed_ok, self.can_tools = embed_ok, can_tools
        self.providers = ["fake"]

    def supports(self, capability: str) -> bool:
        return self.embed_ok if capability == "embed" else self.can_tools

    async def chat(self, messages, **kw) -> ChatResult:
        if not self.can_tools and kw.get("tools"):
            raise LlmUnavailableError("không có đường hỗ trợ tool")
        self.calls.append({"messages": [dict(m) for m in messages], **kw})
        r = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        if callable(r):
            r = await r(messages, kw)
        if isinstance(r, Exception):
            raise r
        return r

    async def embed(self, texts):
        self.embed_calls.append(list(texts))
        if not self.embed_ok:
            raise LlmUnavailableError("embed sập")
        return [[0.1, 0.2, 0.3] for _ in texts]

    @property
    def embedding_model(self) -> str:
        return "fake-embed"
