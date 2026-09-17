"""
Kết nối CSDL phân tích cho API (SQLAlchemy Core + psycopg 3, pool_size=10 – SPEC 5.1).

Mỗi request mượn một Connection từ pool (dependency get_conn). Endpoint chỉ đọc không cần commit;
endpoint ghi (can thiệp, đăng nhập) gọi conn.commit() tường minh trong repository.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from functools import lru_cache
from typing import Any

from sqlalchemy import URL, Connection, Engine, create_engine, text

from backend.app.core.config import APP_TIMEZONE, get_settings
from database.config import load_db_config


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    cfg = load_db_config("ANALYTICS_DB")
    settings = get_settings()
    url = URL.create("postgresql+psycopg", username=cfg.user, password=cfg.password,
                     host=cfg.host, port=cfg.port, database=cfg.dbname)
    options = f"-c statement_timeout={settings.db_statement_timeout_ms} -c timezone={APP_TIMEZONE}"
    return create_engine(url, pool_pre_ping=True, pool_size=settings.db_pool_size, max_overflow=5,
                         connect_args={"options": options, "application_name": "lms-backend", "connect_timeout": 5})


def get_conn() -> Iterator[Connection]:
    with get_engine().connect() as conn:
        yield conn


def fetch_all(conn: Connection, sql: str, params: Mapping[str, Any] | None = None) -> list[dict]:
    """Chạy truy vấn có tham số bind, trả về danh sách dict (không bao giờ ghép giá trị vào chuỗi SQL)."""
    return [dict(r) for r in conn.execute(text(sql), dict(params or {})).mappings()]


def fetch_one(conn: Connection, sql: str, params: Mapping[str, Any] | None = None) -> dict | None:
    row = conn.execute(text(sql), dict(params or {})).mappings().first()
    return dict(row) if row is not None else None


def fetch_value(conn: Connection, sql: str, params: Mapping[str, Any] | None = None) -> Any:
    return conn.execute(text(sql), dict(params or {})).scalar()
