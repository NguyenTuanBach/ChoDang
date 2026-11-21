"""Chuẩn hóa hồ sơ bằng AI (A4): trích các trường từ giấy tiếp nhận. Chỉ **gợi ý**: mỗi trường kèm nguồn và độ tin cậy,
sinh viên bấm xác nhận từng trường; kết quả không được lưu cho tới khi sinh viên lưu hồ sơ.
"""

from __future__ import annotations

import base64

from vin15.domain.exception import InvalidInputError, ResourceNotFoundError
from vin15.domain.model.user import User
from vin15.domain.ports import FileStorage
from vin15.infrastructure.agent_api import AgentApiClient
from vin15.infrastructure.persistence.case_repository import PROFILE_FIELDS, CaseRepository

_EXTRACTABLE = tuple(f for f in PROFILE_FIELDS if f not in ("mode",))


class IntakeService:
    def __init__(self, cases: CaseRepository, storage: FileStorage, agent: AgentApiClient):
        self._cases = cases
        self._storage = storage
        self._agent = agent

    async def extract(self, student: User, document_id: int) -> dict:
        doc = self._cases.get_document(document_id)
        if doc is None or doc["owner_id"] != student.id:
            raise ResourceNotFoundError("Không tìm thấy giấy tiếp nhận")
        data = self._storage.get(doc["storage_key"])
        body = await self._agent.call(
            "/v1/intake/extract",
            {"filename": doc["filename"], "mime": doc["mime"], "content_b64": base64.b64encode(data).decode(), "fields": list(_EXTRACTABLE)},
        )
        fields = {}
        for name, item in (body.get("fields") or {}).items():
            if name not in _EXTRACTABLE or not isinstance(item, dict) or item.get("value") in (None, ""):
                continue
            try:
                confidence = max(0.0, min(1.0, float(item.get("confidence", 0))))
            except (TypeError, ValueError):
                confidence = 0.0
            fields[name] = {"value": str(item["value"])[:2000], "confidence": confidence, "source": str(item.get("source", ""))[:300]}
        if not fields:
            raise InvalidInputError("Không trích được thông tin nào từ giấy tiếp nhận; hãy nhập tay")
        return {"fields": fields, "notes": str(body.get("notes", ""))[:500]}
