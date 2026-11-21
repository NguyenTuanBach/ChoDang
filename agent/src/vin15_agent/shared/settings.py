"""Cấu hình của agent-api, đọc từ biến môi trường và `.env` ở gốc repo."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
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

    # ---- LLM chính: gọi thẳng OpenAI (``openai_base_url`` trống = api.openai.com) ----
    openai_api_key: SecretStr = SecretStr("")
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.7
    openai_max_tokens: int = 2048
    openai_timeout_seconds: float = 30.0
    # ---- LLM dự phòng: proxy ``AiClient`` (tương thích OpenAI). Trống ``aiclient_base_url`` = tắt dự phòng ----
    aiclient_base_url: str = ""
    aiclient_api_key: SecretStr = SecretStr("")
    aiclient_model: str = ""
    #: Khả năng đường dự phòng hỗ trợ ngoài chat thường, cách nhau bằng dấu phẩy (tools, stream, embed). Trống = chỉ chat.
    aiclient_capabilities: str = ""

    # ---- Trợ lý hỏi đáp chính sách ----
    openai_embedding_model: str = "text-embedding-3-small"
    #: Nhiệt độ riêng của trợ lý (thấp để bám nguồn); model suy luận sẽ bỏ qua.
    assistant_temperature: float = 0.2
    agent_max_rounds: int = 6
    agent_max_tool_calls: int = 8
    agent_turn_seconds: float = 25.0
    #: Thời gian tối đa cho một lời gọi tool tới BE.
    agent_tool_timeout_seconds: float = 8.0
    #: Số lượt đang chạy đồng thời tối đa trên một tiến trình agent; vượt thì trả ``error: busy``.
    assistant_max_concurrent_turns: int = 50
    #: Địa chỉ BE để agent gọi ``/api/agent-tools/*`` (cùng service token với chiều BE → agent).
    be_api_url: str = "http://localhost:8000"
    #: Regex mã sinh viên để che PII (trống = không che theo mã).
    pii_student_id_pattern: str = ""
    school_name: str = "Trường"
    #: Thêm cảnh báo "quy chế hiện là văn bản mẫu" vào prompt (R1: chưa có quy chế thật).
    assistant_sample_notice: bool = True
    #: Thư mục prompt; trống = tự tìm (``agent/prompts`` trong repo, hoặc ``./prompts``).
    agent_prompts_dir: str = ""

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
