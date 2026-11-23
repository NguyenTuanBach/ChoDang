"""Danh mục trang để trợ lý điều hướng (``pages.json``). Khóa trang là hợp đồng với FE (``fe/src/lib/nav.ts``); agent không biết URL.

Một trang có thể cần mã hồ sơ (``param = "internship_id"``, ví dụ trang chi tiết hồ sơ) và có bộ lọc mở sẵn (``filters``: khóa -> giá trị cho phép).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PAGES_PATH = Path(__file__).with_name("pages.json")


@dataclass(frozen=True)
class PageFilter:
    values: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class Page:
    key: str
    label: str
    description: str
    #: Tham số bắt buộc của trang (hiện chỉ ``internship_id``); ``None`` = trang tĩnh.
    param: str | None = None
    filters: dict[str, PageFilter] = field(default_factory=dict)


def _page(raw: dict) -> Page:
    filters = {k: PageFilter(tuple(v["values"]), v.get("description", "")) for k, v in (raw.get("filters") or {}).items()}
    return Page(raw["key"], raw["label"], raw["description"], raw.get("param"), filters)


@lru_cache(maxsize=1)
def _catalog() -> dict[str, list[Page]]:
    raw = json.loads(PAGES_PATH.read_text(encoding="utf-8"))
    return {role: [_page(p) for p in pages] for role, pages in raw.items() if not role.startswith("_")}


def pages_for(role: str) -> list[Page]:
    """Các trang mà một vai trò được phép nhờ trợ lý mở (trang của vai trò + trang chung). Vai trò lạ: chỉ trang chung."""
    catalog = _catalog()
    return [*catalog.get(role, []), *catalog["common"]]


def find_page(role: str, key: str) -> Page | None:
    return next((p for p in pages_for(role) if p.key == key), None)
