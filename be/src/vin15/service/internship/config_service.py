"""Cấu hình do QTV quản lý: mẫu mốc (9.1) và chuẩn đầu ra theo khóa (Q5). Thay đổi có audit."""

from __future__ import annotations

from vin15.domain.exception import ForbiddenRoleError, InvalidInputError
from vin15.domain.model.audit import ActorKind, AuditEntry
from vin15.domain.model.user import Role, User
from vin15.infrastructure.persistence.config_repository import ConfigRepository


class ConfigService:
    def __init__(self, config: ConfigRepository):
        self._config = config

    @staticmethod
    def _audit(admin: User, entity: str, action: str, after: dict) -> AuditEntry:
        if admin.role != Role.ADMIN:
            raise ForbiddenRoleError("Chỉ quản trị viên được thay đổi cấu hình")
        return AuditEntry(actor_kind=ActorKind.HUMAN, actor_id=admin.id, actor_role=admin.role.value, entity=entity, action=action, after=after, reason="Cấu hình")

    def milestone_templates(self) -> list[dict]:
        return self._config.milestone_templates()

    def update_milestone_template(self, admin: User, code: str, name: str, anchor: str, offset_days: int) -> None:
        self._config.update_milestone_template(code, name.strip(), anchor, offset_days, self._audit(admin, "milestone_template", "update", {"code": code, "anchor": anchor, "offset_days": offset_days}))

    def outcomes(self, cohort: str) -> list[dict]:
        return self._config.learning_outcomes(cohort)

    def upsert_outcome(self, admin: User, cohort: str, code: str, description: str) -> None:
        if not code.strip() or not description.strip():
            raise InvalidInputError("Cần mã và mô tả chuẩn đầu ra")
        self._config.upsert_learning_outcome(cohort.strip(), code.strip().upper(), description.strip(), self._audit(admin, "learning_outcome", "upsert", {"cohort": cohort, "code": code}))

    def delete_outcome(self, admin: User, outcome_id: int) -> None:
        self._config.delete_learning_outcome(outcome_id, self._audit(admin, "learning_outcome", "delete", {"id": outcome_id}))
