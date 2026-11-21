"""Cấu hình ứng dụng, đọc từ biến môi trường và file `.env` ở gốc repo. Một đối tượng :class:`Settings` bất biến được dựng khi khởi động.

``APP_ENV=production`` bật kiểm tra lúc khởi động (secret, CORS, database, token nội bộ).
BE không giữ khóa LLM: mọi cuộc gọi LLM do service ``agent`` thực hiện.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict

#: Gốc repo (``be/src/vin15/config`` → ``.``), nơi đặt `.env`.
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]

_LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})
_DEV_JWT_SECRET = "dev-only-change-me"
_DEV_AGENT_TOKEN = "agent-api-local-only"


def _origin_is_local_or_insecure(origin: str) -> bool:
    if origin == "*":
        return True
    try:
        parts = urlsplit(origin)
    except ValueError:
        return True
    host = (parts.hostname or "").lower().rstrip(".")
    return host in _LOCAL_HOSTNAMES or host.endswith(".localhost") or parts.scheme.lower() != "https"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPOSITORY_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
        frozen=True,
    )

    # ---- Ứng dụng ----
    app_name: str = "VIN-15 Backend"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    #: Múi giờ nghiệp vụ: hạn nộp, giờ chạy job tính theo múi giờ này.
    app_timezone: str = "Asia/Ho_Chi_Minh"
    log_level: str = "INFO"

    # ---- Database (Supabase Postgres) ----
    #: Chuỗi kết nối Postgres. Trống hoặc không phải ``postgresql://`` thì BE chạy không DB (chỉ health, test).
    database_url: str = ""
    db_pool_min_size: int = 1
    db_pool_max_size: int = 5
    #: Tự áp migration ``resources/db/migration/V*.sql`` khi khởi động.
    migrations_enabled: bool = True

    # ---- Xác thực ----
    jwt_secret: str = _DEV_JWT_SECRET
    jwt_ttl_minutes: int = 480
    #: Danh sách email quản trị viên khởi tạo (cách nhau bằng dấu phẩy). QTV mời GV, GV mời SV.
    app_admin_emails: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    # ---- Email (Gmail SMTP, dùng App Password) ----
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # ---- Lưu tệp minh chứng (Cloudflare R2, tương thích S3) ----
    r2_endpoint: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""

    # ---- Service agent (chạy riêng, cổng riêng) ----
    #: URL nội bộ của agent-api. Trống thì BE chạy không có agent.
    agent_api_url: str = ""
    agent_api_service_token: str = _DEV_AGENT_TOKEN
    agent_api_timeout_seconds: float = 10.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def admin_email_list(self) -> list[str]:
        return [item.strip().lower() for item in self.app_admin_emails.split(",") if item.strip()]

    @property
    def has_database(self) -> bool:
        return self.database_url.strip().lower().startswith(("postgresql://", "postgres://"))

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    def validate_production(self) -> list[str]:
        """Danh sách vấn đề cấu hình khi ``APP_ENV=production``; rỗng nếu không phải production hoặc đã hợp lệ."""
        if not self.is_production:
            return []
        issues: list[str] = []
        if self.jwt_secret == _DEV_JWT_SECRET or len(self.jwt_secret) < 32:
            issues.append("JWT_SECRET phải đổi khỏi giá trị mặc định và dài ít nhất 32 ký tự")
        if not self.has_database:
            issues.append("DATABASE_URL phải là chuỗi kết nối Postgres (Supabase)")
        if any(_origin_is_local_or_insecure(origin) for origin in self.cors_origin_list):
            issues.append("CORS_ORIGINS phải là các origin https:// thật, không dùng * hay localhost")
        if self.agent_api_url and self.agent_api_service_token == _DEV_AGENT_TOKEN:
            issues.append("AGENT_API_SERVICE_TOKEN phải đổi khỏi giá trị mặc định")
        if not self.admin_email_list:
            issues.append("APP_ADMIN_EMAILS phải có ít nhất một email quản trị viên khởi tạo")
        return issues


@lru_cache
def get_settings() -> Settings:
    return Settings()
