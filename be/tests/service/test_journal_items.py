"""Chuẩn hóa danh sách việc trong nhật ký tuần: bỏ dòng trống, cắt độ dài, giới hạn số dòng."""

from __future__ import annotations

import pytest

from vin15.domain.exception import InvalidInputError
from vin15.service.milestone.milestone_service import MAX_ITEM_CHARS, MAX_PLAN_ITEMS, normalize_plan_items


def test_blank_items_are_dropped_and_text_is_trimmed():
    items = normalize_plan_items([{"text": "  Viết báo cáo  ", "done": True}, {"text": "   "}, {"text": ""}])
    assert items == [{"text": "Viết báo cáo", "done": True}]


def test_done_defaults_to_false_and_none_is_empty():
    assert normalize_plan_items([{"text": "Học kiểm thử"}]) == [{"text": "Học kiểm thử", "done": False}]
    assert normalize_plan_items(None) == []


def test_long_text_is_truncated():
    (item,) = normalize_plan_items([{"text": "a" * (MAX_ITEM_CHARS + 50)}])
    assert len(item["text"]) == MAX_ITEM_CHARS


def test_too_many_items_is_rejected():
    with pytest.raises(InvalidInputError):
        normalize_plan_items([{"text": f"việc {i}"} for i in range(MAX_PLAN_ITEMS + 1)])
