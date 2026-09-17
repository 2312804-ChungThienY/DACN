"""
Truy vấn cho Admin 1.1 (Khoa → Môn → Sinh viên) và thẻ KPI.

Số liệu một học kỳ lấy DÒNG MỚI NHẤT của từng môn (không muộn hơn hôm nay) trong fact_course_progress_daily,
nên môn đã kết thúc trước hôm nay vẫn có mặt với số liệu chốt cuối cùng.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Connection

from backend.app.core.cache import cached
from backend.app.core.db import fetch_all, fetch_one, fetch_value
from backend.app.repositories._sql import IS_ACTIVE_IN_TERM, like_pattern, offset, order_by, where


def latest_courses_cte(*, faculty_id: int | None = None, course_id: int | None = None,
                       term: bool = True, teacher: bool = False) -> str:
    """CTE `latest`: dòng tiến độ mới nhất (<= :today) của mỗi môn. Tham số bind: :ay :sem :today [:faculty_id] ..."""
    conditions = ["stat_date <= :today"]
    if term:
        conditions += ["academic_year = :ay", "semester = :sem"]
    if faculty_id is not None:
        conditions.append("faculty_id = :faculty_id")
    if course_id is not None:
        conditions.append("course_id = :course_id")
    if teacher:
        conditions.append("teacher_ids @> ARRAY[CAST(:teacher_id AS integer)]")
    return f"""latest AS (
        SELECT DISTINCT ON (course_id) *
        FROM analytics.fact_course_progress_daily
        WHERE {where(conditions)}
        ORDER BY course_id, stat_date DESC)"""


ACTIVE_RATE = "ROUND(100.0 * total_active_students / NULLIF(total_enrolled_students, 0), 2)"


@cached
def overview_kpis(conn: Connection, academic_year: str, semester: int, faculty_id: int | None,
                  now: datetime) -> dict:
    """now: thời điểm tham chiếu (giờ địa phương, không kèm múi giờ) đã làm tròn tới phút."""
    today = now.date()
    params = {"ay": academic_year, "sem": semester, "today": today, "faculty_id": faculty_id}
    courses = fetch_one(conn, f"""
        WITH {latest_courses_cte(faculty_id=faculty_id)}
        SELECT COUNT(*)                                     AS total_courses,
               COALESCE(SUM(total_enrolled_students), 0)    AS total_enrolled,
               COALESCE(SUM(total_active_students), 0)      AS total_active,
               COALESCE(SUM(red_count), 0)                  AS red_students,
               COALESCE(SUM(yellow_count), 0)               AS yellow_students,
               COALESCE(SUM(green_count), 0)                AS green_students,
               MAX(stat_date)                               AS stat_date
        FROM latest""", params)

    day_start = datetime.combine(today, datetime.min.time())
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    peak = fetch_one(conn, """
        SELECT stat_hour, total_requests FROM analytics.fact_server_traffic_hourly
        WHERE stat_hour >= :day_start AND stat_hour <= :current_hour
        ORDER BY total_requests DESC, stat_hour
        LIMIT 1""", {"day_start": day_start, "current_hour": current_hour})
    online = fetch_one(conn, """
        SELECT slot_start, online_users FROM analytics.etl_online_snapshot
        WHERE slot_start <= :now ORDER BY slot_start DESC LIMIT 1""", {"now": now})
    avg_online = fetch_value(conn, """
        SELECT ROUND(AVG(online_users), 1) FROM analytics.etl_online_snapshot
        WHERE slot_start >= :day_start AND slot_start <= :now""", {"day_start": day_start, "now": now})

    enrolled = int(courses["total_enrolled"])
    return dict(
        academic_year=academic_year, semester=semester, faculty_id=faculty_id, stat_date=courses["stat_date"],
        total_courses=int(courses["total_courses"]), total_enrolled=enrolled,
        total_active=int(courses["total_active"]),
        active_rate=round(100 * int(courses["total_active"]) / enrolled, 2) if enrolled else 0.0,
        red_students=int(courses["red_students"]), yellow_students=int(courses["yellow_students"]),
        green_students=int(courses["green_students"]),
        red_rate=round(100 * int(courses["red_students"]) / enrolled, 2) if enrolled else 0.0,
        peak_requests_today=(dict(hour=peak["stat_hour"].strftime("%H:%M"), stat_hour=peak["stat_hour"],
                                  value=int(peak["total_requests"])) if peak else None),
        avg_online_users_today=float(avg_online) if avg_online is not None else 0.0,
        current_online=int(online["online_users"]) if online else 0,
        current_online_at=online["slot_start"] if online else None,
    )


@cached
def enrollment_by_faculty(conn: Connection, academic_year: str, semester: int, today: date) -> list[dict]:
    rows = fetch_all(conn, f"""
        WITH {latest_courses_cte()}
        SELECT faculty_id, faculty_name,
               COUNT(*)                        AS course_count,
               SUM(total_enrolled_students)    AS enrolled,
               SUM(total_active_students)      AS active,
               SUM(red_count)                  AS red_count,
               SUM(yellow_count)               AS yellow_count,
               SUM(green_count)                AS green_count
        FROM latest
        GROUP BY faculty_id, faculty_name
        ORDER BY enrolled DESC, faculty_name""", {"ay": academic_year, "sem": semester, "today": today})
    for r in rows:
        r["inactive"] = int(r["enrolled"]) - int(r["active"])
        r["active_rate"] = round(100 * int(r["active"]) / int(r["enrolled"]), 2) if r["enrolled"] else 0.0
    return rows


COURSE_SORTS = {
    "active_rate": f"COALESCE({ACTIVE_RATE}, 0)",
    "enrolled": "total_enrolled_students",
    "active": "total_active_students",
    "red_count": "red_count",
    "shortname": "course_shortname",
    "fullname": "course_fullname",
}


@cached
def faculty_courses(conn: Connection, faculty_id: int, academic_year: str, semester: int, today: date,
                    sort: str, order: str) -> list[dict]:
    return fetch_all(conn, f"""
        WITH {latest_courses_cte(faculty_id=faculty_id)}
        SELECT course_id, course_shortname AS shortname, course_fullname AS fullname,
               category_id, category_name, stat_date,
               total_enrolled_students AS enrolled,
               total_active_students   AS active,
               total_enrolled_students - total_active_students AS inactive,
               COALESCE({ACTIVE_RATE}, 0) AS active_rate,
               red_count, yellow_count, green_count,
               avg_completion_rate, assignment_submission_rate, attendance_rate
        FROM latest
        ORDER BY {order_by(sort, order, COURSE_SORTS, "course_shortname, course_id")}""",
        {"ay": academic_year, "sem": semester, "today": today, "faculty_id": faculty_id})


def latest_risk_snapshot_date(conn: Connection, course_id: int, today: date) -> date | None:
    return fetch_value(conn, """
        SELECT MAX(snapshot_date) FROM analytics.fact_student_risk_summary
        WHERE course_id = :course_id AND snapshot_date <= :today""", {"course_id": course_id, "today": today})


def course_header(conn: Connection, course_id: int, today: date) -> dict | None:
    return fetch_one(conn, """
        SELECT course_id, course_shortname AS shortname, course_fullname AS fullname, faculty_id, faculty_name,
               category_id, category_name, academic_year, semester, teacher_ids, stat_date,
               total_enrolled_students AS enrolled, total_active_students AS active
        FROM analytics.fact_course_progress_daily
        WHERE course_id = :course_id AND stat_date <= :today
        ORDER BY stat_date DESC LIMIT 1""", {"course_id": course_id, "today": today})


def course_students(conn: Connection, course_id: int, snapshot_date: date, *, status: str | None,
                    search: str | None, page: int, page_size: int) -> tuple[list[dict], int]:
    """Cấp drill-down cuối của Admin 1.1: danh sách SV của môn, lọc SV có/không tương tác."""
    conditions = ["course_id = :course_id", "snapshot_date = :snapshot_date"]
    params: dict = {"course_id": course_id, "snapshot_date": snapshot_date}
    if status == "active":
        conditions.append(IS_ACTIVE_IN_TERM)
    elif status == "inactive":
        conditions.append(f"NOT {IS_ACTIVE_IN_TERM}")
    if search:
        conditions.append("(student_code ILIKE :q OR student_name ILIKE :q OR email ILIKE :q)")
        params["q"] = like_pattern(search)
    condition = where(conditions)
    total = int(fetch_value(conn, f"SELECT COUNT(*) FROM analytics.fact_student_risk_summary WHERE {condition}", params))
    items = fetch_all(conn, f"""
        SELECT user_id, student_code, student_name, email,
               {IS_ACTIVE_IN_TERM} AS is_active,
               total_access_count, access_count_7d, last_access_time, days_since_last_access,
               risk_level, risk_score
        FROM analytics.fact_student_risk_summary
        WHERE {condition}
        ORDER BY student_code NULLS LAST, user_id
        LIMIT :limit OFFSET :offset""", {**params, "limit": page_size, "offset": offset(page, page_size)})
    return items, total


def active_counts_by_course(conn: Connection, today: date) -> dict[int, int]:
    """Số SV có tương tác theo snapshot rủi ro mới nhất của mỗi môn (dùng để đối chiếu trong kiểm thử)."""
    rows = fetch_all(conn, f"""
        WITH d AS (SELECT course_id, MAX(snapshot_date) AS snapshot_date FROM analytics.fact_student_risk_summary
                   WHERE snapshot_date <= :today GROUP BY course_id)
        SELECT f.course_id, COUNT(*) FILTER (WHERE {IS_ACTIVE_IN_TERM}) AS active
        FROM analytics.fact_student_risk_summary f JOIN d USING (course_id, snapshot_date)
        GROUP BY f.course_id""", {"today": today})
    return {int(r["course_id"]): int(r["active"]) for r in rows}
