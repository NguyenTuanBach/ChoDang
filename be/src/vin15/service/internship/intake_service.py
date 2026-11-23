"""AI đọc giấy tờ để **gợi ý** trường (A4): giấy tiếp nhận → hồ sơ; giấy xác nhận / phiếu đánh giá → mốc M5.

Mỗi trường kèm nguồn và độ tin cậy; sinh viên bấm xác nhận từng trường; không lưu gì cho tới khi sinh viên lưu hồ sơ / xác nhận giấy.
Ảnh và PDF quét cũng được gửi cho AI (đã chốt: dữ liệu hiện là mock, AI sẽ chạy nội bộ).
"""

from __future__ import annotations

import base64

from vin15.domain.exception import InvalidInputError, ResourceNotFoundError
from vin15.domain.model.user import User
from vin15.domain.ports import FileStorage
from vin15.infrastructure.agent_api import AgentApiClient
from vin15.infrastructure.persistence.case_repository import CaseRepository
from vin15.service.files.upload import RECEIPT_TYPES, sniff_mime
from vin15.service.internship.internship_service import InternshipService
from vin15.service.milestone.evidence_check import COMPLETION_FIELDS, normalize
from vin15.service.milestone.milestone_service import MilestoneService

#: Tên trường phía agent → cột hồ sơ. ``student_name``/``student_code`` chỉ để đối chiếu, không ghi vào hồ sơ.
RECEIPT_MAP = {
    "company_name": "company_name",
    "company_tax_code": "company_tax_code",
    "company_address": "company_address",
    "position": "position",
    "department": "department",
    "mentor_name": "mentor_name",
    "mentor_title": "mentor_title",
    "mentor_email": "mentor_email",
    "mentor_phone": "mentor_phone",
    "job_description": "job_description",
    "start_date": "start_date",
    "end_date": "end_date",
    "mode": "mode",
    "letter_number": "receipt_letter_number",
    "letter_date": "receipt_letter_date",
    "signer_name": "receipt_signer_name",
    "signer_title": "receipt_signer_title",
}
_IDENTITY = ("student_name", "student_code")
_AGENT_TIMEOUT = 120.0
_COMPLETION_MILESTONE = "M5"


class IntakeService:
    def __init__(
        self, cases: CaseRepository, storage: FileStorage, agent: AgentApiClient, internships: InternshipService, milestones: MilestoneService
    ):
        self._cases = cases
        self._storage = storage
        self._agent = agent
        self._internships = internships
        self._milestones = milestones

    # ---- Giấy tiếp nhận (hồ sơ) ----
    async def extract(self, student: User, document_id: int) -> dict:
        doc = self._cases.get_document(document_id)
        if doc is None or doc["owner_id"] != student.id:
            raise ResourceNotFoundError("Không tìm thấy giấy tiếp nhận")
        body = await self._ask(doc["filename"], doc["mime"], self._storage.get(doc["storage_key"]), "receipt_letter", [*RECEIPT_MAP, *_IDENTITY])
        return self._receipt_result(student, body)

    # ---- Giấy xác nhận / phiếu đánh giá (M5) ----
    async def extract_evidence(self, student: User, evidence_id: int) -> dict:
        ev = self._milestones.own_evidence(student, evidence_id)
        if ev["mime"] not in RECEIPT_TYPES:
            raise InvalidInputError("AI chỉ đọc được PDF, PNG hoặc JPG")
        body = await self._ask(ev["filename"], ev["mime"], self._storage.get(ev["storage_key"]), "completion_letter", list(COMPLETION_FIELDS))
        return {"fields": self._clean(body, COMPLETION_FIELDS), "notes": str(body.get("notes", ""))[:500], "warnings": []}

    # ---- Đính kèm trong ngăn Trợ lý: AI tự phân loại rồi lưu vào đúng chỗ ----
    async def auto_intake(self, student: User, filename: str, data: bytes) -> dict:
        mime = sniff_mime(data, filename)
        if mime not in RECEIPT_TYPES:
            raise InvalidInputError("Chỉ đọc được PDF, PNG hoặc JPG")
        body = await self._ask(filename, mime, data, "auto", [])
        kind = body.get("kind")
        if kind == "receipt_letter":
            result = self._receipt_result(student, body)  # trước khi lưu tệp: không trích được gì thì không lưu
            doc = self._internships.upload_document(student, filename, data)
            return {"kind": kind, "target_page": "internship", "document_id": doc["id"], "evidence_id": None, **result}
        if kind == "completion_letter":
            evidence_id = self._milestones.upload_evidence(student, _COMPLETION_MILESTONE, filename, data, "Giấy xác nhận / phiếu đánh giá của doanh nghiệp")
            return {
                "kind": kind, "target_page": "milestones", "document_id": None, "evidence_id": evidence_id,
                "fields": self._clean(body, COMPLETION_FIELDS), "notes": str(body.get("notes", ""))[:500], "warnings": [],
            }
        raise InvalidInputError(str(body.get("notes") or "Không nhận ra loại giấy (giấy tiếp nhận hoặc giấy xác nhận thực tập)")[:300])

    # ---- nội bộ ----
    async def _ask(self, filename: str, mime: str, data: bytes, kind: str, fields: list[str]) -> dict:
        return await self._agent.call(
            "/v1/intake/extract",
            {"filename": filename[:200], "mime": mime, "content_b64": base64.b64encode(data).decode(), "fields": fields, "kind": kind},
            timeout=_AGENT_TIMEOUT,
        )

    def _receipt_result(self, student: User, body: dict) -> dict:
        raw = self._clean(body, (*RECEIPT_MAP, *_IDENTITY))
        warnings = self._identity_warnings(student, raw)
        fields = {RECEIPT_MAP[k]: v for k, v in raw.items() if k in RECEIPT_MAP}
        if "mode" in fields and fields["mode"]["value"] not in ("onsite", "remote", "hybrid"):
            fields.pop("mode")
        if not fields:
            raise InvalidInputError(str(body.get("notes") or "Không trích được thông tin nào từ giấy; hãy nhập tay")[:300])
        return {"fields": fields, "notes": str(body.get("notes", ""))[:500], "warnings": warnings}

    @staticmethod
    def _clean(body: dict, allowed) -> dict:
        fields = {}
        for name, item in (body.get("fields") or {}).items():
            if name not in allowed or not isinstance(item, dict) or item.get("value") in (None, ""):
                continue
            try:
                confidence = max(0.0, min(1.0, float(item.get("confidence", 0))))
            except (TypeError, ValueError):
                confidence = 0.0
            fields[name] = {"value": str(item["value"])[:2000], "confidence": confidence, "source": str(item.get("source", ""))[:300]}
        return fields

    @staticmethod
    def _identity_warnings(student: User, raw: dict) -> list[str]:
        out = []
        name = normalize(raw.get("student_name", {}).get("value"))
        if name and normalize(student.full_name) and name != normalize(student.full_name):
            out.append(f"Tên sinh viên trên giấy ({raw['student_name']['value']}) khác tên tài khoản ({student.full_name}).")
        code = normalize(raw.get("student_code", {}).get("value")).replace(" ", "")
        if code and student.student_code and code != normalize(student.student_code).replace(" ", ""):
            out.append(f"Mã sinh viên trên giấy ({raw['student_code']['value']}) khác mã của bạn ({student.student_code}).")
        return out
