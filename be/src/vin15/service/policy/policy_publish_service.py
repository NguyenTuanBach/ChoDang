"""Xuất bản phiên bản văn bản quy định (HITL của quản trị viên cho nội dung quy định)."""

from __future__ import annotations

import anyio.to_thread

from vin15.domain.clock import Clock
from vin15.domain.model.policy import PolicyChunk, PolicyVersion
from vin15.infrastructure.persistence.policy_repository import PolicyRepository


class PolicyPublishService:
    def __init__(self, repository: PolicyRepository, clock: Clock):
        self._repo = repository
        self._clock = clock

    def publish(self, version_id: int, actor_id: int, actor_role: str = "admin") -> PolicyVersion:
        """Đóng ``effective_to`` bản cũ cùng văn bản, đánh dấu ``superseded`` khi đã hết hiệu lực, ghi audit. Đồng bộ (chạy trong thread)."""
        return self._repo.publish_version(version_id, actor_id, self._clock(), actor_role=actor_role)

    async def publish_async(self, version_id: int, actor_id: int, actor_role: str = "admin") -> PolicyVersion:
        return await anyio.to_thread.run_sync(lambda: self.publish(version_id, actor_id, actor_role))

    def preview(self, version_id: int) -> tuple[PolicyVersion, list[PolicyChunk]] | None:
        version = self._repo.get_version(version_id)
        return (version, self._repo.list_chunks(version_id)) if version else None

    def list_versions(self) -> list[PolicyVersion]:
        return self._repo.list_versions()
