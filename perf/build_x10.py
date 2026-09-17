"""
Dựng CSDL lms_analytics_x10 – bộ dữ liệu x10 để đo SQL/API (SPEC 6.2), nhân 10 lần dữ liệu của lms_analytics.

Bản sao k = 0..9 (k = 0 giữ nguyên bản gốc):
  - course_id + k·10.000, category_id + k·100, faculty_id + k·100, tên khoa/mã môn gắn hậu tố "(cơ sở k+1)"
    -> 10 khoa, 150 môn, ~23.800 lượt ghi danh, ~1,46 triệu dòng fact_student_risk_summary.
  - user_id (SV và GV) + k·1.000.000; teacher_ids dịch cùng -> phân quyền dữ liệu vẫn đúng trong từng bản sao.
  - fact_server_traffic_hourly / etl_online_snapshot giữ khóa thời gian, các số đếm ×10 (hệ thống đông gấp 10).
  - app_user: admin + các GV của từng bản sao (username gv.xxx.k, cùng mật khẩu với tài khoản gốc) cho Locust.

    python -m perf.build_x10 [--reset]
"""
from __future__ import annotations

import argparse
import sys
import time

import psycopg

from database.config import load_db_config
from perf.common import X10_ANALYTICS_DB, child_env, run

COPIES = 10
COURSE_STEP, USER_STEP, GROUP_STEP = 10_000, 1_000_000, 100
SUFFIX = "CASE WHEN k = 0 THEN '' ELSE ' (cơ sở ' || (k + 1) || ')' END"
TEACHERS = f"ARRAY(SELECT t + k * {USER_STEP} FROM unnest(s.teacher_ids) AS t)"

RISK_COLUMNS = """snapshot_date, course_id, user_id, faculty_id, faculty_name, course_shortname, course_fullname,
    academic_year, semester, teacher_ids, student_code, student_name, email, total_access_count, access_count_7d,
    access_count_14d, active_actions, last_access_time, days_since_last_access, total_sessions, attended_sessions,
    absent_sessions, absence_rate, attendance_status, total_assignments, submitted_assignments,
    missing_assignments_count, late_submissions, completion_rate, score_attendance, score_inactivity,
    score_assignment, risk_score, risk_level, risk_reasons, weekly_activity, assignment_detail, class_avg_access"""
PROGRESS_COLUMNS = """stat_date, course_id, faculty_id, faculty_name, category_id, category_name, course_shortname,
    course_fullname, academic_year, semester, teacher_ids, total_enrolled_students, active_students_day,
    active_students_7d, total_active_students, total_views_day, total_actions_day, submissions_day,
    total_assignments, assignment_submission_rate, attendance_rate, avg_completion_rate, avg_access_per_student,
    red_count, yellow_count, green_count, section_progress"""
TRAFFIC_COLUMNS = """stat_hour, total_requests, unique_users, login_count, failed_login_count, ws_requests,
    peak_online_users, avg_online_users, online_sample_count, is_peak_hour"""
ONLINE_COLUMNS = "slot_start, online_users, source"

TRANSFORMS = {
    "fact_student_risk_summary": (RISK_COLUMNS, f"""
        s.snapshot_date, s.course_id + k * {COURSE_STEP}, s.user_id + k * {USER_STEP}, s.faculty_id + k * {GROUP_STEP},
        s.faculty_name || {SUFFIX}, s.course_shortname || CASE WHEN k = 0 THEN '' ELSE '-' || (k + 1) END,
        s.course_fullname || {SUFFIX}, s.academic_year, s.semester, {TEACHERS},
        CASE WHEN k = 0 THEN s.student_code ELSE s.student_code || '.' || k END, s.student_name,
        CASE WHEN k = 0 THEN s.email ELSE k || '.' || s.email END,
        s.total_access_count, s.access_count_7d, s.access_count_14d, s.active_actions, s.last_access_time,
        s.days_since_last_access, s.total_sessions, s.attended_sessions, s.absent_sessions, s.absence_rate,
        s.attendance_status, s.total_assignments, s.submitted_assignments, s.missing_assignments_count,
        s.late_submissions, s.completion_rate, s.score_attendance, s.score_inactivity, s.score_assignment,
        s.risk_score, s.risk_level, s.risk_reasons, s.weekly_activity, s.assignment_detail, s.class_avg_access"""),
    "fact_course_progress_daily": (PROGRESS_COLUMNS, f"""
        s.stat_date, s.course_id + k * {COURSE_STEP}, s.faculty_id + k * {GROUP_STEP}, s.faculty_name || {SUFFIX},
        s.category_id + k * {GROUP_STEP}, s.category_name || {SUFFIX},
        s.course_shortname || CASE WHEN k = 0 THEN '' ELSE '-' || (k + 1) END, s.course_fullname || {SUFFIX},
        s.academic_year, s.semester, {TEACHERS}, s.total_enrolled_students, s.active_students_day,
        s.active_students_7d, s.total_active_students, s.total_views_day, s.total_actions_day, s.submissions_day,
        s.total_assignments, s.assignment_submission_rate, s.attendance_rate, s.avg_completion_rate,
        s.avg_access_per_student, s.red_count, s.yellow_count, s.green_count, s.section_progress"""),
}
# Bảng theo thời gian: một dòng mỗi khóa, nhân số đếm ×10
SCALED = {
    "fact_server_traffic_hourly": (TRAFFIC_COLUMNS, f"""
        s.stat_hour, s.total_requests * {COPIES}, s.unique_users * {COPIES}, s.login_count * {COPIES},
        s.failed_login_count * {COPIES}, s.ws_requests * {COPIES}, s.peak_online_users * {COPIES},
        s.avg_online_users * {COPIES}, s.online_sample_count, s.is_peak_hour"""),
    "etl_online_snapshot": (ONLINE_COLUMNS, f"s.slot_start, s.online_users * {COPIES}, s.source"),
}


def copy_to_staging(source: psycopg.Connection, target: psycopg.Connection, table: str, columns: str) -> int:
    staging = f"stg_{table}"
    target.execute(f"CREATE TEMP TABLE {staging} AS SELECT {columns} FROM analytics.{table} WITH NO DATA")
    rows = 0
    with source.cursor().copy(f"COPY (SELECT {columns} FROM analytics.{table}) TO STDOUT") as out, \
            target.cursor().copy(f"COPY {staging} ({columns}) FROM STDIN") as inp:
        for chunk in out:
            inp.write(chunk)
    rows = target.execute(f"SELECT COUNT(*) FROM {staging}").fetchone()[0]
    return rows


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Dựng CSDL phân tích x10 cho đo hiệu năng")
    parser.add_argument("--reset", action="store_true", help="xóa dữ liệu x10 cũ rồi dựng lại")
    args = parser.parse_args(argv)

    env = child_env(ANALYTICS_DB_NAME=X10_ANALYTICS_DB)
    run(["database.migrate", "up", "--target", "analytics"], env, label="migrate x10")

    source_cfg = load_db_config("ANALYTICS_DB")
    started = time.perf_counter()
    with psycopg.connect(**source_cfg.conninfo(application_name="lms-perf-x10")) as source, \
            psycopg.connect(**source_cfg.conninfo(dbname=X10_ANALYTICS_DB, application_name="lms-perf-x10")) as target:
        source.read_only = True
        existing = target.execute("SELECT COUNT(*) FROM analytics.fact_course_progress_daily").fetchone()[0]
        if existing and not args.reset:
            print(f"{X10_ANALYTICS_DB} đã có dữ liệu ({existing} dòng tiến độ). Dùng --reset để dựng lại.")
            return 0
        target.execute("""TRUNCATE analytics.fact_student_risk_summary, analytics.fact_course_progress_daily,
                                   analytics.fact_server_traffic_hourly, analytics.etl_online_snapshot,
                                   analytics.intervention_log, analytics.app_user, analytics.etl_run_log""")

        summary = {}
        for table, (columns, select) in {**TRANSFORMS, **SCALED}.items():
            t0 = time.perf_counter()
            copy_to_staging(source, target, table, columns)
            copies = f"CROSS JOIN generate_series(0, {COPIES - 1}) AS k" if table in TRANSFORMS else ""
            inserted = target.execute(
                f"INSERT INTO analytics.{table} ({columns}) SELECT {select} FROM stg_{table} s {copies}").rowcount
            summary[table] = inserted
            print(f"  {table:<30} {inserted:>12,} dòng  ({time.perf_counter() - t0:.1f}s)", flush=True)

        accounts = source.execute("""SELECT user_id, username, full_name, email, role, password_hash, is_active
                                     FROM analytics.app_user WHERE user_id < 900000""").fetchall()
        with target.cursor() as cur:
            for user_id, username, full_name, email, role, password_hash, is_active in accounts:
                for k in range(COPIES if role == "TEACHER" else 1):
                    cur.execute("""INSERT INTO analytics.app_user
                                   (user_id, username, full_name, email, role, password_hash, is_active)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                                (user_id + k * USER_STEP, username if k == 0 else f"{username}.{k}",
                                 full_name, email, role, password_hash, is_active))
        target.execute("""INSERT INTO analytics.etl_run_log (job_name, status, finished_at, rows_loaded)
                          VALUES ('x10_build', 'SUCCESS', clock_timestamp(), %s)""", (sum(summary.values()),))
        print(f"  app_user                       {len(accounts) and target.execute('SELECT COUNT(*) FROM analytics.app_user').fetchone()[0]:>12,} tài khoản")

    with psycopg.connect(**source_cfg.conninfo(dbname=X10_ANALYTICS_DB), autocommit=True) as conn:
        for table in (*TRANSFORMS, *SCALED, "app_user"):
            conn.execute(f"VACUUM (ANALYZE) analytics.{table}")
        size = conn.execute("SELECT pg_size_pretty(pg_database_size(current_database()))").fetchone()[0]
    print(f"Hoàn tất sau {time.perf_counter() - started:.0f}s – dung lượng {X10_ANALYTICS_DB}: {size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
