"""
Kiểm thử đơn vị Transform (student_risk, course_progress) trên bộ dữ liệu nhỏ dựng tay – không cần CSDL.

Kịch bản: môn 10 bắt đầu 07/09/2026, AS_OF = 30/09/2026 10:00 (tuần 4).
  SV 101: chăm chỉ – đi học đủ 3/3 buổi, nộp bài đúng hạn, vào môn 2 ngày trước.
  SV 102: chưa từng truy cập – vắng 2/3 buổi (1 buổi không có bản ghi, 1 buổi 'A', 1 buổi 'L'), không nộp bài.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from common.settings import TZ
from etl.extract.course_data import CourseDataset
from etl.transform.course_progress import build_progress_rows
from etl.transform.student_risk import build_risk_rows, student_metrics

START = datetime(2026, 9, 7, tzinfo=TZ)
AS_OF = datetime(2026, 9, 30, 10, 0, tzinfo=TZ)
S = int(START.timestamp())
DAY, WEEK = 86_400, 7 * 86_400
A1_DUE = S + 13 * DAY + 23 * 3600 + 59 * 60        # Chủ nhật tuần 2 – đã tới hạn
A2_DUE = S + 27 * DAY + 23 * 3600 + 59 * 60        # Chủ nhật tuần 4 – chưa tới hạn


def dataset(*, submitted_101=(A1_DUE - 3600, int(AS_OF.timestamp()) - 3600), last_access_101=int(AS_OF.timestamp()) - 2 * DAY):
    courses = pd.DataFrame([dict(course_id=10, course_shortname="IT004", course_fullname="Cơ sở dữ liệu",
                                 startdate=S, enddate=S + 15 * WEEK, category_id=3, category_name="Bộ môn HTTT",
                                 faculty_id=1, faculty_name="Khoa CNTT", teacher_ids=[5, 7])])
    enrolments = pd.DataFrame([
        dict(course_id=10, user_id=101, student_code="2212001", lastname="Nguyễn Văn", firstname="An", email="a@x.vn"),
        dict(course_id=10, user_id=102, student_code="2212002", lastname="Trần Thị", firstname="Bình", email=None),
    ])
    # Cột có thể NULL được tạo ở dạng object/None giống pandas đọc từ CSDL khi mọi giá trị NULL
    interaction = pd.DataFrame({
        "course_id": [10, 10], "user_id": [101, 102],
        "last_access_ts": pd.Series([last_access_101, None], dtype=object),
        "total_access_count": [40, 0], "access_count_7d": [10, 0], "access_count_14d": [20, 0], "active_actions": [3, 0],
        "term_access_count": [40, 0], "access_count_day": [0, 0], "views_day": [0, 0], "actions_day": [0, 0],
    })
    weekly = pd.DataFrame([dict(course_id=10, user_id=101, week=1, views=10, actions=1),
                           dict(course_id=10, user_id=101, week=3, views=5, actions=0)])
    sessions = [(1, S + DAY + 7 * 3600), (2, S + 8 * DAY + 7 * 3600), (3, S + 15 * DAY + 7 * 3600)]
    attendance = pd.DataFrame(
        [dict(course_id=10, user_id=101, session_id=sid, sessdate=t, acronym="P") for sid, t in sessions]
        + [dict(course_id=10, user_id=102, session_id=sid, sessdate=t, acronym=acr)
           for (sid, t), acr in zip(sessions, [None, "A", "L"])])
    assignments = pd.DataFrame({
        "course_id": [10] * 4, "user_id": [101, 101, 102, 102], "assign_id": [1, 2, 1, 2],
        "assign_name": ["Bài tập 1", "Bài tập 2"] * 2, "duedate": [A1_DUE, A2_DUE] * 2,
        "submitted_ts": pd.Series([submitted_101[0], submitted_101[1], None, None], dtype=object),
    })
    completion = pd.DataFrame([
        dict(course_id=10, user_id=101, section_no=1, section_name="Tuần 1", tracked_activities=2, completed_activities=2),
        dict(course_id=10, user_id=101, section_no=2, section_name="Tuần 2", tracked_activities=2, completed_activities=1),
        dict(course_id=10, user_id=102, section_no=1, section_name="Tuần 1", tracked_activities=2, completed_activities=0),
        dict(course_id=10, user_id=102, section_no=2, section_name="Tuần 2", tracked_activities=2, completed_activities=0),
    ])
    return CourseDataset(as_of=AS_OF, day_start=AS_OF.replace(hour=0), courses=courses, enrolments=enrolments,
                         interaction=interaction, weekly_activity=weekly, attendance=attendance,
                         assignments=assignments, completion=completion,
                         submissions_day=pd.DataFrame(columns=["course_id", "submissions_day"]))


def rows_by_user(ds):
    return {r["user_id"]: r for r in build_risk_rows(ds, student_metrics(ds), run_id=1)}


def test_risk_rows_for_diligent_student():
    r = rows_by_user(dataset())[101]
    assert (r["risk_level"], r["risk_score"], r["attendance_status"]) == ("GREEN", 0, "OK")
    assert (r["total_sessions"], r["attended_sessions"], r["absent_sessions"], r["absence_rate"]) == (3, 3, 0, 0.0)
    assert (r["total_assignments"], r["submitted_assignments"], r["missing_assignments_count"], r["late_submissions"]) == (1, 1, 0, 0)
    assert r["days_since_last_access"] == 2
    assert r["completion_rate"] == 75.0
    assert r["student_name"] == "Nguyễn Văn An"
    assert (r["academic_year"], r["semester"], r["teacher_ids"]) == ("2026-2027", 1, [5, 7])
    assert r["weekly_activity"] == [
        dict(week=1, views=10, actions=1, sessions=1, present=1, attended=True),
        dict(week=2, views=0, actions=0, sessions=1, present=1, attended=True),
        dict(week=3, views=5, actions=0, sessions=1, present=1, attended=True),
        dict(week=4, views=0, actions=0, sessions=0, present=0, attended=None),
    ]
    assert [(a["name"], a["status"], a["late"]) for a in r["assignment_detail"]] == \
        [("Bài tập 1", "submitted", False), ("Bài tập 2", "submitted", False)]


def test_risk_rows_for_never_accessed_student():
    r = rows_by_user(dataset())[102]
    assert (r["risk_level"], r["risk_score"], r["attendance_status"]) == ("RED", 100, "CRITICAL")
    assert (r["total_sessions"], r["attended_sessions"], r["absent_sessions"]) == (3, 1, 2)
    assert r["absence_rate"] == 66.67
    assert r["last_access_time"] is None and r["days_since_last_access"] is None
    assert r["risk_reasons"] == ["Vắng 2/3 buổi (67%)", "Chưa từng truy cập môn học", "Thiếu 1/1 bài tập"]
    assert [a["status"] for a in r["assignment_detail"]] == ["missing", "not_due"]
    assert r["class_avg_access"] == 20.0
    assert r["email"] is None


def test_all_null_epoch_columns_are_supported():
    """Hồi quy: đầu học kỳ chưa có bài nộp / chưa ai truy cập -> cột toàn NULL (kiểu object) không được làm hỏng Transform."""
    rows = rows_by_user(dataset(submitted_101=(None, None), last_access_101=None))
    assert rows[101]["days_since_last_access"] is None
    assert rows[101]["missing_assignments_count"] == 1
    assert [a["status"] for a in rows[101]["assignment_detail"]] == ["missing", "not_due"]


def test_late_submission_is_counted():
    rows = rows_by_user(dataset(submitted_101=(A1_DUE + 3600, None)))
    assert (rows[101]["submitted_assignments"], rows[101]["late_submissions"]) == (1, 1)
    assert rows[101]["assignment_detail"][0]["late"] is True


def test_progress_row():
    ds = dataset()
    [row] = build_progress_rows(ds, student_metrics(ds), {10: (1, 0, 1)}, run_id=1)
    assert row["stat_date"] == AS_OF.date()
    assert (row["total_enrolled_students"], row["active_students_day"], row["active_students_7d"],
            row["total_active_students"]) == (2, 0, 1, 1)
    assert (row["total_assignments"], row["assignment_submission_rate"]) == (1, 50.0)
    assert row["attendance_rate"] == 66.67
    assert row["avg_completion_rate"] == 37.5
    assert row["avg_access_per_student"] == 20.0
    assert (row["red_count"], row["yellow_count"], row["green_count"]) == (1, 0, 1)
    assert row["section_progress"] == [dict(section=1, name="Tuần 1", completion_rate=50.0),
                                       dict(section=2, name="Tuần 2", completion_rate=25.0)]
    assert (row["category_name"], row["faculty_name"]) == ("Bộ môn HTTT", "Khoa CNTT")


def test_progress_for_course_without_students():
    ds = dataset()
    ds.enrolments = ds.enrolments.iloc[0:0]
    ds.interaction = ds.interaction.iloc[0:0]
    ds.attendance = ds.attendance.iloc[0:0]
    ds.assignments = ds.assignments.iloc[0:0]
    ds.completion = ds.completion.iloc[0:0]
    ds.weekly_activity = ds.weekly_activity.iloc[0:0]
    metrics = student_metrics(ds)
    assert build_risk_rows(ds, metrics, run_id=1) == []
    [row] = build_progress_rows(ds, metrics, {}, run_id=1)
    assert (row["total_enrolled_students"], row["avg_access_per_student"]) == (0, 0.0)
    assert (row["attendance_rate"], row["assignment_submission_rate"], row["avg_completion_rate"]) == (None, None, None)
    assert row["section_progress"] == []


def test_rates_without_data_are_none_not_zero():
    """Chưa có buổi điểm danh / bài tới hạn / hoạt động tới hạn -> tỷ lệ None ("chưa có dữ liệu"), không phải 0%."""
    ds = dataset()
    ds.attendance = ds.attendance.iloc[0:0]
    ds.completion = ds.completion.iloc[0:0]
    ds.assignments = ds.assignments[ds.assignments["duedate"] == A2_DUE]      # chỉ còn bài chưa tới hạn
    risk = rows_by_user(ds)
    for r in risk.values():
        assert (r["total_sessions"], r["absence_rate"], r["attendance_status"]) == (0, None, "NO_DATA")
        assert (r["total_assignments"], r["completion_rate"], r["score_assignment"]) == (0, None, 0)
    [row] = build_progress_rows(ds, student_metrics(ds), {}, run_id=1)
    assert (row["attendance_rate"], row["assignment_submission_rate"], row["avg_completion_rate"]) == (None, None, None)
