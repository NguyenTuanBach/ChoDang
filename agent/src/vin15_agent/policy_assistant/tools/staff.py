"""Tool dữ liệu cho giảng viên/quản trị viên (hàng chờ, cờ rủi ro, số liệu tổng hợp, danh sách hồ sơ). Chỉ-đọc.

Tham số chỉ là bộ lọc; KHÔNG có tham số chọn người/phạm vi: BE xác định phạm vi (giảng viên: sinh viên mình phụ trách,
quản trị viên: toàn hệ thống) từ agent-token. BE không trả email/SĐT/MST.
"""

from __future__ import annotations

from typing import Any

from vin15_agent.core.tools import BaseTool, ToolResult, TurnContext
from vin15_agent.policy_assistant.be_client import BeToolError, BeToolsClient

_STATUS = {"type": "string", "description": "Lọc theo trạng thái (tùy chọn)."}
_COHORT = {"type": "string", "description": "Lọc theo khóa, ví dụ K2026 (tùy chọn)."}


def _schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "additionalProperties": False}


class StaffTool(BaseTool):
    data_source = True

    def __init__(self, be: BeToolsClient, *, name: str, endpoint: str, label: str, description: str, parameters: dict[str, Any]) -> None:
        self._be, self._endpoint = be, endpoint
        self.name, self.label, self.description, self.parameters = name, label, description, parameters

    async def run(self, args: dict[str, Any], ctx: TurnContext) -> ToolResult:
        allowed = self.parameters["properties"]
        params = {k: v for k, v in args.items() if k in allowed}
        try:
            data = await self._be.staff(self._endpoint, params)
        except BeToolError as exc:
            return ToolResult.failure(exc.code, exc.message)
        ctx.seen_internship_ids.update(_internship_ids(data, self._endpoint))
        return ToolResult.success(data, f"Đã đọc: {self.label.lower()}")


def _internship_ids(data: Any, endpoint: str) -> set[int]:
    """Mã hồ sơ trong kết quả (``id`` ở danh sách hồ sơ, ``internship_id`` ở hàng chờ/cờ) để ``navigate_to`` mở được trang chi tiết."""
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return set()
    keys = ("id", "internship_id") if endpoint == "internships" else ("internship_id",)
    found: set[int] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in keys:
            value = item.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                found.add(value)
    return found


def build_staff_tools(be: BeToolsClient) -> list[StaffTool]:
    return [
        StaffTool(
            be, name="get_staff_queue", endpoint="queue", label="Xem hàng chờ cần xử lý",
            description="Hàng chờ việc cần người dùng xử lý (hồ sơ/đề cương/mốc chờ duyệt, yêu cầu, cờ rủi ro), đã sắp theo ưu tiên. "
            "Trả tổng số (total) và tối đa 30 mục đầu.",
            parameters=_schema({}),
        ),
        StaffTool(
            be, name="list_risk_flags", endpoint="flags", label="Xem cờ rủi ro",
            description="Cờ rủi ro (mốc quá hạn, thiếu nhật ký, minh chứng yếu...) trong phạm vi của người hỏi. Trả tổng số (total) và tối đa 30 cờ đầu.",
            parameters=_schema({"status": {"type": "string", "enum": ["open", "acknowledged", "resolved", "dismissed"], "description": "Trạng thái cờ (tùy chọn)."}}),
        ),
        StaffTool(
            be, name="get_dashboard_summary", endpoint="dashboard", label="Xem số liệu tổng hợp",
            description="Số liệu tổng hợp trong phạm vi của người hỏi: số hồ sơ đang thực tập, số hồ sơ có mốc quá hạn (late_internships), "
            "hồ sơ và mốc theo trạng thái, cờ đang mở theo mức độ, kết quả tín chỉ. Dùng cho câu hỏi 'bao nhiêu sinh viên...'.",
            parameters=_schema({"cohort": _COHORT}),
        ),
        StaffTool(
            be, name="list_internships", endpoint="internships", label="Xem danh sách hồ sơ thực tập",
            description="Danh sách hồ sơ thực tập trong phạm vi của người hỏi (mỗi hồ sơ có id = mã hồ sơ), kèm số mốc quá hạn, mốc chờ duyệt, "
            "cờ đang mở. Trả tổng số (total) và tối đa 30 hồ sơ đầu. Tìm hồ sơ của một sinh viên cụ thể (để mở trang chi tiết) thì truyền student.",
            parameters=_schema(
                {
                    "status": _STATUS,
                    "overdue_only": {"type": "boolean", "description": "Chỉ hồ sơ có mốc quá hạn."},
                    "cohort": _COHORT,
                    "student": {"type": "string", "description": "Tên (một phần, có dấu hay không dấu đều được) hoặc mã sinh viên (tùy chọn)."},
                }
            ),
        ),
    ]
