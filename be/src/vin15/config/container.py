"""Container DI thủ công: dựng và giữ các thành phần dùng chung. Thành phần chỉ được tạo khi cần (``cached_property``)."""

from __future__ import annotations

from functools import cached_property

from vin15.domain.clock import Clock, business_clock
from vin15.domain.exception import DatabaseUnavailableError
from vin15.domain.pii import PiiRedactor
from vin15.infrastructure.agent_api import AgentApiClient
from vin15.infrastructure.persistence.audit_repository import AuditRepository
from vin15.infrastructure.persistence.chat_repository import ChatRepository
from vin15.infrastructure.persistence.database import Database
from vin15.infrastructure.persistence.internship_repository import InternshipRepository
from vin15.infrastructure.persistence.policy_repository import PolicyRepository
from vin15.infrastructure.persistence.user_repository import UserRepository
from vin15.infrastructure.security.actor_token import ActorTokenService
from vin15.service.agent.agent_subject_resolver import AgentSubjectResolver
from vin15.service.agent.agent_tool_service import AgentToolService
from vin15.service.agent.assistant_limits import AskRateLimiter, ConnectionLimiter
from vin15.service.agent.assistant_orchestrator import AssistantOrchestrator
from vin15.service.agent.conversation_service import ConversationService
from vin15.service.agent.ws_ticket_store import WsTicketStore
from vin15.service.auth.current_user_service import CurrentUserService
from vin15.service.auth.dev_login_service import DevLoginService
from vin15.service.credit.credit_checklist_service import CreditChecklistService
from vin15.service.health_service import HealthService
from vin15.service.internship.internship_read_service import InternshipReadService
from vin15.service.lms.lms_port import FakeLmsAdapter, LmsPort
from vin15.service.policy.policy_ingest_service import PolicyIngestService
from vin15.service.policy.policy_publish_service import PolicyPublishService
from vin15.service.policy.policy_search_service import PolicySearchService

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
        return AgentApiClient(self.settings.agent_api_url, self.settings.agent_api_service_token, self.settings.agent_api_timeout_seconds)

    @cached_property
    def health_service(self) -> HealthService:
        return HealthService(self.database)

    # ---- Dùng chung ----
    @cached_property
    def clock(self) -> Clock:
        """Ngày nghiệp vụ theo ``APP_TIMEZONE`` (Asia/Ho_Chi_Minh): hiệu lực quy định và hạn mốc tính theo đây."""
        return business_clock(self.settings.app_timezone)

    @cached_property
    def pii_redactor(self) -> PiiRedactor:
        return PiiRedactor(self.settings.pii_student_id_pattern)

    def require_database(self) -> Database:
        """Database cho tính năng cần lưu trữ; chưa cấu hình thì 503 (BE vẫn chạy phần không cần DB)."""
        database = self.database
        if database is None:
            raise DatabaseUnavailableError("Chưa cấu hình DATABASE_URL: tính năng này cần database")
        return database

    # ---- Persistence ----
    @cached_property
    def user_repository(self) -> UserRepository:
        return UserRepository(self.require_database())

    @cached_property
    def audit_repository(self) -> AuditRepository:
        return AuditRepository(self.require_database())

    @cached_property
    def policy_repository(self) -> PolicyRepository:
        return PolicyRepository(self.require_database())

    @cached_property
    def chat_repository(self) -> ChatRepository:
        return ChatRepository(self.require_database())

    @cached_property
    def internship_repository(self) -> InternshipRepository:
        return InternshipRepository(self.require_database())

    # ---- Kho quy định ----
    @cached_property
    def policy_search_service(self) -> PolicySearchService:
        return PolicySearchService(self.policy_repository, self.clock, self.settings.policy_no_match_threshold)

    @cached_property
    def policy_ingest_service(self) -> PolicyIngestService:
        return PolicyIngestService(self.policy_repository, self.agent_client)

    @cached_property
    def policy_publish_service(self) -> PolicyPublishService:
        return PolicyPublishService(self.policy_repository, self.clock)

    # ---- Dữ liệu thực tập cho tool cá nhân ----
    @cached_property
    def lms(self) -> LmsPort:
        return FakeLmsAdapter()

    @cached_property
    def internship_read_service(self) -> InternshipReadService:
        return InternshipReadService(self.internship_repository, self.clock)

    @cached_property
    def credit_checklist_service(self) -> CreditChecklistService:
        return CreditChecklistService(
            self.internship_repository, self.lms, self.clock, self.settings.credit_min_weeks, self.settings.credit_min_journal_ratio
        )

    # ---- Agent: tool, chủ thể, hội thoại ----
    @cached_property
    def current_user_service(self) -> CurrentUserService:
        return CurrentUserService(self.token_service, self.user_repository)

    @cached_property
    def dev_login_service(self) -> DevLoginService:
        return DevLoginService(self.user_repository, self.token_service, self.audit_repository)

    @cached_property
    def agent_subject_resolver(self) -> AgentSubjectResolver:
        return AgentSubjectResolver(
            self.settings.agent_api_service_token,
            self.token_service,
            self.user_repository,
            self.audit_repository,
            self.settings.dev_default_user_email,
        )

    @cached_property
    def agent_tool_service(self) -> AgentToolService:
        return AgentToolService(
            self.policy_search_service,
            self.internship_read_service,
            self.credit_checklist_service,
            self.audit_repository,
            self.pii_redactor,
        )

    @cached_property
    def assistant_orchestrator(self) -> AssistantOrchestrator:
        return AssistantOrchestrator(
            self.agent_client,
            self.chat_repository,
            self.audit_repository,
            self.token_service,
            self.pii_redactor,
            self.clock,
            history_turns=self.settings.assistant_history_turns,
            question_max_chars=self.settings.assistant_question_max_chars,
            deadline_seconds=self.settings.agent_turn_seconds + self.settings.assistant_turn_grace_seconds,
        )

    @cached_property
    def conversation_service(self) -> ConversationService:
        return ConversationService(self.chat_repository)

    @cached_property
    def ws_ticket_store(self) -> WsTicketStore:
        return WsTicketStore()

    @cached_property
    def ask_rate_limiter(self) -> AskRateLimiter:
        return AskRateLimiter(self.settings.assistant_ask_per_minute)

    @cached_property
    def connection_limiter(self) -> ConnectionLimiter:
        return ConnectionLimiter(self.settings.assistant_max_connections_per_user)
