"""
Thư viện file SQL tĩnh của ETL.

Cú pháp {{ten}} trong file SQL chèn nguyên văn đoạn SQL dùng chung trong file _ten.sql cùng thư mục
(chỉ ghép đoạn SQL tĩnh của dự án – mọi GIÁ TRỊ đều truyền qua tham số bind).
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_INCLUDE = re.compile(r"\{\{(\w+)\}\}")


class SqlLibrary:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.get = lru_cache(maxsize=None)(self._load)

    def _load(self, name: str) -> str:
        path = self.directory / f"{name}.sql"
        if not path.is_file():
            raise FileNotFoundError(f"Không tìm thấy file SQL: {path}")
        content = path.read_text(encoding="utf-8")
        return _INCLUDE.sub(lambda m: self.get(f"_{m.group(1)}").strip(), content)
