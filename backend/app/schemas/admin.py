"""Schema các endpoint Admin 1.1, 1.2."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from backend.app.schemas.common import Page, Stamped


class PeakRequests(BaseModel):
    hour: str
    stat_hour: datetime
    value: int


class KpisOut(Stamped):
    academic_year: str
    semester: int
    faculty_id: int | None
    stat_date: date | None
    total_courses: int
    total_enrolled: int
    total_active: int
    active_rate: float
    red_students: int
    yellow_students: int
    green_students: int
    red_rate: float
    peak_requests_today: PeakRequests | None
    avg_online_users_today: float
    current_online: int
    current_online_at: datetime | None


class FacultyEnrollment(BaseModel):
    faculty_id: int
    faculty_name: str
    course_count: int
    enrolled: int
    active: int
    inactive: int
    active_rate: float
    red_count: int
    yellow_count: int
    green_count: int


class FacultyEnrollmentOut(Stamped):
    academic_year: str
    semester: int
    items: list[FacultyEnrollment]


class CourseEnrollment(BaseModel):
    course_id: int
    shortname: str
    fullname: str
    category_id: int
    category_name: str
    stat_date: date
    enrolled: int
    active: int
    inactive: int
    active_rate: float
    red_count: int
    yellow_count: int
    green_count: int
    avg_completion_rate: float | None          # None = chưa có dữ liệu (migration V007)
    assignment_submission_rate: float | None
    attendance_rate: float | None


class CourseEnrollmentOut(Stamped):
    faculty_id: int
    academic_year: str
    semester: int
    items: list[CourseEnrollment]


class CourseHeader(BaseModel):
    course_id: int
    shortname: str
    fullname: str
    faculty_id: int
    faculty_name: str
    category_name: str
    academic_year: str
    semester: int
    enrolled: int
    active: int


class CourseStudent(BaseModel):
    user_id: int
    student_code: str | None
    student_name: str
    email: str | None
    is_active: bool
    total_access_count: int
    access_count_7d: int
    last_access_time: datetime | None
    days_since_last_access: int | None
    risk_level: str
    risk_score: int


class CourseStudentsOut(Page[CourseStudent]):
    course: CourseHeader
    snapshot_date: date


class TrafficHour(BaseModel):
    stat_hour: datetime
    stat_date: date
    hour_of_day: int
    day_of_week: int
    total_requests: int
    unique_users: int
    login_count: int
    failed_login_count: int
    ws_requests: int
    peak_online_users: int
    avg_online_users: float
    online_sample_count: int
    is_peak_hour: bool


class TrafficHourlyOut(Stamped):
    from_date: date
    to_date: date
    items: list[TrafficHour]


class RealtimeOut(Stamped):
    current_hour: datetime
    current_online: int
    current_online_at: datetime | None
    current_online_source: str | None
    requests_current_hour: int
    requests_so_far: int
    series_24h: list[TrafficHour]


class HeatCell(BaseModel):
    day_of_week: int
    hour_of_day: int
    avg_requests: float
    avg_online_users: float
    peak_share: float
    days: int


class HeatmapOut(Stamped):
    weeks: int
    from_date: date
    to_date: date
    matrix: list[HeatCell]
