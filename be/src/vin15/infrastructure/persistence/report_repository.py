"""Truy vấn tổng hợp chỉ đọc: danh sách hồ sơ (A11), hàng chờ duyệt (A12), dashboard (D7), xem audit."""

from __future__ import annotations

from datetime import date

from .database import Database

_OVERDUE = "(m.status = 'overdue' or (m.status in ('pending', 'rejected') and m.due_date < %(today)s))"


class ReportRepository:
    def __init__(self, database: Database):
        self._db = database

    def list_internships(
        self,
        today: date,
        *,
        lecturer_id: int | None = None,
        status: str | None = None,
        milestone_code: str | None = None,
        milestone_status: str | None = None,
        flagged: bool = False,
        cohort: str | None = None,
    ) -> list[dict]:
        sql = f"""
            select i.id, i.cohort, i.status, i.start_date, i.end_date, i.mode, i.company_name, i.lecturer_id,
                   u.full_name as student_name, u.email as student_email, u.student_code, l.full_name as lecturer_name,
                   (select count(*) from milestone m where m.internship_id = i.id and {_OVERDUE}) as overdue_milestones,
                   (select count(*) from milestone m where m.internship_id = i.id and m.status = 'submitted') as submitted_milestones,
                   (select count(*) from risk_flag f where f.internship_id = i.id and f.status in ('open', 'acknowledged')) as open_flags
            from internship i
            join app_user u on u.id = i.user_id
            left join app_user l on l.id = i.lecturer_id
            where (%(lecturer_id)s::bigint is null or i.lecturer_id = %(lecturer_id)s)
              and (%(status)s::text is null or i.status = %(status)s)
              and (%(cohort)s::text is null or i.cohort = %(cohort)s)
              and (%(mcode)s::text is null or exists (
                    select 1 from milestone m where m.internship_id = i.id and m.code = %(mcode)s
                      and (%(mstatus)s::text is null
                           or (%(mstatus)s = 'overdue' and {_OVERDUE})
                           or (%(mstatus)s <> 'overdue' and m.status = %(mstatus)s))))
              and (not %(flagged)s or exists (
                    select 1 from risk_flag f where f.internship_id = i.id and f.status in ('open', 'acknowledged')))
            order by i.id desc
        """
        params = {
            "today": today,
            "lecturer_id": lecturer_id,
            "status": status,
            "cohort": cohort,
            "mcode": milestone_code,
            "mstatus": milestone_status,
            "flagged": flagged,
        }
        with self._db.connection() as conn:
            return conn.execute(sql, params).fetchall()

    def queue_items(self, role: str, user_id: int) -> list[dict]:
        """Việc chờ người duyệt (A12). ``role`` = ``lecturer`` (SV mình phụ trách) hoặc ``admin`` (toàn khóa)."""
        scope = "i.lecturer_id = %(uid)s" if role == "lecturer" else "true"
        params = {"uid": user_id}
        items: list[dict] = []
        with self._db.connection() as conn:
            if role == "lecturer":
                items += conn.execute(
                    f"select 'internship_submitted' as kind, i.id as internship_id, i.id as ref_id, u.full_name as student_name, "
                    f"'Hồ sơ thực tập chờ xác nhận' as title, i.submitted_at as since, null::date as due_date, null as severity "
                    f"from internship i join app_user u on u.id = i.user_id where i.status = 'submitted' and {scope}",
                    params,
                ).fetchall()
                items += conn.execute(
                    f"select 'outline_submitted' as kind, i.id as internship_id, o.id as ref_id, u.full_name as student_name, "
                    f"'Đề cương (phiên bản ' || o.version || ') chờ duyệt' as title, o.submitted_at as since, null::date as due_date, null as severity "
                    f"from outline o join internship i on i.id = o.internship_id join app_user u on u.id = i.user_id "
                    f"where o.status = 'submitted' and {scope}",
                    params,
                ).fetchall()
                items += conn.execute(
                    f"select 'milestone_submitted' as kind, i.id as internship_id, m.id as ref_id, u.full_name as student_name, "
                    f"m.name || ' chờ chấp nhận' as title, m.submitted_at as since, m.due_date as due_date, null as severity "
                    f"from milestone m join internship i on i.id = m.internship_id join app_user u on u.id = i.user_id "
                    f"where m.status = 'submitted' and {scope}",
                    params,
                ).fetchall()
                items += conn.execute(
                    f"select 'credit_assessment' as kind, i.id as internship_id, i.id as ref_id, u.full_name as student_name, "
                    f"'Thẩm định điều kiện công nhận tín chỉ' as title, i.decided_at as since, null::date as due_date, null as severity "
                    f"from internship i join app_user u on u.id = i.user_id where i.status = 'pending_credit' and {scope}",
                    params,
                ).fetchall()
            else:
                items += conn.execute(
                    "select 'credit_approval' as kind, i.id as internship_id, i.id as ref_id, u.full_name as student_name, "
                    "'Phê duyệt công nhận tín chỉ' as title, i.decided_at as since, null::date as due_date, null as severity "
                    "from internship i join app_user u on u.id = i.user_id where i.status = 'credit_review'"
                ).fetchall()
            items += conn.execute(
                f"select 'risk_flag' as kind, i.id as internship_id, f.id as ref_id, u.full_name as student_name, "
                f"f.reason as title, f.created_at as since, null::date as due_date, f.severity as severity "
                f"from risk_flag f join internship i on i.id = f.internship_id join app_user u on u.id = i.user_id "
                f"where f.status = 'open' and {scope}",
                params,
            ).fetchall()
        return items

    # ---- Dashboard ----
    def dashboard(self, today: date, lecturer_id: int | None, cohort: str | None) -> dict:
        params = {"today": today, "lid": lecturer_id, "cohort": cohort}
        scope = "(%(lid)s::bigint is null or i.lecturer_id = %(lid)s) and (%(cohort)s::text is null or i.cohort = %(cohort)s)"
        with self._db.connection() as conn:
            by_status = conn.execute(f"select i.status, count(*) as n from internship i where {scope} group by i.status order by i.status", params).fetchall()
            milestones = conn.execute(
                f"select m.status, count(*) as n from milestone m join internship i on i.id = m.internship_id where {scope} group by m.status", params
            ).fetchall()
            overdue = conn.execute(
                f"select count(distinct i.id) as late, "
                f"(select count(*) from internship i2 where i2.status in ('confirmed', 'in_progress', 'pending_credit') "
                f" and (%(lid)s::bigint is null or i2.lecturer_id = %(lid)s) and (%(cohort)s::text is null or i2.cohort = %(cohort)s)) as active "
                f"from internship i join milestone m on m.internship_id = i.id "
                f"where i.status in ('confirmed', 'in_progress', 'pending_credit') and {_OVERDUE} and {scope}",
                params,
            ).fetchone()
            flags = conn.execute(
                f"select f.severity, f.status, count(*) as n from risk_flag f join internship i on i.id = f.internship_id where {scope} group by f.severity, f.status",
                params,
            ).fetchall()
            decisions = conn.execute(
                f"""
                select 'internship' as kind, count(*) as n,
                       percentile_cont(0.5) within group (order by extract(epoch from (i.decided_at - i.submitted_at)) / 86400) as median_days
                  from internship i where i.submitted_at is not null and i.decided_at is not null and i.decided_at >= i.submitted_at and {scope}
                union all
                select 'outline', count(*), percentile_cont(0.5) within group (order by extract(epoch from (o.decided_at - o.submitted_at)) / 86400)
                  from outline o join internship i on i.id = o.internship_id where o.decided_at is not null and {scope}
                union all
                select 'milestone', count(*), percentile_cont(0.5) within group (order by extract(epoch from (m.decided_at - m.submitted_at)) / 86400)
                  from milestone m join internship i on i.id = m.internship_id where m.decided_at is not null and m.submitted_at is not null and {scope}
                union all
                select 'request', count(*), percentile_cont(0.5) within group (order by extract(epoch from (r.decided_at - r.created_at)) / 86400)
                  from request r join internship i on i.id = r.internship_id where r.decided_at is not null and r.status in ('approved', 'rejected') and {scope}
                """,
                params,
            ).fetchall()
            credit = conn.execute(
                f"select a.status, count(*) as n from credit_assessment a join internship i on i.id = a.internship_id where {scope} group by a.status", params
            ).fetchall()
            sync = conn.execute("select status, count(*) as n from credit_sync_job group by status").fetchall() if lecturer_id is None else []
        return {
            "internships_by_status": [dict(r) for r in by_status],
            "milestones_by_status": [dict(r) for r in milestones],
            "late_internships": overdue["late"] if overdue else 0,
            "active_internships": overdue["active"] if overdue else 0,
            "flags": [dict(r) for r in flags],
            "decision_times": [{"kind": r["kind"], "count": r["n"], "median_days": float(r["median_days"]) if r["median_days"] is not None else None} for r in decisions],
            "credit_outcomes": [dict(r) for r in credit],
            "sync_jobs": [dict(r) for r in sync],
        }

    def audit_events(self, limit: int = 200, entity: str | None = None, actor_id: int | None = None) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select a.id, a.at, a.actor_id, a.actor_kind, a.actor_role, u.full_name as actor_name, a.entity, a.entity_id, a.action, a.reason "
                "from audit_event a left join app_user u on u.id = a.actor_id "
                "where (%s::text is null or a.entity = %s) and (%s::bigint is null or a.actor_id = %s) order by a.id desc limit %s",
                (entity, entity, actor_id, actor_id, limit),
            ).fetchall()
