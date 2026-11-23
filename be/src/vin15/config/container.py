"""Container DI thủ công: dựng và giữ các thành phần dùng chung. Thành phần chỉ được tạo khi cần (``cached_property``)."""

from __future__ import annotations

from functools import cached_property

from vin15.domain.clock import Clock, business_clock
from vin15.domain.exception import DatabaseUnavailableError
from vin15.domain.pii import PiiRedactor
from vin15.domain.ports import FileStorage, Mailer
from vin15.infrastructure.agent_api import AgentApiClient
from vin15.infrastructure.lms import MiniLmsAdapter, MiniLmsAdmin
from vin15.infrastructure.mail import LogMailer, SmtpMailer
from vin15.infrastructure.oauth import GoogleOAuthClient
from vin15.infrastructure.persistence.audit_repository import AuditRepository
from vin15.infrastructure.persistence.case_repository import CaseRepository
from vin15.infrastructure.persistence.chat_repository import ChatRepository
from vin15.infrastructure.persistence.config_repository import ConfigRepository
from vin15.infrastructure.persistence.database import Database
from vin15.infrastructure.persistence.internship_repository import InternshipRepository
from vin15.infrastructure.persistence.monitoring_repository import MonitoringRepository
from vin15.infrastructure.persistence.notification_repository import NotificationRepository
from vin15.infrastructure.persistence.policy_repository import PolicyRepository
from vin15.infrastructure.persistence.report_repository import ReportRepository
from vin15.infrastructure.persistence.request_repository import RequestRepository
from vin15.infrastructure.persistence.user_repository import UserRepository
from vin15.infrastructure.security.actor_token import ActorTokenService
from vin15.infrastructure.storage import LocalFileStorage, R2FileStorage
from vin15.service.agent.agent_staff_reads import AgentStaffReads
from vin15.service.agent.agent_subject_resolver import AgentSubjectResolver
from vin15.service.agent.agent_tool_service import AgentToolService
from vin15.service.agent.assistant_limits import AskRateLimiter, ConnectionLimiter
from vin15.service.agent.assistant_orchestrator import AssistantOrchestrator
from vin15.service.agent.conversation_service import ConversationService
from vin15.service.agent.ws_ticket_store import WsTicketStore
from vin15.service.auth.account_activation_service import AccountActivationService
from vin15.service.auth.current_user_service import CurrentUserService
from vin15.service.auth.dev_login_service import DevLoginService
from vin15.service.auth.google_login_service import GoogleLoginService
from vin15.service.credit.credit_checklist_service import CreditChecklistService
from vin15.service.credit.credit_decision_service import CreditDecisionService
from vin15.service.dashboard.report_service import ReportService
from vin15.service.exception.request_service import RequestService
from vin15.service.health_service import HealthService
from vin15.service.internship.config_service import ConfigService
from vin15.service.internship.intake_service import IntakeService
from vin15.service.internship.internship_read_service import InternshipReadService
from vin15.service.internship.internship_service import InternshipService
from vin15.service.jobs.scheduler import JobRunner
from vin15.service.lms.lms_admin_service import LmsAdminService
from vin15.service.lms.lms_port import LmsPort
from vin15.service.lms.lms_sync_service import LmsSyncService
from vin15.service.milestone.milestone_service import MilestoneService
from vin15.service.monitoring.monitoring_service import MonitoringService
from vin15.service.monitoring.pre_review_service import PreReviewService
from vin15.service.notification.notification_service import NotificationService
from vin15.service.outline.outline_service import OutlineService
from vin15.service.policy.policy_ingest_service import PolicyIngestService
from vin15.service.policy.policy_publish_service import PolicyPublishService
from vin15.service.policy.policy_search_service import PolicySearchService
from vin15.service.user.account_service import AccountService

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
        """Cổng LMS: ``LMS_ADAPTER=mini`` là LMS mini trong hệ thống. Thêm adapter LMS thật ở đây khi tích hợp."""
        if self.settings.lms_adapter != "mini":
            raise ValueError(f"LMS_ADAPTER không được hỗ trợ: {self.settings.lms_adapter}")
        return MiniLmsAdapter(self.require_database(), self.settings.lms_internship_course_code)

    @cached_property
    def internship_read_service(self) -> InternshipReadService:
        return InternshipReadService(self.internship_repository, self.clock)

    def _student_code_of(self, user_id: int) -> str | None:
        user = self.user_repository.find_by_id(user_id)
        return user.student_code if user else None

    @cached_property
    def credit_checklist_service(self) -> CreditChecklistService:
        return CreditChecklistService(
            self.internship_repository,
            self.lms,
            self.clock,
            self.settings.credit_min_weeks,
            self.settings.credit_min_journal_ratio,
            self._student_code_of,
        )

    # ---- Hạ tầng dùng chung: tệp, mail, thông báo ----
    @cached_property
    def file_storage(self) -> FileStorage:
        s = self.settings
        if s.uses_r2:
            return R2FileStorage(s.r2_endpoint, s.r2_access_key_id, s.r2_secret_access_key, s.r2_bucket)
        return LocalFileStorage(s.local_storage_path)

    @cached_property
    def mailer(self) -> Mailer:
        s = self.settings
        if s.uses_smtp:
            return SmtpMailer(s.smtp_host, s.smtp_port, s.smtp_user, s.smtp_password, s.smtp_from)
        return LogMailer()

    @cached_property
    def notification_repository(self) -> NotificationRepository:
        return NotificationRepository(self.require_database())

    @cached_property
    def notification_service(self) -> NotificationService:
        return NotificationService(self.notification_repository, self.mailer, self.settings.app_base_url, self.clock)

    # ---- Nghiệp vụ thực tập: persistence ----
    @cached_property
    def case_repository(self) -> CaseRepository:
        return CaseRepository(self.require_database())

    @cached_property
    def request_repository(self) -> RequestRepository:
        return RequestRepository(self.require_database())

    @cached_property
    def config_repository(self) -> ConfigRepository:
        return ConfigRepository(self.require_database())

    @cached_property
    def report_repository(self) -> ReportRepository:
        return ReportRepository(self.require_database())

    @cached_property
    def monitoring_repository(self) -> MonitoringRepository:
        return MonitoringRepository(self.require_database())

    @cached_property
    def mini_lms_admin(self) -> MiniLmsAdmin:
        return MiniLmsAdmin(self.require_database())

    # ---- Nghiệp vụ thực tập: service ----
    @cached_property
    def account_activation_service(self) -> AccountActivationService:
        return AccountActivationService(self.user_repository)

    @cached_property
    def google_client(self) -> GoogleOAuthClient:
        s = self.settings
        return GoogleOAuthClient(s.google_client_id, s.google_client_secret, s.google_redirect_uri)

    @cached_property
    def google_login_service(self) -> GoogleLoginService:
        return GoogleLoginService(self.google_client, self.account_activation_service, self.token_service, self.audit_repository)

    @cached_property
    def account_service(self) -> AccountService:
        return AccountService(self.user_repository, self.notification_service)

    @cached_property
    def internship_service(self) -> InternshipService:
        s = self.settings
        return InternshipService(
            self.case_repository,
            self.user_repository,
            self.config_repository,
            self.policy_search_service,
            self.notification_service,
            self.file_storage,
            self.clock,
            cohort=s.current_cohort,
            min_weeks=s.credit_min_weeks,
            upload_max_bytes=s.upload_max_bytes,
        )

    @cached_property
    def config_service(self) -> ConfigService:
        return ConfigService(self.config_repository)

    @cached_property
    def intake_service(self) -> IntakeService:
        return IntakeService(self.case_repository, self.file_storage, self.agent_client, self.internship_service, self.milestone_service)

    @cached_property
    def outline_service(self) -> OutlineService:
        return OutlineService(self.case_repository, self.config_repository, self.notification_service)

    @cached_property
    def milestone_service(self) -> MilestoneService:
        return MilestoneService(self.case_repository, self.notification_service, self.file_storage, self.clock, self.settings.upload_max_bytes)

    @cached_property
    def request_service(self) -> RequestService:
        return RequestService(
            self.request_repository,
            self.case_repository,
            self.user_repository,
            self.notification_service,
            self.file_storage,
            self.clock,
            self.settings.upload_max_bytes,
        )

    @cached_property
    def credit_decision_service(self) -> CreditDecisionService:
        s = self.settings
        return CreditDecisionService(
            self.case_repository,
            self.request_repository,
            self.user_repository,
            self.credit_checklist_service,
            self.notification_service,
            s.lms_internship_course_code,
            s.lms_internship_credits,
        )

    @cached_property
    def report_service(self) -> ReportService:
        return ReportService(
            self.report_repository,
            self.case_repository,
            self.request_repository,
            self.monitoring_repository,
            self.milestone_service,
            self.credit_decision_service,
            self.clock,
        )

    @cached_property
    def lms_admin_service(self) -> LmsAdminService:
        return LmsAdminService(self.mini_lms_admin, self.audit_repository)

    @cached_property
    def lms_sync_service(self) -> LmsSyncService:
        return LmsSyncService(
            self.request_repository, self.lms, self.user_repository, self.notification_service, self.settings.lms_sync_max_attempts
        )

    @cached_property
    def monitoring_service(self) -> MonitoringService:
        s = self.settings
        return MonitoringService(
            self.monitoring_repository,
            self.case_repository,
            self.credit_checklist_service,
            self.notification_service,
            self.agent_client,
            self.pii_redactor,
            timezone=s.app_timezone,
            window=(s.reminder_window_start_hour, s.reminder_window_end_hour),
            max_per_day=s.reminder_max_per_day,
            max_per_milestone=s.reminder_max_per_milestone,
            outcomes_of=self.config_repository.learning_outcomes,
        )

    @cached_property
    def pre_review_service(self) -> PreReviewService:
        return PreReviewService(self.case_repository, self.config_repository, self.monitoring_repository, self.agent_client, self.pii_redactor)

    @cached_property
    def job_runner(self) -> JobRunner:
        s = self.settings
        return JobRunner(
            self.require_database(),
            self.notification_repository,
            self.milestone_service,
            self.notification_service,
            self.lms_sync_service,
            self.monitoring_service,
            self.user_repository,
            self.report_repository,
            timezone=s.app_timezone,
            interval_seconds=s.jobs_interval_seconds,
            digest_hour=s.daily_digest_hour,
            monitor_enabled=s.monitor_enabled,
        )

    # ---- Agent: tool, chủ thể, hội thoại ----
    @cached_property
    def current_user_service(self) -> CurrentUserService:
        return CurrentUserService(self.token_service, self.user_repository)

    @cached_property
    def dev_login_service(self) -> DevLoginService:
        return DevLoginService(self.user_repository, self.token_service, self.audit_repository, self.account_activation_service)

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
            lambda: self.agent_staff_reads,
        )

    @cached_property
    def agent_staff_reads(self) -> AgentStaffReads:
        return AgentStaffReads(self.user_repository, self.report_service, self.monitoring_service)

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
