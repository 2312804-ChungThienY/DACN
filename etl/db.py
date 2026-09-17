"""
Kết nối CSDL cho ETL (SQLAlchemy 2 + psycopg 3).

- moodle_engine(): CHỈ ĐỌC. Mọi transaction mặc định read-only và có statement_timeout,
  nên dù dùng tài khoản có quyền ghi, ETL cũng không thể sửa dữ liệu Moodle.
- analytics_engine(): đọc/ghi CSDL phân tích.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd
from sqlalchemy import URL, Connection, Engine, create_engine, text

from database.config import DbConfig, load_db_config
from etl import config


def _url(cfg: DbConfig) -> URL:
    return URL.create("postgresql+psycopg", username=cfg.user, password=cfg.password,
                      host=cfg.host, port=cfg.port, database=cfg.dbname)


@lru_cache(maxsize=1)
def moodle_engine() -> Engine:
    cfg = load_db_config("MOODLE_DB")
    options = f"-c default_transaction_read_only=on -c statement_timeout={config.MOODLE_STATEMENT_TIMEOUT_MS}"
    return create_engine(_url(cfg), pool_pre_ping=True, pool_size=5,
                         connect_args={"options": options, "application_name": "lms-etl-extract", "connect_timeout": 5})


@lru_cache(maxsize=1)
def analytics_engine() -> Engine:
    cfg = load_db_config("ANALYTICS_DB")
    options = (f"-c statement_timeout={config.ANALYTICS_STATEMENT_TIMEOUT_MS} "
               f"-c timezone={config.APP_TIMEZONE}")
    return create_engine(_url(cfg), pool_pre_ping=True, pool_size=5,
                         connect_args={"options": options, "application_name": "lms-etl-load", "connect_timeout": 5})


def read_frame(conn: Connection, sql: str, params: dict | None = None) -> pd.DataFrame:
    """Chạy truy vấn có tham số bind và trả về DataFrame (không bao giờ ghép chuỗi giá trị vào SQL)."""
    return pd.read_sql_query(text(sql), conn, params=params or {})
