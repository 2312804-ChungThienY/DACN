"""Extract: câu SQL trích xuất Moodle trong etl/extract/sql/*.sql (SPEC Phần 1, tham số hóa bằng :as_of)."""
from __future__ import annotations

from pathlib import Path

from etl.sqlfile import SqlLibrary

_LIBRARY = SqlLibrary(Path(__file__).resolve().parent / "sql")
load_sql = _LIBRARY.get
