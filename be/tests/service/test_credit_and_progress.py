from datetime import date, timedelta

import pytest

from tests.fakes import FakeInternships
from vin15.domain.model.internship import EvidenceRecord, InternshipRecord, MilestoneRecord
from vin15.service.credit.credit_checklist_service import CreditChecklistService
from vin15.service.lms.lms_port import FakeLmsAdapter
from vin15.service.milestone.milestone_view import milestone_view
from vin15.service.progress.progress_calculator import evidence_progress, expected_weeks, journal_progress, total_weeks

START = date(2026, 1, 5)


def record(status="in_progress", start=START, end=START + timedelta(days=83)):
    return InternshipRecord(1, "K1", status, start, end, "onsite", "Cô Lan")


def milestones(**statuses):
    codes = ("M1", "M2", "M3", "M4", "M5")
    return [MilestoneRecord(c, f"Mốc {c}", START + timedelta(days=7 * i), statuses.get(c, "accepted")) for i, c in enumerate(codes)]


def service(rec, ms, weeks, today, lms=None, min_weeks=8, ratio=0.8):
    repo = FakeInternships({7: (rec, ms, [], weeks, [])})
    return CreditChecklistService(repo, lms or FakeLmsAdapter(), lambda: today, min_weeks, ratio)


def items(rec, ms, weeks, today, **kw):
    result = service(rec, ms, weeks, today, **kw).checklist(7)
    return {i.code: i for i in result.items}, result


def all_weeks(n):
    return [START + timedelta(days=7 * k) for k in range(n)]


# ---- Tiến độ ----
def test_total_and_expected_weeks():
    assert total_weeks(START, START + timedelta(days=83)) == 12
    assert total_weeks(START, START + timedelta(days=84)) == 13
    end = START + timedelta(days=83)
    assert expected_weeks(START, end, START - timedelta(days=1)) == 0  # chưa bắt đầu
    assert expected_weeks(START, end, START + timedelta(days=6)) == 0  # tuần đầu chưa kết thúc
    assert expected_weeks(START, end, START + timedelta(days=7)) == 1
    assert expected_weeks(START, end, START + timedelta(days=400)) == 12  # không vượt tổng số tuần
    assert expected_weeks(None, end, START) == 0


def test_journal_week_counts_if_any_entry_falls_in_its_seven_days():
    entries = [START + timedelta(days=2), START + timedelta(days=14)]  # lệch ngày bắt đầu tuần vẫn tính
    progress = journal_progress(START, START + timedelta(days=83), START + timedelta(days=21), entries)
    assert (progress.submitted, progress.expected) == (2, 3) and progress.missing_weeks == [START + timedelta(days=7)]
    assert journal_progress(None, None, START, [START]).expected == 0


def test_evidence_progress_ignores_rejected_and_counts_required_milestones_only():
    ms = milestones()
    ev = [EvidenceRecord("M3", "rejected"), EvidenceRecord("M4", "submitted"), EvidenceRecord("M2", "accepted"), EvidenceRecord("M4", "accepted")]
    assert evidence_progress(ms, ev).submitted == 1 and evidence_progress(ms, ev).required == 3
    assert evidence_progress([], ev).required == 0


# ---- Mốc ----
@pytest.mark.parametrize(
    ("status", "due_offset", "expected_status", "needle"),
    [
        ("pending", -1, "overdue", "quá hạn 1 ngày"),
        ("rejected", -3, "overdue", "quá hạn 3 ngày"),
        ("pending", 0, "pending", "Nộp"),  # đúng hạn hôm nay chưa quá hạn
        ("rejected", 2, "rejected", "Sửa theo nhận xét"),
        ("submitted", -5, "submitted", "Chờ giảng viên"),  # đã nộp thì không bị coi là quá hạn
        ("accepted", -30, "accepted", "Đã hoàn tất"),
    ],
)
def test_milestone_view(status, due_offset, expected_status, needle):
    today = date(2026, 3, 1)
    view = milestone_view(MilestoneRecord("M3", "Báo cáo giữa kỳ", today + timedelta(days=due_offset), status), today)
    assert view.status == expected_status and needle in view.next_action and view.days_left == due_offset


# ---- T1-T6 ----
def test_t1_boundary_exactly_eight_weeks_met_and_seven_weeks_six_days_not():
    rec = record(end=START + timedelta(days=200))
    met, _ = items(rec, milestones(), all_weeks(8), START + timedelta(days=55))  # 56 ngày = 8 tuần
    assert met["T1"].met and met["T1"].value == "8 tuần" and met["T1"].threshold == "≥ 8 tuần"
    short, _ = items(rec, milestones(), all_weeks(8), START + timedelta(days=54))  # 55 ngày = 7 tuần + 6 ngày
    assert not short["T1"].met and short["T1"].value == "7 tuần"


def test_t1_is_capped_by_end_date_and_handles_missing_start():
    rec = record(end=START + timedelta(days=41))  # 6 tuần
    result, _ = items(rec, milestones(), all_weeks(6), START + timedelta(days=500))
    assert not result["T1"].met and result["T1"].value == "6 tuần"
    nostart, _ = items(record(start=None, end=None), milestones(), [], START)
    assert not nostart["T1"].met and nostart["T4"].value == "chưa có tuần nào đến hạn" and not nostart["T4"].met


def test_t2_from_status_or_accepted_m2():
    ms_pending_m2 = milestones(M2="pending")
    assert items(record("in_progress"), ms_pending_m2, [], START)[0]["T2"].met
    assert items(record("submitted"), milestones(M2="accepted"), [], START)[0]["T2"].met
    assert not items(record("confirmed"), ms_pending_m2, [], START)[0]["T2"].met


def test_t3_requires_every_milestone_accepted():
    assert items(record(), milestones(), [], START)[0]["T3"].met
    partial, _ = items(record(), milestones(M4="submitted"), [], START)
    assert not partial["T3"].met and partial["T3"].value == "4/5 mốc"
    none, _ = items(record(), [], [], START)
    assert not none["T3"].met and none["T3"].value == "chưa có mốc"


def test_t4_ratio_boundary():
    end_day = START + timedelta(days=70)  # 10 tuần đã kết thúc
    rec = record(end=START + timedelta(days=200))
    ok, _ = items(rec, milestones(), all_weeks(8), end_day)  # 8/10 = 80%
    assert ok["T4"].met and ok["T4"].value == "8/10 tuần (80%)" and ok["T4"].threshold == "≥ 80%"
    low, _ = items(rec, milestones(), all_weeks(7), end_day)
    assert not low["T4"].met


def test_t5_states_and_t6_from_lms():
    class NoLms:
        def prerequisites_met(self, user_id):
            return False

    done, _ = items(record(), milestones(), [], START)
    assert done["T5"].met and done["T5"].value == "đã xác thực" and done["T6"].met
    submitted, _ = items(record(), milestones(M5="submitted"), [], START, lms=NoLms())
    assert not submitted["T5"].met and "chờ giảng viên" in submitted["T5"].value and not submitted["T6"].met
    assert not items(record(), milestones(M5="pending"), [], START)[0]["T5"].met


def test_all_met_only_when_every_item_met_and_never_decides():
    rec = record(status="pending_credit", end=START + timedelta(days=83))
    items_map, result = items(rec, milestones(), all_weeks(12), START + timedelta(days=90))
    assert result.available and result.all_met and len(items_map) == 6
    assert not items(rec, milestones(M3="submitted"), all_weeks(12), START + timedelta(days=90))[1].all_met


def test_no_internship_record():
    result = CreditChecklistService(FakeInternships({}), FakeLmsAdapter(), lambda: START, 8, 0.8).checklist(99)
    assert (result.available, result.reason, result.items, result.all_met) == (False, "no_internship_record", [], False)
