"""
Xóa dữ liệu giả lập trong moodle_src (SPEC 3.3 – ghi chú 3).

    python -m mockdata.cleanup --activity   # chỉ xóa hành vi (log, bài nộp, điểm danh, hoàn thành, phiên...)
    python -m mockdata.cleanup --all        # xóa toàn bộ dữ liệu mdl_* (giữ nguyên schema)
"""
from __future__ import annotations

import argparse
import sys

from mockdata.db import ACTIVITY_TABLES, STRUCTURE_TABLES, connect, truncate
from mockdata.generate_activity import reset_activity


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Xóa dữ liệu giả lập trong moodle_src")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--activity", action="store_true", help="chỉ xóa dữ liệu hành vi")
    scope.add_argument("--all", action="store_true", help="xóa toàn bộ dữ liệu mdl_*")
    args = parser.parse_args(argv)

    with connect() as conn:
        if args.all:
            truncate(conn, STRUCTURE_TABLES + ACTIVITY_TABLES)
            print("Đã xóa toàn bộ dữ liệu mdl_* trong moodle_src.")
        else:
            reset_activity(conn)
            print("Đã xóa dữ liệu hành vi, giữ nguyên cấu trúc khóa học/người dùng.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
