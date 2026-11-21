"""Tool ngữ cảnh cá nhân ``get_my_*`` (chỉ sinh viên). KHÔNG có tham số chủ thể: BE xác định người hỏi từ token.

BE chỉ trả trường tối thiểu (không email/SĐT/MST). Chưa có hồ sơ → ``available=false`` và trợ lý phải nói rõ chưa xem được.
"""

from __future__ import annotations

from typing import Any

from vin15_agent.core.tools import BaseTool, ToolResult, TurnContext
from vin15_agent.policy_assistant.be_client import BeToolError, BeToolsClient

_NO_PARAMS: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}


class PersonalTool(BaseTool):
    parameters = _NO_PARAMS
    data_source = True

    def __init__(self, be: BeToolsClient, *, name: str, endpoint: str, label: str, description: str) -> None:
        self._be, self._endpoint = be, endpoint
        self.name, self.label, self.description = name, label, description

    async def run(self, args: dict[str, Any], ctx: TurnContext) -> ToolResult:
        try:
            data = await self._be.me(self._endpoint)
        except BeToolError as exc:
            return ToolResult.failure(exc.code, exc.message)
        if data.get("available") is False:
            return ToolResult.success(data, "Chưa có hồ sơ thực tập để xem")
        return ToolResult.success(data, f"Đã đọc: {self.label.lower()}")


#: (tên tool, endpoint BE, nhãn, mô tả)
PERSONAL_TOOLS = [
    ("get_my_internship", "internship", "Xem hồ sơ thực tập của bạn",
     "Hồ sơ thực tập của chính người hỏi: khóa, trạng thái, ngày bắt đầu/kết thúc, hình thức, giảng viên hướng dẫn."),
    ("get_my_milestones", "milestones", "Xem các mốc của bạn",
     "Các mốc thực tập của chính người hỏi: mã, tên, hạn, trạng thái, số ngày còn lại, việc cần làm tiếp."),
    ("get_my_progress", "progress", "Xem tiến độ nhật ký và minh chứng",
     "Tiến độ của chính người hỏi: số nhật ký đã nộp/dự kiến, các tuần thiếu nhật ký, số minh chứng đã nộp/yêu cầu."),
    ("get_my_credit_checklist", "credit-checklist", "Xem điều kiện công nhận tín chỉ của bạn",
     "Bảng điều kiện công nhận tín chỉ T1-T6 của chính người hỏi: đạt/chưa đạt, số liệu và ngưỡng. Chỉ là số liệu, không phải kết luận công nhận."),
    ("get_my_requests", "requests", "Xem các yêu cầu của bạn",
     "Các yêu cầu đã tạo của chính người hỏi: loại, trạng thái, ngày tạo."),
]  # fmt: skip


def build_personal_tools(be: BeToolsClient) -> list[PersonalTool]:
    return [PersonalTool(be, name=n, endpoint=e, label=lb, description=d) for n, e, lb, d in PERSONAL_TOOLS]
