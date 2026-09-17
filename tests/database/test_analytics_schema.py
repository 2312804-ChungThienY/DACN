"""
Kiểm thử tích hợp schema CSDL phân tích (cần PostgreSQL và đã chạy: python -m database.migrate up).

Mỗi test chạy trong một transaction và được rollback khi kết thúc -> không để lại dữ liệu.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import psycopg
import pytest
from psycopg import errors, sql
from psycopg.types.json import Jsonb

from database.config import load_db_config
from database.migrate import discover_migrations, fetch_applied, validate_history

SCHEMA = "analytics"
# Khóa "canh gác" không bao giờ xuất hiện trong dữ liệu thật do ETL nạp -> test không va chạm dữ liệu đang có
TEST_DAY = date(2099, 1, 5)
TEST_HOUR = datetime(2099, 1, 5, 9, 0)


# ----------------------------------------------------------------------------- fixtures
@pytest.fixture(scope="session")
def connection():
    cfg = load_db_config("ANALYTICS_DB")
    with psycopg.connect(**cfg.conninfo(application_name="lms-schema-tests")) as conn:
        yield conn


@pytest.fixture()
def db(connection):
    yield connection
    connection.rollback()


def insert(conn: psycopg.Connection, table: str, row: dict) -> None:
    query = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({})").format(
        sql.Identifier(SCHEMA),
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, row)),
        sql.SQL(", ").join(sql.Placeholder() * len(row)),
    )
    conn.execute(query, list(row.values()))


def risk_row(**overrides) -> dict:
    row = {
        "snapshot_date": TEST_DAY, "course_id": 101, "user_id": 2301,
        "faculty_id": 3, "faculty_name": "Khoa Công nghệ Thông tin",
        "course_shortname": "CT101", "course_fullname": "Cơ sở dữ liệu",
        "academic_year": "2026-2027", "semester": 1, "teacher_ids": [501],
        "student_code": "2112345", "student_name": "Nguyễn Văn A", "email": "a@dlu.edu.vn",
        "total_access_count": 40, "access_count_7d": 1, "access_count_14d": 3, "active_actions": 2,
        "last_access_time": datetime(2026, 8, 29, 1, 0, tzinfo=timezone.utc), "days_since_last_access": 16,
        "total_sessions": 12, "attended_sessions": 7, "absent_sessions": 5,
        "absence_rate": 41.67, "attendance_status": "CRITICAL",
        "total_assignments": 5, "submitted_assignments": 1, "missing_assignments_count": 4,
        "late_submissions": 0, "completion_rate": 20,
        "score_attendance": 2, "score_inactivity": 2, "score_assignment": 2,
        "risk_score": 100, "risk_level": "RED",
        "risk_reasons": Jsonb(["Vắng 5/12 buổi (42%)", "Thiếu 4/5 bài tập"]),
        "weekly_activity": Jsonb([{"week": 1, "views": 12, "actions": 2, "attended": True}]),
        "assignment_detail": Jsonb([]),
        "class_avg_access": 24.6,
    }
    row.update(overrides)
    return row


def progress_row(**overrides) -> dict:
    row = {
        "stat_date": TEST_DAY, "course_id": 101,
        "faculty_id": 3, "faculty_name": "Khoa Công nghệ Thông tin",
        "category_id": 12, "category_name": "CNTT - HK1 2026-2027",
        "course_shortname": "CT101", "course_fullname": "Cơ sở dữ liệu",
        "academic_year": "2026-2027", "semester": 1, "teacher_ids": [501],
        "total_enrolled_students": 62, "active_students_day": 20, "active_students_7d": 45,
        "total_active_students": 55, "total_views_day": 800, "total_actions_day": 60, "submissions_day": 12,
        "total_assignments": 5, "assignment_submission_rate": 78.5, "attendance_rate": 88.1,
        "avg_completion_rate": 71.2, "avg_access_per_student": 24.6,
        "red_count": 7, "yellow_count": 12, "green_count": 43,
        "section_progress": Jsonb([{"section": 1, "name": "Chương 1", "completion_rate": 92.0}]),
    }
    row.update(overrides)
    return row


def traffic_row(**overrides) -> dict:
    row = {
        "stat_hour": TEST_HOUR, "total_requests": 15320, "unique_users": 930,
        "login_count": 400, "failed_login_count": 12, "ws_requests": 50,
        "peak_online_users": 265, "avg_online_users": 210.5, "online_sample_count": 12,
    }
    row.update(overrides)
    return row


# ----------------------------------------------------------------------------- structure
def test_migration_history_matches_files(db):
    migrations = discover_migrations("analytics")
    applied = fetch_applied(db)
    validate_history(migrations, applied)
    assert sorted(applied) == [m.version for m in migrations], "Còn migration chưa áp dụng – chạy: python -m database.migrate up"


def test_tables_and_views_exist(db):
    rows = db.execute(
        "SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = %s", (SCHEMA,)
    ).fetchall()
    found = {name: kind for name, kind in rows}
    for table in ("etl_run_log", "etl_watermark", "app_user", "intervention_log",
                  "fact_student_risk_summary", "fact_course_progress_daily", "fact_server_traffic_hourly"):
        assert found.get(table) == "BASE TABLE", table
    assert found.get("v_student_risk_latest") == "VIEW"


@pytest.mark.parametrize(
    ("table", "expected"),
    [
        ("fact_student_risk_summary", ["course_id", "user_id", "snapshot_date"]),
        ("fact_course_progress_daily", ["course_id", "stat_date"]),
        ("fact_server_traffic_hourly", ["stat_hour"]),
    ],
)
def test_primary_keys(db, table, expected):
    columns = db.execute(
        """
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey)
        WHERE i.indrelid = %s::regclass AND i.indisprimary
        ORDER BY array_position(i.indkey::int2[], a.attnum)
        """,
        (f"{SCHEMA}.{table}",),
    ).fetchall()
    assert [c[0] for c in columns] == expected


def test_foreign_keys(db):
    rows = db.execute(
        """
        SELECT conrelid::regclass::text, confrelid::regclass::text
        FROM pg_constraint
        WHERE contype = 'f' AND connamespace = %s::regnamespace
        """,
        (SCHEMA,),
    ).fetchall()
    assert set(rows) == {
        ("analytics.fact_student_risk_summary", "analytics.etl_run_log"),
        ("analytics.fact_course_progress_daily", "analytics.etl_run_log"),
        ("analytics.fact_server_traffic_hourly", "analytics.etl_run_log"),
        ("analytics.etl_online_snapshot", "analytics.etl_run_log"),
        ("analytics.intervention_log", "analytics.app_user"),
    }


def test_indexes_exist(db):
    names = {r[0] for r in db.execute("SELECT indexname FROM pg_indexes WHERE schemaname = %s", (SCHEMA,))}
    expected = {
        "ix_risk_course_date_level", "ix_risk_teacher_gin", "ix_risk_user", "ix_risk_faculty_term",
        "ix_risk_red_partial", "ix_risk_etl_run",
        "ix_cpd_term_faculty", "ix_cpd_date_brin", "ix_cpd_teacher_gin", "ix_cpd_etl_run",
        "ix_traffic_date_hour", "ix_traffic_brin", "ix_traffic_etl_run",
        "ix_etl_run_job_time", "ix_intervention_course_user", "ix_intervention_teacher",
    }
    assert expected <= names, f"Thiếu index: {expected - names}"


# ----------------------------------------------------------------------------- valid data
def test_valid_rows_are_accepted(db):
    insert(db, "fact_student_risk_summary", risk_row())
    insert(db, "fact_course_progress_daily", progress_row())
    insert(db, "fact_server_traffic_hourly", traffic_row())


def test_rates_without_data_are_null(db):
    """V007: chưa có buổi điểm danh / bài tới hạn / hoạt động tới hạn -> tỷ lệ NULL (không phải 0%)."""
    insert(db, "fact_student_risk_summary", risk_row(
        total_sessions=0, attended_sessions=0, absent_sessions=0, absence_rate=None, attendance_status="NO_DATA",
        score_attendance=0, completion_rate=None))
    insert(db, "fact_course_progress_daily", progress_row(
        total_assignments=0, assignment_submission_rate=None, attendance_rate=None, avg_completion_rate=None))


def test_absence_rate_null_only_without_sessions(db):
    with pytest.raises(errors.CheckViolation):
        with db.transaction():
            insert(db, "fact_student_risk_summary", risk_row(absence_rate=None))          # có 12 buổi mà NULL
    with pytest.raises(errors.CheckViolation):
        with db.transaction():
            insert(db, "fact_student_risk_summary", risk_row(
                total_sessions=0, attended_sessions=0, absent_sessions=0, absence_rate=0,
                attendance_status="NO_DATA", score_attendance=0))                          # 0 buổi mà 0%


def test_traffic_generated_columns(db):
    insert(db, "fact_server_traffic_hourly", traffic_row())
    row = db.execute(
        "SELECT stat_date, hour_of_day, day_of_week FROM analytics.fact_server_traffic_hourly WHERE stat_hour = %s",
        (TEST_HOUR,),
    ).fetchone()
    assert row == (TEST_DAY, 9, TEST_DAY.isoweekday())  # ISO: 1 = Thứ 2 ... 7 = Chủ nhật


def test_traffic_generated_columns_cannot_be_written(db):
    with pytest.raises(errors.GeneratedAlways):
        with db.transaction():
            insert(db, "fact_server_traffic_hourly", traffic_row(hour_of_day=10))


# ----------------------------------------------------------------------------- constraints
@pytest.mark.parametrize(
    "overrides",
    [
        {"risk_level": "BLUE"},
        {"semester": 4},
        {"academic_year": "2026-2028"},
        {"academic_year": "HK1-2026"},
        {"absence_rate": 120},
        {"submitted_assignments": 6, "missing_assignments_count": -1},
        {"missing_assignments_count": 3},                      # 5 - 1 phải = 4
        {"late_submissions": 2},                               # trễ > đã nộp
        {"attended_sessions": 8},                              # 8 + 5 > 12 buổi
        {"total_sessions": 0, "attended_sessions": 0, "absent_sessions": 0},  # 0 buổi nhưng không NO_DATA
        {"attendance_status": "NO_DATA"},                      # có 12 buổi mà NO_DATA
        {"days_since_last_access": None},                      # lệch cặp last_access
        {"days_since_last_access": -1},
        {"access_count_7d": 5},                                # 7 ngày > 14 ngày
        {"score_attendance": 3},
        {"risk_score": 101},
        {"teacher_ids": [501, None]},
        {"risk_reasons": Jsonb({"reason": "x"})},
        {"attendance_status": "WARN"},                         # V006: WARN phải đi với C1 = 1 (đang là 2)
        {"attendance_status": "OK"},                           # V006: OK phải đi với C1 = 0
    ],
)
def test_risk_constraints_reject_invalid_data(db, overrides):
    with pytest.raises(errors.CheckViolation):
        with db.transaction():
            insert(db, "fact_student_risk_summary", risk_row(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"total_active_students": 63},
        {"active_students_day": 50},
        {"attendance_rate": -1},
        {"red_count": -1},
        {"section_progress": Jsonb({})},
    ],
)
def test_progress_constraints_reject_invalid_data(db, overrides):
    with pytest.raises(errors.CheckViolation):
        with db.transaction():
            insert(db, "fact_course_progress_daily", progress_row(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"stat_hour": TEST_HOUR.replace(minute=30)},
        {"unique_users": 20000},
        {"login_count": 15000, "failed_login_count": 1000},
        {"avg_online_users": 300},
        {"online_sample_count": 0},
    ],
)
def test_traffic_constraints_reject_invalid_data(db, overrides):
    with pytest.raises(errors.CheckViolation):
        with db.transaction():
            insert(db, "fact_server_traffic_hourly", traffic_row(**overrides))


# ----------------------------------------------------------------------------- behaviour
def test_upsert_is_idempotent_and_trigger_sets_updated_at(db):
    upsert = """
        INSERT INTO analytics.fact_server_traffic_hourly (stat_hour, total_requests, unique_users, updated_at)
        VALUES (%s, %s, %s, '2000-01-01')
        ON CONFLICT (stat_hour) DO UPDATE
        SET total_requests = EXCLUDED.total_requests, unique_users = EXCLUDED.unique_users,
            updated_at = EXCLUDED.updated_at
    """
    hour = TEST_HOUR.replace(hour=10)
    db.execute(upsert, (hour, 100, 10))
    db.execute(upsert, (hour, 250, 20))
    rows = db.execute(
        "SELECT total_requests, unique_users, updated_at > '2001-01-01' "
        "FROM analytics.fact_server_traffic_hourly WHERE stat_hour = %s",
        (hour,),
    ).fetchall()
    assert rows == [(250, 20, True)]


def test_latest_view_returns_newest_snapshot(db):
    insert(db, "fact_student_risk_summary", risk_row(
        snapshot_date=TEST_DAY - timedelta(days=1), risk_level="GREEN", risk_score=0, attendance_status="OK",
        score_attendance=0, score_inactivity=0, score_assignment=0))
    insert(db, "fact_student_risk_summary", risk_row(snapshot_date=TEST_DAY))
    rows = db.execute(
        "SELECT snapshot_date, risk_level FROM analytics.v_student_risk_latest WHERE course_id = 101 AND user_id = 2301"
    ).fetchall()
    assert rows == [(TEST_DAY, "RED")]


def test_fact_rejects_unknown_etl_run(db):
    with pytest.raises(errors.ForeignKeyViolation):
        with db.transaction():
            insert(db, "fact_server_traffic_hourly", traffic_row(etl_run_id=999_999_999))


def test_deleting_etl_run_sets_fact_reference_null(db):
    run_id = db.execute(
        "INSERT INTO analytics.etl_run_log (job_name) VALUES ('traffic') RETURNING run_id"
    ).fetchone()[0]
    insert(db, "fact_server_traffic_hourly", traffic_row(etl_run_id=run_id))
    db.execute("DELETE FROM analytics.etl_run_log WHERE run_id = %s", (run_id,))
    ref = db.execute(
        "SELECT etl_run_id FROM analytics.fact_server_traffic_hourly WHERE stat_hour = %s",
        (TEST_HOUR,),
    ).fetchone()[0]
    assert ref is None


@pytest.mark.parametrize(
    ("row", "error"),
    [
        ({"job_name": "traffic", "status": "SUCCESS"}, errors.CheckViolation),        # SUCCESS nhưng chưa có finished_at
        ({"job_name": "traffic", "status": "FAILED", "finished_at": datetime.now(timezone.utc)}, errors.CheckViolation),
        ({"job_name": "traffic", "status": "DONE"}, errors.CheckViolation),
    ],
)
def test_etl_run_log_constraints(db, row, error):
    with pytest.raises(error):
        with db.transaction():
            insert(db, "etl_run_log", row)


@pytest.mark.parametrize(
    "row",
    [
        {"slot_start": TEST_HOUR.replace(minute=7), "online_users": 10, "source": "SESSIONS"},   # không tròn 5 phút
        {"slot_start": TEST_HOUR.replace(minute=5), "online_users": -1, "source": "SESSIONS"},
        {"slot_start": TEST_HOUR.replace(minute=5), "online_users": 10, "source": "NGINX"},
    ],
)
def test_online_snapshot_constraints(db, row):
    with pytest.raises(errors.CheckViolation):
        with db.transaction():
            insert(db, "etl_online_snapshot", row)


def test_intervention_log_constraints(db):
    with pytest.raises(errors.ForeignKeyViolation):
        with db.transaction():
            insert(db, "intervention_log", {"course_id": 101, "user_id": 2301, "teacher_id": 999_999, "action_type": "NOTE"})

    insert(db, "app_user", {"user_id": 501, "username": "gv.tranb", "role": "TEACHER", "password_hash": "x"})
    with pytest.raises(errors.CheckViolation):
        with db.transaction():
            insert(db, "intervention_log", {"course_id": 101, "user_id": 2301, "teacher_id": 501, "action_type": "SMS"})
    insert(db, "intervention_log", {"course_id": 101, "user_id": 2301, "teacher_id": 501, "action_type": "NOTE",
                                    "content": "Đã nhắc trên lớp", "risk_level_at_time": "RED"})
