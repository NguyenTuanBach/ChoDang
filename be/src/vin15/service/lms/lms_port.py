"""Cổng tới LMS: nghiệp vụ thực tập **chỉ** thấy cổng này. Bản mini nằm trong hệ thống (``infrastructure/lms``); LMS thật của trường
(Moodle, Canvas...) sẽ là một adapter khác chọn bằng ``LMS_ADAPTER``. Sinh viên nhận diện bằng mã sinh viên.
"""

from __future__ import annotations

from typing import Protocol

from vin15.domain.model.lms import PrerequisiteStatus, StudentRecord


class LmsPort(Protocol):
    def prerequisite_status(self, student_code: str | None) -> PrerequisiteStatus:
        """Điều kiện tiên quyết của học phần thực tập (T6)."""
        ...

    def prerequisites_met(self, student_code: str | None) -> bool: ...

    def student_record(self, student_code: str | None) -> StudentRecord | None:
        """Học phần đã học, điểm, tín chỉ tích lũy của sinh viên (D5)."""
        ...

    def post_credit_result(self, student_code: str, course_code: str, credits: int, external_ref: str) -> None:
        """Ghi kết quả quy đổi tín chỉ (D6). Idempotent theo ``external_ref``. Lỗi thì ném ngoại lệ để việc đồng bộ thử lại."""
        ...


class FakeLmsAdapter:
    """Dữ liệu cố định, không gọi mạng: luôn đủ điều kiện tiên quyết. Dùng cho test."""

    def __init__(self) -> None:
        self.posted: list[tuple[str, str, int, str]] = []

    def prerequisite_status(self, student_code: str | None) -> PrerequisiteStatus:
        return PrerequisiteStatus(True)

    def prerequisites_met(self, student_code: str | None) -> bool:
        return True

    def student_record(self, student_code: str | None) -> StudentRecord | None:
        return None

    def post_credit_result(self, student_code: str, course_code: str, credits: int, external_ref: str) -> None:
        self.posted.append((student_code, course_code, credits, external_ref))
