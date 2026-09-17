"""Chuyển giá trị CSDL sang dạng hiển thị trong file xuất (định dạng số/ngày kiểu vi-VN)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from backend.app.core.config import TZ

RISK_LABELS = {"RED": "Nguy cơ cao", "YELLOW": "Cần lưu ý", "GREEN": "An toàn"}
RISK_COLORS = {"RED": "D64545", "YELLOW": "B07F00", "GREEN": "2E9D5B"}   # vàng đậm hơn #E0A100 để đọc được trên nền trắng
NEVER_ACCESSED = "Chưa truy cập"
NO_DATA = "–"       # tỷ lệ NULL = chưa có dữ liệu (migration V007), khác với 0%


@dataclass(frozen=True)
class ExportDocument:
    title: str
    columns: tuple            # tuple[Column, ...]
    rows: list[dict]
    filters: list[tuple[str, str]]
    generated_at: datetime


def _local_naive(value: datetime) -> datetime:
    return value.astimezone(TZ).replace(tzinfo=None) if value.tzinfo else value


def _vi_number(value: float, digits: int) -> str:
    text = f"{value:,.{digits}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def excel_value(value, kind: str):
    """Giá trị gốc cho ô Excel (giữ kiểu số/ngày để người dùng lọc, tính toán được)."""
    if kind == "days" and value is None:
        return NEVER_ACCESSED
    if value is None:
        return None
    if kind == "risk_level":
        return RISK_LABELS.get(value, value)
    if kind == "bool":
        return "Có" if value else "Không"
    if kind == "list":
        return "; ".join(map(str, value))
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return _local_naive(value)
    return value


def text_value(value, kind: str) -> str:
    """Chuỗi hiển thị cho PDF."""
    if kind == "days" and value is None:
        return NEVER_ACCESSED
    if kind == "percent" and value is None:
        return NO_DATA
    if value is None:
        return ""
    if kind == "risk_level":
        return RISK_LABELS.get(value, str(value))
    if kind == "bool":
        return "Có" if value else ""
    if kind == "list":
        return "; ".join(map(str, value))
    if kind in ("int", "days"):
        return _vi_number(float(value), 0)
    if kind in ("percent", "decimal"):
        return _vi_number(float(value), 2)
    if isinstance(value, datetime):
        return _local_naive(value).strftime("%d/%m/%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)
