"""Đăng ký tool theo vai trò: mọi vai trò có tool tra quy định; sinh viên có ``get_my_*`` (R5.7);
giảng viên/quản trị viên có tool dữ liệu phạm vi phụ trách (``tools/staff.py``)."""

from __future__ import annotations

from vin15_agent.core.ai_client import AiClient
from vin15_agent.core.tools import ToolRegistry
from vin15_agent.policy_assistant.be_client import BeToolsClient
from vin15_agent.policy_assistant.tools.get_policy_clause import GetPolicyClauseTool
from vin15_agent.policy_assistant.tools.navigate import NavigateTool
from vin15_agent.policy_assistant.tools.personal import build_personal_tools
from vin15_agent.policy_assistant.tools.search_policy import SearchPolicyTool
from vin15_agent.policy_assistant.tools.staff import build_staff_tools

POLICY_TOOL_NAMES = frozenset({"search_policy", "get_policy_clause"})
STAFF_ROLES = frozenset({"lecturer", "admin"})


def build_registry(role: str, be: BeToolsClient, ai: AiClient) -> ToolRegistry:
    registry = ToolRegistry([SearchPolicyTool(be, ai), GetPolicyClauseTool(be)])
    if role == "student":
        for tool in build_personal_tools(be):
            registry.register(tool)
    elif role in STAFF_ROLES:
        for tool in build_staff_tools(be):
            registry.register(tool)
    registry.register(NavigateTool(role))  # điều hướng giao diện: mọi vai trò, chỉ trả hành động, không đụng dữ liệu
    return registry
