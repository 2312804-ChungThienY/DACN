"""Transform: tiến độ & tương tác của từng môn học trong ngày -> dòng fact_course_progress_daily (SPEC 1.3, 1.7)."""
from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from etl.extract.course_data import CourseDataset
from etl.transform.semester import academic_term
from etl.transform.student_risk import percent

PROGRESS_KEYS = ("course_id", "stat_date")
PROGRESS_JSON_COLUMNS = ("section_progress",)
PROGRESS_COLUMNS = (
    "stat_date", "course_id", "faculty_id", "faculty_name", "category_id", "category_name", "course_shortname",
    "course_fullname", "academic_year", "semester", "teacher_ids", "total_enrolled_students",
    "active_students_day", "active_students_7d", "total_active_students", "total_views_day",
    "total_actions_day", "submissions_day", "total_assignments", "assignment_submission_rate",
    "attendance_rate", "avg_completion_rate", "avg_access_per_student", "red_count", "yellow_count",
    "green_count", "section_progress", "etl_run_id",
)


def build_progress_rows(ds: CourseDataset, metrics: pd.DataFrame,
                        risk_counts: Mapping[int, tuple[int, int, int]], run_id: int) -> list[dict]:
    """
    metrics: kết quả student_metrics(ds). risk_counts: course_id -> (red, yellow, green) từ snapshot rủi ro
    mới nhất không muộn hơn ngày thống kê.
    """
    stat_date = ds.as_of.date()
    submissions_day = dict(zip(ds.submissions_day["course_id"].astype(int), ds.submissions_day["submissions_day"]))
    due = ds.assignments[ds.assignments["duedate"] < ds.as_of_ts]
    due_assignments = due.groupby("course_id")["assign_id"].nunique().to_dict()
    sections = (ds.completion.groupby(["course_id", "section_no", "section_name"], as_index=False)
                [["tracked_activities", "completed_activities"]].sum())
    metrics_by_course = {int(cid): group for cid, group in metrics.groupby("course_id")}
    sections_by_course = {int(cid): group for cid, group in sections.groupby("course_id")}
    empty_metrics = metrics.iloc[0:0]

    rows = []
    for c in ds.courses.itertuples(index=False):
        cid = int(c.course_id)
        cm = metrics_by_course.get(cid, empty_metrics)
        academic_year, semester = academic_term(int(c.startdate))
        red, yellow, green = risk_counts.get(cid, (0, 0, 0))
        section_progress = [
            dict(section=int(s.section_no), name=s.section_name,
                 completion_rate=percent(s.completed_activities, s.tracked_activities))
            for s in sections_by_course.get(cid, sections.iloc[0:0]).sort_values("section_no").itertuples(index=False)
        ]
        rows.append(dict(
            stat_date=stat_date, course_id=cid,
            faculty_id=int(c.faculty_id), faculty_name=c.faculty_name,
            category_id=int(c.category_id), category_name=c.category_name,
            course_shortname=c.course_shortname, course_fullname=c.course_fullname,
            academic_year=academic_year, semester=semester, teacher_ids=[int(t) for t in c.teacher_ids],
            total_enrolled_students=len(cm),
            active_students_day=int((cm["access_count_day"] > 0).sum()),
            active_students_7d=int((cm["access_count_7d"] > 0).sum()),
            total_active_students=int((cm["term_access_count"] > 0).sum()),
            total_views_day=int(cm["views_day"].sum()),
            total_actions_day=int(cm["actions_day"].sum()),
            submissions_day=int(submissions_day.get(cid, 0)),
            total_assignments=int(due_assignments.get(cid, 0)),
            assignment_submission_rate=percent(cm["submitted_assignments"].sum(), cm["total_assignments"].sum()),
            attendance_rate=percent(cm["attended_sessions"].sum(), cm["total_sessions"].sum()),
            avg_completion_rate=percent(cm["completed_activities"].sum(), cm["tracked_activities"].sum()),
            avg_access_per_student=round(float(cm["total_access_count"].mean()), 2) if len(cm) else 0.0,
            red_count=red, yellow_count=yellow, green_count=green,
            section_progress=section_progress,
            etl_run_id=run_id,
        ))
    return rows
