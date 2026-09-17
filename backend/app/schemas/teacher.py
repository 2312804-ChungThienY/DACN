"""Schema các endpoint Giảng viên 2.1, 2.2."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.common import Page, RiskLevel, Stamped

ActionType = Literal["MESSAGE", "EMAIL", "NOTE", "MEETING"]


class TeacherCourse(BaseModel):
    course_id: int
    shortname: str
    fullname: str
    faculty_name: str
    category_name: str
    academic_year: str
    semester: int
    stat_date: date
    enrolled: int
    active: int
    red: int
    yellow: int
    green: int
    avg_completion_rate: float | None          # None = chưa có dữ liệu (migration V007)
    assignment_submission_rate: float | None
    attendance_rate: float | None


class TeacherCoursesOut(Stamped):
    items: list[TeacherCourse]


class Criteria(BaseModel):
    attendance: int
    inactivity: int
    assignment: int


class RiskSummaryOut(Stamped):
    course_id: int
    snapshot_date: date
    total: int
    red: int
    yellow: int
    green: int
    by_criterion: Criteria          # số SV có điểm tiêu chí > 0
    by_criterion_red: Criteria      # số SV có điểm tiêu chí = 2
    attendance_no_data: int


class RiskStudent(BaseModel):
    user_id: int
    student_code: str | None
    student_name: str
    email: str | None
    risk_level: RiskLevel
    risk_score: int
    risk_reasons: list[str]
    score_attendance: int
    score_inactivity: int
    score_assignment: int
    total_sessions: int
    attended_sessions: int
    absent_sessions: int
    absence_rate: float | None                 # None = chưa có buổi điểm danh
    attendance_status: str
    total_assignments: int
    submitted_assignments: int
    missing_assignments_count: int
    missing_assignments: str        # "4/5" = thiếu / đã tới hạn
    late_submissions: int
    completion_rate: float | None              # None = chưa có hoạt động theo dõi tới hạn
    total_access_count: int
    access_count_7d: int
    access_count_14d: int
    last_access_time: datetime | None
    days_since_last_access: int | None


class RiskStudentsOut(Page[RiskStudent]):
    course_id: int
    snapshot_date: date


class WeekActivity(BaseModel):
    week: int
    views: int
    actions: int
    sessions: int = 0
    present: int = 0
    attended: bool | None = None


class AssignmentItem(BaseModel):
    assign_id: int | None = None
    name: str
    duedate: datetime | None = None
    status: str
    submitted_at: datetime | None = None
    late: bool = False


class HistoryPoint(BaseModel):
    date: date
    risk_level: RiskLevel
    risk_score: int
    score_attendance: int
    score_inactivity: int
    score_assignment: int


class InterventionOut(BaseModel):
    id: int
    action_type: str
    content: str | None
    risk_level_at_time: str | None
    created_at: datetime
    teacher_id: int
    teacher_name: str | None


class StudentDetailOut(RiskStudent, Stamped):
    snapshot_date: date
    course_id: int
    course_shortname: str
    course_fullname: str
    active_actions: int
    weekly_activity: list[WeekActivity]
    assignment_detail: list[AssignmentItem]
    class_avg_access: float | None
    risk_history: list[HistoryPoint]
    interventions: list[InterventionOut]


class InterventionIn(BaseModel):
    action_type: ActionType
    content: str | None = Field(default=None, max_length=2000)

    @field_validator("content")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        value = value.strip() if value is not None else None
        return value or None


class InterventionCreated(BaseModel):
    id: int
    created_at: datetime


class ProgressPoint(BaseModel):
    period: str
    period_start: date
    period_end: date
    enrolled: int
    active_students_day: int
    active_students_7d: int
    total_active_students: int
    total_views_day: int
    total_actions_day: int
    submissions_day: int
    total_assignments: int
    avg_completion_rate: float | None
    assignment_submission_rate: float | None
    attendance_rate: float | None
    avg_access_per_student: float
    red_count: int
    yellow_count: int
    green_count: int


class SectionProgress(BaseModel):
    section: int
    name: str
    completion_rate: float


class ProgressSummary(BaseModel):
    stat_date: date
    enrolled: int
    active_students_7d: int
    total_active_students: int
    total_assignments: int
    avg_completion_rate: float | None
    submission_rate: float | None
    attendance_rate: float | None
    avg_access_per_student: float
    red: int
    yellow: int
    green: int


class ProgressOut(Stamped):
    course_id: int
    granularity: Literal["day", "week"]
    summary: ProgressSummary
    series: list[ProgressPoint]
    sections: list[SectionProgress]


class CompareMetric(BaseModel):
    key: str
    label: str
    unit: str
    student: float | None       # None = chưa có dữ liệu (vd 0 bài tới hạn)
    class_avg: float | None


class CompareOut(Stamped):
    course_id: int
    user_id: int
    snapshot_date: date
    metrics: list[CompareMetric]
