"""Offline adversarial evaluation for the policy guard.

Usage: python eval/policy_guard_eval.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "eval" / "datasets" / "policy_adversarial.jsonl"
sys.path.insert(0, str(ROOT))

from src.agents.policy_guard import check_policy_query  # noqa: E402


def main() -> int:
    cases = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    failed = []
    for case in cases:
        result = check_policy_query(case["query"], "SV2026003")
        refused = bool(result.refusal_reason)
        if refused != case["expect_refusal"]:
            failed.append((case["id"], result.violation_type or "allowed"))
    print(f"policy_guard: {len(cases) - len(failed)}/{len(cases)} passed")
    if failed:
        for case_id, actual in failed:
            print(f"FAIL {case_id}: {actual}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
