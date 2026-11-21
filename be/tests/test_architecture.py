"""Khóa ranh giới kiến trúc bằng phân tích import (ast), không cần chạy code.

- BE không import gói agent: hai service chỉ nói chuyện qua HTTP (infrastructure/agent_api).
- Hướng phụ thuộc: domain là lõi; infrastructure và service chỉ phụ thuộc vào trong; presentation đi qua container.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
ROOT = SRC / "vin15"

#: tầng -> các tầng KHÔNG được import
FORBIDDEN = {
    "domain": {"config", "infrastructure", "presentation", "service"},
    "infrastructure": {"presentation", "service"},
    "service": {"presentation"},
    "presentation": {"infrastructure"},
}


def imports_of(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
    return names


def test_backend_never_imports_agent_package():
    offenders = [
        f"{path.relative_to(SRC)} -> {name}"
        for path in SRC.rglob("*.py")
        for name in imports_of(path)
        if name == "vin15_agent" or name.startswith("vin15_agent.")
    ]
    assert not offenders, offenders


def test_layers_respect_dependency_direction():
    offenders = []
    for layer, banned in FORBIDDEN.items():
        for path in (ROOT / layer).rglob("*.py"):
            for name in imports_of(path):
                parts = name.split(".")
                if parts[0] == "vin15" and len(parts) > 1 and parts[1] in banned:
                    offenders.append(f"{path.relative_to(SRC)} -> {name}")
    assert not offenders, offenders
