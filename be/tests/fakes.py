"""Kho dữ liệu giả trong bộ nhớ cho test không cần database: người dùng, audit, hồ sơ thực tập, quy định, hội thoại."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from vin15.domain.model.chat import ChatMessage, Conversation
from vin15.domain.model.internship import EvidenceRecord, InternshipRecord, MilestoneRecord, RequestRecord
from vin15.domain.model.policy import PolicyChunk, PolicyChunkLookup, PolicySearchResult
from vin15.domain.model.user import Role, User, UserStatus

NOW = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
TODAY = date(2026, 11, 21)


def make_user(user_id: int, email: str, role: Role, status: UserStatus = UserStatus.ACTIVE, name: str = "") -> User:
    return User(id=user_id, email=email, full_name=name or email.split("@")[0], role=role, status=status)


ADMIN = make_user(1, "qtv@example.test", Role.ADMIN)
LECTURER = make_user(2, "gv@example.test", Role.LECTURER, name="Cô Lan")
STUDENT_A = make_user(3, "sv.a@example.test", Role.STUDENT)
STUDENT_B = make_user(4, "sv.b@example.test", Role.STUDENT)
STUDENT_NO_RECORD = make_user(5, "sv.c@example.test", Role.STUDENT)
REVOKED = make_user(6, "sv.x@example.test", Role.STUDENT, UserStatus.REVOKED)


class FakeUsers:
    def __init__(self, *users: User):
        self._users = {u.id: u for u in users}

    def find_by_id(self, user_id):
        return self._users.get(user_id)

    def find_by_email(self, email):
        return next((u for u in self._users.values() if u.email == email.strip().lower()), None)

    def list_by_email_suffix(self, suffix):
        order = {Role.ADMIN: 0, Role.LECTURER: 1, Role.STUDENT: 2}
        found = [u for u in self._users.values() if u.email.endswith(suffix.strip().lower())]
        return sorted(found, key=lambda u: (order[u.role], u.email))


class FakeAudit:
    def __init__(self):
        self.entries = []

    def record(self, entry):
        self.entries.append(entry)
        return len(self.entries)


class FakeInternships:
    """Hồ sơ theo user_id: ``{user_id: (InternshipRecord, [MilestoneRecord], [EvidenceRecord], [week_start], [RequestRecord])}``."""

    def __init__(self, data):
        self._data = data
        self.queried_users = []

    def latest_internship(self, user_id):
        self.queried_users.append(user_id)
        entry = self._data.get(user_id)
        return entry[0] if entry else None

    def _by_internship(self, internship_id):
        return next(e for e in self._data.values() if e[0].id == internship_id)

    def milestones(self, internship_id):
        return self._by_internship(internship_id)[1]

    def evidence(self, internship_id):
        return self._by_internship(internship_id)[2]

    def journal_week_starts(self, internship_id):
        return self._by_internship(internship_id)[3]

    def requests(self, internship_id):
        return self._by_internship(internship_id)[4]


def internship_a() -> tuple:
    """SV A: đang thực tập 6 tuần, trễ mốc M3, thiếu nhật ký tuần 3 và 5."""
    start = date(2026, 10, 10)
    record = InternshipRecord(101, "2026-K1", "in_progress", start, date(2027, 1, 1), "onsite", "Cô Lan")
    milestones = [
        MilestoneRecord("M1", "Hồ sơ đăng ký được xác nhận", date(2026, 10, 3), "accepted"),
        MilestoneRecord("M2", "Đề cương được duyệt", date(2026, 10, 24), "accepted"),
        MilestoneRecord("M3", "Báo cáo giữa kỳ", date(2026, 11, 16), "pending"),
        MilestoneRecord("M4", "Báo cáo cuối kỳ", date(2026, 12, 25), "pending"),
        MilestoneRecord("M5", "Phiếu đánh giá của doanh nghiệp", date(2027, 1, 8), "pending"),
    ]
    evidence = [EvidenceRecord("M2", "accepted")]
    weeks = [date(2026, 10, 10), date(2026, 10, 17), date(2026, 10, 24), date(2026, 11, 7)]  # thiếu tuần 3 (31/10) và 5 (14/11)
    requests = [RequestRecord("milestone_extension", "open", NOW)]
    return record, milestones, evidence, weeks, requests


def internship_b() -> tuple:
    """SV B: đã nộp báo cáo cuối, chờ thẩm định."""
    start = date(2026, 8, 1)
    record = InternshipRecord(102, "2026-K1", "pending_credit", start, date(2026, 11, 18), "remote", "Cô Lan")
    milestones = [
        MilestoneRecord("M1", "Hồ sơ đăng ký được xác nhận", date(2026, 7, 25), "accepted"),
        MilestoneRecord("M2", "Đề cương được duyệt", date(2026, 8, 15), "accepted"),
        MilestoneRecord("M3", "Báo cáo giữa kỳ", date(2026, 9, 15), "accepted"),
        MilestoneRecord("M4", "Báo cáo cuối kỳ", date(2026, 11, 11), "submitted"),
        MilestoneRecord("M5", "Phiếu đánh giá của doanh nghiệp", date(2026, 11, 25), "pending"),
    ]
    evidence = [EvidenceRecord("M3", "accepted"), EvidenceRecord("M4", "submitted")]
    weeks = [date(2026, 8, 1) + (date(2026, 8, 8) - date(2026, 8, 1)) * k for k in range(15)]
    return record, milestones, evidence, weeks, []


def chunk(chunk_id: str = "QD-TT-01@v1/d3/k1", **overrides) -> PolicyChunk:
    base = PolicyChunk(
        chunk_id=chunk_id,
        doc_code="QD-TT-01",
        doc_title="Quy chế thực tập (mẫu)",
        version="v1",
        article_no="3",
        clause_no="1",
        heading="Điều 3. Thời lượng",
        text="Thời lượng thực tập tối thiểu là 8 tuần.",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        is_sample=True,
        score=0.0164,
    )
    return replace(base, **overrides)


class FakePolicySearch:
    """Thay ``PolicySearchService``: ghi lại tham số, trả kết quả cố định."""

    def __init__(self, chunks=None):
        self.chunks = [chunk()] if chunks is None else chunks
        self.calls = []

    def search(self, query, query_vector=None, top_k=5):
        self.calls.append(("search", query, query_vector, top_k))
        return PolicySearchResult("ok" if self.chunks else "no_match", "hybrid" if query_vector else "keyword", self.chunks)

    def get_chunk(self, chunk_id, with_neighbors=False):
        from vin15.domain.exception import ResourceNotFoundError

        self.calls.append(("get_chunk", chunk_id, with_neighbors))
        found = next((c for c in self.chunks if c.chunk_id == chunk_id), None)
        if found is None:
            raise ResourceNotFoundError("Không tìm thấy đoạn quy định đang có hiệu lực với mã này")
        return PolicyChunkLookup(found, self.chunks[:0])


class FakeChats:
    """Thay ``ChatRepository`` trong bộ nhớ."""

    def __init__(self):
        self.conversations: dict[int, Conversation] = {}
        self.messages: list[ChatMessage] = []
        self._next = 1

    def create_conversation(self, user_id, title):
        conversation = Conversation(len(self.conversations) + 1, user_id, title, NOW, NOW)
        self.conversations[conversation.id] = conversation
        return conversation

    def get_conversation(self, conversation_id):
        return self.conversations.get(conversation_id)

    def list_conversations(self, user_id, limit=100):
        return [c for c in self.conversations.values() if c.user_id == user_id][::-1]

    def list_messages(self, conversation_id):
        return [m for m in self.messages if m.conversation_id == conversation_id]

    def recent_messages(self, conversation_id, limit):
        return self.list_messages(conversation_id)[-limit:]

    def turn_exists(self, conversation_id, turn_id):
        return any(m.conversation_id == conversation_id and m.turn_id == turn_id for m in self.messages)

    def add_message(self, conversation_id, turn_id, role, content, *, citations=None, trace=None, degraded=False):
        message = ChatMessage(self._next, conversation_id, turn_id, role, content, NOW, citations or [], trace or {}, degraded)
        self._next += 1
        self.messages.append(message)
        return message

    def find_message_by_trace_id(self, trace_id):
        message = next((m for m in self.messages if m.trace.get("trace_id") == trace_id), None)
        return (message, self.conversations[message.conversation_id]) if message else None
