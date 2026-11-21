"""Đường dẫn tới thư mục ``resources/`` đóng gói cùng gói ``vin15`` (migration SQL...)."""

from __future__ import annotations

from pathlib import Path

RESOURCES_DIR = Path(__file__).resolve().parents[1] / "resources"
MIGRATION_DIR = RESOURCES_DIR / "db" / "migration"
