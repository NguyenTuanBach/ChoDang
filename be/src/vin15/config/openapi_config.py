"""Thông tin OpenAPI (``/docs``)."""

TITLE = "VIN-15 — Hệ thống hỗ trợ thực tập bằng AI"
DESCRIPTION = (
    "Backend của cổng thực tập Sinh viên – Giảng viên – Quản trị viên. "
    "Mọi quyết định học thuật do con người; các tác tử AI chạy ở service riêng (agent-api)."
)
VERSION = "0.1.0"
TAGS = [
    {"name": "Health", "description": "Kiểm tra tiến trình và kết nối."},
    {"name": "Agent", "description": "Trạng thái kết nối tới service agent."},
]
