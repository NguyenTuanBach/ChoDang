"""Cấu hình của agent-api, đọc từ biến môi trường và `.env` ở gốc repo."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

#: Gốc repo (``agent/src/vin15_agent/shared`` → ``.``).
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_DEV_TOKEN = "agent-api-local-only"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPOSITORY_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        frozen=True,
    )

    app_env: str = "development"
    agent_api_host: str = "0.0.0.0"
    agent_api_port: int = 8100
    #: Token BE phải gửi (``Authorization: Bearer``). Phải khớp ``AGENT_API_SERVICE_TOKEN`` bên BE.
    agent_api_service_token: str = _DEV_TOKEN
    log_level: str = "INFO"

    def validate_production(self) -> list[str]:
        if self.app_env.strip().lower() != "production":
            return []
        issues = []
        if self.agent_api_service_token == _DEV_TOKEN or len(self.agent_api_service_token) < 16:
            issues.append("AGENT_API_SERVICE_TOKEN phải đổi khỏi giá trị mặc định và dài ít nhất 16 ký tự")
        return issues


@lru_cache
def get_settings() -> Settings:
    return Settings()
