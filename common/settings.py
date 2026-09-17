"""
Thiết lập dùng chung: múi giờ ứng dụng và thời điểm tham chiếu AS_OF.

AS_OF thay cho now() trong mọi phép tính "tính đến thời điểm hiện tại" (ETL, mock data):
    - LMS_AS_OF để trống  -> dùng thời gian thực (chế độ vận hành thật).
    - LMS_AS_OF=2026-11-06T10:30:00+07:00 -> "đóng băng" đồng hồ tại thời điểm đó
      (chế độ demo: mock data được sinh tới AS_OF và ETL tính rủi ro tại AS_OF).
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Ho_Chi_Minh")
TZ = ZoneInfo(APP_TIMEZONE)


class SettingsError(RuntimeError):
    """Giá trị cấu hình dùng chung không hợp lệ."""


def parse_as_of(raw: str | None, tz: ZoneInfo = TZ) -> datetime | None:
    """Chuyển chuỗi ISO 8601 thành datetime có múi giờ. Chuỗi rỗng/None -> None (dùng thời gian thực)."""
    if raw is None or not raw.strip():
        return None
    try:
        value = datetime.fromisoformat(raw.strip())
    except ValueError as exc:
        raise SettingsError(
            f"LMS_AS_OF không đúng định dạng ISO 8601: {raw!r} (ví dụ 2026-11-06T10:30:00+07:00)"
        ) from exc
    if value.tzinfo is None:
        value = value.replace(tzinfo=tz)
    return value.astimezone(tz)


def is_clock_frozen() -> bool:
    return parse_as_of(os.getenv("LMS_AS_OF")) is not None


def resolve_as_of(override: datetime | None = None) -> datetime:
    """Thời điểm tham chiếu. Thứ tự ưu tiên: tham số truyền vào > LMS_AS_OF > thời gian thực."""
    if override is not None:
        return (override if override.tzinfo else override.replace(tzinfo=TZ)).astimezone(TZ)
    fixed = parse_as_of(os.getenv("LMS_AS_OF"))
    return fixed if fixed is not None else datetime.now(TZ)
