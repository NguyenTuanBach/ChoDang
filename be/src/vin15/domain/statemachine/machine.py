"""Cỗ máy trạng thái khai báo theo bảng cạnh. Một cổng duy nhất: :meth:`StateMachine.transition`.

Quy tắc (docs/nghiep-vu-thuc-tap.md mục 6.3):

- BR-S1: cạnh chỉ đi được khi actor là **người** đúng vai trò **và** đúng phạm vi (SV chủ hồ sơ, GV phụ trách, QTV).
  Agent không bao giờ đi được. ``system`` chỉ đi được cạnh khai báo ``system=True`` (hệ thống đánh dấu quá hạn).
- BR-S2: cạnh ``needs_reason`` bắt buộc có lý do.
- BR-S3: mỗi lần chuyển trả về một :class:`AuditEntry` để service ghi cùng transaction với thay đổi dữ liệu.
"""

from __future__ import annotations

from dataclasses import dataclass

from vin15.domain.exception import ForbiddenRoleError, PermissionDeniedError, ReasonRequiredError, ScopeDeniedError, StateConflictError
from vin15.domain.model.audit import Actor, ActorKind, AuditEntry
from vin15.domain.model.user import Role


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    roles: tuple[Role, ...] = ()
    needs_reason: bool = False
    #: Hệ thống (job nền) được đi cạnh này. Không bao giờ áp dụng cho agent.
    system: bool = False


@dataclass(frozen=True)
class Subject:
    """Ngữ cảnh kiểm phạm vi: chủ hồ sơ (sinh viên) và giảng viên phụ trách."""

    owner_id: int | None = None
    lecturer_id: int | None = None


@dataclass(frozen=True)
class Transition:
    entity: str
    source: str
    target: str
    reason: str


class StateMachine:
    def __init__(self, entity: str, edges: list[Edge]):
        self.entity = entity
        self._edges = {(e.source, e.target): e for e in edges}

    def targets(self, source: str) -> list[str]:
        return [t for (s, t) in self._edges if s == source]

    def can_reach(self, source: str, target: str) -> bool:
        return (source, target) in self._edges

    def transition(
        self, source: str, target: str, actor: Actor, subject: Subject | None = None, reason: str | None = None
    ) -> Transition:
        edge = self._edges.get((source, target))
        if edge is None:
            raise StateConflictError(f"Không thể chuyển {self.entity} từ '{source}' sang '{target}'")
        self._authorize(edge, actor, subject or Subject())
        text = (reason or "").strip()
        if edge.needs_reason and not text:
            raise ReasonRequiredError("Cần nhập lý do cho quyết định này")
        return Transition(self.entity, source, target, text)

    def _authorize(self, edge: Edge, actor: Actor, subject: Subject) -> None:
        if actor.kind == ActorKind.AGENT:
            raise PermissionDeniedError("Tác tử AI không được đổi trạng thái nghiệp vụ")
        if actor.kind == ActorKind.SYSTEM:
            if not edge.system:
                raise PermissionDeniedError("Hệ thống không được thực hiện cạnh quyết định này")
            return
        try:
            role = Role(actor.role)
        except ValueError as error:
            raise ForbiddenRoleError("Vai trò không hợp lệ") from error
        if role not in edge.roles:
            raise ForbiddenRoleError("Vai trò của bạn không được thực hiện bước này")
        if role == Role.STUDENT and (actor.id is None or actor.id != subject.owner_id):
            raise ScopeDeniedError("Chỉ chủ hồ sơ được thực hiện bước này")
        if role == Role.LECTURER and (actor.id is None or actor.id != subject.lecturer_id):
            raise ScopeDeniedError("Chỉ giảng viên phụ trách được thực hiện bước này")

    def audit(self, transition: Transition, actor: Actor, entity_id: int, *, extra: dict | None = None) -> AuditEntry:
        """Bản ghi audit cho một lần chuyển (BR-S3): ai, vai trò, trước/sau, lý do."""
        after = {"status": transition.target, **(extra or {})}
        return AuditEntry(
            actor_kind=actor.kind,
            actor_id=actor.id,
            actor_role=actor.role,
            entity=self.entity,
            entity_id=entity_id,
            action=f"{transition.source}->{transition.target}",
            before={"status": transition.source},
            after=after,
            reason=transition.reason,
        )
