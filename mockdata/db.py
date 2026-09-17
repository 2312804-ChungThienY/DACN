"""Truy cập CSDL nguồn moodle_src cho các script sinh dữ liệu giả lập (psycopg 3, COPY hàng loạt)."""
from __future__ import annotations

from collections.abc import Iterable, Sequence

import pandas as pd
import psycopg
from psycopg import sql

from database.config import load_db_config

# Toàn bộ bảng mdl_* do migration moodle tạo (thứ tự không quan trọng vì không có khóa ngoại)
STRUCTURE_TABLES = (
    "mdl_course_categories", "mdl_course", "mdl_user", "mdl_role", "mdl_context", "mdl_role_assignments",
    "mdl_enrol", "mdl_user_enrolments", "mdl_groups", "mdl_groups_members", "mdl_modules",
    "mdl_course_sections", "mdl_course_modules", "mdl_assign", "mdl_page", "mdl_forum",
    "mdl_attendance", "mdl_attendance_sessions", "mdl_attendance_statuses",
)
ACTIVITY_TABLES = (
    "mdl_logstore_standard_log", "mdl_sessions", "mdl_user_lastaccess", "mdl_assign_submission",
    "mdl_attendance_log", "mdl_course_modules_completion",
)


def connect() -> psycopg.Connection:
    cfg = load_db_config("MOODLE_DB")
    return psycopg.connect(**cfg.conninfo(application_name="lms-mockdata"))


def fetch_frame(conn: psycopg.Connection, query: str, params: dict | None = None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(query, params)
        columns = [col.name for col in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=columns)


def count_rows(conn: psycopg.Connection, table: str) -> int:
    return conn.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))).fetchone()[0]


def truncate(conn: psycopg.Connection, tables: Iterable[str]) -> None:
    conn.execute(
        sql.SQL("TRUNCATE {} RESTART IDENTITY").format(sql.SQL(", ").join(map(sql.Identifier, tables)))
    )


def copy_rows(conn: psycopg.Connection, table: str, columns: Sequence[str], rows: Iterable[Sequence]) -> int:
    """Nạp hàng loạt bằng COPY FROM STDIN. Giá trị None được ghi thành NULL."""
    statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns))
    )
    count = 0
    with conn.cursor() as cur, cur.copy(statement) as copy:
        for row in rows:
            copy.write_row(row)
            count += 1
    return count


def frame_rows(df: pd.DataFrame) -> Iterable[tuple]:
    """Chuyển DataFrame thành các tuple kiểu Python thuần (numpy scalar -> int/float/str, NaN/NA -> None)."""
    columns = []
    for name in df.columns:
        series = df[name]
        columns.append(series.astype(object).where(series.notna(), None).tolist())
    return zip(*columns)


def copy_frame(conn: psycopg.Connection, table: str, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    return copy_rows(conn, table, list(df.columns), frame_rows(df))


def analyze_tables(tables: Iterable[str]) -> None:
    """ANALYZE sau khi nạp hàng loạt (kết nối autocommit, sau khi dữ liệu đã commit)."""
    cfg = load_db_config("MOODLE_DB")
    with psycopg.connect(**cfg.conninfo(application_name="lms-mockdata"), autocommit=True) as conn:
        for table in tables:
            conn.execute(sql.SQL("ANALYZE {}").format(sql.Identifier(table)))


def sync_sequence(conn: psycopg.Connection, table: str) -> None:
    """Đồng bộ sequence của cột id sau khi COPY với id tường minh (để Moodle/ETL chèn tiếp không trùng)."""
    conn.execute(
        sql.SQL("SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE((SELECT MAX(id) FROM {}), 0) + 1, false)")
        .format(sql.Identifier(table)),
        (table,),
    )
