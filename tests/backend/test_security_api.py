"""Bảo mật cơ bản của API (SPEC 6.3): CORS giới hạn, chống SQL injection qua tham số, bcrypt, header bảo mật."""
from __future__ import annotations

import pytest

from tests.backend.conftest import API

ALLOWED_ORIGIN = "http://localhost:5173"


def test_cors_allows_only_configured_origin(client):
    allowed = client.options(f"{API}/auth/login", headers={"Origin": ALLOWED_ORIGIN, "Access-Control-Request-Method": "POST"})
    assert allowed.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    denied = client.options(f"{API}/auth/login", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in denied.headers
    simple = client.get(f"{API}/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in simple.headers


def test_security_headers(client, admin_headers):
    res = client.get(f"{API}/admin/overview/kpis", headers=admin_headers)
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("payload", ["' OR 1=1 --", "x'; DROP TABLE analytics.app_user; --", "%' UNION SELECT 1 --", "\\"])
def test_search_injection_is_treated_as_text(client, teacher_headers, admin_headers, accounts, payload):
    course = accounts["course"]["course_id"]
    teacher = client.get(f"{API}/teacher/courses/{course}/students", params={"search": payload}, headers=teacher_headers)
    admin = client.get(f"{API}/admin/enrollment/courses/{course}/students", params={"search": payload}, headers=admin_headers)
    assert teacher.status_code == admin.status_code == 200
    assert teacher.json()["total"] == 0 and admin.json()["total"] == 0


@pytest.mark.parametrize("url, params", [
    ("/teacher/courses/{course}/students", {"sort": "risk_score; DROP TABLE x"}),
    ("/teacher/courses/{course}/students", {"order": "desc; --"}),
    ("/teacher/courses/{course}/students", {"risk_level": "RED' OR '1'='1"}),
    ("/teacher/courses/{course}/students", {"page_size": "10; --"}),
    ("/teacher/courses/1 OR 1=1/students", {}),
])
def test_structured_parameters_are_validated(client, teacher_headers, accounts, url, params):
    res = client.get(API + url.format(course=accounts["course"]["course_id"]), params=params, headers=teacher_headers)
    assert res.status_code == 422


def test_passwords_are_bcrypt_hashes(db, accounts):
    hashes = [r[0] for r in db.execute("SELECT password_hash FROM analytics.app_user")]
    assert hashes and all(h.startswith(("$2a$", "$2b$", "$2y$")) and len(h) == 60 for h in hashes)


def test_error_responses_do_not_leak_internals(client, teacher_headers):
    res = client.get(f"{API}/teacher/courses/999999/students", headers=teacher_headers)
    assert res.status_code == 404 and set(res.json()) == {"detail"}
    assert "Traceback" not in res.text and "SELECT" not in res.text
