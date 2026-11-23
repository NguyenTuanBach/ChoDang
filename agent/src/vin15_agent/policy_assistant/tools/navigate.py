"""Tool ``navigate_to``: nhờ giao diện mở một trang. Tool chỉ ghi một *hành động giao diện* vào lượt hiện tại; không đọc/ghi dữ liệu nghiệp vụ.

Trang hợp lệ do danh mục theo vai trò (``pages.json``) quyết; FE tự đổi khóa sang URL và vẫn kiểm lại khóa theo vai trò của người dùng,
còn quyền xem nội dung trang do BE kiểm khi trang tải. Mỗi lượt chỉ mở được một trang.

Trang chi tiết hồ sơ cần ``internship_id``; mã phải xuất hiện trong kết quả tool dữ liệu của lượt này (hoặc là hồ sơ đang mở) để mô hình
không bịa mã. Bộ lọc (``filters``) chỉ nhận khóa/giá trị khai báo cho đúng trang đó.
"""

from __future__ import annotations

from typing import Any

from vin15_agent.core.tools import BaseTool, ToolResult, TurnContext
from vin15_agent.policy_assistant.pages import Page, pages_for

_PARAM = "internship_id"


def _describe_page(page: Page) -> str:
    text = f"{page.key} = {page.label} ({page.description})"
    if page.param:
        text += f" [cần {page.param}]"
    if page.filters:
        text += " [bộ lọc: " + "; ".join(f"{k}: {f.description}" for k, f in page.filters.items()) + "]"
    return text


class NavigateTool(BaseTool):
    name = "navigate_to"
    label = "Mở trang"

    def __init__(self, role: str) -> None:
        self._pages: dict[str, Page] = {p.key: p for p in pages_for(role)}
        listing = "; ".join(_describe_page(p) for p in self._pages.values())
        self.description = (
            "Mở một trang của hệ thống cho người dùng (điều hướng giao diện) khi họ yêu cầu mở, đi tới hoặc chuyển sang một trang. "
            "Chỉ điều hướng, không đọc hay thay đổi dữ liệu. Mỗi lượt chỉ mở một trang. "
            "Trang cần internship_id thì phải lấy mã từ kết quả tool dữ liệu trong lượt này (ví dụ list_internships), không tự đặt mã. "
            "Người dùng nêu điều kiện lọc (loại việc, trạng thái...) thì truyền filters của đúng trang đó; không nêu thì bỏ trống. "
            f"Các trang có thể mở (khóa = tên): {listing}. Trang không có trong danh sách thì không gọi tool này mà nói rõ không mở được."
        )
        properties: dict[str, Any] = {"page": {"type": "string", "enum": list(self._pages), "description": "Khóa của trang cần mở."}}
        if any(p.param == _PARAM for p in self._pages.values()):
            properties[_PARAM] = {"type": "integer", "description": "Mã hồ sơ thực tập (chỉ cho trang cần internship_id)."}
        filter_props: dict[str, Any] = {}
        for page in self._pages.values():
            for key, flt in page.filters.items():
                values = filter_props.setdefault(key, {"type": "string", "enum": []})["enum"]
                values.extend(v for v in flt.values if v not in values)
        if filter_props:
            properties["filters"] = {
                "type": "object",
                "properties": filter_props,
                "additionalProperties": False,
                "description": "Bộ lọc mở sẵn (tùy chọn); chỉ dùng khóa thuộc trang đã chọn.",
            }
        self.parameters = {"type": "object", "properties": properties, "required": ["page"], "additionalProperties": False}

    def describe(self, args: dict[str, Any]) -> str:
        page = self._pages.get(str(args.get("page", "")))
        return f"Mở trang {page.label}" if page else self.label

    async def run(self, args: dict[str, Any], ctx: TurnContext) -> ToolResult:
        page = self._pages.get(str(args.get("page", "")))
        if page is None:
            return ToolResult.failure("unknown_page", "Không có trang này trong danh sách được phép mở")
        if any(a["type"] == "navigate" for a in ctx.actions):
            return ToolResult.failure("already_navigating", "Mỗi lượt chỉ mở được một trang")

        action: dict[str, Any] = {"type": "navigate", "page": page.key, "label": page.label}
        if page.param == _PARAM:
            raw_id = args.get(_PARAM)
            if isinstance(raw_id, bool) or not isinstance(raw_id, int) or raw_id <= 0:
                return ToolResult.failure("missing_internship_id", "Trang này cần internship_id: gọi list_internships để tìm mã hồ sơ trước")
            if raw_id not in ctx.seen_internship_ids:
                return ToolResult.failure(
                    "unknown_internship", "Mã hồ sơ này chưa có trong kết quả tool của lượt này: tra list_internships để lấy đúng mã"
                )
            action[_PARAM] = raw_id

        raw_filters = args.get("filters") or {}
        if not isinstance(raw_filters, dict):
            return ToolResult.failure("invalid_filter", "filters phải là object")
        filters: dict[str, str] = {}
        for key, value in raw_filters.items():
            flt = page.filters.get(key)
            if flt is None:
                return ToolResult.failure("invalid_filter", f"Trang {page.label} không có bộ lọc '{key}'")
            if str(value) not in flt.values:
                return ToolResult.failure("invalid_filter", f"Giá trị '{value}' không hợp lệ cho bộ lọc '{key}' của trang {page.label}")
            filters[key] = str(value)
        if filters:
            action["filters"] = filters

        ctx.actions.append(action)
        return ToolResult.success({"opened": page.label, **({"filters": filters} if filters else {})}, f"Mở trang {page.label}")
