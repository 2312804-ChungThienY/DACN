"""Truy vấn dùng chung: thời điểm dữ liệu cập nhật, bộ lọc, trạng thái ETL, học kỳ mặc định."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Connection

from backend.app.core.cache import cached
from backend.app.core.config import TZ
from backend.app.core.db import fetch_all, fetch_one, fetch_value
from etl.transform.semester import academic_term

ETL_JOBS = ("traffic", "course_progress", "student_risk", "nightly", "maintenance", "backfill")


@cached
def data_updated_at(conn: Connection) -> datetime | None:
    """Thời điểm một job ETL chạy thành công gần nhất (SPEC 5.1: mỗi response có data_updated_at)."""
    return fetch_value(conn, "SELECT MAX(finished_at) FROM analytics.etl_run_log WHERE status = 'SUCCESS'")


@cached
def current_term(conn: Connection, today: date) -> tuple[str, int]:
    """Học kỳ của dữ liệu tiến độ mới nhất tới hôm nay; CSDL trống thì suy ra từ ngày hôm nay."""
    row = fetch_one(conn, """
        SELECT academic_year, semester FROM analytics.fact_course_progress_daily
        WHERE stat_date <= :today
        ORDER BY stat_date DESC, academic_year DESC, semester DESC
        LIMIT 1""", {"today": today})
    if row is None:
        return academic_term(datetime.combine(today, datetime.min.time(), TZ))
    return str(row["academic_year"]), int(row["semester"])


@cached
def filters(conn: Connection, today: date) -> dict:
    faculties = fetch_all(conn, """
        SELECT DISTINCT faculty_id AS id, faculty_name AS name
        FROM analytics.fact_course_progress_daily WHERE stat_date <= :today
        ORDER BY name""", {"today": today})
    years = fetch_all(conn, """
        SELECT DISTINCT academic_year FROM analytics.fact_course_progress_daily
        WHERE stat_date <= :today ORDER BY academic_year DESC""", {"today": today})
    academic_year, semester = current_term(conn, today)
    return dict(faculties=faculties, academic_years=[str(r["academic_year"]) for r in years],
                semesters=[1, 2, 3], current={"academic_year": academic_year, "semester": semester})


def etl_status(conn: Connection) -> list[dict]:
    return fetch_all(conn, """
        SELECT j.job_name,
               (SELECT MAX(r.finished_at) FROM analytics.etl_run_log r
                WHERE r.job_name = j.job_name AND r.status = 'SUCCESS') AS last_success_at,
               last.status, last.started_at, last.finished_at
        FROM unnest(CAST(:jobs AS text[])) AS j(job_name)
        LEFT JOIN LATERAL (
            SELECT status, started_at, finished_at FROM analytics.etl_run_log r
            WHERE r.job_name = j.job_name ORDER BY started_at DESC LIMIT 1) last ON TRUE
        ORDER BY array_position(CAST(:jobs AS text[]), j.job_name)""", {"jobs": list(ETL_JOBS)})
