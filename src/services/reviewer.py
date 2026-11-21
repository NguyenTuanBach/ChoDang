"""Reviewer Summarizer (R3.2, R12.2) — gợi ý cho GV, KHÔNG ảnh hưởng quyết định.

- "CĐR chưa nhắc tới" tính xác định bằng từ khóa (không cần LLM, giải thích được).
- Tóm tắt: LLM nếu có (văn bản đã che PII), không thì trích câu đầu.
- Mọi kết quả gắn nhãn "Gợi ý của AI"; AI lỗi → trả None, UI ẩn phần gợi ý.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import date

from sqlalchemy.orm import Session

from src.agents.prompts import load_prompt
from src.models.orm import Cohort, ExtensionRequest
from src.services.llm import get_llm, llm_available
from src.services.pii import Redactor
from src.services.policy_index import normalize, search_policy

logger = logging.getLogger("vin15.reviewer")

AI_LABEL = "Gợi ý của AI — chỉ để tham khảo, GV là người quyết định"

# Ngân sách thời gian cho phần tóm tắt bằng LLM khi SV nộp đề cương: hết hạn → dùng bản tóm tắt theo luật,
# việc nộp không bị chậm theo model. Thread LLM quá hạn vẫn chạy nốt ở nền (không hủy được), nên pool có giới hạn.
OUTLINE_SUMMARY_BUDGET_SECONDS = 5.0
_llm_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="reviewer-llm")


def uncovered_outcomes(text: str, outcomes: list[dict]) -> list[dict]:
    plain = normalize(text)
    missing = []
    for outcome in outcomes:
        keywords = [normalize(k) for k in outcome.get("keywords", [])]
        if not any(re.search(rf"\b{re.escape(k)}\b", plain) for k in keywords):
            missing.append({"code": outcome["code"], "text": outcome["text"]})
    return missing


def _first_sentences(text: str, n: int = 2) -> str:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return " ".join(s for s in sentences[:n] if s).strip()[:400]


def _llm_summary(text: str, purpose: str) -> str:
    # Hướng dẫn ở system, văn bản ở human — model nhỏ hay chép lại hướng dẫn nếu gộp chung
    system = load_prompt("reviewer_summary.md").replace("{{purpose}}", purpose)
    out = str(get_llm("classify").invoke([("system", system), ("human", text[:6000])]).content).strip()
    # Bỏ dòng model lặp lại hướng dẫn ("Tối đa 3 câu…") nếu có
    lines = [ln for ln in out.splitlines() if not re.search(r"(?i)tối đa \d+ câu|không đưa ra khuyến nghị", ln)]
    return "\n".join(lines).strip() or out


def _llm_summary_within(text: str, purpose: str, budget: float) -> str | None:
    """Tóm tắt bằng LLM trong `budget` giây; quá hạn hoặc lỗi → None (người gọi dùng bản theo luật). budget<=0: không giới hạn."""
    future = _llm_pool.submit(_llm_summary, text, purpose)
    try:
        return future.result(timeout=budget if budget > 0 else None)
    except FutureTimeout:
        future.cancel()
        logger.warning("summarize_outline: LLM quá ngân sách %.1fs → dùng bản tóm tắt theo luật", budget)
    except Exception as exc:
        logger.warning("summarize_outline: LLM lỗi (%s) → dùng bản tóm tắt theo luật", exc)
    return None


def summarize_outline(content: str, cohort: Cohort, redactor: Redactor) -> dict | None:
    try:
        summary = None
        if llm_available():
            summary = _llm_summary_within(redactor.redact(content), "đề cương thực tập", OUTLINE_SUMMARY_BUDGET_SECONDS)
        return {
            "label": AI_LABEL,
            "summary": summary or _first_sentences(content),
            "uncovered_outcomes": uncovered_outcomes(content, cohort.outcomes or []),
            "source": "llm" if summary else "rules",
        }
    except Exception as exc:  # R3.2: AI lỗi → GV vẫn duyệt bình thường
        logger.error("FAILED summarize_outline: %s", exc)
        return None


def summarize_extension(db: Session, request: ExtensionRequest, redactor: Redactor, today: date) -> dict | None:
    try:
        m = request.milestone
        days = (request.requested_due_date - request.previous_due_date).days
        # Truy vấn cố định theo chủ đề gia hạn — tên mốc làm nhiễu xếp hạng (kéo về Điều quy định mốc)
        hits = search_policy(db, "đề nghị gia hạn thời hạn nộp mốc lý do chính đáng", today, top_k=2)
        summary = (
            f"Xin dời hạn mốc '{m.name}' từ {request.previous_due_date:%d/%m/%Y} sang "
            f"{request.requested_due_date:%d/%m/%Y} (+{days} ngày). Lý do: {_first_sentences(request.reason, 1)}"
        )
        if llm_available():
            summary = _llm_summary(redactor.redact(summary + "\n" + request.reason), "yêu cầu gia hạn mốc")
        return {
            "label": AI_LABEL,
            "summary": summary,
            "extra_days": days,
            "related_clauses": [{"label": h.label, "text": h.text[:500], "chunk_id": h.chunk_id} for h in hits],
            "source": "llm" if llm_available() else "rules",
        }
    except Exception as exc:
        logger.error("FAILED summarize_extension: %s", exc)
        return None


_EXCEPTION_QUERIES = {
    "late_extension": "đề nghị gia hạn thời hạn nộp mốc quá hạn trường hợp đặc biệt lý do chính đáng",
    "credit_recognition": "công nhận kết quả thực tập quy đổi tín chỉ Hội đồng Khoa quyết định",
}
_EXCEPTION_LABELS = {"late_extension": "gia hạn quá hạn", "credit_recognition": "công nhận/quy đổi tín chỉ"}


def summarize_exception(db: Session, request, redactor: Redactor, today: date) -> dict | None:
    """Gợi ý cho GV về yêu cầu ngoại lệ: tóm tắt + điều khoản liên quan. Không bao giờ quyết định."""
    try:
        label = _EXCEPTION_LABELS.get(request.kind, request.kind)
        hits = search_policy(db, _EXCEPTION_QUERIES.get(request.kind, request.reason), today, top_k=2)
        summary = f"Đề nghị ngoại lệ ({label}). Lý do: {_first_sentences(request.reason, 2)}"
        if llm_available():
            summary = _llm_summary(redactor.redact(summary + "\n" + request.reason), "yêu cầu ngoại lệ thực tập")
        return {
            "label": AI_LABEL,
            "summary": summary,
            "related_clauses": [{"label": h.label, "text": h.text[:500], "chunk_id": h.chunk_id} for h in hits],
            "source": "llm" if llm_available() else "rules",
        }
    except Exception as exc:
        logger.error("FAILED summarize_exception: %s", exc)
        return None
