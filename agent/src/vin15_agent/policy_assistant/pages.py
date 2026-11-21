"""Danh mục trang để trợ lý điều hướng (``pages.json``). Khóa trang là hợp đồng với FE (``fe/src/lib/nav.ts``); agent không biết URL."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PAGES_PATH = Path(__file__).with_name("pages.json")


@dataclass(frozen=True)
class Page:
    key: str
    label: str
    description: str


@lru_cache(maxsize=1)
def _catalog() -> dict[str, list[Page]]:
    raw = json.loads(PAGES_PATH.read_text(encoding="utf-8"))
    return {role: [Page(p["key"], p["label"], p["description"]) for p in pages] for role, pages in raw.items() if not role.startswith("_")}


def pages_for(role: str) -> list[Page]:
    """Các trang mà một vai trò được phép nhờ trợ lý mở (trang của vai trò + trang chung). Vai trò lạ: chỉ trang chung."""
    catalog = _catalog()
    return [*catalog.get(role, []), *catalog["common"]]
