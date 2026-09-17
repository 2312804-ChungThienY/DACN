"""API Admin 1.1, 1.2 – đối chiếu với truy vấn trực tiếp bảng fact."""
from __future__ import annotations

from datetime import datetime, timedelta

from backend.app.core.config import as_of
from backend.app.core.db import get_engine
from backend.app.repositories.admin import active_counts_by_course
from tests.backend.conftest import API

TERM = {"academic_year": "2026-2027", "semester": 1}


def test_kpis_match_fact_tables(client, admin_headers, courses, db, snapshot):
    body = client.get(f"{API}/admin/overview/kpis", params=TERM, headers=admin_headers).json()
    enrolled = sum(c["enrolled"] for c in courses)
    assert body["total_courses"] == len(courses)
    assert body["total_enrolled"] == enrolled
    assert body["total_active"] == sum(c["active"] for c in courses)
    assert body["red_students"] == sum(c["red_count"] for c in courses)
    assert body["red_students"] + body["yellow_students"] + body["green_students"] == enrolled
    assert body["stat_date"] == snapshot.isoformat()

    now = as_of().replace(tzinfo=None)
    online = db.execute("""SELECT online_users FROM analytics.etl_online_snapshot WHERE slot_start <= %s
                           ORDER BY slot_start DESC LIMIT 1""", (now,)).fetchone()[0]
    peak = db.execute("""SELECT MAX(total_requests) FROM analytics.fact_server_traffic_hourly
                         WHERE stat_date = %s""", (snapshot,)).fetchone()[0]
    assert body["current_online"] == online
    assert body["peak_requests_today"]["value"] == peak
    assert body["avg_online_users_today"] > 0
    assert body["data_updated_at"] is not None


def test_kpis_default_term_and_filters(client, admin_headers, courses):
    default = client.get(f"{API}/admin/overview/kpis", headers=admin_headers).json()
    assert (default["academic_year"], default["semester"]) == ("2026-2027", 1)
    assert client.get(f"{API}/admin/overview/kpis", params={"faculty_id": 999_999},
                      headers=admin_headers).json()["total_courses"] == 0
    assert client.get(f"{API}/admin/overview/kpis", params={"academic_year": "2026-2027"},
                      headers=admin_headers).status_code == 422
    assert client.get(f"{API}/admin/overview/kpis", params={"academic_year": "26-27", "semester": 1},
                      headers=admin_headers).status_code == 422
    assert client.get(f"{API}/admin/overview/kpis", params={"academic_year": "2026-2027", "semester": 4},
                      headers=admin_headers).status_code == 422


def test_enrollment_by_faculty(client, admin_headers, courses):
    body = client.get(f"{API}/admin/enrollment/by-faculty", params=TERM, headers=admin_headers).json()
    assert len(body["items"]) == len({c["faculty_id"] for c in courses})
    item = body["items"][0]
    assert item["enrolled"] == sum(c["enrolled"] for c in courses)
    assert item["inactive"] == item["enrolled"] - item["active"]
    assert item["course_count"] == len(courses)


def test_faculty_courses_drill_down(client, admin_headers, courses):
    faculty_id = courses[0]["faculty_id"]
    url = f"{API}/admin/enrollment/faculties/{faculty_id}/courses"
    items = client.get(url, params=TERM, headers=admin_headers).json()["items"]
    assert len(items) == len(courses)
    rates = [i["active_rate"] for i in items]
    assert rates == sorted(rates, reverse=True)
    by_code = client.get(url, params={**TERM, "sort": "shortname", "order": "asc"}, headers=admin_headers).json()["items"]
    assert [i["shortname"] for i in by_code] == sorted(c["course_shortname"] for c in courses)
    assert client.get(url, params={"sort": "course_id; DROP"}, headers=admin_headers).status_code == 422
    assert client.get(f"{API}/admin/enrollment/faculties/999999/courses", headers=admin_headers).status_code == 404


def test_active_definition_matches_course_progress(courses, snapshot):
    """SV 'có tương tác' ở cấp drill-down SV phải khớp total_active_students của bảng tiến độ."""
    with get_engine().connect() as conn:
        counts = active_counts_by_course(conn, snapshot)
    assert counts == {c["course_id"]: c["active"] for c in courses}


def test_course_students(client, admin_headers, courses):
    course = max(courses, key=lambda c: c["enrolled"])
    url = f"{API}/admin/enrollment/courses/{course['course_id']}/students"
    all_students = client.get(url, params={"page_size": 200}, headers=admin_headers).json()
    assert all_students["total"] == course["enrolled"]
    assert all_students["course"]["shortname"] == course["course_shortname"]
    assert len(all_students["items"]) == min(200, course["enrolled"])

    active = client.get(url, params={"status": "active", "page_size": 1}, headers=admin_headers).json()
    inactive = client.get(url, params={"status": "inactive", "page_size": 1}, headers=admin_headers).json()
    assert active["total"] == course["active"]
    assert active["total"] + inactive["total"] == course["enrolled"]

    target = all_students["items"][3]
    found = client.get(url, params={"search": target["student_code"]}, headers=admin_headers).json()
    assert [s["user_id"] for s in found["items"]] == [target["user_id"]]
    assert client.get(url, params={"search": "%"}, headers=admin_headers).json()["total"] == 0   # ký tự đại diện bị thoát

    page2 = client.get(url, params={"page": 2, "page_size": 10}, headers=admin_headers).json()
    assert [s["user_id"] for s in page2["items"]] == [s["user_id"] for s in all_students["items"][10:20]]
    assert client.get(url, params={"page_size": 500}, headers=admin_headers).status_code == 422
    assert client.get(f"{API}/admin/enrollment/courses/999999/students", headers=admin_headers).status_code == 404


def test_traffic_hourly(client, admin_headers, snapshot):
    body = client.get(f"{API}/admin/traffic/hourly", headers=admin_headers).json()
    now = as_of()
    assert body["from_date"] == (snapshot - timedelta(days=6)).isoformat()
    assert len(body["items"]) == 6 * 24 + now.hour + 1
    hours = [i["stat_hour"] for i in body["items"]]
    assert hours == sorted(hours)
    peak = body["items"][0]
    assert {"total_requests", "unique_users", "peak_online_users", "avg_online_users", "is_peak_hour"} <= set(peak)

    two_days = client.get(f"{API}/admin/traffic/hourly", params={"from": "2026-10-01", "to": "2026-10-02"},
                          headers=admin_headers).json()
    assert len(two_days["items"]) == 48
    assert client.get(f"{API}/admin/traffic/hourly", params={"from": "2026-10-05", "to": "2026-10-01"},
                      headers=admin_headers).status_code == 422
    assert client.get(f"{API}/admin/traffic/hourly", params={"from": "2026-01-01", "to": "2026-10-01"},
                      headers=admin_headers).status_code == 422


def test_traffic_realtime(client, admin_headers, db, snapshot):
    body = client.get(f"{API}/admin/traffic/realtime", headers=admin_headers).json()
    current = as_of().replace(minute=0, second=0, microsecond=0, tzinfo=None)
    assert body["current_hour"] == current.isoformat()
    assert len(body["series_24h"]) == 24
    assert body["series_24h"][-1]["stat_hour"] == current.isoformat()
    requests_today = db.execute("SELECT SUM(total_requests) FROM analytics.fact_server_traffic_hourly WHERE stat_date = %s",
                                (snapshot,)).fetchone()[0]
    assert body["requests_so_far"] == requests_today
    assert body["current_online"] > 0 and body["current_online_source"] == "SESSIONS"


def test_traffic_heatmap(client, admin_headers):
    body = client.get(f"{API}/admin/traffic/heatmap", params={"weeks": 4}, headers=admin_headers).json()
    assert len(body["matrix"]) == 7 * 24
    assert all(cell["days"] == 4 for cell in body["matrix"])
    cell = {(c["day_of_week"], c["hour_of_day"]): c["avg_requests"] for c in body["matrix"]}
    assert cell[(2, 9)] > cell[(2, 3)]          # sáng thứ 3 đông hơn 3 giờ sáng
    assert datetime.fromisoformat(body["to_date"]).date() < as_of().date()
    assert client.get(f"{API}/admin/traffic/heatmap", params={"weeks": 13}, headers=admin_headers).status_code == 422
