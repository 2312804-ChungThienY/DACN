"""
Cấu hình Backend đọc từ .env (tiền tố BACKEND_*), cùng thời điểm tham chiếu AS_OF dùng chung với ETL.

"Hôm nay", "giờ hiện tại" của API luôn tính theo AS_OF: khi LMS_AS_OF được đặt (chế độ demo), Dashboard
hiển thị đúng thời điểm mà mock data và ETL đã "đóng băng"; để trống thì là thời gian thực.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from common.settings import APP_TIMEZONE, TZ, resolve_as_of  # noqa: F401  (tái xuất)

MIN_SECRET_LENGTH = 32
_FONT_CANDIDATES = (
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
)


class BackendConfigError(RuntimeError):
    """Thiếu hoặc sai cấu hình Backend."""


def _default_fonts() -> tuple[str, str]:
    for regular, bold in _FONT_CANDIDATES:
        if Path(regular).is_file():
            return regular, bold if Path(bold).is_file() else regular
    return "", ""


@dataclass(frozen=True)
class BackendSettings:
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
    cache_ttl_seconds: int = 60
    login_max_failures: int = 5
    login_window_seconds: int = 300
    db_pool_size: int = 10
    db_statement_timeout_ms: int = 15_000
    pdf_font: str = ""
    pdf_font_bold: str = ""
    pdf_max_rows: int = 5_000
    excel_max_rows: int = 200_000


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise BackendConfigError(f"{name} phải là số nguyên, nhận được {raw!r}") from exc


@lru_cache(maxsize=1)
def get_settings() -> BackendSettings:
    secret = os.getenv("BACKEND_JWT_SECRET", "")
    if len(secret) < MIN_SECRET_LENGTH:
        raise BackendConfigError(
            f"BACKEND_JWT_SECRET phải dài ít nhất {MIN_SECRET_LENGTH} ký tự (khai báo trong .env). "
            "Tạo nhanh: python -c \"import secrets; print(secrets.token_urlsafe(48))\"")
    font, font_bold = _default_fonts()
    origins = tuple(o.strip() for o in os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip())
    return BackendSettings(
        jwt_secret=secret,
        jwt_expire_minutes=_int_env("BACKEND_JWT_EXPIRE_MINUTES", 480),
        cors_origins=origins,
        cache_ttl_seconds=_int_env("BACKEND_CACHE_TTL_SECONDS", 60),
        pdf_font=os.getenv("BACKEND_PDF_FONT") or font,
        # Tự khai báo font thường mà không có font đậm -> dùng luôn font thường (không trộn với font mặc định)
        pdf_font_bold=os.getenv("BACKEND_PDF_FONT_BOLD") or ("" if os.getenv("BACKEND_PDF_FONT") else font_bold),
        pdf_max_rows=_int_env("BACKEND_PDF_MAX_ROWS", 5_000),
        excel_max_rows=_int_env("BACKEND_EXCEL_MAX_ROWS", 200_000),
    )


def as_of() -> datetime:
    """Thời điểm tham chiếu hiện tại (LMS_AS_OF hoặc thời gian thực), giờ địa phương."""
    return resolve_as_of()


def today() -> date:
    return as_of().date()
