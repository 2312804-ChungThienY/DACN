"""Admin 1.3 – Data Preview và Export Excel/PDF với bộ lọc đa chiều."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import Connection

from backend.app.core.config import today
from backend.app.core.db import get_conn
from backend.app.repositories import admin as admin_repo
from backend.app.repositories import common as common_repo
from backend.app.repositories import reports as reports_repo
from backend.app.routers._export import export_response
from backend.app.routers.deps import admin_user, optional_term, stamp, unprocessable
from backend.app.schemas.common import RiskLevel
from backend.app.schemas.reports import ExportFormat, ReportPreviewOut, ReportType
from backend.app.services.formatting import RISK_LABELS

router = APIRouter(prefix="/admin/reports", tags=["Báo cáo"], dependencies=[Depends(admin_user)])


def report_filters(
    report_type: ReportType = Query(..., description="enrollment | traffic | risk"),
    selected: tuple[str | None, int | None] = Depends(optional_term),
    faculty_id: int | None = Query(None, ge=1),
    course_id: int | None = Query(None, ge=1),
    risk_level: RiskLevel | None = Query(None, description="Chỉ áp dụng cho báo cáo risk"),
    from_date: date | None = Query(None, alias="from", description="Báo cáo traffic: ngày bắt đầu"),
    to_date: date | None = Query(None, alias="to", description="traffic: ngày kết thúc; enrollment/risk: ngày số liệu"),
    conn: Connection = Depends(get_conn),
) -> reports_repo.ReportFilters:
    academic_year, semester = selected
    if report_type != "traffic" and academic_year is None:
        academic_year, semester = common_repo.current_term(conn, today())
    if from_date and to_date and from_date > to_date:
        raise unprocessable("`from` phải không muộn hơn `to`")
    filters = reports_repo.ReportFilters(report_type=report_type, academic_year=academic_year, semester=semester,
                                         faculty_id=faculty_id, course_id=course_id,
                                         risk_level=risk_level if report_type == "risk" else None,
                                         from_date=from_date, to_date=to_date)
    if report_type == "traffic":
        start, end = reports_repo.traffic_range(filters, today())
        if start > end:
            raise unprocessable("Khoảng thời gian không hợp lệ")
        if (end - start).days + 1 > reports_repo.REPORT_TRAFFIC_MAX_DAYS:
            raise unprocessable(f"Báo cáo lưu lượng tối đa {reports_repo.REPORT_TRAFFIC_MAX_DAYS} ngày")
    return filters


def describe(conn: Connection, f: reports_repo.ReportFilters) -> list[tuple[str, str]]:
    """Mô tả bộ lọc bằng chữ để in lên đầu file xuất."""
    lines: list[tuple[str, str]] = []
    if f.report_type == "traffic":
        start, end = reports_repo.traffic_range(f, today())
        return [("Khoảng thời gian", f"{start:%d/%m/%Y} – {end:%d/%m/%Y}")]
    lines.append(("Năm học – học kỳ", f"{f.academic_year} – HK{f.semester}"))
    if f.faculty_id is not None:
        names = {x["id"]: x["name"] for x in common_repo.filters(conn, today())["faculties"]}
        lines.append(("Khoa", names.get(f.faculty_id, f"#{f.faculty_id}")))
    if f.course_id is not None:
        header = admin_repo.course_header(conn, f.course_id, today())
        lines.append(("Môn học", f"{header['shortname']} – {header['fullname']}" if header else f"#{f.course_id}"))
    if f.risk_level is not None:
        lines.append(("Mức rủi ro", RISK_LABELS[f.risk_level]))
    if f.to_date is not None:
        lines.append(("Ngày số liệu", f"{f.to_date:%d/%m/%Y}"))
    return lines


def filters_dict(f: reports_repo.ReportFilters) -> dict:
    if f.report_type == "traffic":
        start, end = reports_repo.traffic_range(f, today())
        return {"from": start, "to": end}
    return {"academic_year": f.academic_year, "semester": f.semester, "faculty_id": f.faculty_id,
            "course_id": f.course_id, "risk_level": f.risk_level, "to": f.to_date}


def filename_stem(f: reports_repo.ReportFilters) -> str:
    if f.report_type == "traffic":
        start, end = reports_repo.traffic_range(f, today())
        return f"bao_cao_traffic_{start:%Y%m%d}_{end:%Y%m%d}"
    return f"bao_cao_{f.report_type}_HK{f.semester}_{f.academic_year}"


@router.get("/preview", response_model=ReportPreviewOut, summary="Xem trước dữ liệu báo cáo (phân trang)")
def preview(filters: reports_repo.ReportFilters = Depends(report_filters),
            page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
            conn: Connection = Depends(get_conn)) -> dict:
    items, total = reports_repo.preview(conn, filters, today(), page, page_size)
    return {
        "report_type": filters.report_type, "title": reports_repo.report_title(filters.report_type),
        "columns": [{"key": c.key, "title": c.title, "kind": c.kind}
                    for c in reports_repo.report_columns(filters.report_type)],
        "items": items, "total": total, "page": page, "page_size": page_size,
        "filters": filters_dict(filters), "data_updated_at": stamp(conn),
    }


@router.get("/export", summary="Xuất báo cáo Excel/PDF (file stream)",
            responses={200: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
                                         "application/pdf": {}}}})
def export(filters: reports_repo.ReportFilters = Depends(report_filters),
           format: ExportFormat = Query("xlsx"), conn: Connection = Depends(get_conn)) -> Response:  # noqa: A002
    return export_response(conn, filters, format, title=reports_repo.report_title(filters.report_type),
                           filename_stem=filename_stem(filters), description=describe(conn, filters))
