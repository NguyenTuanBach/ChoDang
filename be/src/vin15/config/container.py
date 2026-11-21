"""Container DI thủ công: dựng và giữ các thành phần dùng chung. Thành phần chỉ được tạo khi cần (``cached_property``)."""

from __future__ import annotations

from functools import cached_property

from vin15.infrastructure.agent_api import AgentApiClient
from vin15.infrastructure.persistence.database import Database
from vin15.infrastructure.security.actor_token import ActorTokenService
from vin15.service.health_service import HealthService

from .settings import Settings


class Container:
    def __init__(self, settings: Settings):
        self.settings = settings

    @cached_property
    def database(self) -> Database | None:
        """``None`` khi chưa cấu hình DATABASE_URL Postgres: BE chạy không DB (health, test)."""
        if not self.settings.has_database:
            return None
        return Database(self.settings.database_url, self.settings.db_pool_min_size, self.settings.db_pool_max_size)

    @cached_property
    def token_service(self) -> ActorTokenService:
        return ActorTokenService(self.settings.jwt_secret, self.settings.jwt_ttl_minutes)

    @cached_property
    def agent_client(self) -> AgentApiClient:
        return AgentApiClient(
            self.settings.agent_api_url, self.settings.agent_api_service_token, self.settings.agent_api_timeout_seconds
        )

    @cached_property
    def health_service(self) -> HealthService:
        return HealthService(self.database)
