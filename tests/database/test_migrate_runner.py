"""Kiểm thử đơn vị cho database/migrate.py (không cần kết nối CSDL)."""
from pathlib import Path

import pytest

from database.migrate import MigrationError, discover_migrations, validate_history


def _write(directory: Path, name: str, content: str, newline: str = "\n") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(content.replace("\n", newline).encode("utf-8"))


def test_real_analytics_migrations_are_valid():
    migrations = discover_migrations("analytics")
    assert [m.version for m in migrations] == [1, 2, 3, 4, 5, 6, 7]


def test_real_moodle_migrations_are_valid():
    migrations = discover_migrations("moodle")
    assert [m.version for m in migrations] == [1, 2, 3, 4]


def test_checksum_ignores_crlf_line_endings(tmp_path):
    _write(tmp_path / "lf", "V001__a.sql", "SELECT 1;\nSELECT 2;\n")
    _write(tmp_path / "crlf", "V001__a.sql", "SELECT 1;\nSELECT 2;\n", newline="\r\n")
    lf = discover_migrations("lf", root=tmp_path)[0]
    crlf = discover_migrations("crlf", root=tmp_path)[0]
    assert lf.checksum == crlf.checksum


@pytest.mark.parametrize("filename", ["V1__a.sql", "V001_a.sql", "V001__Tao-Bang.sql", "001__a.sql"])
def test_invalid_filename_is_rejected(tmp_path, filename):
    _write(tmp_path / "t", filename, "SELECT 1;")
    with pytest.raises(MigrationError, match="Tên file migration không hợp lệ"):
        discover_migrations("t", root=tmp_path)


def test_duplicate_version_is_rejected(tmp_path):
    _write(tmp_path / "t", "V001__a.sql", "SELECT 1;")
    _write(tmp_path / "t", "V001__b.sql", "SELECT 2;")
    with pytest.raises(MigrationError, match="Trùng phiên bản"):
        discover_migrations("t", root=tmp_path)


def test_explicit_transaction_statements_are_rejected(tmp_path):
    _write(tmp_path / "t", "V001__a.sql", "BEGIN;\nSELECT 1;\nCOMMIT;\n")
    with pytest.raises(MigrationError, match="BEGIN/COMMIT/ROLLBACK"):
        discover_migrations("t", root=tmp_path)


def test_plpgsql_begin_block_is_allowed(tmp_path):
    _write(tmp_path / "t", "V001__a.sql", "CREATE FUNCTION f() RETURNS int LANGUAGE plpgsql AS $$\nBEGIN\n  RETURN 1;\nEND;\n$$;")
    assert len(discover_migrations("t", root=tmp_path)) == 1


def test_modified_applied_migration_is_rejected(tmp_path):
    _write(tmp_path / "t", "V001__a.sql", "SELECT 1;")
    migrations = discover_migrations("t", root=tmp_path)
    with pytest.raises(MigrationError, match="checksum khác"):
        validate_history(migrations, {1: ("a", "0" * 64)})


def test_missing_file_for_applied_migration_is_rejected(tmp_path):
    _write(tmp_path / "t", "V002__b.sql", "SELECT 1;")
    migrations = discover_migrations("t", root=tmp_path)
    with pytest.raises(MigrationError, match="không còn file"):
        validate_history(migrations, {1: ("a", "0" * 64)})


def test_skipped_older_migration_is_rejected(tmp_path):
    _write(tmp_path / "t", "V001__a.sql", "SELECT 1;")
    _write(tmp_path / "t", "V002__b.sql", "SELECT 2;")
    migrations = discover_migrations("t", root=tmp_path)
    with pytest.raises(MigrationError, match="chưa chạy"):
        validate_history(migrations, {2: ("b", migrations[1].checksum)})
