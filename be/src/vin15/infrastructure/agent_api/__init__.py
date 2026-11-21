"""Client gọi service ``agent-api``. Đây là **cách duy nhất** BE nói chuyện với agent (HTTP + service token)."""

from .agent_client import AgentApiClient

__all__ = ["AgentApiClient"]
