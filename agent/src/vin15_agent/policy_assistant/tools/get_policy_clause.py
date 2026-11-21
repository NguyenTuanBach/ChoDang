"""``get_policy_clause``: đọc nguyên văn một điều/khoản (kèm đoạn liền trước/sau nếu cần)."""

from __future__ import annotations

from typing import Any

from vin15_agent.core.tools import BaseTool, ToolResult, TurnContext
from vin15_agent.policy_assistant.be_client import BeToolError, BeToolsClient, is_valid_chunk_id
from vin15_agent.policy_assistant.tools.search_policy import remember_chunks, slim_chunk


class GetPolicyClauseTool(BaseTool):
    name = "get_policy_clause"
    label = "Đọc điều khoản"
    description = (
        "Đọc nguyên văn một đoạn quy định theo chunk_id (lấy từ kết quả search_policy), có thể kèm đoạn liền trước/sau "
        "trong cùng văn bản. Chỉ đọc được đoạn thuộc văn bản đang có hiệu lực."
    )
    parameters = {
        "type": "object",
        "properties": {
            "chunk_id": {"type": "string", "description": "Mã đoạn đã nhận từ search_policy."},
            "with_neighbors": {"type": "boolean", "description": "Lấy thêm đoạn liền trước và liền sau."},
        },
        "required": ["chunk_id"],
        "additionalProperties": False,
    }

    def __init__(self, be: BeToolsClient) -> None:
        self._be = be

    async def run(self, args: dict[str, Any], ctx: TurnContext) -> ToolResult:
        chunk_id = str(args.get("chunk_id", "")).strip()
        if not is_valid_chunk_id(chunk_id):
            return ToolResult.failure("invalid_arguments", "chunk_id không hợp lệ")
        try:
            data = await self._be.get_chunk(chunk_id, bool(args.get("with_neighbors", False)))
        except BeToolError as exc:
            return ToolResult.failure(exc.code, exc.message)
        chunk = data.get("chunk")
        if not isinstance(chunk, dict):
            return ToolResult.failure("be_bad_response", "Hệ thống trả dữ liệu không hợp lệ")
        remember_chunks(ctx, [chunk])
        neighbors = remember_chunks(ctx, data.get("neighbors") or [])
        return ToolResult.success({"chunk": slim_chunk(chunk), "neighbors": neighbors}, "Đã đọc điều khoản")
