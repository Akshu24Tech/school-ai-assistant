"""The ERP tools the agent can call, plus the dispatch table it runs them through.

Each function below is what the model "sees" — its name, signature and docstring
become the tool declaration, so the docstrings double as prompt engineering. None
of them take a student id: the subject student is bound per-request in a contextvar
by the agent, so the model can never read another student's record by guessing one.
"""

import contextvars

from app.services import erp

# set by the agent before each run; read by the wrappers below
subject_student: contextvars.ContextVar[str] = contextvars.ContextVar("subject_student")


def _sid() -> str:
    return subject_student.get()


def get_attendance(month: str = "") -> dict:
    """Get the student's attendance record and percentage.

    Use for any question about attendance, days present/absent, or classes missed.
    'month' is optional — pass a name like 'November', a 'YYYY-MM' value, or phrases
    like 'this month' / 'last month'. Omit it for the overall percentage.
    """
    return erp.attendance(_sid(), month or None)


def get_marks(subject: str = "") -> dict:
    """Get exam marks. Use for scores, averages, best/worst subject questions.

    Pass 'subject' (e.g. 'Mathematics') for one subject, or omit it to get every
    subject's average plus the highest and lowest scoring subject.
    """
    return erp.marks(_sid(), subject or None)


def get_fee_status() -> dict:
    """Get fee status: how much is pending, which months, and full payment history.

    Use for anything about fees, dues, payments or whether this month is paid.
    """
    return erp.fees(_sid())


def get_homework(when: str = "") -> dict:
    """Get homework and assignments.

    'when' is optional: 'today', 'tomorrow', or 'pending' to filter; omit for all.
    """
    return erp.homework(_sid(), when or None)


def get_timetable(day: str = "") -> dict:
    """Get the class timetable for a day.

    'day' can be a weekday name, 'today' or 'tomorrow'. Defaults to today. Use for
    questions about the schedule, the first class, or when a subject is on.
    """
    return erp.timetable(_sid(), day or None)


def get_academic_summary() -> dict:
    """Summarise overall academic performance: average, strong and weak subjects,
    and attendance. Use when the student asks to summarise their semester or how
    they are doing overall."""
    return erp.academic_summary(_sid())


def get_parent_report() -> dict:
    """Build a guardian progress report: attendance, subject marks, pending
    homework and pending fees in one place. Use for a parent asking for a report."""
    return erp.parent_report(_sid())


# everything wired into the model, and how we run them by name
TOOLS = [
    get_attendance,
    get_marks,
    get_fee_status,
    get_homework,
    get_timetable,
    get_academic_summary,
    get_parent_report,
]

DISPATCH = {fn.__name__: fn for fn in TOOLS}

# tool name → the intent label we report back in the structured response
INTENT_BY_TOOL = {
    "get_attendance": "Attendance",
    "get_marks": "Marks",
    "get_fee_status": "Fees",
    "get_homework": "Homework",
    "get_timetable": "Timetable",
    "get_academic_summary": "AcademicSummary",
    "get_parent_report": "ParentReport",
}
