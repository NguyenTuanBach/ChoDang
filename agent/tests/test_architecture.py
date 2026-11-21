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


def test_llm_sdk_only_imported_in_core():
    """SDK ``openai`` chỉ được import trong ``vin15_agent/core``."""
    offenders = []
    for path in SRC.rglob("*.py"):
        if "core" in path.relative_to(SRC).parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            offenders += [f"{path.name} -> {n}" for n in names if n == "openai" or n.startswith("openai.")]
    assert not offenders, offenders


def _imports(path: Path) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module)
    return names


def test_agent_layering_runtime_agent_core_shared():
    """``runtime → <agent> → core → shared``: tầng dưới không import tầng trên."""
    package = SRC / "vin15_agent"
    forbidden = {"shared": ("core", "policy_assistant", "runtime"), "core": ("policy_assistant", "runtime"), "policy_assistant": ("runtime",)}
    offenders = []
    for layer, upper in forbidden.items():
        for path in (package / layer).rglob("*.py"):
            for name in _imports(path):
                if any(name == f"vin15_agent.{u}" or name.startswith(f"vin15_agent.{u}.") for u in upper):
                    offenders.append(f"{path.relative_to(SRC)} -> {name}")
    assert not offenders, offenders


def test_no_long_prompt_strings_embedded_in_python():
    """Prompt nằm ở ``prompts/*.md``, không nhúng chuỗi dài trong Python (docstring được bỏ qua)."""
    offenders = []
    for path in (SRC / "vin15_agent").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}  # noqa: E501
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings and len(node.value) > 400:
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno}")
    assert not offenders, offenders
