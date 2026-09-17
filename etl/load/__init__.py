"""Load: nạp dữ liệu vào CSDL phân tích bằng COPY -> bảng tạm -> INSERT ... ON CONFLICT (SPEC 4.1)."""
from __future__ import annotations

from pathlib import Path

from etl.sqlfile import SqlLibrary

_LIBRARY = SqlLibrary(Path(__file__).resolve().parent / "sql")
load_sql = _LIBRARY.get
