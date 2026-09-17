"""Dependency dùng chung của các router: vai trò, học kỳ, thời điểm tham chiếu, dấu thời gian dữ liệu."""
from __future__ import annotations

from datetime import datetime
from http import HTTPStatus

from fastapi import Depends, HTTPException, Query
from sqlalchemy import Connection

from backend.app.core.config import as_of, today
from backend.app.core.db import get_conn
from backend.app.core.security import ROLE_ADMIN, ROLE_TEACHER, require_role
from backend.app.repositories import common as common_repo

admin_user = require_role(ROLE_ADMIN)
teacher_user = require_role(ROLE_TEACHER)

ACADEMIC_YEAR_PATTERN = r"^\d{4}-\d{4}$"


def unprocessable(detail: str) -> HTTPException:
    return HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, detail)


def not_found(detail: str) -> HTTPException:
    return HTTPException(HTTPStatus.NOT_FOUND, detail)


def now_local() -> datetime:
    """AS_OF theo giờ địa phương, bỏ múi giờ (so sánh được với cột TIMESTAMP của bảng fact)."""
    return as_of().replace(tzinfo=None, microsecond=0)


def now_minute() -> datetime:
    """AS_OF làm tròn xuống phút – dùng làm khóa cache cho các endpoint KPI."""
    return now_local().replace(second=0)


def stamp(conn: Connection) -> datetime | None:
    return common_repo.data_updated_at(conn)


def optional_term(
    academic_year: str | None = Query(None, pattern=ACADEMIC_YEAR_PATTERN, description="Năm học, vd 2026-2027"),
    semester: int | None = Query(None, ge=1, le=3, description="Học kỳ 1, 2, 3 (hè)"),
) -> tuple[str | None, int | None]:
    if (academic_year is None) != (semester is None):
        raise unprocessable("Cần truyền đủ cả academic_year và semester, hoặc bỏ trống cả hai")
    return academic_year, semester


def term(selected: tuple[str | None, int | None] = Depends(optional_term),
         conn: Connection = Depends(get_conn)) -> tuple[str, int]:
    """Học kỳ được chọn; bỏ trống thì dùng học kỳ của dữ liệu mới nhất."""
    if selected[0] is None:
        return common_repo.current_term(conn, today())
    return selected  # type: ignore[return-value]
