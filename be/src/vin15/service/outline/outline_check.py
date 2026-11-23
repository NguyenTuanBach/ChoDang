"""Kiểm tra đề cương bằng luật tất định (hàm thuần): đủ độ dài và đủ bốn phần mục tiêu, nhiệm vụ, kế hoạch, kết quả dự kiến.

Phần AI (nhận xét nội dung, nhận diện chuẩn đầu ra) nằm ở agent; ở đây chỉ chặn những lỗi chắc chắn để báo đúng chỗ sai.
"""

from __future__ import annotations

import unicodedata

MIN_CHARS = 50

#: (tên phần hiển thị, các từ khóa nhận diện — viết thường, không dấu).
REQUIRED_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Mục tiêu", ("muc tieu", "muc dich")),
    ("Nhiệm vụ", ("nhiem vu", "cong viec")),
    ("Kế hoạch", ("ke hoach", "lich trinh", "tien do")),
    ("Kết quả dự kiến", ("ket qua",)),
)


def _plain(text: str) -> str:
    """Viết thường, bỏ dấu tiếng Việt để so khớp từ khóa không phụ thuộc cách gõ dấu."""
    decomposed = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def check_outline(content: str) -> list[dict]:
    """Danh sách lỗi chắc chắn: ``[{"section", "level": "error", "message"}]``; rỗng nghĩa là đạt phần kiểm tra luật."""
    text = content.strip()
    issues: list[dict] = []
    if len(text) < MIN_CHARS:
        issues.append({"section": "Nội dung", "level": "error", "message": f"Đề cương cần ít nhất {MIN_CHARS} ký tự (hiện {len(text)})."})
    plain = _plain(text)
    for name, keywords in REQUIRED_SECTIONS:
        if not any(k in plain for k in keywords):
            issues.append({"section": name, "level": "error", "message": f"Chưa thấy phần “{name}” trong đề cương."})
    return issues
