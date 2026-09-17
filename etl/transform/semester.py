"""Suy ra năm học / học kỳ từ ngày bắt đầu môn học (Moodle không có sẵn khái niệm này) – SPEC Phần 1.1."""
from __future__ import annotations

from datetime import datetime

from etl.config import SEMESTER_BY_MONTH, TZ


def academic_term(course_start: datetime | int) -> tuple[str, int]:
    """
    Trả về (academic_year, semester), ví dụ 07/09/2026 -> ('2026-2027', 1); 15/02/2027 -> ('2026-2027', 2).
    course_start: datetime có múi giờ hoặc epoch giây (mdl_course.startdate).
    """
    if isinstance(course_start, (int, float)):
        if course_start <= 0:
            raise ValueError("mdl_course.startdate = 0: môn học chưa đặt ngày bắt đầu, không suy ra được học kỳ")
        course_start = datetime.fromtimestamp(course_start, TZ)
    elif course_start.tzinfo is None:
        raise ValueError("course_start phải có múi giờ")

    local = course_start.astimezone(TZ)
    semester = SEMESTER_BY_MONTH[local.month]
    first_year = local.year if semester == 1 else local.year - 1
    return f"{first_year}-{first_year + 1}", semester
