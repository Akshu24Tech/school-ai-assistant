"""Unit tests for the ERP data layer — pure arithmetic, no model calls."""

import pytest

from app.services import erp

S = "S101"  # Aarav Sharma, anchored to today = 2025-11-10 (Monday)


def test_unknown_student_raises():
    with pytest.raises(erp.RecordNotFound):
        erp.get_student("S999")


def test_attendance_overall_percentage():
    out = erp.attendance(S)
    # 23+24+7 present of 24+26+8 total = 54/58
    assert out["present"] == 54
    assert out["total"] == 58
    assert out["percentage"] == pytest.approx(93.1, abs=0.1)
    assert out["status"] == "Good"


def test_attendance_by_month_name():
    out = erp.attendance(S, "November")
    assert out["scope"] == "2025-11"
    assert out["present"] == 7
    assert out["missed"] == 1


def test_marks_highlights_best_and_worst():
    out = erp.marks(S)
    assert out["highest_subject"]["subject"] == "Mathematics"
    assert out["lowest_subject"]["subject"] == "Social Science"


def test_marks_single_subject():
    out = erp.marks(S, "mathematics")  # case-insensitive
    assert out["subject"] == "Mathematics"
    assert out["average"] == pytest.approx(90.0)


def test_fees_pending_total():
    out = erp.fees(S)
    assert out["pending_amount"] == 4500
    assert out["pending_months"] == ["2025-11"]
    assert out["status"] == "Pending"


def test_homework_due_today_and_tomorrow():
    today = erp.homework(S, "today")
    assert today["count"] == 1
    assert today["items"][0]["subject"] == "Science"

    tomorrow = erp.homework(S, "tomorrow")
    assert tomorrow["items"][0]["subject"] == "Mathematics"


def test_timetable_today_is_monday():
    out = erp.timetable(S, "today")
    assert out["day"] == "Monday"
    assert out["first_class"]["subject"] == "Mathematics"

    tomorrow = erp.timetable(S, "tomorrow")
    assert tomorrow["day"] == "Tuesday"


def test_academic_summary_flags_weak_subject():
    out = erp.academic_summary(S)
    assert out["performance"] in {"Excellent", "Good"}
    assert "Mathematics" in out["strong_subjects"]


def test_parent_report_has_all_sections():
    out = erp.parent_report(S)
    assert set(out) >= {"attendance", "marks", "pending_homework", "fees"}
    assert out["fees"]["status"] == "Pending"
