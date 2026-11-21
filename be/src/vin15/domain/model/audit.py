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
