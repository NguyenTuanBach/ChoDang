"""Bảng cạnh của từng thực thể (docs/nghiep-vu-thuc-tap.md mục 6.1 và 6.2)."""

from __future__ import annotations

from vin15.domain.model.user import Role

from .machine import Edge, StateMachine

S, L, A = Role.STUDENT, Role.LECTURER, Role.ADMIN

INTERNSHIP = StateMachine(
    "internship",
    [
        Edge("draft", "submitted", (S,)),
        Edge("revision_requested", "submitted", (S,)),
        Edge("submitted", "confirmed", (L,)),
        Edge("submitted", "revision_requested", (L,), needs_reason=True),
        Edge("submitted", "rejected", (L,), needs_reason=True),
        # Đề cương bị từ chối thì kết thúc đợt thực tập (mục 5.1).
        Edge("confirmed", "rejected", (L,), needs_reason=True),
        Edge("confirmed", "in_progress", (L,)),
        Edge("in_progress", "pending_credit", (S,)),
        Edge("pending_credit", "in_progress", (L,), needs_reason=True),
        Edge("pending_credit", "credit_review", (L,)),
        Edge("credit_review", "completed", (A,)),
        Edge("credit_review", "closed_no_credit", (A,), needs_reason=True),
    ],
)

OUTLINE = StateMachine(
    "outline",
    [
        Edge("submitted", "approved", (L,)),
        Edge("submitted", "revision_requested", (L,), needs_reason=True),
        Edge("submitted", "rejected", (L,), needs_reason=True),
    ],
)

MILESTONE = StateMachine(
    "milestone",
    [
        Edge("pending", "submitted", (S,)),
        Edge("rejected", "submitted", (S,)),
        Edge("overdue", "submitted", (S,)),
        Edge("submitted", "accepted", (L,)),
        Edge("submitted", "rejected", (L,), needs_reason=True),
        # Hệ thống đánh dấu quá hạn (mục 6.2).
        Edge("pending", "overdue", system=True),
        Edge("rejected", "overdue", system=True),
        # Gia hạn được duyệt thì mốc quay lại chờ nộp.
        Edge("overdue", "pending", (L, A)),
        # M2 "đề cương được duyệt" đạt ngay khi giảng viên duyệt đề cương (hệ quả của quyết định đó).
        Edge("pending", "accepted", (L,)),
        Edge("overdue", "accepted", (L,)),
    ],
)


def _request_edges(decider: Role) -> list[Edge]:
    return [
        Edge("open", "approved", (decider,)),
        Edge("open", "rejected", (decider,), needs_reason=True),
        Edge("open", "cancelled", (S,)),
    ]


#: Gia hạn mốc và ngoại lệ loại thường do GV duyệt; ngoại lệ ảnh hưởng tín chỉ do QTV duyệt (D13).
REQUEST_LECTURER = StateMachine("request", _request_edges(L))
REQUEST_ADMIN = StateMachine("request", _request_edges(A))

#: Cờ rủi ro: agent chỉ tạo (tạo không phải chuyển trạng thái), người xử lý.
RISK_FLAG = StateMachine(
    "risk_flag",
    [
        Edge("open", "acknowledged", (L, A)),
        Edge("open", "resolved", (L, A)),
        Edge("acknowledged", "resolved", (L, A)),
        Edge("open", "dismissed", (L, A), needs_reason=True),
        Edge("acknowledged", "dismissed", (L, A), needs_reason=True),
    ],
)

#: Công nhận tín chỉ: GV thẩm định (``pending_credit`` → ``credit_review``) nằm ở INTERNSHIP; bản ghi thẩm định có máy riêng.
CREDIT_REQUEST = StateMachine(
    "credit_assessment",
    [
        Edge("pending", "lecturer_passed", (L,)),
        Edge("pending", "lecturer_returned", (L,), needs_reason=True),
        Edge("lecturer_passed", "approved", (A,)),
        Edge("lecturer_passed", "denied", (A,), needs_reason=True),
    ],
)


def request_machine(affects_credit: bool) -> StateMachine:
    return REQUEST_ADMIN if affects_credit else REQUEST_LECTURER
