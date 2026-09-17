"""
Truy vấn cho Giảng viên 2.1 (cảnh báo) và 2.2 (tiến độ, so sánh).

Mọi truy vấn trên bảng fact đều kèm điều kiện teacher_ids @> ARRAY[:teacher_id] (phân quyền ngay trong dữ liệu –
SPEC 2.1), bên cạnh bước kiểm tra quyền ở tầng API. Toán tử @> dùng được GIN index (còn = ANY() thì không).
Bảng cảnh báo dùng snapshot MỚI NHẤT CỦA MÔN: SV đã hủy/hết hạn ghi danh không còn trong snapshot đó nên
không hiện lên (view v_student_risk_latest lấy bản mới nhất theo từng SV nên vẫn giữ các SV này).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Connection

from backend.app.core.db import fetch_all, fetch_one, fetch_value
from backend.app.repositories._sql import LEVEL_RANK, like_pattern, offset, order_by, where
from backend.app.repositories.admin import latest_courses_cte

TEACHER_FILTER = "teacher_ids @> ARRAY[CAST(:teacher_id AS integer)]"
CRITERION_COLUMNS = {"attendance": "score_attendance", "inactivity": "score_inactivity",
                     "assignment": "score_assignment"}


def teacher_courses(conn: Connection, teacher_id: int, today: date, academic_year: str | None,
                    semester: int | None) -> list[dict]:
    term = academic_year is not None and semester is not None
    return fetch_all(conn, f"""
        WITH {latest_courses_cte(term=term, teacher=True)}
        SELECT course_id, course_shortname AS shortname, course_fullname AS fullname, faculty_name, category_name,
               academic_year, semester, stat_date,
               total_enrolled_students AS enrolled, total_active_students AS active,
               red_count AS red, yellow_count AS yellow, green_count AS green,
               avg_completion_rate, assignment_submission_rate, attendance_rate
        FROM latest
        ORDER BY academic_year DESC, semester DESC, course_shortname""",
        {"teacher_id": teacher_id, "today": today, "ay": academic_year, "sem": semester})


def course_teacher_ids(conn: Connection, course_id: int, today: date) -> list[int] | None:
    """teacher_ids của dòng tiến độ mới nhất; None nếu môn không có dữ liệu."""
    row = fetch_one(conn, """
        SELECT teacher_ids FROM analytics.fact_course_progress_daily
        WHERE course_id = :course_id AND stat_date <= :today
        ORDER BY stat_date DESC LIMIT 1""", {"course_id": course_id, "today": today})
    return None if row is None else [int(t) for t in row["teacher_ids"]]


def risk_snapshot_date(conn: Connection, course_id: int, teacher_id: int, today: date) -> date | None:
    return fetch_value(conn, f"""
        SELECT MAX(snapshot_date) FROM analytics.fact_student_risk_summary
        WHERE course_id = :course_id AND snapshot_date <= :today AND {TEACHER_FILTER}""",
        {"course_id": course_id, "today": today, "teacher_id": teacher_id})


def risk_summary(conn: Connection, course_id: int, teacher_id: int, snapshot_date: date) -> dict:
    return fetch_one(conn, f"""
        SELECT COUNT(*)                                            AS total,
               COUNT(*) FILTER (WHERE risk_level = 'RED')          AS red,
               COUNT(*) FILTER (WHERE risk_level = 'YELLOW')       AS yellow,
               COUNT(*) FILTER (WHERE risk_level = 'GREEN')        AS green,
               COUNT(*) FILTER (WHERE score_attendance > 0)        AS attendance,
               COUNT(*) FILTER (WHERE score_inactivity > 0)        AS inactivity,
               COUNT(*) FILTER (WHERE score_assignment > 0)        AS assignment,
               COUNT(*) FILTER (WHERE score_attendance = 2)        AS attendance_red,
               COUNT(*) FILTER (WHERE score_inactivity = 2)        AS inactivity_red,
               COUNT(*) FILTER (WHERE score_assignment = 2)        AS assignment_red,
               COUNT(*) FILTER (WHERE attendance_status = 'NO_DATA') AS attendance_no_data
        FROM analytics.fact_student_risk_summary
        WHERE course_id = :course_id AND snapshot_date = :snapshot_date AND {TEACHER_FILTER}""",
        {"course_id": course_id, "snapshot_date": snapshot_date, "teacher_id": teacher_id})


STUDENT_SORTS = {
    "risk_score": "risk_score",
    "student_code": "student_code",
    "student_name": "student_name",
    "absence_rate": "absence_rate",
    "missing_assignments": "missing_assignments_count",
    # NULL = chưa từng truy cập -> coi là "lâu nhất"
    "days_since_last_access": "COALESCE(days_since_last_access, 2147483647)",
    "last_access_time": "last_access_time",
}
TIE_BREAKER = "student_code NULLS LAST, user_id"
STUDENT_LIST_COLUMNS = """user_id, student_code, student_name, email, risk_level, risk_score, risk_reasons,
       score_attendance, score_inactivity, score_assignment,
       total_sessions, attended_sessions, absent_sessions, absence_rate, attendance_status,
       total_assignments, submitted_assignments, missing_assignments_count, late_submissions, completion_rate,
       total_access_count, access_count_7d, access_count_14d, last_access_time, days_since_last_access"""


def students(conn: Connection, course_id: int, teacher_id: int, snapshot_date: date, *,
             risk_levels: list[str], criterion: str | None, search: str | None,
             sort: str, order: str, page: int, page_size: int) -> tuple[list[dict], int]:
    conditions = ["course_id = :course_id", "snapshot_date = :snapshot_date", TEACHER_FILTER]
    params: dict = {"course_id": course_id, "snapshot_date": snapshot_date, "teacher_id": teacher_id}
    if risk_levels:
        conditions.append("risk_level = ANY(CAST(:levels AS text[]))")
        params["levels"] = risk_levels
    if criterion:
        conditions.append(f"{CRITERION_COLUMNS[criterion]} > 0")
    if search:
        conditions.append("(student_code ILIKE :q OR student_name ILIKE :q OR email ILIKE :q)")
        params["q"] = like_pattern(search)
    condition = where(conditions)

    if sort == "risk":   # mặc định (SPEC 2.4): ĐỎ -> VÀNG -> XANH, trong cùng mức điểm cao trước
        ordering = (f"{LEVEL_RANK} ASC, risk_score DESC" if order == "desc" else f"{LEVEL_RANK} DESC, risk_score ASC")
        ordering += f", {TIE_BREAKER}"
    else:
        ordering = order_by(sort, order, STUDENT_SORTS, TIE_BREAKER)

    total = int(fetch_value(conn, f"SELECT COUNT(*) FROM analytics.fact_student_risk_summary WHERE {condition}", params))
    items = fetch_all(conn, f"""
        SELECT {STUDENT_LIST_COLUMNS}
        FROM analytics.fact_student_risk_summary
        WHERE {condition}
        ORDER BY {ordering}
        LIMIT :limit OFFSET :offset""", {**params, "limit": page_size, "offset": offset(page, page_size)})
    return items, total


def student_detail(conn: Connection, course_id: int, user_id: int, teacher_id: int, snapshot_date: date) -> dict | None:
    return fetch_one(conn, f"""
        SELECT snapshot_date, course_id, course_shortname, course_fullname, faculty_name, academic_year, semester,
               {STUDENT_LIST_COLUMNS}, active_actions, weekly_activity, assignment_detail, class_avg_access, updated_at
        FROM analytics.fact_student_risk_summary
        WHERE course_id = :course_id AND user_id = :user_id AND snapshot_date = :snapshot_date AND {TEACHER_FILTER}""",
        {"course_id": course_id, "user_id": user_id, "snapshot_date": snapshot_date, "teacher_id": teacher_id})


def risk_history(conn: Connection, course_id: int, user_id: int, teacher_id: int, today: date) -> list[dict]:
    return fetch_all(conn, f"""
        SELECT snapshot_date AS date, risk_level, risk_score, score_attendance, score_inactivity, score_assignment
        FROM analytics.fact_student_risk_summary
        WHERE user_id = :user_id AND course_id = :course_id AND snapshot_date <= :today AND {TEACHER_FILTER}
        ORDER BY snapshot_date""",
        {"course_id": course_id, "user_id": user_id, "teacher_id": teacher_id, "today": today})


def interventions(conn: Connection, course_id: int, user_id: int) -> list[dict]:
    """Can thiệp của mọi GV trong môn với SV (GV đồng giảng dạy thấy được lịch sử của nhau)."""
    return fetch_all(conn, """
        SELECT i.id, i.action_type, i.content, i.risk_level_at_time, i.created_at,
               i.teacher_id, u.full_name AS teacher_name
        FROM analytics.intervention_log i
        LEFT JOIN analytics.app_user u ON u.user_id = i.teacher_id
        WHERE i.course_id = :course_id AND i.user_id = :user_id
        ORDER BY i.created_at DESC, i.id DESC""", {"course_id": course_id, "user_id": user_id})


def create_intervention(conn: Connection, course_id: int, user_id: int, teacher_id: int, action_type: str,
                        content: str | None, risk_level: str | None) -> dict:
    row = fetch_one(conn, """
        INSERT INTO analytics.intervention_log (course_id, user_id, teacher_id, action_type, content, risk_level_at_time)
        VALUES (:course_id, :user_id, :teacher_id, :action_type, :content, :risk_level)
        RETURNING id, created_at""",
        {"course_id": course_id, "user_id": user_id, "teacher_id": teacher_id, "action_type": action_type,
         "content": content, "risk_level": risk_level})
    conn.commit()
    return row


PROGRESS_METRICS = """total_enrolled_students AS enrolled, active_students_day, active_students_7d,
       total_active_students, total_views_day, total_actions_day, submissions_day, total_assignments,
       avg_completion_rate, assignment_submission_rate, attendance_rate, avg_access_per_student,
       red_count, yellow_count, green_count"""


def progress_latest(conn: Connection, course_id: int, teacher_id: int, today: date) -> dict | None:
    return fetch_one(conn, f"""
        SELECT stat_date, {PROGRESS_METRICS}, section_progress
        FROM analytics.fact_course_progress_daily
        WHERE course_id = :course_id AND stat_date <= :today AND {TEACHER_FILTER}
        ORDER BY stat_date DESC LIMIT 1""", {"course_id": course_id, "today": today, "teacher_id": teacher_id})


def progress_daily(conn: Connection, course_id: int, teacher_id: int, today: date) -> list[dict]:
    return fetch_all(conn, f"""
        SELECT stat_date AS period_start, stat_date AS period_end, to_char(stat_date, 'YYYY-MM-DD') AS period,
               {PROGRESS_METRICS}
        FROM analytics.fact_course_progress_daily
        WHERE course_id = :course_id AND stat_date <= :today AND {TEACHER_FILTER}
        ORDER BY stat_date""", {"course_id": course_id, "today": today, "teacher_id": teacher_id})


def progress_weekly(conn: Connection, course_id: int, teacher_id: int, today: date) -> list[dict]:
    """
    Một dòng mỗi tuần ISO: chỉ số trạng thái (tỷ lệ, SV hoạt động 7 ngày, đèn) lấy tại NGÀY CUỐI của tuần
    (snapshot Chủ nhật 23:59:59 bao trọn Thứ 2–Chủ nhật); lượt xem/thao tác/bài nộp cộng dồn trong tuần.
    """
    return fetch_all(conn, f"""
        SELECT DISTINCT ON (date_trunc('week', stat_date))
               date_trunc('week', stat_date)::date                             AS period_start,
               stat_date                                                       AS period_end,
               to_char(stat_date, 'IYYY-"W"IW')                                AS period,
               total_enrolled_students AS enrolled,
               MAX(active_students_day) OVER w                                 AS active_students_day,
               active_students_7d, total_active_students,
               SUM(total_views_day) OVER w                                     AS total_views_day,
               SUM(total_actions_day) OVER w                                   AS total_actions_day,
               SUM(submissions_day) OVER w                                     AS submissions_day,
               total_assignments, avg_completion_rate, assignment_submission_rate, attendance_rate,
               avg_access_per_student, red_count, yellow_count, green_count
        FROM analytics.fact_course_progress_daily
        WHERE course_id = :course_id AND stat_date <= :today AND {TEACHER_FILTER}
        WINDOW w AS (PARTITION BY date_trunc('week', stat_date))
        ORDER BY date_trunc('week', stat_date), stat_date DESC""",
        {"course_id": course_id, "today": today, "teacher_id": teacher_id})


def compare(conn: Connection, course_id: int, user_id: int, teacher_id: int, snapshot_date: date) -> dict | None:
    """
    Chỉ số của SV so với lớp tại cùng snapshot. Tỷ lệ nộp bài / chuyên cần / hoàn thành của lớp lấy từ
    fact_course_progress_daily cùng ngày để khớp với trang Tiến độ lớp.
    """
    return fetch_one(conn, f"""
        WITH cls AS (
            SELECT ROUND(AVG(access_count_14d), 2)   AS access_14d,
                   ROUND(AVG(total_access_count), 2) AS total_access
            FROM analytics.fact_student_risk_summary
            WHERE course_id = :course_id AND snapshot_date = :snapshot_date AND {TEACHER_FILTER}
        ), progress AS (
            SELECT assignment_submission_rate, attendance_rate, avg_completion_rate
            FROM analytics.fact_course_progress_daily
            WHERE course_id = :course_id AND stat_date <= :snapshot_date AND {TEACHER_FILTER}
            ORDER BY stat_date DESC LIMIT 1
        )
        SELECT s.access_count_14d, s.total_access_count, s.total_assignments, s.total_sessions,
               CASE WHEN s.total_assignments > 0
                    THEN ROUND(100.0 * s.submitted_assignments / s.total_assignments, 2) END AS submission_rate,
               CASE WHEN s.total_sessions > 0
                    THEN ROUND(100.0 * s.attended_sessions / s.total_sessions, 2) END       AS attendance_rate,
               s.completion_rate,
               cls.access_14d AS class_access_14d, cls.total_access AS class_total_access,
               p.assignment_submission_rate AS class_submission_rate,
               p.attendance_rate AS class_attendance_rate,
               p.avg_completion_rate AS class_completion_rate
        FROM analytics.fact_student_risk_summary s
        CROSS JOIN cls
        LEFT JOIN progress p ON TRUE
        WHERE s.course_id = :course_id AND s.user_id = :user_id AND s.snapshot_date = :snapshot_date
          AND s.{TEACHER_FILTER}""",
        {"course_id": course_id, "user_id": user_id, "snapshot_date": snapshot_date, "teacher_id": teacher_id})
