"""
Kiểm thử tải API (SPEC 6.2 dòng "API"): 50 người dùng đồng thời (40 GV, 10 Admin), think-time 2–5 giây.
Mục tiêu: p95 < 500 ms, p99 < 1 s, lỗi < 0,1%.

    $env:LMS_DEMO_PASSWORD = "<mật khẩu demo>"
    python -m locust -f perf/locustfile.py --host http://127.0.0.1:8000 --headless -u 50 -r 5 -t 10m \
        --csv perf/results/locust_x10 --html perf/results/locust_x10.html

Tài khoản: admin và các GV (gv.*; với bộ x10 thêm gv.*.1 … gv.*.9) lấy từ app_user qua biến LOCUST_TEACHERS
(danh sách phân tách bằng dấu phẩy) hoặc tự dò bằng /teacher/courses sau khi đăng nhập.
"""
from __future__ import annotations

import itertools
import os
import random
import threading

from locust import HttpUser, between, events, task

PASSWORD = os.environ.get("LMS_DEMO_PASSWORD", "")
TEACHERS = [u.strip() for u in os.environ.get("LOCUST_TEACHERS", "").split(",") if u.strip()]
ADMINS = [u.strip() for u in os.environ.get("LOCUST_ADMINS", "admin").split(",") if u.strip()]
_teacher_cycle = itertools.cycle(TEACHERS or ["gv.tranminhhung"])
_lock = threading.Lock()


@events.test_start.add_listener
def check_config(environment, **_kwargs):
    if not PASSWORD:
        raise SystemExit("Cần đặt LMS_DEMO_PASSWORD")


class DashboardUser(HttpUser):
    abstract = True
    wait_time = between(2, 5)
    username = ""

    def login(self, username: str) -> None:
        with self.client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD},
                              name="POST /auth/login", catch_response=True) as res:
            if res.status_code != 200:
                res.failure(f"đăng nhập {username}: {res.status_code}")
                raise SystemExit
            self.client.headers["Authorization"] = f"Bearer {res.json()['access_token']}"


class TeacherUser(DashboardUser):
    weight = 4

    def on_start(self):
        with _lock:
            self.username = next(_teacher_cycle)
        self.login(self.username)
        courses = self.client.get("/api/v1/teacher/courses", name="GET /teacher/courses").json()["items"]
        self.course_ids = [c["course_id"] for c in courses]
        self.student_ids: dict[int, list[int]] = {}

    def course(self) -> int:
        return random.choice(self.course_ids)

    @task(3)
    def risk_table(self):
        cid = self.course()
        self.client.get(f"/api/v1/teacher/courses/{cid}/risk-summary", name="GET /teacher/courses/{id}/risk-summary")
        params = random.choice([{}, {"risk_level": "RED"}, {"criterion": "attendance"}, {"sort": "days_since_last_access"}])
        data = self.client.get(f"/api/v1/teacher/courses/{cid}/students", params=params,
                               name="GET /teacher/courses/{id}/students").json()
        self.student_ids[cid] = [s["user_id"] for s in data["items"]]

    @task(2)
    def student_modal(self):
        cid = self.course()
        students = self.student_ids.get(cid)
        if not students:
            return self.risk_table()
        uid = random.choice(students[:20])
        self.client.get(f"/api/v1/teacher/courses/{cid}/students/{uid}", name="GET /teacher/courses/{id}/students/{uid}")
        self.client.get(f"/api/v1/teacher/courses/{cid}/students/{uid}/compare", name="GET /teacher/courses/{id}/students/{uid}/compare")

    @task(1)
    def progress(self):
        self.client.get(f"/api/v1/teacher/courses/{self.course()}/progress", params={"granularity": random.choice(["day", "week"])},
                        name="GET /teacher/courses/{id}/progress")


class AdminUser(DashboardUser):
    weight = 1

    def on_start(self):
        self.login(random.choice(ADMINS))
        filters = self.client.get("/api/v1/filters", name="GET /filters").json()
        self.faculties = [f["id"] for f in filters["faculties"]]
        self.courses: list[int] = []

    @task(3)
    def overview(self):
        self.client.get("/api/v1/admin/overview/kpis", name="GET /admin/overview/kpis")
        self.client.get("/api/v1/admin/enrollment/by-faculty", name="GET /admin/enrollment/by-faculty")
        self.client.get("/api/v1/admin/traffic/realtime", name="GET /admin/traffic/realtime")

    @task(2)
    def drill_down(self):
        fid = random.choice(self.faculties)
        items = self.client.get(f"/api/v1/admin/enrollment/faculties/{fid}/courses", name="GET /admin/enrollment/faculties/{id}/courses").json()["items"]
        if items:
            cid = random.choice(items)["course_id"]
            self.client.get(f"/api/v1/admin/enrollment/courses/{cid}/students", params={"status": random.choice(["active", "inactive"])},
                            name="GET /admin/enrollment/courses/{id}/students")

    @task(2)
    def traffic(self):
        self.client.get("/api/v1/admin/traffic/hourly", name="GET /admin/traffic/hourly")
        self.client.get("/api/v1/admin/traffic/heatmap", params={"weeks": 4}, name="GET /admin/traffic/heatmap")

    @task(1)
    def report_preview(self):
        self.client.get("/api/v1/admin/reports/preview", params={"report_type": random.choice(["enrollment", "risk", "traffic"]),
                                                                  "page": random.randint(1, 3)},
                        name="GET /admin/reports/preview")
