"""Gia hạn mốc và ngoại lệ (D1-D3). SV tạo; người duyệt do loại quyết định: GV duyệt loại thường, QTV duyệt loại ảnh hưởng tín chỉ (D13)."""

from __future__ import annotations

from datetime import date

from vin15.domain.authorization import actor_of, require_view_internship
from vin15.domain.clock import Clock
from vin15.domain.exception import ForbiddenRoleError, InvalidInputError, ResourceNotFoundError, StateConflictError
from vin15.domain.model.audit import ActorKind, AuditEntry
from vin15.domain.model.user import Role, User
from vin15.domain.ports import FileStorage
from vin15.domain.statemachine import MILESTONE, Subject, request_machine
from vin15.infrastructure.persistence.case_repository import CaseRepository
from vin15.infrastructure.persistence.request_repository import RequestRepository
from vin15.infrastructure.persistence.user_repository import UserRepository
from vin15.service.files.upload import EVIDENCE_TYPES, store_upload
from vin15.service.notification.notification_service import NotificationService

_ACTIVE = ("confirmed", "in_progress", "pending_credit")


class RequestService:
    def __init__(
        self,
        requests: RequestRepository,
        cases: CaseRepository,
        users: UserRepository,
        notifications: NotificationService,
        storage: FileStorage,
        clock: Clock,
        upload_max_bytes: int,
    ):
        self._requests = requests
        self._cases = cases
        self._users = users
        self._notifications = notifications
        self._storage = storage
        self._clock = clock
        self._max_bytes = upload_max_bytes

    # ---- Danh mục ----
    def exception_types(self, *, active_only: bool = True) -> list[dict]:
        return self._requests.exception_types(active_only=active_only)

    def upsert_exception_type(self, admin: User, code: str, name: str, affects_credit: bool, active: bool) -> None:
        if admin.role != Role.ADMIN:
            raise ForbiddenRoleError("Chỉ quản trị viên cấu hình loại ngoại lệ")
        code = code.strip().lower()
        if not code or not name.strip():
            raise InvalidInputError("Cần mã và tên loại ngoại lệ")
        self._requests.upsert_exception_type(
            code, name.strip(), affects_credit, active,
            AuditEntry(actor_kind=ActorKind.HUMAN, actor_id=admin.id, actor_role=admin.role.value, entity="exception_type", action="upsert",
                       after={"code": code, "affects_credit": affects_credit, "active": active}, reason="Cấu hình loại ngoại lệ"),
        )

    # ---- Sinh viên ----
    def _internship(self, student: User) -> dict:
        row = self._cases.student_internship(student.id)
        if row is None or row["status"] not in _ACTIVE:
            raise StateConflictError("Chỉ tạo yêu cầu khi hồ sơ đang trong quá trình thực tập")
        return row

    def _audit(self, student: User, action: str, after: dict, reason: str) -> AuditEntry:
        return AuditEntry(actor_kind=ActorKind.HUMAN, actor_id=student.id, actor_role=student.role.value, entity="request", action=action, after=after, reason=reason)

    def create_extension(self, student: User, milestone_code: str, new_due_date: date, reason: str) -> int:
        row = self._internship(student)
        if not reason.strip():
            raise InvalidInputError("Cần nêu lý do gia hạn")
        milestone = self._cases.milestone_by_code(row["id"], milestone_code)
        if milestone is None:
            raise ResourceNotFoundError("Không tìm thấy mốc")
        if milestone["status"] in ("accepted", "submitted"):
            raise StateConflictError("Mốc đã nộp hoặc đã được chấp nhận, không cần gia hạn")
        if new_due_date <= milestone["due_date"] or new_due_date < self._clock():
            raise InvalidInputError("Hạn mới phải sau hạn hiện tại và không ở quá khứ")
        request_id = self._requests.create_request(
            row["id"], "milestone_extension", exception_type_code=None, milestone_code=milestone_code, reason=reason.strip(),
            new_due_date=new_due_date, affects_credit=False,
            audit=self._audit(student, "create", {"kind": "milestone_extension", "milestone": milestone_code, "new_due_date": new_due_date.isoformat()}, reason.strip()),
        )
        self._notify_deciders(row, False, f"{student.full_name} xin gia hạn {milestone['name']}", reason)
        return request_id

    def create_exception(self, student: User, type_code: str, reason: str) -> int:
        row = self._internship(student)
        if not reason.strip():
            raise InvalidInputError("Cần nêu lý do")
        kind = self._requests.get_exception_type(type_code)
        if kind is None or not kind["active"]:
            raise InvalidInputError("Loại ngoại lệ không hợp lệ")
        request_id = self._requests.create_request(
            row["id"], "exception", exception_type_code=type_code, milestone_code=None, reason=reason.strip(), new_due_date=None,
            affects_credit=kind["affects_credit"],
            audit=self._audit(student, "create", {"kind": "exception", "type": type_code, "affects_credit": kind["affects_credit"]}, reason.strip()),
        )
        self._notify_deciders(row, kind["affects_credit"], f"{student.full_name} gửi yêu cầu ngoại lệ: {kind['name']}", reason)
        return request_id

    def _notify_deciders(self, row: dict, affects_credit: bool, title: str, body: str) -> None:
        if affects_credit:
            self._notifications.notify_many(self._users.admin_ids(), title, body, kind="request_open", link="/admin/requests", email=True)
        elif row["lecturer_id"]:
            self._notifications.notify(row["lecturer_id"], title, body, kind="request_open", link="/lecturer/requests", email=True)

    def attach(self, student: User, request_id: int, filename: str, data: bytes) -> int:
        req = self._requests.get_request(request_id)
        if req is None or req["owner_id"] != student.id:
            raise ResourceNotFoundError("Không tìm thấy yêu cầu")
        if req["status"] != "open":
            raise StateConflictError("Yêu cầu đã được xử lý")
        stored = store_upload(self._storage, f"request/{request_id}", filename, data, EVIDENCE_TYPES, self._max_bytes)
        return self._requests.add_attachment(request_id, stored.filename, stored.mime, stored.size, stored.sha256, stored.key)

    def cancel(self, student: User, request_id: int) -> None:
        req = self._requests.get_request(request_id)
        if req is None:
            raise ResourceNotFoundError("Không tìm thấy yêu cầu")
        machine = request_machine(req["affects_credit"])
        actor = actor_of(student)
        transition = machine.transition(req["status"], "cancelled", actor, Subject(req["owner_id"], req["lecturer_id"]))
        self._requests.cancel_request(request_id, machine.audit(transition, actor, request_id))

    # ---- Xem ----
    def mine(self, student: User) -> list[dict]:
        row = self._cases.student_internship(student.id)
        return self._with_attachments(self._requests.requests_for_internship(row["id"])) if row else []

    def for_internship(self, viewer: User, internship_id: int) -> list[dict]:
        row = self._cases.get_internship(internship_id)
        if row is None:
            raise ResourceNotFoundError("Không tìm thấy hồ sơ")
        require_view_internship(viewer, row["user_id"], row["lecturer_id"])
        return self._with_attachments(self._requests.requests_for_internship(internship_id))

    def pending_for(self, user: User) -> list[dict]:
        if user.role == Role.ADMIN:
            return self._with_attachments(self._requests.pending_requests("admin", None))
        if user.role == Role.LECTURER:
            return self._with_attachments(self._requests.pending_requests("lecturer", user.id))
        raise ForbiddenRoleError("Chỉ giảng viên hoặc quản trị viên duyệt yêu cầu")

    def _with_attachments(self, rows: list[dict]) -> list[dict]:
        return [{**r, "attachments": self._requests.attachments(r["id"])} for r in rows]

    def attachment_bytes(self, viewer: User, attachment_id: int) -> tuple[bytes, str, str]:
        a = self._requests.get_attachment(attachment_id)
        if a is None:
            raise ResourceNotFoundError("Không tìm thấy tệp")
        if viewer.role == Role.ADMIN or (a["affects_credit"] is False and viewer.id == a["lecturer_id"]) or viewer.id == a["owner_id"]:
            return self._storage.get(a["storage_key"]), a["mime"], a["filename"]
        require_view_internship(viewer, a["owner_id"], a["lecturer_id"])
        return self._storage.get(a["storage_key"]), a["mime"], a["filename"]

    # ---- Người duyệt ----
    def decide(self, user: User, request_id: int, approve: bool, reason: str = "") -> None:
        req = self._requests.get_request(request_id)
        if req is None:
            raise ResourceNotFoundError("Không tìm thấy yêu cầu")
        machine = request_machine(req["affects_credit"])
        actor = actor_of(user)
        subject = Subject(req["owner_id"], req["lecturer_id"])
        target = "approved" if approve else "rejected"
        transition = machine.transition(req["status"], target, actor, subject, reason)
        milestone_update = None
        if approve and req["kind"] == "milestone_extension":
            m = self._cases.milestone_by_code(req["internship_id"], req["milestone_code"])
            if m is None or m["status"] in ("accepted", "submitted"):
                raise StateConflictError("Mốc không còn cần gia hạn")
            revive = None
            if m["status"] == "overdue" and req["new_due_date"] >= self._clock():
                revive_t = MILESTONE.transition("overdue", "pending", actor, subject)
                revive = MILESTONE.audit(revive_t, actor, m["id"])
            milestone_update = (m["id"], req["new_due_date"], revive)
        self._requests.decide_request(request_id, target, user.id, reason.strip(), machine.audit(transition, actor, request_id), milestone_update=milestone_update)
        label = "Yêu cầu gia hạn mốc" if req["kind"] == "milestone_extension" else f"Yêu cầu ngoại lệ ({req['exception_type_name']})"
        self._notifications.notify(
            req["owner_id"], f"{label}: " + ("đã được duyệt" if approve else "bị từ chối"), reason.strip(), kind=f"request_{target}", link="/student/requests", email=True
        )
