from __future__ import annotations

from pydantic import BaseModel

from vin15.domain.model.application_health import ApplicationHealth


class HealthResponse(BaseModel):
    status: str
    components: dict[str, str] = {}

    @classmethod
    def of(cls, health: ApplicationHealth) -> HealthResponse:
        return cls(status=health.status, components=dict(health.components))
