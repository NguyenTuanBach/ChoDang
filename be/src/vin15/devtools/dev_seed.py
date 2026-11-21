"""``make seed-dev``: dữ liệu giả cho dev/test. **Từ chối chạy khi ``APP_ENV=production``.** Chạy lại được (idempotent).

Gồm: 1 quản trị viên, 1 giảng viên, 3 sinh viên (A: đang thực tập, trễ mốc M3, thiếu nhật ký; B: đã nộp báo cáo cuối, chờ
thẩm định; C: chưa có hồ sơ) kèm mốc/nhật ký/minh chứng/yêu cầu; và bộ quy chế mẫu (``is_sample=true``) nạp bằng
``PolicyIngestService`` rồi xuất bản bằng ``PolicyPublishService``.

Mốc thời gian tính tương đối theo "hôm nay" **ở lần seed đầu tiên**; chạy lại không đổi dữ liệu đã có (``on conflict do nothing``).
Dữ liệu giả KHÔNG nằm trong migration (migration chạy cả ở production).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import anyio.to_thread

from vin15.config.container import Container
from vin15.config.resources import RESOURCES_DIR
from vin15.domain.model.policy import VersionStatus
from vin15.infrastructure.persistence.database import Database
from vin15.infrastructure.persistence.migrations import SqlMigrator

log = logging.getLogger(__name__)

POLICY_DIR = RESOURCES_DIR / "seed" / "policies"

ADMIN_EMAIL = "qtv@example.test"
LECTURER_EMAIL = "gv@example.test"
STUDENT_A_EMAIL = "sv.a@example.test"
STUDENT_B_EMAIL = "sv.b@example.test"
STUDENT_C_EMAIL = "sv.c@example.test"
COHORT = "2026-K1"

_FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


class SeedRefusedError(RuntimeError):
    """Không được seed ở môi trường production."""


@dataclass
class SeedReport:
    users: int = 0
    internships: int = 0
    policy_versions: int = 0
    policy_published_now: int = 0
    embedded_chunks: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PolicyFile:
    code: str
    title: str
    issuer: str
    version: str
    effective_from: date
    is_sample: bool
    text: str


def read_policy_files(directory: Path = POLICY_DIR) -> list[PolicyFile]:
    """Đọc bộ quy chế mẫu (Markdown có front matter ``key: value``), sắp theo (mã, hiệu lực) để bản cũ xuất bản trước bản mới."""
    files: list[PolicyFile] = []
    for path in sorted(directory.glob("*.md")):
        match = _FRONT_MATTER.match(path.read_text(encoding="utf-8"))
        if match is None:
            raise ValueError(f"{path.name}: thiếu front matter (--- key: value ---)")
        meta = dict(line.split(":", 1) for line in match.group(1).splitlines() if ":" in line)
        meta = {k.strip(): v.strip() for k, v in meta.items()}
        files.append(
            PolicyFile(
                code=meta["code"],
                title=meta["title"],
                issuer=meta.get("issuer", ""),
                version=meta["version"],
                effective_from=date.fromisoformat(meta["effective_from"]),
                is_sample=meta.get("is_sample", "true").lower() == "true",
                text=match.group(2),
            )
        )
    return sorted(files, key=lambda f: (f.code, f.effective_from))


async def run_seed(container: Container) -> SeedReport:
    """Áp migration, nạp người dùng/hồ sơ giả và bộ quy chế mẫu. Từ chối khi production."""
    if container.settings.is_production:
        raise SeedRefusedError("Từ chối seed dữ liệu giả khi APP_ENV=production")
    database = container.require_database()
    report = SeedReport()
    await anyio.to_thread.run_sync(SqlMigrator(database).migrate)
    today = container.clock()
    await anyio.to_thread.run_sync(lambda: _seed_people(database, today, report))
    await _seed_policies(container, report)
    return report


# ---------------------------------------------------------------- người dùng và hồ sơ ----


def _seed_people(database: Database, today: date, report: SeedReport) -> None:
    with database.connection() as conn:
        admin = _user(conn, ADMIN_EMAIL, "Quản trị viên mẫu", "admin", None)
        lecturer = _user(conn, LECTURER_EMAIL, "Cô Nguyễn Thị Lan (mẫu)", "lecturer", admin)
        student_a = _user(conn, STUDENT_A_EMAIL, "Sinh viên A (mẫu)", "student", lecturer, "SV0001", lecturer)
        student_b = _user(conn, STUDENT_B_EMAIL, "Sinh viên B (mẫu)", "student", lecturer, "SV0002", lecturer)
        _user(conn, STUDENT_C_EMAIL, "Sinh viên C (mẫu, chưa có hồ sơ)", "student", lecturer, "SV0003", lecturer)
        report.users = 5
        _seed_outcomes(conn)
        _seed_student_a(conn, student_a, lecturer, today)
        _seed_student_b(conn, student_b, lecturer, today)
        _seed_lms(conn)
        report.internships = 2


def _user(conn, email: str, name: str, role: str, invited_by: int | None, student_code: str | None = None, advisor_id: int | None = None) -> int:
    conn.execute(
        "insert into app_user (email, full_name, role, status, invited_by, activated_at, student_code, advisor_id) "
        "values (%s, %s, %s, 'active', %s, now(), %s, %s) on conflict (email) do nothing",
        (email, name, role, invited_by, student_code, advisor_id),
    )
    return conn.execute("select id from app_user where email = %s", (email,)).fetchone()["id"]


def _internship(conn, user_id: int, lecturer_id: int, status: str, start: date, end: date, mode: str) -> int:
    conn.execute(
        "insert into internship (user_id, cohort, status, start_date, end_date, mode, lecturer_id, company_name, company_tax_code, company_address, "
        "position, mentor_name, mentor_email, mentor_phone, job_description, submitted_at) "
        "values (%s, %s, %s, %s, %s, %s, %s, 'Công ty TNHH Giải pháp Mẫu', %s, '12 Đường Mẫu, Quận 1, TP.HCM', 'Thực tập sinh phát triển phần mềm', "
        "'Anh Trần Văn Mẫu', 'mentor@congty-mau.example', '0901234567', 'Tham gia phát triển và kiểm thử các module web của sản phẩm nội bộ.', now()) "
        "on conflict (user_id, cohort) do nothing",
        (user_id, COHORT, status, start, end, mode, lecturer_id, "0100000000" if user_id % 2 else "0100000001"),
    )
    return conn.execute("select id from internship where user_id = %s and cohort = %s", (user_id, COHORT)).fetchone()["id"]


def _milestones(conn, internship_id: int, items: list[tuple[str, str, date, str]]) -> dict[str, int]:
    for code, name, due, status in items:
        conn.execute(
            "insert into milestone (internship_id, code, name, due_date, status) values (%s, %s, %s, %s, %s) "
            "on conflict (internship_id, code) do nothing",
            (internship_id, code, name, due, status),
        )
    rows = conn.execute("select code, id from milestone where internship_id = %s", (internship_id,)).fetchall()
    return {r["code"]: r["id"] for r in rows}


def _journal(conn, internship_id: int, start: date, weeks: list[int]) -> None:
    for k in weeks:
        conn.execute(
            "insert into journal_entry (internship_id, week_start, content) values (%s, %s, %s) on conflict (internship_id, week_start) do nothing",
            (internship_id, start + timedelta(days=7 * k), f"Tuần {k + 1}: làm việc với nhóm, hoàn thành các nhiệm vụ được giao và học thêm quy trình kiểm thử."),
        )


def _outline(conn, internship_id: int, status: str) -> None:
    conn.execute(
        "insert into outline (internship_id, version, content, outcome_codes, status, decided_at) select %s, 1, %s, %s, %s, now() "
        "where not exists (select 1 from outline where internship_id = %s)",
        (
            internship_id,
            "Mục tiêu: vận dụng kiến thức lập trình web vào dự án thực tế; thực hiện phát triển và kiểm thử module, báo cáo tiến độ hằng tuần cho người hướng dẫn.",
            ["LO1", "LO2"],
            status,
            internship_id,
        ),
    )


def _seed_outcomes(conn) -> None:
    outcomes = [
        ("LO1", "Vận dụng kiến thức chuyên ngành vào công việc thực tế"),
        ("LO2", "Làm việc nhóm và giao tiếp trong môi trường doanh nghiệp"),
        ("LO3", "Tuân thủ quy trình, chuẩn mực nghề nghiệp"),
        ("LO4", "Tự học và báo cáo kết quả công việc"),
    ]
    for code, description in outcomes:
        conn.execute(
            "insert into learning_outcome (cohort, code, description) values (%s, %s, %s) on conflict (cohort, code) do nothing",
            (COHORT, code, description),
        )


def _seed_lms(conn) -> None:
    """LMS mini: học phần, tiên quyết của học phần thực tập TT-101 (CS101 và CS201 từ 5 điểm) và điểm mẫu. SV C chưa đủ tiên quyết."""
    for code, name, credits, kind in [
        ("MATH101", "Toán cao cấp", 3, "regular"),
        ("CS101", "Nhập môn lập trình", 3, "regular"),
        ("CS201", "Cấu trúc dữ liệu và giải thuật", 3, "regular"),
        ("TT-101", "Thực tập doanh nghiệp", 4, "internship"),
    ]:
        conn.execute("insert into lms_course (code, name, credits, kind) values (%s, %s, %s, %s) on conflict (code) do nothing", (code, name, credits, kind))
    for required in ("CS101", "CS201"):
        conn.execute(
            "insert into lms_prerequisite (course_code, required_course_code, min_score) values ('TT-101', %s, 5.0) on conflict do nothing", (required,)
        )
    students = [("SV0001", "Sinh viên A (mẫu)"), ("SV0002", "Sinh viên B (mẫu)"), ("SV0003", "Sinh viên C (mẫu, chưa có hồ sơ)")]
    for code, name in students:
        conn.execute("insert into lms_student (student_code, full_name) values (%s, %s) on conflict do nothing", (code, name))
    grades = [
        ("SV0001", "CS101", 8.0), ("SV0001", "CS201", 7.5), ("SV0001", "MATH101", 7.0),
        ("SV0002", "CS101", 7.0), ("SV0002", "CS201", 6.0),
        ("SV0003", "CS101", 4.0), ("SV0003", "MATH101", 6.5),
    ]
    for student_code, course_code, score in grades:
        conn.execute(
            "insert into lms_grade (student_code, course_code, score, term) values (%s, %s, %s, '2025-2026') on conflict do nothing",
            (student_code, course_code, score),
        )


def _evidence(conn, milestone_id: int, title: str, status: str) -> None:
    conn.execute(
        "insert into evidence (milestone_id, title, status) select %s, %s, %s "
        "where not exists (select 1 from evidence where milestone_id = %s and title = %s)",
        (milestone_id, title, status, milestone_id, title),
    )


def _request(conn, internship_id: int, kind: str, status: str) -> None:
    conn.execute(
        "insert into request (internship_id, kind, status) select %s, %s, %s "
        "where not exists (select 1 from request where internship_id = %s and kind = %s and status = %s)",
        (internship_id, kind, status, internship_id, kind, status),
    )


_M = {
    "M1": "Hồ sơ đăng ký được xác nhận",
    "M2": "Đề cương được duyệt",
    "M3": "Báo cáo giữa kỳ",
    "M4": "Báo cáo cuối kỳ",
    "M5": "Phiếu đánh giá của doanh nghiệp",
}


def _seed_student_a(conn, user_id: int, lecturer_id: int, today: date) -> None:
    """SV A: đang thực tập tuần 7/12, trễ mốc M3 (đã yêu cầu gia hạn), thiếu nhật ký tuần 4 và 6."""
    start = today - timedelta(days=42)
    end = start + timedelta(days=83)
    internship = _internship(conn, user_id, lecturer_id, "in_progress", start, end, "onsite")
    milestones = _milestones(
        conn,
        internship,
        [
            ("M1", _M["M1"], start - timedelta(days=7), "accepted"),
            ("M2", _M["M2"], start + timedelta(days=14), "accepted"),
            ("M3", _M["M3"], today - timedelta(days=5), "overdue"),
            ("M4", _M["M4"], end - timedelta(days=7), "pending"),
            ("M5", _M["M5"], end + timedelta(days=7), "pending"),
        ],
    )
    _journal(conn, internship, start, [0, 1, 2, 4])
    _outline(conn, internship, "approved")
    _evidence(conn, milestones["M2"], "Đề cương thực tập", "accepted")
    _request(conn, internship, "milestone_extension", "open")


def _seed_student_b(conn, user_id: int, lecturer_id: int, today: date) -> None:
    """SV B: đã thực tập đủ 12 tuần, nộp báo cáo cuối (M4), phiếu đánh giá doanh nghiệp (M5) chưa nộp; thiếu 1 tuần nhật ký."""
    end = today - timedelta(days=4)
    start = end - timedelta(days=83)
    internship = _internship(conn, user_id, lecturer_id, "pending_credit", start, end, "remote")
    milestones = _milestones(
        conn,
        internship,
        [
            ("M1", _M["M1"], start - timedelta(days=7), "accepted"),
            ("M2", _M["M2"], start + timedelta(days=14), "accepted"),
            ("M3", _M["M3"], start + timedelta(days=42), "accepted"),
            ("M4", _M["M4"], end - timedelta(days=7), "submitted"),
            ("M5", _M["M5"], end + timedelta(days=7), "pending"),
        ],
    )
    _journal(conn, internship, start, [k for k in range(12) if k != 5])
    _outline(conn, internship, "approved")
    _evidence(conn, milestones["M3"], "Báo cáo giữa kỳ", "accepted")
    _evidence(conn, milestones["M4"], "Báo cáo cuối kỳ", "submitted")


# ---------------------------------------------------------------- quy chế mẫu ----


async def _seed_policies(container: Container, report: SeedReport) -> None:
    ingest = container.policy_ingest_service
    publish = container.policy_publish_service
    for file in read_policy_files():
        result = await ingest.ensure(
            doc_code=file.code,
            doc_title=file.title,
            issuer=file.issuer,
            version_label=file.version,
            effective_from=file.effective_from,
            is_sample=file.is_sample,
            text=file.text,
        )
        report.policy_versions += 1
        report.embedded_chunks += result.embedded_count
        if result.version.status == VersionStatus.DRAFT:
            admin = await anyio.to_thread.run_sync(lambda: container.user_repository.find_by_email(ADMIN_EMAIL))
            assert admin is not None
            await publish.publish_async(result.version.id, admin.id, admin.role.value)
            report.policy_published_now += 1
    if not container.agent_client.enabled:
        report.notes.append("Không có AGENT_API_URL: quy chế chỉ tìm được bằng từ khóa (chưa có embedding).")
    elif report.embedded_chunks == 0:
        report.notes.append(
            "Agent không trả embedding (không chạy hoặc lỗi LLM): quy chế chỉ tìm bằng từ khóa. Chạy lại `make seed-dev` khi agent sẵn sàng để bù embedding."
        )
