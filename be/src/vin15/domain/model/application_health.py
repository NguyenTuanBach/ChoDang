from __future__ import annotations

from dataclasses import dataclass, field

UP = "UP"
DOWN = "DOWN"
NOT_CONFIGURED = "NOT_CONFIGURED"


@dataclass(frozen=True)
class ApplicationHealth:
    status: str
    components: dict[str, str] = field(default_factory=dict)
