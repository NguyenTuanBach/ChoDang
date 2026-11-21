"""Job nền trong tiến trình BE: đánh dấu mốc quá hạn, gửi email đang chờ, đồng bộ LMS, giám sát và email tổng hợp hằng ngày.

Khóa advisory Postgres (giữ suốt một nhịp) bảo đảm chỉ một tiến trình chạy job tại một thời điểm. Job theo ngày ghi ``job_state``
để không chạy lặp. Lỗi của một bước không làm dừng các bước khác hay vòng lặp.
"""

from __future__ import annotations

import logging
from contextlib import ExitStack
from datetime import datetime
from zoneinfo import ZoneInfo

import anyio
import anyio.to_thread

from vin15.infrastructure.persistence.database import Database
from vin15.infrastructure.persistence.notification_repository import NotificationRepository
from vin15.infrastructure.persistence.report_repository import ReportRepository
from vin15.infrastructure.persistence.user_repository import UserRepository
from vin15.service.lms.lms_sync_service import LmsSyncService
from vin15.service.milestone.milestone_service import MilestoneService
from vin15.service.monitoring.monitoring_service import MonitoringService
from vin15.service.notification.notification_service import NotificationService

log = logging.getLogger(__name__)

_LOCK_KEY = 8_015_002
DAILY_JOB = "daily_monitor"


class JobRunner:
    def __init__(
        self,
        database: Database,
        state: NotificationRepository,
        milestones: MilestoneService,
        notifications: NotificationService,
        lms_sync: LmsSyncService,
        monitoring: MonitoringService,
        users: UserRepository,
        reports: ReportRepository,
        *,
        timezone: str,
        interval_seconds: int,
        digest_hour: int,
        monitor_enabled: bool,
    ):
        self._db = database
        self._state = state
        self._milestones = milestones
        self._notifications = notifications
        self._lms_sync = lms_sync
        self._monitoring = monitoring
        self._users = users
        self._reports = reports
        self._zone = ZoneInfo(timezone)
        self._interval = interval_seconds
        self._digest_hour = digest_hour
        self._monitor_enabled = monitor_enabled

    async def run_forever(self) -> None:
        await anyio.sleep(5)  # để ứng dụng khởi động xong
        while True:
            try:
                await self.tick()
            except Exception:
                log.exception("Nhịp job nền lỗi")
            await anyio.sleep(self._interval)

    async def tick(self, now: datetime | None = None) -> dict:
        """Một nhịp. Trả về thống kê; ``{"skipped": True}`` nếu tiến trình khác đang giữ khóa."""
        stack = ExitStack()
        conn = stack.enter_context(self._db.connection())
        try:
            got = await anyio.to_thread.run_sync(lambda: conn.execute("select pg_try_advisory_lock(%s) as ok", (_LOCK_KEY,)).fetchone()["ok"])
            if not got:
                return {"skipped": True}
            try:
                return await self._steps(now or datetime.now(self._zone))
            finally:
                await anyio.to_thread.run_sync(lambda: conn.execute("select pg_advisory_unlock(%s)", (_LOCK_KEY,)))
        finally:
            stack.close()

    async def _steps(self, now: datetime) -> dict:
        stats: dict = {}
        stats["overdue"] = await self._safe("mark_overdue", self._milestones.mark_overdue)
        stats["emails"] = await self._safe("flush_outbox", self._notifications.flush_outbox)
        stats["lms_sync"] = await self._safe("lms_sync", self._lms_sync.run_due)
        today = now.astimezone(self._zone).date()
        due_daily = now.astimezone(self._zone).hour >= self._digest_hour and await anyio.to_thread.run_sync(self._state.last_run_on, DAILY_JOB) != today
        event = bool(stats["overdue"])  # có mốc vừa quá hạn: quét ngay (C1: theo sự kiện)
        if self._monitor_enabled and (due_daily or event):
            try:
                stats["monitor"] = await self._monitoring.scan(now)
            except Exception:
                log.exception("Quét giám sát lỗi")
        if due_daily:
            lecturers = await anyio.to_thread.run_sync(self._users.lecturer_ids)
            stats["digests"] = await self._safe("digest", lambda: self._monitoring.daily_digest(lecturers, lambda lid: self._reports.queue_items("lecturer", lid)))
            await anyio.to_thread.run_sync(self._state.set_run_on, DAILY_JOB, today, "ok")
        return stats

    @staticmethod
    async def _safe(name: str, fn):
        try:
            return await anyio.to_thread.run_sync(fn)
        except Exception:
            log.exception("Bước job '%s' lỗi", name)
            return None
