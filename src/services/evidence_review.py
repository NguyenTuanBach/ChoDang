"""AI hỗ trợ đọc minh chứng — GỢI Ý cho GV, KHÔNG ảnh hưởng quyết định (HITL).

Cùng khuôn với reviewer.summarize_outline:
- Kiểm tra xác định (không cần LLM, giải thích được): checklist từ khóa theo loại minh chứng
  (khoa cấu hình trong cohort.yaml), file trùng hệt với minh chứng khác (sha256), file gần như
  không có chữ, không thấy tên doanh nghiệp trong giấy tờ của doanh nghiệp, CĐR chưa nhắc tới.
- Tóm tắt: LLM nếu có — văn bản ĐÃ CHE thông tin SV và doanh nghiệp (tên, MSSV, email, SĐT,
  mã số thuế) trước khi gửi; không có key thì trích vài câu đầu.
- Không bao giờ khẳng định chữ ký/con dấu là thật — luôn kèm `limits`.
- Lỗi bất kỳ → trả None, UI ẩn phần gợi ý, GV vẫn duyệt bình thường.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agents.prompts import load_prompt
from src.models.orm import Evidence, Internship
from src.services.documents import UnreadableDocument, read_document
from src.services.llm import get_llm, llm_available
from src.services.pii import Redactor
from src.services.policy_index import normalize
from src.services.reviewer import AI_LABEL, _first_sentences, uncovered_outcomes
from src.workflow.rules import load_cohort_config

logger = logging.getLogger("vin15.evidence_review")

LIMITS = ("AI chỉ đọc phần chữ trong file. AI không xác nhận được chữ ký, con dấu hay tính xác thực của giấy tờ "
          "— giảng viên cần tự kiểm tra trên file gốc.")
COMPANY_DOCS = ("acceptance_letter", "company_evaluation")  # giấy tờ do doanh nghiệp phát hành
REPORT_DOCS = ("midterm_report", "final_report")  # báo cáo của SV → đối chiếu chuẩn đầu ra
DEFAULT_MIN_TEXT_CHARS = 200
LLM_TEXT_CHARS = 6000


def _has(plain: str, keyword: str) -> bool:
    return re.search(rf"\b{re.escape(normalize(keyword))}\b", plain) is not None


def _redactor(i: Internship) -> Redactor:
    s = i.student
    return Redactor({
        "HO_TEN": s.full_name, "MSSV": s.student_code, "EMAIL": s.email, "SDT": s.phone,
        "DOANH_NGHIEP": i.company_name, "MST": i.company_tax_code, "DIA_CHI_DN": i.company_address,
        "NGUOI_HD": i.mentor_name, "EMAIL_HD": i.mentor_email, "SDT_HD": i.mentor_phone,
    })


def _llm_summary(text: str, label: str) -> str:
    system = load_prompt("evidence_review.md").replace("{{evidence_label}}", label)
    out = str(get_llm("classify").invoke([("system", system), ("human", text[:LLM_TEXT_CHARS])]).content).strip()
    lines = [ln for ln in out.splitlines() if not re.search(r"(?i)tối đa \d+ câu|không đưa ra khuyến nghị", ln)]
    return "\n".join(lines).strip() or out


def _duplicates(db: Session, ev: Evidence) -> list[str]:
    """File giống hệt từng byte. Không nêu tên SV khác — GV có thể không có quyền xem hồ sơ đó (P5)."""
    rows = db.execute(
        select(Evidence.internship_id, Evidence.milestone_id).where(Evidence.sha256 == ev.sha256, Evidence.id != ev.id)
    ).all()
    warnings = []
    if any(iid != ev.internship_id for iid, _ in rows):
        warnings.append("File giống hệt một minh chứng đã nộp ở hồ sơ của sinh viên khác.")
    if any(iid == ev.internship_id and mid not in (None, ev.milestone_id) for iid, mid in rows):
        warnings.append("File giống hệt file sinh viên đã nộp cho một mốc khác.")
    return warnings


def review_evidence(db: Session, ev: Evidence) -> dict | None:
    try:
        cfg = load_cohort_config().get("evidence_review", {})
        labels = load_cohort_config().get("evidence_types", {})
        label = labels.get(ev.evidence_type, ev.evidence_type)
        i = db.get(Internship, ev.internship_id)
        warnings = _duplicates(db, ev)

        try:
            doc = read_document(ev.filename, Path(ev.path).read_bytes(), ocr=True)
            text, used_ocr = doc.text.strip(), doc.used_ocr
        except (UnreadableDocument, OSError) as exc:
            text, used_ocr = "", False
            warnings.append(f"Không đọc được nội dung file ({exc}).")
        plain = normalize(text)
        if text and len(text) < cfg.get("min_text_chars", DEFAULT_MIN_TEXT_CHARS):
            warnings.append(f"File gần như không có chữ ({len(text)} ký tự) — có thể là ảnh chụp mờ hoặc trang trống.")

        spec = cfg.get("checklists", {}).get(ev.evidence_type, {})
        checklist = [{"item": c["item"], "found": any(_has(plain, k) for k in c.get("keywords", []))}
                     for c in spec.get("items", [])] if text else []
        if checklist and not any(c["found"] for c in checklist):
            warnings.append(f"Không thấy nội dung đặc trưng của '{label}' — kiểm tra lại file có đúng loại không.")
        if text and ev.evidence_type in COMPANY_DOCS and i.company_name and normalize(i.company_name) not in plain:
            warnings.append("Không thấy tên doanh nghiệp đã đăng ký trong file.")
        uncovered = uncovered_outcomes(text, i.cohort.outcomes or []) if text and ev.evidence_type in REPORT_DOCS else []

        use_llm = bool(text) and llm_available()
        summary = _llm_summary(_redactor(i).redact(text), label) if use_llm else _first_sentences(text, 3)
        return {
            "label": AI_LABEL,
            "evidence_label": label,
            "summary": summary or "Không trích được nội dung chữ từ file.",
            "checklist": checklist,
            "checklist_citation": spec.get("citation", {}),
            "warnings": warnings,
            "uncovered_outcomes": uncovered,
            "text_chars": len(text),
            "used_ocr": used_ocr,
            "limits": LIMITS,
            "source": "llm" if use_llm else "rules",
        }
    except Exception as exc:  # AI lỗi → GV vẫn xem file và duyệt bình thường
        logger.error("FAILED review_evidence id=%s: %s", ev.id, exc)
        return None
