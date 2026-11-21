"""State machine nghiệp vụ: cổng duy nhất để đổi trạng thái (docs/nghiep-vu-thuc-tap.md mục 6)."""

from .definitions import (
    CREDIT_REQUEST,
    INTERNSHIP,
    MILESTONE,
    OUTLINE,
    REQUEST_ADMIN,
    REQUEST_LECTURER,
    RISK_FLAG,
    request_machine,
)
from .machine import Edge, StateMachine, Subject, Transition

__all__ = [
    "CREDIT_REQUEST",
    "INTERNSHIP",
    "MILESTONE",
    "OUTLINE",
    "REQUEST_ADMIN",
    "REQUEST_LECTURER",
    "RISK_FLAG",
    "Edge",
    "StateMachine",
    "Subject",
    "Transition",
    "request_machine",
]
