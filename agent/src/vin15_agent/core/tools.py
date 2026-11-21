"""Khung tool của agent: ``Tool`` (chỉ-đọc), ``ToolSpec``, ``ToolResult``, ``ToolRegistry``.

Bất biến (có test kiến trúc chạy trên registry của mọi agent):
- mọi tool ``read_only = True`` (agent không có công cụ quyết định);
- không schema nào có tham số chọn chủ thể (``user_id``, ``student_id``, ``email``...): chủ thể do BE quyết.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from vin15_agent.core.pii import PiiRedactor
from vin15_agent.core.tracing import TurnTrace

#: Chuỗi con (viết thường) không được xuất hiện trong tên tham số của tool.
FORBIDDEN_PARAM_SUBSTRINGS = (
    "user", "student", "email", "mail", "phone", "owner", "subject", "account", "actor", "uid", "mssv", "sinh_vien", "sinhvien", "tax",
)  # fmt: skip

MAX_TOOL_CONTENT_CHARS = 16_000


@dataclass(frozen=True)
class ToolError:
    code: str
    message: str


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    error: ToolError | None = None
    #: Mô tả ngắn cho khung ``tool_result`` và trace (không chứa dữ liệu nhạy cảm).
    summary: str = ""

    @classmethod
    def success(cls, data: Any, summary: str = "") -> ToolResult:
        return cls(ok=True, data=data, summary=summary)

    @classmethod
    def failure(cls, code: str, message: str) -> ToolResult:
        return cls(ok=False, error=ToolError(code, message), summary=message)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]

    def to_openai(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}


@dataclass
class TurnContext:
    """Trạng thái của một lượt hỏi, dùng chung giữa vòng lặp, tool và hậu kiểm."""

    actor_role: str
    today: str
    agent_token: str = ""
    #: Chunk quy định đã nhận từ tool trong lượt này (chunk_id → dữ liệu gốc từ BE). Nguồn của hậu kiểm trích dẫn.
    seen_chunks: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Kết quả tool (dạng chuỗi JSON gốc) để NumberChecker đối chiếu số liệu.
    tool_texts: list[str] = field(default_factory=list)
    redactor: PiiRedactor = field(default_factory=PiiRedactor)
    trace: TurnTrace = field(default_factory=TurnTrace)
    #: Hành động giao diện mà tool yêu cầu trong lượt này (hiện chỉ ``{"type": "navigate", "page": khóa, "label": tên}``); vào ``final.actions``.
    actions: list[dict[str, str]] = field(default_factory=list)
    #: Tên các tool đọc dữ liệu của BE (hồ sơ, hàng chờ...; không phải tra quy định) trong registry của lượt này.
    data_tool_names: frozenset[str] = frozenset()


@runtime_checkable
class Tool(Protocol):
    name: str
    description: str
    parameters: dict[str, Any]
    #: Nhãn thân thiện hiển thị ở khung ``tool_call``.
    label: str
    read_only: Literal[True]

    async def run(self, args: dict[str, Any], ctx: TurnContext) -> ToolResult: ...

    def describe(self, args: dict[str, Any]) -> str:
        """Nhãn kèm chi tiết (ví dụ truy vấn) cho khung ``tool_call``."""
        ...


class BaseTool:
    """Lớp nền tiện dụng: ``read_only`` luôn ``True``, ``describe`` mặc định trả nhãn."""

    name: str
    description: str
    parameters: dict[str, Any]
    label: str
    read_only: Literal[True] = True
    #: ``True`` nếu tool đọc dữ liệu nghiệp vụ của BE (câu trả lời dựa trên đó không cần ``[cite]`` quy định).
    data_source: bool = False

    async def run(self, args: dict[str, Any], ctx: TurnContext) -> ToolResult:  # pragma: no cover - lớp con ghi đè
        raise NotImplementedError

    def describe(self, args: dict[str, Any]) -> str:
        return self.label


def find_subject_params(schema: Any) -> list[str]:
    """Liệt kê tên tham số (đệ quy) có dạng chọn chủ thể."""
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            props = node.get("properties")
            if isinstance(props, Mapping):
                for name, sub in props.items():
                    if any(bad in str(name).lower() for bad in FORBIDDEN_PARAM_SUBSTRINGS):
                        found.append(str(name))
                    walk(sub)
            for key, value in node.items():
                if key != "properties":
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return found


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if getattr(tool, "read_only", False) is not True:
            raise ValueError(f"Tool '{tool.name}' phải chỉ-đọc (read_only=True): agent không có công cụ quyết định")
        bad = find_subject_params(tool.parameters)
        if bad:
            raise ValueError(f"Tool '{tool.name}' có tham số chọn chủ thể {bad}: chủ thể do BE quyết định")
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' đã được đăng ký")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def data_tool_names(self) -> frozenset[str]:
        return frozenset(name for name, tool in self._tools.items() if getattr(tool, "data_source", False) is True)

    def __len__(self) -> int:
        return len(self._tools)

    def specs(self) -> list[ToolSpec]:
        return [ToolSpec(t.name, t.description, t.parameters) for t in self._tools.values()]

    def to_openai_schema(self) -> list[dict[str, Any]]:
        return [s.to_openai() for s in self.specs()]


def wrap_tool_result(name: str, content: str) -> str:
    """Bọc kết quả tool thành khối dữ liệu không tin cậy; vô hiệu thẻ đóng giả nằm trong nội dung."""
    safe = content.replace("</tool_result>", "</ tool_result>")
    return f'<tool_result name="{name}">\n{safe}\n</tool_result>'


def tool_result_content(name: str, result: ToolResult, redactor: PiiRedactor) -> str:
    """Chuỗi đưa cho LLM: JSON đã che PII, bọc ``<tool_result>``, có trần độ dài."""
    payload: dict[str, Any]
    if result.ok:
        payload = {"ok": True, "data": result.data}
    else:
        err = result.error or ToolError("error", "lỗi không rõ")
        payload = {"ok": False, "error": {"code": err.code, "message": err.message}}
    text = redactor.redact_text(json.dumps(payload, ensure_ascii=False, default=str))
    if len(text) > MAX_TOOL_CONTENT_CHARS:
        text = text[:MAX_TOOL_CONTENT_CHARS] + "…(đã cắt bớt)"
    return wrap_tool_result(name, text)
