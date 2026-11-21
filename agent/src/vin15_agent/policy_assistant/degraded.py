"""Chế độ suy giảm (R12): khi LLM không dùng được, trả nguyên văn các điều khoản tìm được bằng TỪ KHÓA.

Câu trả lời chỉ gồm mẫu cố định + nguyên văn chunk; không có chữ nào do LLM sinh (P9).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from vin15_agent.policy_assistant.be_client import BeToolError, BeToolsClient
from vin15_agent.policy_assistant.tools.search_policy import MAX_QUERY_CHARS

logger = logging.getLogger(__name__)

DEGRADED_TOP_K = 3


@dataclass
class ChunkListing:
    text: str
    chunks: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def cited_ids(self) -> list[str]:
        return list(self.chunks)


def render_chunk_listing(chunks: list[dict[str, Any]]) -> ChunkListing:
    """Nguyên văn từng điều/khoản kèm ``[cite:id]``."""
    blocks, kept = [], {}
    for chunk in chunks:
        cid = chunk.get("chunk_id")
        if not isinstance(cid, str):
            continue
        clause = chunk.get("clause_no")
        where = f"Điều {chunk.get('article_no', '')}" + (f", khoản {clause}" if clause not in (None, "") else "")
        quote = "\n".join(f"> {line}" for line in str(chunk.get("text", "")).splitlines() if line.strip())
        blocks.append(f"**{chunk.get('doc_title', '')} ({where})** [cite:{cid}]\n{quote}")
        kept[cid] = chunk
    return ChunkListing("\n\n".join(blocks), kept)


async def degraded_answer(be: BeToolsClient, redacted_question: str, *, notice: str, empty_notice: str) -> tuple[str, dict[str, dict[str, Any]]]:
    """Trả ``(answer, chunks)``. Gọi BE chỉ bằng từ khóa (không vector) với câu hỏi đã che PII."""
    try:
        data = await be.search(redacted_question[:MAX_QUERY_CHARS], None, DEGRADED_TOP_K)
    except BeToolError as exc:
        logger.warning("Suy giảm: tra cứu từ khóa lỗi (%s)", exc.code)
        return empty_notice, {}
    listing = render_chunk_listing([c for c in data.get("chunks") or [] if isinstance(c, dict)][:DEGRADED_TOP_K])
    if not listing.chunks:
        return empty_notice, {}
    return f"{notice}\n\n{listing.text}", listing.chunks
