from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ActorKind(StrEnum):
    HUMAN = "human"
    SYSTEM = "system"
    #: Tác tử AI. Không bao giờ được thực hiện cạnh quyết định (xem statemachine/README.md).
    AGENT = "agent"


@dataclass(frozen=True)
class Actor:
    kind: ActorKind
    id: int | None = None
    role: str = ""


@dataclass(frozen=True)
class AuditEntry:
    """Một bản ghi nhật ký kiểm toán (chỉ-thêm). ``after`` là dữ liệu đã che PII."""

    actor_kind: ActorKind
    entity: str
    action: str
    actor_id: int | None = None
    actor_role: str = ""
    entity_id: int | None = None
    before: dict | None = None
    after: dict | None = None
    reason: str = ""
