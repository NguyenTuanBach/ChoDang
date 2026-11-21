"""Tool ``navigate_to``: nhờ giao diện mở một trang. Tool chỉ ghi một *hành động giao diện* vào lượt hiện tại; không đọc/ghi dữ liệu nghiệp vụ.

Trang hợp lệ do danh mục theo vai trò (``pages.json``) quyết; FE tự đổi khóa sang URL và vẫn kiểm lại khóa theo vai trò của người dùng,
còn quyền xem nội dung trang do BE kiểm khi trang tải. Mỗi lượt chỉ mở được một trang.
"""

from __future__ import annotations

from typing import Any

from vin15_agent.core.tools import BaseTool, ToolResult, TurnContext
from vin15_agent.policy_assistant.pages import Page, pages_for


class NavigateTool(BaseTool):
    name = "navigate_to"
    label = "Mở trang"

    def __init__(self, role: str) -> None:
        self._pages: dict[str, Page] = {p.key: p for p in pages_for(role)}
        listing = "; ".join(f"{p.key} = {p.label} ({p.description})" for p in self._pages.values())
        self.description = (
            "Mở một trang của hệ thống cho người dùng (điều hướng giao diện) khi họ yêu cầu mở, đi tới hoặc chuyển sang một trang. "
            "Chỉ điều hướng, không đọc hay thay đổi dữ liệu. Mỗi lượt chỉ mở một trang. "
            f"Các trang có thể mở (khóa = tên): {listing}. Trang không có trong danh sách thì không gọi tool này mà nói rõ không mở được."
        )
        self.parameters = {
            "type": "object",
            "properties": {"page": {"type": "string", "enum": list(self._pages), "description": "Khóa của trang cần mở."}},
            "required": ["page"],
            "additionalProperties": False,
        }

    def describe(self, args: dict[str, Any]) -> str:
        page = self._pages.get(str(args.get("page", "")))
        return f"Mở trang {page.label}" if page else self.label

    async def run(self, args: dict[str, Any], ctx: TurnContext) -> ToolResult:
        page = self._pages.get(str(args.get("page", "")))
        if page is None:
            return ToolResult.failure("unknown_page", "Không có trang này trong danh sách được phép mở")
        if any(a["type"] == "navigate" for a in ctx.actions):
            return ToolResult.failure("already_navigating", "Mỗi lượt chỉ mở được một trang")
        ctx.actions.append({"type": "navigate", "page": page.key, "label": page.label})
        return ToolResult.success({"opened": page.label}, f"Mở trang {page.label}")
