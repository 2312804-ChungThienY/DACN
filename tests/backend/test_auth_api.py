"""Xác thực, phân quyền 401/403, giới hạn đăng nhập sai, endpoint dùng chung (SPEC 6.3)."""
from __future__ import annotations

from tests.backend.conftest import (ADMIN_ID, ADMIN_PASSWORD, ADMIN_USERNAME, API, DEFAULT_PASSWORD, INACTIVE_ID,
                                    INACTIVE_USERNAME, bearer)


def test_health_does_not_require_login(client):
    body = client.get(f"{API}/health").json()
    assert body["status"] == "ok" and body["database"] is True
    assert body["as_of"].startswith("2026-11-06") or not body["clock_frozen"]


def test_login_success_and_me(client, accounts):
    res = client.post(f"{API}/auth/login", json={"username": ADMIN_USERNAME.upper(), "password": ADMIN_PASSWORD})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["token_type"] == "bearer" and body["expires_in"] > 0
    assert body["user"] == {"id": ADMIN_ID, "username": ADMIN_USERNAME, "full_name": f"Kiểm thử {ADMIN_USERNAME}",
                            "email": None, "role": "ADMIN"}
    me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["role"] == "ADMIN"
    assert "X-Process-Time-Ms" in me.headers


def test_login_failures_do_not_reveal_which_part_is_wrong(client, accounts):
    wrong_password = client.post(f"{API}/auth/login", json={"username": ADMIN_USERNAME, "password": "sai-mat-khau"})
    unknown_user = client.post(f"{API}/auth/login", json={"username": "khong.ton.tai", "password": "sai-mat-khau"})
    inactive = client.post(f"{API}/auth/login", json={"username": INACTIVE_USERNAME, "password": DEFAULT_PASSWORD})
    for res in (wrong_password, unknown_user, inactive):
        assert res.status_code == 401
        assert res.json() == {"detail": "Sai tên đăng nhập hoặc mật khẩu"}


def test_login_rate_limit(client, accounts):
    for _ in range(5):
        assert client.post(f"{API}/auth/login", json={"username": ADMIN_USERNAME, "password": "sai"}).status_code == 401
    blocked = client.post(f"{API}/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


def test_login_validation(client):
    assert client.post(f"{API}/auth/login", json={"username": "", "password": "x"}).status_code == 422


def test_missing_invalid_expired_tokens(client, accounts):
    assert client.get(f"{API}/auth/me").status_code == 401
    assert client.get(f"{API}/auth/me", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401
    expired = client.get(f"{API}/auth/me", headers=bearer(ADMIN_ID, "ADMIN", expires_minutes=-1))
    assert expired.status_code == 401 and expired.json()["detail"] == "Phiên đăng nhập đã hết hạn"
    assert client.get(f"{API}/auth/me", headers=bearer(INACTIVE_ID, "ADMIN")).status_code == 401
    assert client.get(f"{API}/auth/me", headers=bearer(123_456_789, "ADMIN")).status_code == 401


def test_role_is_loaded_from_database_not_token(client, accounts):
    """Token ghi role=ADMIN nhưng tài khoản là TEACHER -> vẫn bị chặn ở /admin."""
    forged_role = bearer(accounts["teacher"], "ADMIN")
    assert client.get(f"{API}/admin/overview/kpis", headers=forged_role).status_code == 403


def test_role_separation(client, admin_headers, teacher_headers):
    assert client.get(f"{API}/admin/overview/kpis").status_code == 401
    assert client.get(f"{API}/admin/overview/kpis", headers=teacher_headers).status_code == 403
    assert client.get(f"{API}/admin/reports/preview?report_type=enrollment", headers=teacher_headers).status_code == 403
    assert client.get(f"{API}/teacher/courses", headers=admin_headers).status_code == 403


def test_filters(client, teacher_headers, courses):
    body = client.get(f"{API}/filters", headers=teacher_headers).json()
    assert body["current"] == {"academic_year": "2026-2027", "semester": 1}
    assert {f["id"] for f in body["faculties"]} == {c["faculty_id"] for c in courses}
    assert body["academic_years"] == ["2026-2027"] and body["semesters"] == [1, 2, 3]
    assert body["data_updated_at"] is not None


def test_etl_status(client, admin_headers):
    jobs = {j["job_name"]: j for j in client.get(f"{API}/etl/status", headers=admin_headers).json()}
    assert {"traffic", "course_progress", "student_risk", "nightly", "maintenance", "backfill"} <= set(jobs)
    assert jobs["backfill"]["last_success_at"] is not None


def test_openapi_lists_all_endpoints(client):
    paths = client.get("/api/openapi.json").json()["paths"]
    expected = {
        "/auth/login", "/auth/me", "/filters", "/etl/status",
        "/admin/overview/kpis", "/admin/enrollment/by-faculty", "/admin/enrollment/faculties/{faculty_id}/courses",
        "/admin/enrollment/courses/{course_id}/students", "/admin/traffic/hourly", "/admin/traffic/realtime",
        "/admin/traffic/heatmap", "/admin/reports/preview", "/admin/reports/export",
        "/teacher/courses", "/teacher/courses/{course_id}/risk-summary", "/teacher/courses/{course_id}/students",
        "/teacher/courses/{course_id}/students/{user_id}", "/teacher/courses/{course_id}/students/{user_id}/interventions",
        "/teacher/courses/{course_id}/progress", "/teacher/courses/{course_id}/students/{user_id}/compare",
        "/teacher/courses/{course_id}/export",
    }
    assert {API + p for p in expected} <= set(paths)
