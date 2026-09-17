"""
Trình chạy migration của Database Layer.

- Migration là file SQL đặt tên theo mẫu  V<3 chữ số>__<mo_ta>.sql  trong
  database/migrations/<target>/ và được áp dụng tăng dần theo phiên bản.
- Mỗi file chạy trong MỘT transaction: lỗi ở bất kỳ câu lệnh nào -> rollback cả file.
- Lịch sử lưu ở bảng public.schema_migrations (version, checksum SHA-256, thời gian chạy).
  File đã áp dụng mà bị sửa nội dung -> báo lỗi; muốn thay đổi schema phải tạo phiên bản mới.

Cách dùng (chạy từ thư mục gốc dự án):
    python -m database.migrate status --target analytics
    python -m database.migrate up     --target analytics
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg import sql

from database.config import ConfigError, DbConfig, load_db_config

MIGRATIONS_ROOT = Path(__file__).resolve().parent / "migrations"
FILENAME_PATTERN = re.compile(r"^V(?P<version>\d{3})__(?P<name>[a-z0-9_]+)\.sql$")
# Migration tự mở/đóng transaction sẽ phá cơ chế rollback theo file của runner.
FORBIDDEN_TX_PATTERN = re.compile(r"^\s*(BEGIN|COMMIT|ROLLBACK)\s*;", re.IGNORECASE | re.MULTILINE)
# Khóa advisory để hai tiến trình migrate không chạy chồng lên nhau.
ADVISORY_LOCK_KEY = 7_424_001

# target -> tiền tố biến môi trường trong .env
#   analytics : CSDL phân tích (3 bảng fact)
#   moodle    : CSDL nguồn Moodle 3.9 rút gọn (bảng mdl_*) dùng cho mock data và ETL
TARGETS: dict[str, str] = {"analytics": "ANALYTICS_DB", "moodle": "MOODLE_DB"}

HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version      INTEGER     PRIMARY KEY,
    name         TEXT        NOT NULL,
    checksum     CHAR(64)    NOT NULL,
    applied_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    execution_ms INTEGER     NOT NULL CHECK (execution_ms >= 0)
)
"""


class MigrationError(RuntimeError):
    """Lỗi của tiến trình migration (tên file, checksum, thứ tự, câu lệnh SQL lỗi...)."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path
    checksum: str

    @property
    def label(self) -> str:
        return f"V{self.version:03d}__{self.name}"


def read_sql(path: Path) -> str:
    """Đọc file SQL, chuẩn hóa CRLF -> LF để checksum không đổi khi Git trên Windows đổi kiểu xuống dòng."""
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def discover_migrations(target: str, root: Path = MIGRATIONS_ROOT) -> list[Migration]:
    directory = root / target
    if not directory.is_dir():
        raise MigrationError(f"Không tìm thấy thư mục migration: {directory}")

    migrations: dict[int, Migration] = {}
    for path in sorted(directory.glob("*.sql")):
        match = FILENAME_PATTERN.match(path.name)
        if not match:
            raise MigrationError(f"Tên file migration không hợp lệ: {path.name} (mẫu đúng: V001__mo_ta.sql)")
        content = read_sql(path)
        if FORBIDDEN_TX_PATTERN.search(content):
            raise MigrationError(f"{path.name} chứa BEGIN/COMMIT/ROLLBACK – runner đã tự bọc transaction cho mỗi file.")
        version = int(match["version"])
        if version in migrations:
            raise MigrationError(f"Trùng phiên bản V{version:03d}: {migrations[version].path.name} và {path.name}")
        migrations[version] = Migration(
            version=version,
            name=match["name"],
            path=path,
            checksum=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )
    return [migrations[v] for v in sorted(migrations)]


def validate_history(migrations: list[Migration], applied: dict[int, tuple[str, str]]) -> None:
    """Đảm bảo lịch sử trên CSDL khớp với các file trên đĩa trước khi áp dụng thêm."""
    on_disk = {m.version: m for m in migrations}
    for version, (name, checksum) in sorted(applied.items()):
        migration = on_disk.get(version)
        if migration is None:
            raise MigrationError(f"V{version:03d}__{name} đã áp dụng trên CSDL nhưng không còn file trên đĩa.")
        if migration.checksum != checksum:
            raise MigrationError(
                f"{migration.label} đã áp dụng nhưng nội dung file đã bị sửa (checksum khác). "
                "Không sửa migration cũ – hãy tạo file phiên bản mới."
            )
    if applied:
        latest = max(applied)
        skipped = [m.label for m in migrations if m.version < latest and m.version not in applied]
        if skipped:
            raise MigrationError("Có migration phiên bản cũ hơn bản đã áp dụng nhưng chưa chạy: " + ", ".join(skipped))


def database_exists(cfg: DbConfig) -> bool:
    with psycopg.connect(**cfg.conninfo(dbname=cfg.maintenance_db, application_name="lms-migrate"), autocommit=True) as conn:
        return conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (cfg.dbname,)).fetchone() is not None


def create_database(cfg: DbConfig) -> None:
    # CREATE DATABASE không chạy được trong transaction -> dùng kết nối autocommit.
    with psycopg.connect(**cfg.conninfo(dbname=cfg.maintenance_db, application_name="lms-migrate"), autocommit=True) as conn:
        conn.execute(
            sql.SQL("CREATE DATABASE {} WITH ENCODING 'UTF8' TEMPLATE template0").format(sql.Identifier(cfg.dbname))
        )


def fetch_applied(conn: psycopg.Connection) -> dict[int, tuple[str, str]]:
    if conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()[0] is None:
        return {}
    rows = conn.execute("SELECT version, name, checksum FROM public.schema_migrations ORDER BY version").fetchall()
    return {version: (name, checksum) for version, name, checksum in rows}


def cmd_status(cfg: DbConfig, target: str) -> int:
    migrations = discover_migrations(target)
    applied: dict[int, tuple[str, str]] = {}
    if database_exists(cfg):
        with psycopg.connect(**cfg.conninfo(application_name="lms-migrate"), autocommit=True) as conn:
            applied = fetch_applied(conn)
    else:
        print(f"Database '{cfg.dbname}' chưa tồn tại (sẽ được tạo khi chạy 'up').")

    print(f"Migration của target '{target}' trên {cfg.host}:{cfg.port}/{cfg.dbname}:")
    for m in migrations:
        if m.version not in applied:
            mark = "[ ] chờ áp dụng"
        elif applied[m.version][1] != m.checksum:
            mark = "[!] ĐÃ BỊ SỬA SAU KHI ÁP DỤNG"
        else:
            mark = "[x] đã áp dụng"
        print(f"  {mark:<32} {m.label}")
    validate_history(migrations, applied)
    return 0


def cmd_up(cfg: DbConfig, target: str) -> int:
    migrations = discover_migrations(target)
    if not database_exists(cfg):
        create_database(cfg)
        print(f"Đã tạo database '{cfg.dbname}' (UTF8).")

    with psycopg.connect(**cfg.conninfo(application_name="lms-migrate"), autocommit=True) as conn:
        conn.execute(HISTORY_DDL)
        conn.execute("SELECT pg_advisory_lock(%s)", (ADVISORY_LOCK_KEY,))
        try:
            applied = fetch_applied(conn)
            validate_history(migrations, applied)
            pending = [m for m in migrations if m.version not in applied]
            if not pending:
                print("CSDL đã ở phiên bản mới nhất, không có migration nào cần áp dụng.")
                return 0

            for m in pending:
                started = time.perf_counter()
                try:
                    with conn.transaction():
                        conn.execute("SET LOCAL lock_timeout = '10s'")
                        conn.execute(read_sql(m.path))
                        elapsed_ms = int((time.perf_counter() - started) * 1000)
                        conn.execute(
                            "INSERT INTO public.schema_migrations (version, name, checksum, execution_ms) "
                            "VALUES (%s, %s, %s, %s)",
                            (m.version, m.name, m.checksum, elapsed_ms),
                        )
                except psycopg.Error as exc:
                    raise MigrationError(f"{m.label} thất bại và đã được rollback: {exc}") from exc
                print(f"  áp dụng {m.label} ({elapsed_ms} ms)")
            print(f"Hoàn tất: {len(pending)} migration.")
            return 0
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Quản lý migration CSDL phân tích LMS")
    parser.add_argument("command", choices=("status", "up"))
    parser.add_argument("--target", choices=sorted(TARGETS), default="analytics")
    args = parser.parse_args(argv)

    try:
        cfg = load_db_config(TARGETS[args.target])
    except ConfigError as exc:
        print(f"LỖI CẤU HÌNH: {exc}", file=sys.stderr)
        return 1

    try:
        handler = cmd_up if args.command == "up" else cmd_status
        return handler(cfg, args.target)
    except MigrationError as exc:
        print(f"LỖI MIGRATION: {exc}", file=sys.stderr)
        return 1
    except psycopg.OperationalError as exc:
        print(f"LỖI KẾT NỐI CSDL {cfg.host}:{cfg.port} (user={cfg.user}): {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
