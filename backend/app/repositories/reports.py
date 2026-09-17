"""
Admin 1.3 – định nghĩa báo cáo (cột + truy vấn) dùng chung cho Data Preview và Export Excel/PDF.

Báo cáo không đọc Moodle, chỉ đọc 3 bảng fact (SPEC 1.5), lọc theo khoa, năm học, học kỳ, môn, mức rủi ro,
khoảng ngày. Mỗi báo cáo dựng một câu SELECT (chưa ORDER BY) từ các đoạn SQL tĩnh + tham số bind.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import Connection

from backend.app.core.db import fetch_all, fetch_value
from backend.app.repositories._sql import LEVEL_RANK, offset, where

REPORT_TRAFFIC_MAX_DAYS = 366


@dataclass(frozen=True)
class Column:
    key: str
    title: str
    kind: str = "text"      # text | int | decimal | percent | date | datetime | bool | list | risk_level | days
    width: float = 1.0      # tỷ lệ độ rộng tương đối khi xuất PDF/Excel


@dataclass
class ReportFilters:
    report_type: str
    academic_year: str | None = None
    semester: int | None = None
    faculty_id: int | None = None
    course_id: int | None = None
    risk_level: str | None = None
    from_date: date | None = None
    to_date: date | None = None
    teacher_id: int | None = None          # chỉ dùng cho export của giảng viên (phân quyền dữ liệu)


@dataclass(frozen=True)
class ReportQuery:
    sql: str
    order: str
    params: dict = field(default_factory=dict)


# Độ rộng tương đối được chọn để trên PDF A4 ngang không từ nào (tiêu đề, email, tên khoa) bị ngắt giữa chừng
ENROLLMENT_COLUMNS = (
    Column("faculty_name", "Khoa", width=1.3),
    Column("category_name", "Bộ môn", width=1.5),
    Column("course_shortname", "Mã môn", width=0.6),
    Column("course_fullname", "Tên môn", width=1.9),
    Column("total_enrolled_students", "SV đăng ký", "int", 0.7),
    Column("total_active_students", "SV tương tác", "int", 0.7),
    Column("inactive_students", "SV không tương tác", "int", 0.8),
    Column("active_rate", "Tỷ lệ tương tác (%)", "percent", 0.8),
    Column("assignment_submission_rate", "Nộp bài (%)", "percent", 0.7),
    Column("attendance_rate", "Chuyên cần (%)", "percent", 0.7),
    Column("avg_completion_rate", "Hoàn thành (%)", "percent", 0.7),
    Column("red_count", "Đỏ", "int", 0.55),
    Column("yellow_count", "Vàng", "int", 0.6),
    Column("green_count", "Xanh", "int", 0.6),
    Column("stat_date", "Ngày số liệu", "date", 0.75),
)

RISK_COLUMNS = (
    Column("faculty_name", "Khoa", width=1.2),
    Column("course_shortname", "Mã môn", width=0.6),
    Column("student_code", "MSSV", width=0.7),
    Column("student_name", "Họ tên", width=1.35),
    Column("email", "Email", width=1.85),
    Column("risk_level", "Mức rủi ro", "risk_level", 0.85),
    Column("risk_score", "Điểm", "int", 0.55),
    Column("absence_rate", "Vắng (%)", "percent", 0.6),
    Column("attendance_ratio", "Có mặt / số buổi", width=0.75),
    Column("missing_ratio", "Bài thiếu / tới hạn", width=0.75),
    Column("days_since_last_access", "Ngày chưa truy cập", "days", 0.8),
    Column("risk_reasons", "Lý do", "list", 2.35),
    Column("snapshot_date", "Ngày số liệu", "date", 0.75),
)

TRAFFIC_COLUMNS = (
    Column("stat_hour", "Giờ", "datetime", 1.2),
    Column("total_requests", "Requests", "int"),
    Column("unique_users", "Người dùng", "int"),
    Column("login_count", "Đăng nhập", "int"),
    Column("failed_login_count", "Đăng nhập lỗi", "int"),
    Column("ws_requests", "Từ app di động", "int"),
    Column("peak_online_users", "Online cao nhất", "int"),
    Column("avg_online_users", "Online trung bình", "decimal"),
    Column("is_peak_hour", "Giờ cao điểm", "bool", 0.8),
)

REPORTS: dict[str, tuple[str, tuple[Column, ...]]] = {
    "enrollment": ("Báo cáo quy mô đào tạo và tương tác môn học", ENROLLMENT_COLUMNS),
    "risk": ("Báo cáo cảnh báo sinh viên nguy cơ", RISK_COLUMNS),
    "traffic": ("Báo cáo lưu lượng truy cập theo giờ", TRAFFIC_COLUMNS),
}


def report_title(report_type: str) -> str:
    return REPORTS[report_type][0]


def report_columns(report_type: str) -> tuple[Column, ...]:
    return REPORTS[report_type][1]


def _snapshot_day(f: ReportFilters, today: date) -> date:
    return min(f.to_date, today) if f.to_date else today


def _enrollment(f: ReportFilters, today: date) -> ReportQuery:
    conditions = ["stat_date <= :snapshot", "academic_year = :ay", "semester = :sem"]
    params = {"snapshot": _snapshot_day(f, today), "ay": f.academic_year, "sem": f.semester}
    if f.faculty_id is not None:
        conditions.append("faculty_id = :faculty_id")
        params["faculty_id"] = f.faculty_id
    if f.course_id is not None:
        conditions.append("course_id = :course_id")
        params["course_id"] = f.course_id
    sql = f"""
        WITH latest AS (
            SELECT DISTINCT ON (course_id) *
            FROM analytics.fact_course_progress_daily
            WHERE {where(conditions)}
            ORDER BY course_id, stat_date DESC)
        SELECT faculty_id, faculty_name, category_name, course_id, course_shortname, course_fullname,
               total_enrolled_students, total_active_students,
               total_enrolled_students - total_active_students AS inactive_students,
               COALESCE(ROUND(100.0 * total_active_students / NULLIF(total_enrolled_students, 0), 2), 0) AS active_rate,
               assignment_submission_rate, attendance_rate, avg_completion_rate,
               red_count, yellow_count, green_count, stat_date
        FROM latest"""
    return ReportQuery(sql, "faculty_name, category_name, course_shortname, course_id", params)


def _risk(f: ReportFilters, today: date) -> ReportQuery:
    course_conditions = ["stat_date <= :snapshot"]
    params: dict = {"snapshot": _snapshot_day(f, today)}
    if f.academic_year is not None and f.semester is not None:
        course_conditions += ["academic_year = :ay", "semester = :sem"]
        params.update(ay=f.academic_year, sem=f.semester)
    if f.faculty_id is not None:
        course_conditions.append("faculty_id = :faculty_id")
        params["faculty_id"] = f.faculty_id
    if f.course_id is not None:
        course_conditions.append("course_id = :course_id")
        params["course_id"] = f.course_id
    row_conditions = []
    if f.teacher_id is not None:
        course_conditions.append("teacher_ids @> ARRAY[CAST(:teacher_id AS integer)]")
        row_conditions.append("f.teacher_ids @> ARRAY[CAST(:teacher_id AS integer)]")
        params["teacher_id"] = f.teacher_id
    if f.risk_level is not None:
        row_conditions.append("f.risk_level = :risk_level")
        params["risk_level"] = f.risk_level
    sql = f"""
        WITH courses AS (
            SELECT DISTINCT course_id FROM analytics.fact_course_progress_daily
            WHERE {where(course_conditions)}
        ), snap AS (
            SELECT c.course_id,
                   (SELECT MAX(x.snapshot_date) FROM analytics.fact_student_risk_summary x
                    WHERE x.course_id = c.course_id AND x.snapshot_date <= :snapshot) AS snapshot_date
            FROM courses c
        )
        SELECT f.faculty_name, f.course_id, f.course_shortname, f.course_fullname, f.user_id,
               f.student_code, f.student_name, f.email, f.risk_level, f.risk_score,
               {LEVEL_RANK.replace('risk_level', 'f.risk_level')} AS level_rank,
               f.absence_rate, f.attended_sessions, f.total_sessions,
               f.attended_sessions || '/' || f.total_sessions AS attendance_ratio,
               f.missing_assignments_count, f.total_assignments,
               f.missing_assignments_count || '/' || f.total_assignments AS missing_ratio,
               f.days_since_last_access, f.last_access_time, f.risk_reasons, f.snapshot_date
        FROM analytics.fact_student_risk_summary f
        JOIN snap s ON s.course_id = f.course_id AND s.snapshot_date = f.snapshot_date
        WHERE {where(row_conditions)}"""
    return ReportQuery(sql, "course_shortname, level_rank, risk_score DESC, student_code, user_id", params)


def traffic_range(f: ReportFilters, today: date) -> tuple[date, date]:
    to_date = min(f.to_date or today, today)
    from_date = f.from_date or to_date - timedelta(days=6)
    return from_date, to_date


def _traffic(f: ReportFilters, today: date) -> ReportQuery:
    from_date, to_date = traffic_range(f, today)
    sql = """
        SELECT stat_hour, total_requests, unique_users, login_count, failed_login_count, ws_requests,
               peak_online_users, avg_online_users, is_peak_hour
        FROM analytics.fact_server_traffic_hourly
        WHERE stat_date >= :from_date AND stat_date <= :to_date"""
    return ReportQuery(sql, "stat_hour", {"from_date": from_date, "to_date": to_date})


_BUILDERS = {"enrollment": _enrollment, "risk": _risk, "traffic": _traffic}


def build_query(f: ReportFilters, today: date) -> ReportQuery:
    return _BUILDERS[f.report_type](f, today)


def _visible(rows: list[dict], report_type: str) -> list[dict]:
    keys = [c.key for c in report_columns(report_type)]
    extra = {"enrollment": ("faculty_id", "course_id"), "risk": ("course_id", "user_id"), "traffic": ()}[report_type]
    return [{k: r[k] for k in (*keys, *extra)} for r in rows]


def preview(conn: Connection, f: ReportFilters, today: date, page: int, page_size: int) -> tuple[list[dict], int]:
    q = build_query(f, today)
    total = int(fetch_value(conn, f"SELECT COUNT(*) FROM ({q.sql}) t", q.params))
    rows = fetch_all(conn, f"SELECT * FROM ({q.sql}) t ORDER BY {q.order} LIMIT :limit OFFSET :offset",
                     {**q.params, "limit": page_size, "offset": offset(page, page_size)})
    return _visible(rows, f.report_type), total


def rows_for_export(conn: Connection, f: ReportFilters, today: date, limit: int) -> list[dict]:
    """Tối đa limit + 1 dòng (dòng dư dùng để phát hiện vượt giới hạn)."""
    q = build_query(f, today)
    rows = fetch_all(conn, f"SELECT * FROM ({q.sql}) t ORDER BY {q.order} LIMIT :limit", {**q.params, "limit": limit + 1})
    return _visible(rows, f.report_type)
