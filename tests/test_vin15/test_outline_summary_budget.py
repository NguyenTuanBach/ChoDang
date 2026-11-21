"""summarize_outline không được làm chậm việc nộp đề cương: LLM chậm/lỗi → bản tóm tắt theo luật."""

from __future__ import annotations

import time
from types import SimpleNamespace

from src.services import reviewer
from src.services.pii import Redactor

COHORT = SimpleNamespace(outcomes=[{"code": "CLO1", "text": "Kiểm thử", "keywords": ["kiểm thử"]},
                                   {"code": "CLO2", "text": "Triển khai", "keywords": ["triển khai"]}])
CONTENT = "Xây dựng API backend. Viết kiểm thử tự động cho các endpoint."


def _run(monkeypatch, llm, budget=0.2):
    monkeypatch.setattr(reviewer, "llm_available", lambda: True)
    monkeypatch.setattr(reviewer, "_llm_summary", llm)
    monkeypatch.setattr(reviewer, "OUTLINE_SUMMARY_BUDGET_SECONDS", budget)
    start = time.monotonic()
    out = reviewer.summarize_outline(CONTENT, COHORT, Redactor())
    return out, time.monotonic() - start


def test_slow_llm_falls_back_to_rules_within_budget(monkeypatch):
    out, elapsed = _run(monkeypatch, lambda text, purpose: time.sleep(2) or "chậm")
    assert elapsed < 1.0
    assert out["source"] == "rules" and out["summary"].startswith("Xây dựng API")
    assert [c["code"] for c in out["uncovered_outcomes"]] == ["CLO2"]


def test_failing_llm_falls_back_to_rules(monkeypatch):
    def boom(text, purpose):
        raise RuntimeError("model down")

    out, _ = _run(monkeypatch, boom)
    assert out["source"] == "rules" and out["label"].startswith("Gợi ý của AI")


def test_fast_llm_is_used(monkeypatch):
    out, _ = _run(monkeypatch, lambda text, purpose: "Tóm tắt từ model")
    assert out["source"] == "llm" and out["summary"] == "Tóm tắt từ model"
