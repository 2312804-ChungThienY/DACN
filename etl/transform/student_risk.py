"""
Transform: chỉ số từng cặp (môn, sinh viên) + chấm điểm rủi ro -> dòng fact_student_risk_summary.
Thuần pandas/Python, không truy cập CSDL.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime

import pandas as pd

from etl.config import TZ
from etl.extract.course_data import CourseDataset
from etl.transform.risk_rules import score_student
from etl.transform.semester import academic_term

WEEK_SECONDS = 7 * 86_400
ATTENDED_ACRONYMS = ("P", "L", "E")     # có mặt, trễ, vắng có phép
ABSENT_ACRONYM = "A"
KEYS = ["course_id", "user_id"]
COUNT_COLUMNS = ["total_sessions", "attended_sessions", "absent_sessions", "total_assignments",
                 "submitted_assignments", "late_submissions", "tracked_activities", "completed_activities"]

RISK_KEYS = ("course_id", "user_id", "snapshot_date")
RISK_JSON_COLUMNS = ("risk_reasons", "weekly_activity", "assignment_detail")
RISK_COLUMNS = (
    "snapshot_date", "course_id", "user_id", "faculty_id", "faculty_name", "course_shortname", "course_fullname",
    "academic_year", "semester", "teacher_ids", "student_code", "student_name", "email",
    "total_access_count", "access_count_7d", "access_count_14d", "active_actions", "last_access_time",
    "days_since_last_access", "total_sessions", "attended_sessions", "absent_sessions", "absence_rate",
    "attendance_status", "total_assignments", "submitted_assignments", "missing_assignments_count",
    "late_submissions", "completion_rate", "score_attendance", "score_inactivity", "score_assignment",
    "risk_score", "risk_level", "risk_reasons", "weekly_activity", "assignment_detail", "class_avg_access",
    "etl_run_id",
)


def percent(part: float, whole: float) -> float | None:
    """Tỷ lệ %, làm tròn 2 chữ số. Mẫu số 0 = chưa có dữ liệu -> None (lưu NULL, không phải 0% – migration V007)."""
    return round(100 * part / whole, 2) if whole else None


def student_metrics(ds: CourseDataset) -> pd.DataFrame:
    """Một dòng cho mỗi SV đang ghi danh, đủ chỉ số của 3 tiêu chí và tỷ lệ hoàn thành."""
    base = ds.enrolments[KEYS].merge(ds.interaction, on=KEYS, how="left", validate="one_to_one")

    att = ds.attendance
    attendance = (att.assign(attended=att["acronym"].isin(ATTENDED_ACRONYMS),
                             absent=att["acronym"].isna() | (att["acronym"] == ABSENT_ACRONYM))
                  .groupby(KEYS, as_index=False)
                  .agg(total_sessions=("session_id", "count"), attended_sessions=("attended", "sum"),
                       absent_sessions=("absent", "sum")))

    asg = ds.assignments
    due = asg["duedate"] < ds.as_of_ts
    submitted = asg["submitted_ts"].notna()
    submitted_late = (asg["submitted_ts"] > asg["duedate"]).fillna(False).astype(bool)
    assignments = (asg.assign(due=due, submitted_due=due & submitted, late=due & submitted & submitted_late)
                   .groupby(KEYS, as_index=False)
                   .agg(total_assignments=("due", "sum"), submitted_assignments=("submitted_due", "sum"),
                        late_submissions=("late", "sum")))

    completion = ds.completion.groupby(KEYS, as_index=False)[["tracked_activities", "completed_activities"]].sum()

    metrics = (base.merge(attendance, on=KEYS, how="left")
               .merge(assignments, on=KEYS, how="left")
               .merge(completion, on=KEYS, how="left"))
    metrics[COUNT_COLUMNS] = metrics[COUNT_COLUMNS].fillna(0).astype("int64")
    metrics["missing_assignments_count"] = metrics["total_assignments"] - metrics["submitted_assignments"]
    return metrics


def _course_weeks(course, as_of_ts: int) -> int:
    """Số tuần hiển thị trên biểu đồ hoạt động: từ tuần 1 tới tuần hiện tại (không vượt quá độ dài môn)."""
    current = max(1, (as_of_ts - int(course.startdate)) // WEEK_SECONDS + 1)
    if course.enddate and course.enddate > course.startdate:
        return int(min(current, math.ceil((course.enddate - course.startdate) / WEEK_SECONDS)))
    return int(current)


def _iso_local(epoch) -> str | None:
    if pd.isna(epoch):
        return None
    return datetime.fromtimestamp(int(epoch), TZ).isoformat()


def build_risk_rows(ds: CourseDataset, metrics: pd.DataFrame, run_id: int) -> list[dict]:
    if metrics.empty:
        return []
    as_of_ts, snapshot_date = ds.as_of_ts, ds.as_of.date()
    courses = {int(c.course_id): c for c in ds.courses.itertuples(index=False)}
    terms = {cid: academic_term(int(c.startdate)) for cid, c in courses.items()}
    people = {(int(p.course_id), int(p.user_id)): p for p in ds.enrolments.itertuples(index=False)}

    weekly: dict[tuple, dict[int, tuple[int, int]]] = defaultdict(dict)
    for w in ds.weekly_activity.itertuples(index=False):
        weekly[(int(w.course_id), int(w.user_id))][int(w.week)] = (int(w.views), int(w.actions))

    sessions_by_week: dict[tuple, dict[int, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for a in ds.attendance.itertuples(index=False):
        week = (int(a.sessdate) - int(courses[int(a.course_id)].startdate)) // WEEK_SECONDS + 1
        cell = sessions_by_week[(int(a.course_id), int(a.user_id))][week]
        cell[0] += 1
        cell[1] += int(a.acronym in ATTENDED_ACRONYMS)

    assignments: dict[tuple, list[dict]] = defaultdict(list)
    for a in ds.assignments.itertuples(index=False):
        is_submitted = not pd.isna(a.submitted_ts)
        status = "submitted" if is_submitted else ("missing" if a.duedate < as_of_ts else "not_due")
        assignments[(int(a.course_id), int(a.user_id))].append(dict(
            assign_id=int(a.assign_id), name=a.assign_name, duedate=_iso_local(a.duedate), status=status,
            submitted_at=_iso_local(a.submitted_ts), late=bool(is_submitted and a.submitted_ts > a.duedate)))

    class_median_14d = metrics.groupby("course_id")["access_count_14d"].median().to_dict()
    class_avg_access = metrics.groupby("course_id")["total_access_count"].mean().to_dict()

    rows = []
    for m in metrics.itertuples(index=False):
        key = (int(m.course_id), int(m.user_id))
        course, person = courses[key[0]], people[key]
        academic_year, semester = terms[key[0]]

        if pd.isna(m.last_access_ts):
            last_access, days_since = None, None
        else:
            last_access = datetime.fromtimestamp(int(m.last_access_ts), TZ)
            days_since = (snapshot_date - last_access.date()).days

        result = score_student(dict(
            total_sessions=m.total_sessions, absent_sessions=m.absent_sessions,
            days_since_last_access=days_since, access_count_14d=m.access_count_14d,
            total_assignments=m.total_assignments, missing_assignments_count=m.missing_assignments_count,
        ), float(class_median_14d[key[0]]))

        attendance_weeks = sessions_by_week.get(key, {})
        weekly_activity = []
        for week in range(1, _course_weeks(course, as_of_ts) + 1):
            views, actions = weekly.get(key, {}).get(week, (0, 0))
            held, present = attendance_weeks.get(week, (0, 0))
            weekly_activity.append(dict(week=week, views=views, actions=actions, sessions=held, present=present,
                                        attended=(present == held) if held else None))

        rows.append(dict(
            snapshot_date=snapshot_date, course_id=key[0], user_id=key[1],
            faculty_id=int(course.faculty_id), faculty_name=course.faculty_name,
            course_shortname=course.course_shortname, course_fullname=course.course_fullname,
            academic_year=academic_year, semester=semester, teacher_ids=[int(t) for t in course.teacher_ids],
            student_code=person.student_code, student_name=f"{person.lastname} {person.firstname}".strip(),
            email=person.email,
            total_access_count=int(m.total_access_count), access_count_7d=int(m.access_count_7d),
            access_count_14d=int(m.access_count_14d), active_actions=int(m.active_actions),
            last_access_time=last_access, days_since_last_access=days_since,
            total_sessions=int(m.total_sessions), attended_sessions=int(m.attended_sessions),
            absent_sessions=int(m.absent_sessions), absence_rate=percent(m.absent_sessions, m.total_sessions),
            attendance_status=result["attendance_status"],
            total_assignments=int(m.total_assignments), submitted_assignments=int(m.submitted_assignments),
            missing_assignments_count=int(m.missing_assignments_count), late_submissions=int(m.late_submissions),
            completion_rate=percent(m.completed_activities, m.tracked_activities),
            score_attendance=result["score_attendance"], score_inactivity=result["score_inactivity"],
            score_assignment=result["score_assignment"], risk_score=result["risk_score"],
            risk_level=result["risk_level"], risk_reasons=result["risk_reasons"],
            weekly_activity=weekly_activity, assignment_detail=assignments.get(key, []),
            class_avg_access=round(float(class_avg_access[key[0]]), 2),
            etl_run_id=run_id,
        ))
    return rows
