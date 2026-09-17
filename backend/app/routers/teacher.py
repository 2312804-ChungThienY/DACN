"""
Giảng viên 2.1 (cảnh báo, Modal chi tiết, can thiệp) và 2.2 (tiến độ lớp, so sánh cá nhân).

Chỉ vai trò TEACHER. Mọi endpoint theo môn kiểm tra giảng viên thuộc teacher_ids của môn:
môn không có dữ liệu -> 404, môn của giảng viên khác -> 403 (SPEC 6.3).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from http import HTTPStatus
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy import Connection

from backend.app.core.config import today
from backend.app.core.db import get_conn
from backend.app.core.security import CurrentUser
from backend.app.repositories import admin as admin_repo
from backend.app.repositories import teacher as teacher_repo
from backend.app.repositories.reports import ReportFilters
from backend.app.routers._export import export_response
from backend.app.routers.deps import not_found, optional_term, stamp, teacher_user
from backend.app.schemas.common import RiskLevel
from backend.app.schemas.reports import ExportFormat
from backend.app.schemas.teacher import (CompareOut, InterventionCreated, InterventionIn, ProgressOut,
                                         RiskStudentsOut, RiskSummaryOut, StudentDetailOut, TeacherCoursesOut)
from backend.app.services.formatting import RISK_LABELS

router = APIRouter(prefix="/teacher", tags=["Giảng viên"])

StudentSort = Literal["risk", "risk_score", "student_code", "student_name", "absence_rate", "missing_assignments",
                      "days_since_last_access", "last_access_time"]


@dataclass(frozen=True)
class CourseAccess:
    course_id: int
    teacher_id: int


def course_access(course_id: int = Path(ge=1), user: CurrentUser = Depends(teacher_user),
                  conn: Connection = Depends(get_conn)) -> CourseAccess:
    teacher_ids = teacher_repo.course_teacher_ids(conn, course_id, today())
    if teacher_ids is None:
        raise not_found("Không tìm thấy môn học")
    if user.user_id not in teacher_ids:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Bạn không phụ trách môn học này")
    return CourseAccess(course_id=course_id, teacher_id=user.user_id)


def _snapshot(conn: Connection, access: CourseAccess) -> date:
    snapshot = teacher_repo.risk_snapshot_date(conn, access.course_id, access.teacher_id, today())
    if snapshot is None:
        raise not_found("Môn học chưa có dữ liệu cảnh báo")
    return snapshot


def _with_missing(row: dict) -> dict:
    row["missing_assignments"] = f"{row['missing_assignments_count']}/{row['total_assignments']}"
    return row


@router.get("/courses", response_model=TeacherCoursesOut, summary="Các môn giảng viên phụ trách")
def courses(selected: tuple[str | None, int | None] = Depends(optional_term),
            user: CurrentUser = Depends(teacher_user), conn: Connection = Depends(get_conn)) -> dict:
    items = teacher_repo.teacher_courses(conn, user.user_id, today(), selected[0], selected[1])
    return {"items": items, "data_updated_at": stamp(conn)}


@router.get("/courses/{course_id}/risk-summary", response_model=RiskSummaryOut,
            summary="Số SV theo đèn giao thông và theo tiêu chí (doughnut)")
def risk_summary(access: CourseAccess = Depends(course_access), conn: Connection = Depends(get_conn)) -> dict:
    snapshot = _snapshot(conn, access)
    row = teacher_repo.risk_summary(conn, access.course_id, access.teacher_id, snapshot)
    return {
        "course_id": access.course_id, "snapshot_date": snapshot,
        "total": row["total"], "red": row["red"], "yellow": row["yellow"], "green": row["green"],
        "by_criterion": {k: row[k] for k in ("attendance", "inactivity", "assignment")},
        "by_criterion_red": {k: row[f"{k}_red"] for k in ("attendance", "inactivity", "assignment")},
        "attendance_no_data": row["attendance_no_data"], "data_updated_at": stamp(conn),
    }


@router.get("/courses/{course_id}/students", response_model=RiskStudentsOut, summary="Bảng cảnh báo sinh viên")
def students(access: CourseAccess = Depends(course_access),
             risk_level: list[RiskLevel] = Query(default=[], description="Lặp tham số để chọn nhiều mức"),
             criterion: Literal["attendance", "inactivity", "assignment"] | None = Query(None),
             search: str | None = Query(None, max_length=100, description="MSSV, họ tên hoặc email"),
             sort: StudentSort = "risk", order: Literal["asc", "desc"] = "desc",
             page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
             conn: Connection = Depends(get_conn)) -> dict:
    snapshot = _snapshot(conn, access)
    items, total = teacher_repo.students(conn, access.course_id, access.teacher_id, snapshot,
                                         risk_levels=sorted(set(risk_level)), criterion=criterion, search=search,
                                         sort=sort, order=order, page=page, page_size=page_size)
    return {"course_id": access.course_id, "snapshot_date": snapshot, "items": [_with_missing(r) for r in items],
            "total": total, "page": page, "page_size": page_size, "data_updated_at": stamp(conn)}


@router.get("/courses/{course_id}/students/{user_id}", response_model=StudentDetailOut,
            summary="Modal chi tiết sinh viên")
def student_detail(user_id: int = Path(ge=1), access: CourseAccess = Depends(course_access),
                   conn: Connection = Depends(get_conn)) -> dict:
    snapshot = _snapshot(conn, access)
    row = teacher_repo.student_detail(conn, access.course_id, user_id, access.teacher_id, snapshot)
    if row is None:
        raise not_found("Sinh viên không có trong danh sách lớp hiện tại")
    row = _with_missing(row)
    row["risk_history"] = teacher_repo.risk_history(conn, access.course_id, user_id, access.teacher_id, today())
    row["interventions"] = teacher_repo.interventions(conn, access.course_id, user_id)
    row["data_updated_at"] = stamp(conn)
    return row


@router.post("/courses/{course_id}/students/{user_id}/interventions", response_model=InterventionCreated,
             status_code=HTTPStatus.CREATED, summary="Ghi nhận hành động can thiệp")
def create_intervention(body: InterventionIn, user_id: int = Path(ge=1),
                        access: CourseAccess = Depends(course_access), conn: Connection = Depends(get_conn)) -> dict:
    snapshot = _snapshot(conn, access)
    student = teacher_repo.student_detail(conn, access.course_id, user_id, access.teacher_id, snapshot)
    if student is None:
        raise not_found("Sinh viên không có trong danh sách lớp hiện tại")
    return teacher_repo.create_intervention(conn, access.course_id, user_id, access.teacher_id, body.action_type,
                                            body.content, student["risk_level"])


@router.get("/courses/{course_id}/progress", response_model=ProgressOut, summary="Tiến độ và tương tác của lớp")
def progress(access: CourseAccess = Depends(course_access), granularity: Literal["day", "week"] = "day",
             conn: Connection = Depends(get_conn)) -> dict:
    latest = teacher_repo.progress_latest(conn, access.course_id, access.teacher_id, today())
    if latest is None:
        raise not_found("Môn học chưa có dữ liệu tiến độ")
    loader = teacher_repo.progress_weekly if granularity == "week" else teacher_repo.progress_daily
    summary = {
        "stat_date": latest["stat_date"], "enrolled": latest["enrolled"],
        "active_students_7d": latest["active_students_7d"], "total_active_students": latest["total_active_students"],
        "total_assignments": latest["total_assignments"], "avg_completion_rate": latest["avg_completion_rate"],
        "submission_rate": latest["assignment_submission_rate"], "attendance_rate": latest["attendance_rate"],
        "avg_access_per_student": latest["avg_access_per_student"],
        "red": latest["red_count"], "yellow": latest["yellow_count"], "green": latest["green_count"],
    }
    return {"course_id": access.course_id, "granularity": granularity, "summary": summary,
            "series": loader(conn, access.course_id, access.teacher_id, today()),
            "sections": latest["section_progress"], "data_updated_at": stamp(conn)}


@router.get("/courses/{course_id}/students/{user_id}/compare", response_model=CompareOut,
            summary="So sánh sinh viên với trung bình lớp (comparative bar)")
def compare(user_id: int = Path(ge=1), access: CourseAccess = Depends(course_access),
            conn: Connection = Depends(get_conn)) -> dict:
    snapshot = _snapshot(conn, access)
    row = teacher_repo.compare(conn, access.course_id, user_id, access.teacher_id, snapshot)
    if row is None:
        raise not_found("Sinh viên không có trong danh sách lớp hiện tại")
    metrics = [
        ("access_14d", "Truy cập 14 ngày", "lượt", row["access_count_14d"], row["class_access_14d"]),
        ("total_access", "Tổng lượt truy cập", "lượt", row["total_access_count"], row["class_total_access"]),
        ("submission_rate", "Tỷ lệ nộp bài", "%", row["submission_rate"], row["class_submission_rate"]),
        ("attendance_rate", "Chuyên cần", "%", row["attendance_rate"], row["class_attendance_rate"]),
        ("completion_rate", "Hoàn thành hoạt động", "%", row["completion_rate"], row["class_completion_rate"]),
    ]
    return {"course_id": access.course_id, "user_id": user_id, "snapshot_date": snapshot,
            "metrics": [dict(key=k, label=label, unit=unit, student=s, class_avg=c) for k, label, unit, s, c in metrics],
            "data_updated_at": stamp(conn)}


@router.get("/courses/{course_id}/export", summary="Xuất danh sách cảnh báo của môn (Excel/PDF)",
            responses={200: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
                                         "application/pdf": {}}}})
def export(access: CourseAccess = Depends(course_access), format: ExportFormat = Query("xlsx"),  # noqa: A002
           risk_level: RiskLevel | None = Query(None), conn: Connection = Depends(get_conn)) -> Response:
    header = admin_repo.course_header(conn, access.course_id, today())
    filters = ReportFilters(report_type="risk", course_id=access.course_id, risk_level=risk_level,
                            teacher_id=access.teacher_id)
    description = [("Môn học", f"{header['shortname']} – {header['fullname']}"),
                   ("Mức rủi ro", RISK_LABELS[risk_level] if risk_level else "Tất cả")]
    return export_response(conn, filters, format, title=f"Danh sách cảnh báo sinh viên – {header['shortname']}",
                           filename_stem=f"canh_bao_{header['shortname']}_{today():%Y%m%d}", description=description)
