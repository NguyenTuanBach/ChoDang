"""PromptLoader (task 4.1) và các prompt mới (task 4.2)."""

import pytest

from vin15_agent.core.prompts import PromptError, PromptLoader

REAL = PromptLoader()


@pytest.fixture
def loader(tmp_path):
    (tmp_path / "a.md").write_text("Xin chào {{name}}, hôm nay {{ today }}.\n", encoding="utf-8")
    (tmp_path / "b.md").write_text('<template id="x">\nMột\n</template>\ngiữa\n<template id="y">Hai</template>', encoding="utf-8")
    return PromptLoader(tmp_path)


def test_render_substitutes_placeholders(loader):
    assert loader.render("a", name="An", today="2026-11-21") == "Xin chào An, hôm nay 2026-11-21."
    assert loader.placeholders("a") == {"name", "today"}


def test_render_errors_on_missing_or_extra(loader):
    with pytest.raises(PromptError, match="thiếu.*today"):
        loader.render("a", name="An")
    with pytest.raises(PromptError, match="không có placeholder.*zzz"):
        loader.render("a", name="An", today="x", zzz="y")
    with pytest.raises(PromptError, match="Không đọc được"):
        loader.render("khong_co")


def test_substituted_value_is_not_expanded_again(loader):
    out = loader.render("a", name="{{today}}", today="X")
    assert out == "Xin chào {{today}}, hôm nay X."


def test_raw_is_cached(loader, tmp_path):
    first = loader.raw("a")
    (tmp_path / "a.md").write_text("đã đổi", encoding="utf-8")
    assert loader.raw("a") == first


def test_sections_and_without_sections(loader):
    assert loader.sections("b") == {"x": "Một", "y": "Hai"}
    assert loader.without_sections("b") == "giữa"


# ---- prompt thật ----


def _system_prompt(**over):
    values = {
        "today": "2026-11-21",
        "user_role": "sinh viên",
        "persona": "PERSONA-X",
        "role_workflow": "WORKFLOW-X",
        "school_name": "Trường Mẫu",
        "sample_notice": REAL.sections("refusals")["sample_notice"],
        "citation_rules": REAL.raw("citation_rules"),
        "safeguards": REAL.raw("safeguards"),
        "refusals": REAL.without_sections("refusals"),
    }
    values.update(over)
    return REAL.render("policy_assistant.system", **values)


def test_system_prompt_renders_with_all_blocks():
    prompt = _system_prompt()
    for block in ("role", "persona", "workflow", "rules", "safeguards", "citation_rules", "refusal_markers"):
        assert f"<{block}>" in prompt and f"</{block}>" in prompt, block
    assert "Trường Mẫu" in prompt and "2026-11-21" in prompt and "sinh viên" in prompt
    assert "{{" not in prompt and "}}" not in prompt.replace("]]", "")  # không sót placeholder
    assert "[cite:chunk_id]" in prompt


def test_old_project_traces_are_gone():
    prompt = _system_prompt()
    for old in ("AI20K", "y tế", "uncertain", "src/agents"):
        assert old not in prompt
    assert not (REAL._dir / "system_prompt.md").exists() and not (REAL._dir / "README.md").exists()


def test_refusal_templates_are_complete():
    templates = REAL.sections("refusals")
    required = {
        "other_user", "prompt_injection", "out_of_scope", "no_basis", "no_basis_partial", "no_commitment",
        "number_mismatch", "sample_warning", "sample_notice", "degraded_notice", "degraded_empty", "unfinished", "unfinished_empty",
    }  # fmt: skip
    assert required <= templates.keys()
    # hướng dẫn gửi cho LLM không chứa nguyên văn mẫu (LLM chỉ xuất dấu hiệu)
    assert templates["no_basis"] not in _system_prompt()


def test_persona_files_have_both_parts_for_every_role():
    for role in ("student", "lecturer", "admin"):
        parts = REAL.sections(f"persona.{role}", tag="part")
        assert set(parts) == {"persona", "workflow"} and all(v.strip() for v in parts.values()), role
        assert "{{" not in parts["persona"] + parts["workflow"]


def test_staff_refusal_templates_exist():
    templates = REAL.sections("refusals")
    assert {"other_user_staff", "out_of_scope_staff", "no_basis_staff", "no_basis_partial_staff"} <= templates.keys()
