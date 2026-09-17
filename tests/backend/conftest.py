"""
Fixture kiểm thử Backend API (SPEC 6.3).

Tiền điều kiện: CSDL phân tích đã có dữ liệu ETL tại LMS_AS_OF (python -m etl.jobs.backfill --from 2026-09-07).

Tài khoản test:
  - ADMIN "canh gác" user_id 990001 (mật khẩu biết trước) và 990002 (bị khóa) – tạo mới rồi xóa khi xong.
  - Giảng viên dùng user_id THẬT trong teacher_ids để phân quyền dữ liệu hoạt động đúng. Nếu tài khoản đó đã tồn tại
    (vd đã chạy cli sync-users) thì dùng lại và KHÔNG đổi mật khẩu; token được ký trực tiếp.
  - Can thiệp do test tạo có nội dung bắt đầu bằng TEST_MARK và bị xóa khi xong.
"""
from __future__ import annotations

import os

os.environ.setdefault("BACKEND_JWT_SECRET", "pytest-only-secret-" + "x" * 40)

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.app.core.cache import clear_cache
from backend.app.core.config import today
from backend.app.core.security import create_access_token, hash_password, login_limiter
from database.config import load_db_config

API = "/api/v1"
ADMIN_ID, INACTIVE_ID = 990_001, 990_002
ADMIN_USERNAME, ADMIN_PASSWORD = "test.admin", "Test@Admin2026"
INACTIVE_USERNAME, DEFAULT_PASSWORD = "test.inactive", "Test@Pass2026"
TEST_MARK = "[pytest]"


@pytest.fixture(scope="session")
def db():
    with psycopg.connect(**load_db_config("ANALYTICS_DB").conninfo(application_name="lms-backend-tests"),
                         autocommit=True) as conn:
        yield conn


@pytest.fixture(scope="session")
def app():
    from backend.app.main import create_app
    return create_app()


@pytest.fixture()
def client(app):
    clear_cache()
    login_limiter().clear()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def snapshot():
    return today()


@pytest.fixture(scope="session")
def courses(db, snapshot) -> list[dict]:
    """Dòng tiến độ tại AS_OF của mọi môn."""
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        rows = cur.execute("""
            SELECT course_id, course_shortname, faculty_id, teacher_ids, total_enrolled_students AS enrolled,
                   total_active_students AS active, red_count, yellow_count, green_count,
                   assignment_submission_rate, attendance_rate, avg_completion_rate
            FROM analytics.fact_course_progress_daily WHERE stat_date = %s ORDER BY course_id""", (snapshot,)).fetchall()
    assert rows, "Chưa có dữ liệu ETL tại AS_OF – hãy chạy backfill trước"
    return rows


@pytest.fixture(scope="session")
def teachers(courses) -> dict:
    """teacher: GV chính môn đầu tiên; other: một GV không dạy môn đó."""
    first = courses[0]
    teacher = first["teacher_ids"][0]
    others = sorted({t for c in courses for t in c["teacher_ids"]} - set(first["teacher_ids"]))
    assert others, "Mock data cần ít nhất 2 giảng viên"
    return {"teacher": teacher, "other": others[0], "course": first,
            "teacher_courses": [c for c in courses if teacher in c["teacher_ids"]]}


def _upsert_sentinel(db, user_id, username, password, active):
    db.execute("""
        INSERT INTO analytics.app_user (user_id, username, full_name, role, password_hash, is_active)
        VALUES (%s, %s, %s, 'ADMIN', %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username, password_hash = EXCLUDED.password_hash,
                                            is_active = EXCLUDED.is_active, role = 'ADMIN'""",
               (user_id, username, f"Kiểm thử {username}", hash_password(password), active))


def _ensure_teacher(db, user_id, created):
    row = db.execute("SELECT role, is_active FROM analytics.app_user WHERE user_id = %s", (user_id,)).fetchone()
    if row is None:
        db.execute("""INSERT INTO analytics.app_user (user_id, username, full_name, role, password_hash)
                      VALUES (%s, %s, %s, 'TEACHER', %s)""",
                   (user_id, f"test.teacher.{user_id}", f"GV kiểm thử {user_id}", hash_password(DEFAULT_PASSWORD)))
        created.append(user_id)
    elif row != ("TEACHER", True):
        pytest.fail(f"app_user {user_id} đã tồn tại nhưng không phải TEACHER đang hoạt động: {row}")


@pytest.fixture(scope="session")
def accounts(db, teachers):
    created = [ADMIN_ID, INACTIVE_ID]
    _upsert_sentinel(db, ADMIN_ID, ADMIN_USERNAME, ADMIN_PASSWORD, True)
    _upsert_sentinel(db, INACTIVE_ID, INACTIVE_USERNAME, DEFAULT_PASSWORD, False)
    _ensure_teacher(db, teachers["teacher"], created)
    _ensure_teacher(db, teachers["other"], created)
    yield teachers
    db.execute("DELETE FROM analytics.intervention_log WHERE content LIKE %s", (TEST_MARK + "%",))
    db.execute("DELETE FROM analytics.app_user WHERE user_id = ANY(%s)", (created,))


def bearer(user_id: int, role: str, **kwargs) -> dict:
    token, _ = create_access_token(user_id, role, **kwargs)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(accounts) -> dict:
    return bearer(ADMIN_ID, "ADMIN")


@pytest.fixture()
def teacher_headers(accounts) -> dict:
    return bearer(accounts["teacher"], "TEACHER")


@pytest.fixture()
def other_teacher_headers(accounts) -> dict:
    return bearer(accounts["other"], "TEACHER")
