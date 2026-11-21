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
    #: Thời gian tối đa agent dành cho một lượt hỏi (cùng biến với agent). BE chờ thêm ``ASSISTANT_TURN_GRACE_SECONDS``.
    agent_turn_seconds: float = 25.0

    # ---- Trợ lý hỏi đáp chính sách ----
    #: Ngưỡng độ tương đồng vector tối thiểu τ: dưới ngưỡng và không có kết quả từ khóa thì ``no_match``.
    policy_no_match_threshold: float = 0.25
    #: CHỈ DEV: chủ thể của tool agent khi request không có agent-token. ``validate_production()`` từ chối khi đặt ở production.
    agent_dev_default_user_email: str = ""
    assistant_ask_per_minute: int = 10
    assistant_max_connections_per_user: int = 3
    assistant_max_frame_bytes: int = 65536
    #: Số lượt (một lượt = câu hỏi + câu trả lời) gần nhất gửi cho agent làm lịch sử.
    assistant_history_turns: int = 6
    assistant_ws_auth_seconds: float = 5.0
    assistant_question_max_chars: int = 2000
    assistant_turn_grace_seconds: float = 20.0
    #: Regex mã sinh viên để che PII ở lịch sử/audit (trống = không che theo mã). Cùng biến với agent.
    pii_student_id_pattern: str = ""

    # ---- Nghiệp vụ thực tập ----
    #: Địa chỉ FE dùng trong email (liên kết đăng nhập, việc cần làm).
    app_base_url: str = "http://localhost:3000"
    #: Khóa (đợt) thực tập hiện hành: hồ sơ mới của sinh viên thuộc khóa này.
    current_cohort: str = "2026-K1"
    #: Thư mục lưu tệp khi chưa cấu hình R2 (riêng tư, không phục vụ trực tiếp qua HTTP). Trống = ``<repo>/.data/files``.
    storage_local_dir: str = ""
    upload_max_bytes: int = 10 * 1024 * 1024
    #: LMS: ``mini`` (LMS mini trong hệ thống) hoặc adapter khác sau này.
    lms_adapter: str = "mini"
    lms_internship_course_code: str = "TT-101"
    lms_internship_credits: int = 4
    lms_sync_max_attempts: int = 5

    # ---- Job nền (trong tiến trình BE; khóa advisory Postgres chống chạy đôi) ----
    jobs_enabled: bool = True
    jobs_interval_seconds: int = 300
    #: Giờ (múi giờ nghiệp vụ) gửi email tổng hợp hằng ngày cho giảng viên và chạy giám sát.
    daily_digest_hour: int = 7
    monitor_enabled: bool = True
    reminder_window_start_hour: int = 7
    reminder_window_end_hour: int = 21
    reminder_max_per_day: int = 1
    reminder_max_per_milestone: int = 3

    # ---- Ngưỡng điều kiện công nhận tín chỉ (bản mẫu, khớp bộ quy chế mẫu; thay bằng quy chế thật) ----
    credit_min_weeks: int = 8
    credit_min_journal_ratio: float = 0.8

    @property
    def uses_r2(self) -> bool:
        return all(v.strip() for v in (self.r2_endpoint, self.r2_access_key_id, self.r2_secret_access_key, self.r2_bucket))

    @property
    def uses_smtp(self) -> bool:
        return bool(self.smtp_user.strip() and self.smtp_password.strip())

    @property
    def local_storage_path(self) -> Path:
        return Path(self.storage_local_dir) if self.storage_local_dir.strip() else REPOSITORY_ROOT / ".data" / "files"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def admin_email_list(self) -> list[str]:
        return [item.strip().lower() for item in self.app_admin_emails.split(",") if item.strip()]

    @property
    def dev_login_enabled(self) -> bool:
        """Đăng nhập dev (``/api/auth/dev-login``): chỉ có ở môi trường không phải production."""
        return not self.is_production

    @property
    def dev_default_user_email(self) -> str:
        """Email người dùng mặc định cho tool agent; rỗng nếu không đặt hoặc đang ở production (không bao giờ hiệu lực ở production)."""
        return "" if self.is_production else self.agent_dev_default_user_email.strip().lower()

    @property
    def agent_ws_url(self) -> str:
        base = self.agent_api_url.strip().rstrip("/")
        return ("ws" + base[4:] if base.startswith("http") else base) + "/v1/policy-assistant/ws" if base else ""

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
        if self.agent_dev_default_user_email.strip():
            issues.append("AGENT_DEV_DEFAULT_USER_EMAIL chỉ dùng cho dev: phải để trống khi APP_ENV=production")
        return issues


@lru_cache
def get_settings() -> Settings:
    return Settings()
