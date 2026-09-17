"""
UPSERT hàng loạt vào schema analytics (SPEC 4.1 – load/upsert.py).

Luồng: CREATE TEMP TABLE (LIKE bảng đích) -> COPY dữ liệu vào bảng tạm -> INSERT ... SELECT ... ON CONFLICT DO UPDATE.
- Bảng tạm kế thừa kiểu/domain/NOT NULL của bảng đích nên dữ liệu sai bị chặn ngay khi COPY.
- Chỉ UPDATE khi giá trị thực sự thay đổi (IS DISTINCT FROM) -> chạy lại job không đổi updated_at/etl_run_id
  của dòng không đổi (idempotent, kiểm chứng được bằng checksum).
- Bảng tạm tồn tại tới hết transaction để bước sau có thể dùng (vd xóa dòng không còn trong nguồn).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy import Connection

SCHEMA = "analytics"


def temp_table_name(table: str) -> str:
    return f"tmp_{table}"


def copy_to_temp(conn: Connection, table: str, columns: Sequence[str], rows: Iterable[Mapping],
                 json_columns: Sequence[str] = ()) -> str:
    """Tạo bảng tạm cùng cấu trúc bảng đích và COPY các dòng vào. Trả về tên bảng tạm."""
    tmp = temp_table_name(table)
    json_set = set(json_columns)
    raw = conn.connection.driver_connection
    with raw.cursor() as cur:
        cur.execute(sql.SQL("DROP TABLE IF EXISTS pg_temp.{}").format(sql.Identifier(tmp)))
        cur.execute(sql.SQL("CREATE TEMP TABLE {} (LIKE {}.{} INCLUDING DEFAULTS) ON COMMIT DROP")
                    .format(sql.Identifier(tmp), sql.Identifier(SCHEMA), sql.Identifier(table)))
        copy_stmt = sql.SQL("COPY {} ({}) FROM STDIN").format(
            sql.Identifier(tmp), sql.SQL(", ").join(map(sql.Identifier, columns)))
        with cur.copy(copy_stmt) as copy:
            for row in rows:
                copy.write_row([Jsonb(row[c]) if c in json_set else row[c] for c in columns])
    return tmp


def upsert(conn: Connection, table: str, columns: Sequence[str], rows: Iterable[Mapping],
           key_columns: Sequence[str], json_columns: Sequence[str] = (),
           compare_exclude: Sequence[str] = ("etl_run_id",)) -> int:
    """UPSERT các dòng vào analytics.<table>. Trả về số dòng được chèn mới hoặc thay đổi."""
    missing_keys = set(key_columns) - set(columns)
    if missing_keys:
        raise ValueError(f"Thiếu cột khóa {missing_keys} khi upsert {table}")
    tmp = copy_to_temp(conn, table, columns, rows, json_columns)

    ident = lambda names, prefix=None: sql.SQL(", ").join(  # noqa: E731
        sql.Identifier(prefix, n) if prefix else sql.Identifier(n) for n in names)
    update_cols = [c for c in columns if c not in key_columns]
    compare_cols = [c for c in update_cols if c not in compare_exclude]

    statement = sql.SQL("INSERT INTO {schema}.{table} AS t ({cols}) SELECT {cols} FROM {tmp} ON CONFLICT ({keys}) ").format(
        schema=sql.Identifier(SCHEMA), table=sql.Identifier(table), cols=ident(columns),
        tmp=sql.Identifier(tmp), keys=ident(key_columns))
    if update_cols:
        statement += sql.SQL("DO UPDATE SET {assignments}").format(assignments=sql.SQL(", ").join(
            sql.SQL("{c} = EXCLUDED.{c}").format(c=sql.Identifier(c)) for c in update_cols))
        if compare_cols:
            statement += sql.SQL(" WHERE ({old}) IS DISTINCT FROM ({new})").format(
                old=ident(compare_cols, "t"), new=ident(compare_cols, "excluded"))
    else:
        statement += sql.SQL("DO NOTHING")

    with conn.connection.driver_connection.cursor() as cur:
        cur.execute(statement)
        return cur.rowcount
