"""
Tiện ích dựng SQL an toàn.

Chỉ ghép vào câu SQL các đoạn TĨNH lấy từ danh sách cho phép (điều kiện lọc, biểu thức sắp xếp);
mọi giá trị người dùng gửi lên luôn đi qua tham số bind.
"""
from __future__ import annotations

from collections.abc import Mapping

# Thứ tự mức rủi ro: RED -> YELLOW -> GREEN
LEVEL_RANK = "CASE risk_level WHEN 'RED' THEN 0 WHEN 'YELLOW' THEN 1 ELSE 2 END"

# SV "có tương tác trong học kỳ": có ít nhất 1 log từ ngày bắt đầu môn (khớp total_active_students của
# fact_course_progress_daily). weekly_activity chỉ đếm log từ startdate nên dùng được làm căn cứ.
IS_ACTIVE_IN_TERM = """EXISTS (SELECT 1 FROM jsonb_array_elements(weekly_activity) w
                               WHERE (w->>'views')::int + (w->>'actions')::int > 0)"""


def where(conditions: list[str]) -> str:
    return " AND ".join(conditions) if conditions else "TRUE"


def like_pattern(term: str) -> str:
    """Chuỗi tìm kiếm -> mẫu ILIKE chứa, đã thoát ký tự đặc biệt % _ \\."""
    escaped = term.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def order_by(sort: str, order: str, allowed: Mapping[str, str], tie_breaker: str) -> str:
    """allowed: tên sắp xếp -> biểu thức SQL tĩnh. order: asc|desc (đã được kiểm tra ở tầng API)."""
    if sort not in allowed:
        raise ValueError(f"Không hỗ trợ sắp xếp theo {sort!r}")
    direction = "DESC" if order == "desc" else "ASC"
    nulls = "NULLS LAST" if direction == "ASC" else "NULLS FIRST"
    return f"{allowed[sort]} {direction} {nulls}, {tie_breaker}"


def offset(page: int, page_size: int) -> int:
    return (page - 1) * page_size
