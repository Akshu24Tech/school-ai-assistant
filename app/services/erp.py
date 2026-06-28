"""Read-only access layer over the mock ERP data.

Everything the tools expose goes through here. The JSON files are the "ERP";
this module loads them once and does the small bits of arithmetic (percentages,
averages, pending totals, day-relative lookups) so the tools stay thin.

There are no hardcoded answers — every number is derived from mock_data/.
"""

import json
import logging
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

log = logging.getLogger("app.erp")

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


class RecordNotFound(Exception):
    """A student id that isn't in the ERP. The API turns this into a 404."""


@lru_cache
def _load(name: str) -> dict:
    path = Path(get_settings().data_dir) / f"{name}.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def today() -> date:
    return datetime.strptime(get_settings().today, "%Y-%m-%d").date()


def get_student(student_id: str) -> dict:
    student = _load("students").get(student_id)
    if student is None:
        raise RecordNotFound(f"No student found with id {student_id!r}")
    return {"student_id": student_id, **student}


# ----------------------------------------------------------------------------
# small helpers
# ----------------------------------------------------------------------------

def _resolve_month(month: str | None) -> str | None:
    """Turn a loose month reference into a 'YYYY-MM' key, or None for 'overall'."""
    if not month:
        return None
    text = month.strip().lower()
    if text in {"this month", "current", "current month"}:
        return today().strftime("%Y-%m")
    if text in {"last month", "previous month"}:
        first = today().replace(day=1)
        return (first - timedelta(days=1)).strftime("%Y-%m")
    # already a YYYY-MM
    if len(text) == 7 and text[4] == "-":
        return text
    # a bare month name → assume the year of "today"
    name = text.split()[0]
    if name in _MONTHS:
        return f"{today().year}-{_MONTHS[name]:02d}"
    return text  # let the caller decide it's missing


def _attendance_status(pct: float) -> str:
    if pct >= 90:
        return "Good"
    if pct >= 75:
        return "Average"
    return "At Risk"


def _marks_status(avg: float) -> str:
    if avg >= 85:
        return "Excellent"
    if avg >= 60:
        return "Good"
    return "Needs Improvement"


# ----------------------------------------------------------------------------
# the five ERP services (+ two derived reports)
# ----------------------------------------------------------------------------

def attendance(student_id: str, month: str | None = None) -> dict:
    get_student(student_id)
    records = _load("attendance").get(student_id, {})
    if not records:
        return {"found": False, "message": "No attendance has been recorded yet."}

    key = _resolve_month(month)
    if key:
        rec = records.get(key)
        if not rec:
            return {"found": False, "month": key,
                    "message": f"No attendance recorded for {key}."}
        pct = round(rec["present"] / rec["total"] * 100, 1)
        return {
            "found": True, "scope": key,
            "present": rec["present"], "total": rec["total"],
            "missed": rec["total"] - rec["present"],
            "absent_dates": rec.get("absent_dates", []),
            "percentage": pct, "status": _attendance_status(pct),
        }

    present = sum(r["present"] for r in records.values())
    total = sum(r["total"] for r in records.values())
    pct = round(present / total * 100, 1)
    return {
        "found": True, "scope": "overall",
        "present": present, "total": total, "missed": total - present,
        "percentage": pct, "status": _attendance_status(pct),
        "by_month": {m: round(r["present"] / r["total"] * 100, 1) for m, r in records.items()},
    }


def marks(student_id: str, subject: str | None = None) -> dict:
    get_student(student_id)
    book = _load("marks").get(student_id, {})
    if not book:
        return {"found": False, "message": "No marks have been published yet."}

    def avg(exams):
        return round(sum(e["score"] for e in exams) / len(exams), 1)

    if subject:
        match = next((s for s in book if s.lower() == subject.strip().lower()), None)
        if not match:
            return {"found": False, "subject": subject,
                    "message": f"No marks recorded for {subject}.",
                    "available_subjects": list(book)}
        a = avg(book[match])
        return {"found": True, "subject": match, "exams": book[match],
                "average": a, "status": _marks_status(a)}

    per_subject = {s: avg(exams) for s, exams in book.items()}
    overall = round(sum(per_subject.values()) / len(per_subject), 1)
    best = max(per_subject, key=per_subject.get)
    worst = min(per_subject, key=per_subject.get)
    return {
        "found": True, "subjects": per_subject,
        "overall_average": overall, "status": _marks_status(overall),
        "highest_subject": {"subject": best, "average": per_subject[best]},
        "lowest_subject": {"subject": worst, "average": per_subject[worst]},
    }


def fees(student_id: str) -> dict:
    get_student(student_id)
    record = _load("fees").get(student_id)
    if not record:
        return {"found": False, "message": "No fee record on file."}

    payments = record["payments"]
    pending = [p for p in payments if p["status"] != "paid"]
    pending_total = sum(p["amount"] for p in pending)
    return {
        "found": True,
        "monthly_fee": record["monthly_fee"],
        "currency": record.get("currency", "INR"),
        "pending_amount": pending_total,
        "pending_months": [p["month"] for p in pending],
        "status": "Pending" if pending_total else "Paid",
        "history": payments,
    }


def homework(student_id: str, when: str | None = None) -> dict:
    get_student(student_id)
    items = _load("homework").get(student_id, [])
    if not items:
        return {"found": False, "message": "No homework assigned right now."}

    ref = today()
    text = (when or "").strip().lower()
    if text in {"today"}:
        items = [h for h in items if h["due"] == ref.isoformat()]
    elif text in {"tomorrow"}:
        items = [h for h in items if h["due"] == (ref + timedelta(days=1)).isoformat()]
    elif text in {"pending", "due", "open"}:
        items = [h for h in items if h["status"] == "pending"]
    # "all" or empty → everything

    return {
        "found": bool(items),
        "filter": text or "all",
        "count": len(items),
        "items": items,
        "message": None if items else "Nothing matches that.",
    }


def timetable(student_id: str, day: str | None = None) -> dict:
    get_student(student_id)
    week = _load("timetable").get(student_id, {})
    if not week:
        return {"found": False, "message": "No timetable available."}

    ref = today()
    text = (day or "today").strip().lower()
    if text == "today":
        name = ref.strftime("%A")
    elif text == "tomorrow":
        name = (ref + timedelta(days=1)).strftime("%A")
    else:
        name = text.capitalize()

    periods = week.get(name, [])
    return {
        "found": bool(periods),
        "day": name,
        "periods": periods,
        "first_class": periods[0] if periods else None,
        "message": None if periods else f"No classes scheduled on {name}.",
    }


def academic_summary(student_id: str) -> dict:
    """Aggregate marks + attendance into one performance picture (bonus)."""
    student = get_student(student_id)
    m = marks(student_id)
    a = attendance(student_id)
    if not m.get("found"):
        return {"found": False, "message": "Not enough data for a summary yet."}

    ranked = sorted(m["subjects"].items(), key=lambda kv: kv[1], reverse=True)
    strong = [s for s, v in ranked if v >= 80]
    weak = [s for s, v in ranked if v < 60]
    return {
        "found": True,
        "student": student["name"],
        "overall_average": m["overall_average"],
        "performance": m["status"],
        "strong_subjects": strong or [ranked[0][0]],
        "weak_subjects": weak or [ranked[-1][0]],
        "attendance_percentage": a.get("percentage"),
        "attendance_status": a.get("status"),
        "subject_averages": m["subjects"],
    }


def parent_report(student_id: str) -> dict:
    """A guardian-facing roll-up across all four areas (bonus)."""
    student = get_student(student_id)
    a = attendance(student_id)
    m = marks(student_id)
    f = fees(student_id)
    hw = homework(student_id, "pending")
    return {
        "found": True,
        "student": student["name"],
        "class": student["class"],
        "attendance": {"percentage": a.get("percentage"), "status": a.get("status")},
        "marks": {"overall_average": m.get("overall_average"),
                  "subjects": m.get("subjects")},
        "pending_homework": hw.get("count", 0),
        "fees": {"pending_amount": f.get("pending_amount"), "status": f.get("status")},
    }
