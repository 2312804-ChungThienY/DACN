"""
Kiểm thử tích hợp ETL (SPEC 6.1): đối soát với Moodle, tính nhất quán, idempotency, incremental, ground truth.

Tiền điều kiện (cùng LMS_AS_OF trong .env):
    python -m mockdata.seed_structure --reset
    python -m mockdata.generate_activity --reset
    python -m etl.jobs.backfill --from 2026-09-07

Các truy vấn đối soát ở đây viết ĐỘC LẬP với etl/extract/sql (theo SPEC Phần 1) để phát hiện sai sót của ETL.
"""
from __future__ import annotations

import random
from datetime import timedelta

import pandas as pd
import psycopg
import pytest

from common.settings import TZ, resolve_as_of
from database.config import load_db_config
from etl.jobs import job_course_progress, job_student_risk, job_traffic
from mockdata import config as mock_cfg
from mockdata.generate_activity import OUTPUT_DIR

AS_OF = resolve_as_of()
AS_OF_TS = int(AS_OF.timestamp())
SNAPSHOT = AS_OF.date()


@pytest.fixture(scope="module")
def moodle():
    with psycopg.connect(**load_db_config("MOODLE_DB").conninfo(application_name="lms-etl-tests"), autocommit=True) as c:
        yield c


@pytest.fixture(scope="module")
def analytics():
    with psycopg.connect(**load_db_config("ANALYTICS_DB").conninfo(application_name="lms-etl-tests"), autocommit=True) as c:
        yield c


def frame(conn, query: str, params=None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(query, params)
        return pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])


@pytest.fixture(scope="module")
def sample_courses(analytics) -> list[int]:
    ids = [r[0] for r in analytics.execute(
        "SELECT DISTINCT course_id FROM analytics.fact_course_progress_daily WHERE stat_date = %s ORDER BY 1",
        (SNAPSHOT,))]
    assert len(ids) == 15, "Chưa chạy backfill tới AS_OF?"
    return sorted(random.Random(2026).sample(ids, 5))


# Danh sách SV hợp lệ theo đúng dạng JOIN của SPEC 1.2 (không dùng lại SQL của ETL)
SPEC_STUDENT_ENROL = """
    SELECT DISTINCT c.id AS courseid, u.id AS userid
    FROM mdl_course c
    JOIN mdl_enrol e            ON e.courseid = c.id AND e.status = 0
    JOIN mdl_user_enrolments ue ON ue.enrolid = e.id AND ue.status = 0
         AND ue.timestart <= %(as_of)s AND (ue.timeend = 0 OR ue.timeend > %(as_of)s)
    JOIN mdl_context ctx        ON ctx.instanceid = c.id AND ctx.contextlevel = 50
    JOIN mdl_role_assignments ra ON ra.contextid = ctx.id AND ra.userid = ue.userid
    JOIN mdl_role r             ON r.id = ra.roleid AND r.shortname = 'student'
    JOIN mdl_user u             ON u.id = ue.userid AND u.deleted = 0 AND u.suspended = 0
    WHERE c.id = %(course)s
"""


# ----------------------------------------------------------------------------- nhật ký ETL
def test_latest_backfill_succeeded(analytics):
    status = analytics.execute("""SELECT status FROM analytics.etl_run_log WHERE job_name = 'backfill'
                                  ORDER BY run_id DESC LIMIT 1""").fetchone()
    assert status == ("SUCCESS",)


# ----------------------------------------------------------------------------- đối soát (sai lệch = 0)
def test_reconcile_enrolled_and_active_students(moodle, analytics, sample_courses):
    for course in sample_courses:
        students = frame(moodle, SPEC_STUDENT_ENROL, {"as_of": AS_OF_TS, "course": course})
        user_ids = students["userid"].tolist()
        active = moodle.execute("""
            SELECT COUNT(DISTINCT l.userid) FROM mdl_logstore_standard_log l JOIN mdl_course c ON c.id = l.courseid
            WHERE l.courseid = %s AND l.userid = ANY(%s) AND l.anonymous = 0
              AND l.timecreated >= c.startdate AND l.timecreated <= %s""", (course, user_ids, AS_OF_TS)).fetchone()[0]
        fact = analytics.execute("""SELECT total_enrolled_students, total_active_students
            FROM analytics.fact_course_progress_daily WHERE course_id = %s AND stat_date = %s""",
                                 (course, SNAPSHOT)).fetchone()
        assert fact == (len(user_ids), active), f"course {course}"


def test_reconcile_attendance_per_student(moodle, analytics, sample_courses):
    for course in sample_courses:
        expected = frame(moodle, f"""
            WITH student_enrol AS ({SPEC_STUDENT_ENROL})
            SELECT se.userid AS user_id,
                   COUNT(s.id) AS total_sessions,
                   COUNT(s.id) FILTER (WHERE al.id IS NULL OR st.acronym = 'A') AS absent_sessions
            FROM mdl_attendance a
            JOIN mdl_attendance_sessions s ON s.attendanceid = a.id AND s.lasttaken > 0
                 AND s.lasttaken <= %(as_of)s AND s.sessdate < %(as_of)s
            JOIN student_enrol se ON se.courseid = a.course
            LEFT JOIN mdl_groups_members gm ON gm.groupid = s.groupid AND gm.userid = se.userid
            LEFT JOIN mdl_attendance_log al ON al.sessionid = s.id AND al.studentid = se.userid
            LEFT JOIN mdl_attendance_statuses st ON st.id = al.statusid
            WHERE s.groupid = 0 OR gm.id IS NOT NULL
            GROUP BY se.userid""", {"as_of": AS_OF_TS, "course": course})
        actual = frame(analytics, """SELECT user_id, total_sessions, absent_sessions
            FROM analytics.fact_student_risk_summary WHERE course_id = %s AND snapshot_date = %s AND total_sessions > 0""",
                       (course, SNAPSHOT))
        merged = expected.merge(actual, on="user_id", how="outer", suffixes=("_moodle", "_fact"), indicator=True)
        assert (merged["_merge"] == "both").all(), f"course {course}: lệch tập SV"
        assert (merged["total_sessions_moodle"] == merged["total_sessions_fact"]).all()
        assert (merged["absent_sessions_moodle"] == merged["absent_sessions_fact"]).all()


def test_reconcile_missing_assignments_per_student(moodle, analytics, sample_courses):
    for course in sample_courses:
        expected = frame(moodle, f"""
            WITH student_enrol AS ({SPEC_STUDENT_ENROL})
            SELECT se.userid AS user_id,
                   COUNT(a.id) AS total_due,
                   COUNT(a.id) FILTER (WHERE EXISTS (
                       SELECT 1 FROM mdl_assign_submission s
                       WHERE s.assignment = a.id AND s.latest = 1 AND s.status = 'submitted' AND s.timemodified <= %(as_of)s
                         AND ((a.teamsubmission = 0 AND s.userid = se.userid)
                           OR (a.teamsubmission = 1 AND s.userid = 0 AND s.groupid IN (
                                 SELECT gm.groupid FROM mdl_groups_members gm JOIN mdl_groups g ON g.id = gm.groupid
                                 WHERE g.courseid = a.course AND gm.userid = se.userid))))) AS submitted
            FROM mdl_assign a
            JOIN mdl_course_modules cm ON cm.instance = a.id AND cm.course = a.course AND cm.visible = 1
                 AND cm.deletioninprogress = 0
            JOIN mdl_modules m ON m.id = cm.module AND m.name = 'assign'
            JOIN student_enrol se ON se.courseid = a.course
            WHERE a.duedate > 0 AND a.duedate < %(as_of)s
            GROUP BY se.userid""", {"as_of": AS_OF_TS, "course": course})
        actual = frame(analytics, """SELECT user_id, total_assignments, missing_assignments_count
            FROM analytics.fact_student_risk_summary WHERE course_id = %s AND snapshot_date = %s""", (course, SNAPSHOT))
        merged = expected.merge(actual, on="user_id", how="inner")
        assert len(merged) == len(expected) == len(actual)
        assert (merged["total_due"] == merged["total_assignments"]).all()
        assert (merged["total_due"] - merged["submitted"] == merged["missing_assignments_count"]).all()


def test_reconcile_hourly_requests(moodle, analytics):
    start = AS_OF.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=3)
    expected = frame(moodle, """
        SELECT date_trunc('hour', to_timestamp(timecreated) AT TIME ZONE 'Asia/Ho_Chi_Minh') AS stat_hour,
               COUNT(*) AS n, COUNT(DISTINCT userid) FILTER (WHERE userid > 0) AS users
        FROM mdl_logstore_standard_log WHERE timecreated >= %s AND timecreated <= %s GROUP BY 1""",
                     (int(start.timestamp()), AS_OF_TS))
    actual = frame(analytics, """SELECT stat_hour, total_requests, unique_users FROM analytics.fact_server_traffic_hourly
                                 WHERE stat_hour >= %s""", (start.replace(tzinfo=None),))
    merged = actual.merge(expected, on="stat_hour", how="left").fillna(0)
    assert len(actual) == 3 * 24 + AS_OF.hour + 1, "Thiếu giờ trong chuỗi lưu lượng"
    assert (merged["total_requests"] == merged["n"]).all()
    assert (merged["unique_users"] == merged["users"]).all()


# ----------------------------------------------------------------------------- nhất quán giữa các bảng fact
def test_traffic_light_counts_match_enrolment(analytics):
    bad = analytics.execute("""SELECT COUNT(*) FROM analytics.fact_course_progress_daily
        WHERE stat_date = %s AND red_count + yellow_count + green_count <> total_enrolled_students""",
                            (SNAPSHOT,)).fetchone()[0]
    assert bad == 0


def test_risk_history_has_one_snapshot_per_day(analytics):
    days = analytics.execute("""SELECT COUNT(DISTINCT snapshot_date), MIN(snapshot_date), MAX(snapshot_date)
                                FROM analytics.fact_student_risk_summary""").fetchone()
    assert days[2] == SNAPSHOT
    assert days[0] == (days[2] - days[1]).days + 1


def test_online_samples_cover_closed_hours(analytics):
    rows = analytics.execute("""SELECT COUNT(*) FROM analytics.fact_server_traffic_hourly
        WHERE stat_hour < %s AND online_sample_count <> 12""",
                             ((AS_OF.replace(minute=0, second=0, microsecond=0)).replace(tzinfo=None),)).fetchone()[0]
    assert rows == 0
    assert analytics.execute("SELECT COUNT(*) FROM analytics.etl_online_snapshot WHERE source = 'SESSIONS'").fetchone()[0] >= 1


def test_peak_hours_are_marked(analytics):
    share = analytics.execute("SELECT AVG(is_peak_hour::int) FROM analytics.fact_server_traffic_hourly").fetchone()[0]
    assert 0.05 <= float(share) <= 0.15   # ~10% số giờ vượt P90


# ----------------------------------------------------------------------------- idempotency (SPEC 6.1)
CHECKSUM_SQL = {
    "fact_student_risk_summary": """SELECT COUNT(*), md5(string_agg(row_to_json(t)::text, '|' ORDER BY course_id, user_id, snapshot_date))
        FROM (SELECT * FROM analytics.fact_student_risk_summary) t""",
    "fact_course_progress_daily": """SELECT COUNT(*), md5(string_agg(row_to_json(t)::text, '|' ORDER BY course_id, stat_date))
        FROM (SELECT * FROM analytics.fact_course_progress_daily) t""",
    "fact_server_traffic_hourly": """SELECT COUNT(*), md5(string_agg(row_to_json(t)::text, '|' ORDER BY stat_hour))
        FROM (SELECT * FROM analytics.fact_server_traffic_hourly) t""",
}


def test_rerunning_jobs_is_idempotent(analytics):
    before = {t: analytics.execute(q).fetchone() for t, q in CHECKSUM_SQL.items()}
    for job in (job_student_risk, job_course_progress, job_traffic):
        stats = job.run(AS_OF)
        assert stats is not None and stats.rows_loaded == 0, f"{job.JOB_NAME} thay đổi dữ liệu khi chạy lại"
    after = {t: analytics.execute(q).fetchone() for t, q in CHECKSUM_SQL.items()}
    assert before == after


# ----------------------------------------------------------------------------- incremental (SPEC 6.1)
def test_incremental_traffic_updates_only_new_hour(moodle, analytics):
    hour = AS_OF.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    hour_naive = hour.replace(tzinfo=None)
    baseline = analytics.execute("SELECT stat_hour, total_requests FROM analytics.fact_server_traffic_hourly ORDER BY 1").fetchall()
    old_watermark = analytics.execute("SELECT last_log_id FROM analytics.etl_watermark WHERE job_name = 'traffic'").fetchone()[0]
    max_id = moodle.execute("SELECT MAX(id) FROM mdl_logstore_standard_log").fetchone()[0]
    inserted = 1000
    moodle.execute("""
        INSERT INTO mdl_logstore_standard_log (eventname, component, action, target, crud, edulevel, contextid,
            contextlevel, contextinstanceid, userid, courseid, anonymous, other, timecreated, origin, ip)
        SELECT '\\core\\event\\course_viewed', 'core', 'viewed', 'course', 'r', 2, 1, 10, 0, 0, 0, 0, 'null',
               %s + g, 'web', '10.99.250.1'
        FROM generate_series(1, %s) g""", (int(hour.timestamp()), inserted))
    # id lấy từ sequence nên có thể không liền mạch (sequence không lùi khi xóa) -> đọc lại MAX(id) thực tế
    new_max_id = moodle.execute("SELECT MAX(id) FROM mdl_logstore_standard_log").fetchone()[0]
    try:
        assert job_traffic.run(AS_OF) is not None
        after = dict(analytics.execute("SELECT stat_hour, total_requests FROM analytics.fact_server_traffic_hourly").fetchall())
        changed = {h for h, n in baseline if after[h] != n}
        assert changed == {hour_naive}
        assert after[hour_naive] == dict(baseline)[hour_naive] + inserted
        new_watermark = analytics.execute("SELECT last_log_id FROM analytics.etl_watermark WHERE job_name = 'traffic'").fetchone()[0]
        assert new_watermark == new_max_id > old_watermark
    finally:
        moodle.execute("DELETE FROM mdl_logstore_standard_log WHERE id > %s", (max_id,))
        job_traffic.run(AS_OF)   # giờ bị ảnh hưởng nằm trong "giờ trước" nên được tính lại về số liệu gốc
    restored = analytics.execute("SELECT stat_hour, total_requests FROM analytics.fact_server_traffic_hourly ORDER BY 1").fetchall()
    assert restored == baseline


# ----------------------------------------------------------------------------- ground truth (SPEC 6.1)
def test_ground_truth_precision_recall(analytics, capsys):
    truth = pd.read_csv(OUTPUT_DIR / "ground_truth_profiles.csv").rename(columns={"courseid": "course_id", "userid": "user_id"})
    predicted = frame(analytics, """SELECT course_id, user_id, risk_level FROM analytics.fact_student_risk_summary
                                    WHERE snapshot_date = %s""", (SNAPSHOT,))
    merged = truth.merge(predicted, on=["course_id", "user_id"], how="inner")
    matrix = pd.crosstab(merged["profile"], merged["risk_level"], rownames=["ground truth"], colnames=["ETL"])
    tp = ((merged["profile"] == "RED") & (merged["risk_level"] == "RED")).sum()
    recall = tp / (merged["profile"] == "RED").sum()
    precision = tp / (merged["risk_level"] == "RED").sum()
    with capsys.disabled():
        print(f"\nMa trận nhầm lẫn tại {SNAPSHOT} ({len(merged)} cặp SV–môn):\n{matrix}\n"
              f"RED recall = {recall:.1%}, precision = {precision:.1%}")
    assert recall >= 0.90, f"Recall(RED) = {recall:.1%} < 90%"
    assert precision >= 0.80, f"Precision(RED) = {precision:.1%} < 80%"
