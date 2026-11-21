"""``search_policy``: tìm đoạn quy định đang có hiệu lực (BE tự lọc hiệu lực, agent không gửi ngày)."""

from __future__ import annotations

import logging
from typing import Any

from vin15_agent.core.ai_client import AiClient
from vin15_agent.core.tools import BaseTool, ToolResult, TurnContext
from vin15_agent.policy_assistant.be_client import BeToolError, BeToolsClient

logger = logging.getLogger(__name__)

MAX_QUERY_CHARS = 500
MAX_TOP_K = 8
_CHUNK_FIELDS = (
    "chunk_id", "doc_code", "doc_title", "version", "article_no", "clause_no", "heading", "text", "effective_from", "is_sample", "score",
)  # fmt: skip


def slim_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    return {k: chunk[k] for k in _CHUNK_FIELDS if k in chunk}


def remember_chunks(ctx: TurnContext, chunks: list[Any]) -> list[dict[str, Any]]:
    """Ghi các chunk hợp lệ vào ``seen_chunks`` (nguồn của hậu kiểm trích dẫn) và trả bản gọn đưa cho LLM."""
    out = []
    for chunk in chunks:
        if isinstance(chunk, dict) and isinstance(chunk.get("chunk_id"), str):
            ctx.seen_chunks[chunk["chunk_id"]] = chunk
            out.append(slim_chunk(chunk))
    return out


class SearchPolicyTool(BaseTool):
    name = "search_policy"
    label = "Tra cứu quy định"
    description = (
        "Tìm các đoạn (điều/khoản) trong văn bản quy định thực tập ĐANG CÓ HIỆU LỰC liên quan tới truy vấn. "
        "Trả về nguyên văn từng đoạn kèm chunk_id để trích dẫn. status=no_match nghĩa là không có căn cứ."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Truy vấn tiếng Việt đầy đủ ý, nêu rõ chủ đề cần tra."},
            "top_k": {"type": "integer", "minimum": 1, "maximum": MAX_TOP_K, "description": "Số đoạn tối đa (mặc định 5)."},
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, be: BeToolsClient, ai: AiClient) -> None:
        self._be, self._ai = be, ai

    def describe(self, args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()[:80]
        return f"{self.label}: {query}" if query else self.label

    async def run(self, args: dict[str, Any], ctx: TurnContext) -> ToolResult:
        query = str(args.get("query", "")).strip()
        if not query:
            return ToolResult.failure("invalid_arguments", "Thiếu truy vấn (query)")
        query = query[:MAX_QUERY_CHARS]
        try:
            top_k = max(1, min(MAX_TOP_K, int(args.get("top_k", 5))))
        except (TypeError, ValueError):
            top_k = 5
        vector = await self._embed(query)
        try:
            data = await self._be.search(query, vector, top_k)
        except BeToolError as exc:
            return ToolResult.failure(exc.code, exc.message)
        chunks = remember_chunks(ctx, data.get("chunks") or [])
        status = "ok" if chunks else "no_match"
        summary = f"Tìm thấy {len(chunks)} đoạn quy định" if chunks else "Không có đoạn quy định phù hợp"
        return ToolResult.success({"status": status, "mode": data.get("mode"), "chunks": chunks}, summary)

    async def _embed(self, query: str) -> list[float] | None:
        """Embed truy vấn; không được thì tìm chỉ bằng từ khóa (R2.5)."""
        if not self._ai.supports("embed"):
            return None
        try:
            vectors = await self._ai.embed([query])
        except Exception as exc:
            logger.warning("Embedding truy vấn lỗi (%s), tìm chỉ bằng từ khóa", type(exc).__name__)
            return None
        return vectors[0] if vectors else None
