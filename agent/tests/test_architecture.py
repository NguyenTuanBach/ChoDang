"""Agent không được import gói BE (``vin15``): hai service chỉ nói chuyện qua HTTP."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def test_agent_never_imports_backend_package():
    offenders = []
    for path in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            offenders += [f"{path.name} -> {n}" for n in names if n == "vin15" or n.startswith("vin15.")]
    assert not offenders, offenders
