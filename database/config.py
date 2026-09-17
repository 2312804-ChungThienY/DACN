"""
Cấu hình kết nối CSDL dùng chung cho mọi lớp (Database / ETL / Backend).

Thông tin kết nối đọc từ biến môi trường, nạp từ file .env ở thư mục gốc dự án.
Mỗi CSDL dùng một tiền tố riêng:
    ANALYTICS_DB_*  -> CSDL phân tích lms_analytics (3 bảng fact)
    MOODLE_DB_*     -> CSDL nguồn moodle_src (bảng mdl_* rút gọn, dùng từ Bước 2)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

_REQUIRED_KEYS = ("HOST", "PORT", "NAME", "USER", "PASSWORD")


class ConfigError(RuntimeError):
    """Thiếu hoặc sai cấu hình kết nối CSDL."""


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str
    maintenance_db: str = "postgres"

    def conninfo(self, dbname: str | None = None, application_name: str = "lms-analytics") -> dict[str, object]:
        """Tham số cho psycopg.connect(**conninfo)."""
        return {
            "host": self.host,
            "port": self.port,
            "dbname": dbname or self.dbname,
            "user": self.user,
            "password": self.password,
            "connect_timeout": 5,
            "client_encoding": "UTF8",
            "application_name": application_name,
        }


def load_db_config(prefix: str) -> DbConfig:
    """Đọc cấu hình theo tiền tố (vd 'ANALYTICS_DB'). Thiếu biến nào báo lỗi rõ ràng biến đó."""
    values = {key: os.getenv(f"{prefix}_{key}") for key in _REQUIRED_KEYS}
    missing = [f"{prefix}_{key}" for key, value in values.items() if not value]
    if missing:
        raise ConfigError(
            "Thiếu biến môi trường: " + ", ".join(missing)
            + f". Hãy sao chép .env.example thành .env và điền giá trị ({PROJECT_ROOT / '.env'})."
        )
    try:
        port = int(values["PORT"])
    except ValueError as exc:
        raise ConfigError(f"{prefix}_PORT phải là số nguyên, nhận được: {values['PORT']!r}") from exc

    return DbConfig(
        host=values["HOST"],
        port=port,
        dbname=values["NAME"],
        user=values["USER"],
        password=values["PASSWORD"],
        maintenance_db=os.getenv(f"{prefix}_MAINTENANCE_DB", "postgres"),
    )
