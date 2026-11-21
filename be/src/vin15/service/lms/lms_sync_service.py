"""Đồng bộ kết quả quy đổi tín chỉ sang LMS (D6). Việc được tạo cùng transaction với phê duyệt của QTV; worker gửi, thử lại có backoff,
báo QTV khi thất bại hẳn. Chỉ ghi LMS **sau** phê duyệt: không có đường nào khác tạo việc này.
"""

from __future__ import annotations

import logging

from vin15.infrastructure.persistence.request_repository import RequestRepository
from vin15.infrastructure.persistence.user_repository import UserRepository
from vin15.service.lms.lms_port import LmsPort
from vin15.service.notification.notification_service import NotificationService

log = logging.getLogger(__name__)


class LmsSyncService:
    def __init__(self, requests: RequestRepository, lms: LmsPort, users: UserRepository, notifications: NotificationService, max_attempts: int):
        self._requests = requests
        self._lms = lms
        self._users = users
        self._notifications = notifications
        self._max_attempts = max_attempts

    def jobs(self, status: str | None = None) -> list[dict]:
        return self._requests.sync_jobs(status)

    def retry(self, job_id: int) -> None:
        self._requests.retry_sync(job_id)

    def run_due(self) -> int:
        """Gửi các việc đến hạn; trả về số việc đồng bộ thành công."""
        done = 0
        for job in self._requests.due_sync_jobs():
            ref = f"internship-{job['internship_id']}"
            try:
                self._lms.post_credit_result(job["student_code"], job["course_code"], job["credits"], ref)
            except Exception as error:
                failed = self._requests.mark_sync(job["id"], False, f"{type(error).__name__}: {error}", self._max_attempts)
                log.warning("Đồng bộ LMS lỗi (việc %s): %s", job["id"], error)
                if failed:
                    self._notifications.notify_many(
                        self._users.admin_ids(),
                        "Đồng bộ LMS thất bại",
                        f"Không ghi được kết quả tín chỉ cho sinh viên {job['student_code']}: {error}",
                        kind="lms_sync_failed",
                        link="/admin/lms",
                    )
            else:
                self._requests.mark_sync(job["id"], True, "", self._max_attempts)
                done += 1
        return done
