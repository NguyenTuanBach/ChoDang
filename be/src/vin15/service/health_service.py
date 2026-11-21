from __future__ import annotations

from vin15.domain.model.application_health import DOWN, NOT_CONFIGURED, UP, ApplicationHealth
from vin15.infrastructure.persistence.database import Database


class HealthService:
    def __init__(self, database: Database | None):
        self._database = database

    def get_health(self) -> ApplicationHealth:
        """Liveness: tiến trình còn sống."""
        return ApplicationHealth(UP)

    def get_readiness(self) -> ApplicationHealth:
        """Readiness: kiểm tra cả kết nối database. Chưa cấu hình DB thì vẫn sẵn sàng (chế độ không DB)."""
        if self._database is None:
            return ApplicationHealth(UP, {"database": NOT_CONFIGURED})
        up = self._database.ping()
        return ApplicationHealth(UP if up else DOWN, {"database": UP if up else DOWN})
