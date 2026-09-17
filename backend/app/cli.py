"""
Quản lý tài khoản Dashboard (analytics.app_user). user_id = mdl_user.id để khớp teacher_ids trong bảng fact.

    python -m backend.app.cli sync-users [--password ...] [--reset-password] [--admin admin]
    python -m backend.app.cli set-password --username gv.tranminhhung [--password ...]
    python -m backend.app.cli list-users

sync-users lấy từ Moodle: tài khoản có vai trò editingteacher/teacher trong ít nhất một môn -> TEACHER;
username trong --admin (mặc định "admin") -> ADMIN. Tài khoản Moodle bị khóa -> is_active = false;
TEACHER không còn trong Moodle -> is_active = false. Mật khẩu chỉ đặt cho tài khoản MỚI (trừ khi --reset-password).
Mật khẩu lấy từ --password, biến BACKEND_SEED_PASSWORD, hoặc nhập từ bàn phím.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys

import psycopg
from psycopg import errors

from backend.app.core.security import ROLE_ADMIN, ROLE_TEACHER, hash_password
from database.config import load_db_config

MIN_PASSWORD_LENGTH = 8

MOODLE_ACCOUNTS_SQL = """
SELECT u.id, u.username, u.firstname, u.lastname, NULLIF(u.email, '') AS email, u.suspended,
       CASE WHEN u.username = ANY(%(admins)s) THEN 'ADMIN' ELSE 'TEACHER' END AS role
FROM mdl_user u
WHERE u.deleted = 0
  AND (u.username = ANY(%(admins)s)
       OR EXISTS (SELECT 1
                  FROM mdl_role_assignments ra
                  JOIN mdl_role r      ON r.id = ra.roleid AND r.shortname IN ('editingteacher', 'teacher')
                  JOIN mdl_context ctx ON ctx.id = ra.contextid AND ctx.contextlevel = 50
                  WHERE ra.userid = u.id))
ORDER BY u.id
"""


def _read_password(value: str | None, *, required: bool) -> str | None:
    password = value or os.getenv("BACKEND_SEED_PASSWORD")
    if not password and required and sys.stdin.isatty():
        password = getpass.getpass("Mật khẩu: ")
        if getpass.getpass("Nhập lại mật khẩu: ") != password:
            raise SystemExit("Hai lần nhập mật khẩu không khớp")
    if password is None:
        if required:
            raise SystemExit("Cần mật khẩu: dùng --password, biến BACKEND_SEED_PASSWORD hoặc chạy trong terminal")
        return None
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"Mật khẩu phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự")
    return password


def _analytics() -> psycopg.Connection:
    return psycopg.connect(**load_db_config("ANALYTICS_DB").conninfo(application_name="lms-backend-cli"))


def sync_users(password_arg: str | None, reset_password: bool, admins: list[str]) -> int:
    with psycopg.connect(**load_db_config("MOODLE_DB").conninfo(application_name="lms-backend-cli")) as moodle:
        moodle.read_only = True
        accounts = moodle.execute(MOODLE_ACCOUNTS_SQL, {"admins": admins}).fetchall()

    with _analytics() as conn:
        existing = {row[0] for row in conn.execute("SELECT user_id FROM analytics.app_user")}
        new_count = sum(1 for a in accounts if a[0] not in existing)
        password = _read_password(password_arg, required=bool(new_count) or reset_password)

        created = updated = 0
        try:
            for user_id, username, firstname, lastname, email, suspended, role in accounts:
                full_name = f"{lastname} {firstname}".strip()
                params = {"id": user_id, "username": username, "full_name": full_name, "email": email,
                          "role": role, "active": suspended == 0}
                if user_id in existing:
                    set_password = ", password_hash = %(hash)s" if reset_password else ""
                    if reset_password:
                        params["hash"] = hash_password(password)
                    conn.execute(f"""UPDATE analytics.app_user
                                     SET username = %(username)s, full_name = %(full_name)s, email = %(email)s,
                                         role = %(role)s, is_active = %(active)s{set_password}
                                     WHERE user_id = %(id)s""", params)
                    updated += 1
                else:
                    params["hash"] = hash_password(password)
                    conn.execute("""INSERT INTO analytics.app_user (user_id, username, full_name, email, role,
                                                                     password_hash, is_active)
                                    VALUES (%(id)s, %(username)s, %(full_name)s, %(email)s, %(role)s,
                                            %(hash)s, %(active)s)""", params)
                    created += 1
            deactivated = conn.execute("""
                UPDATE analytics.app_user SET is_active = FALSE
                WHERE role = %s AND is_active AND NOT (user_id = ANY(%s))""",
                (ROLE_TEACHER, [a[0] for a in accounts if a[6] == ROLE_TEACHER])).rowcount
        except errors.UniqueViolation as exc:
            conn.rollback()
            raise SystemExit(f"Trùng username với một tài khoản khác trong app_user: {exc.diag.message_detail}") from exc

    print(f"Đồng bộ xong: {created} tài khoản mới, {updated} cập nhật, {deactivated} giảng viên bị vô hiệu hóa.")
    list_users()
    return 0


def set_password(username: str, password_arg: str | None) -> int:
    password = _read_password(password_arg, required=True)
    with _analytics() as conn:
        count = conn.execute("UPDATE analytics.app_user SET password_hash = %s WHERE lower(username) = lower(%s)",
                             (hash_password(password), username)).rowcount
    if not count:
        raise SystemExit(f"Không tìm thấy tài khoản {username!r}")
    print(f"Đã đặt mật khẩu mới cho {username}.")
    return 0


def list_users() -> int:
    with _analytics() as conn:
        rows = conn.execute("""SELECT user_id, username, role, is_active, full_name
                               FROM analytics.app_user ORDER BY role, user_id""").fetchall()
    print(f"{'user_id':>7}  {'username':<22} {'role':<8} {'active':<6} full_name")
    for user_id, username, role, active, full_name in rows:
        print(f"{user_id:>7}  {username:<22} {role:<8} {str(active):<6} {full_name or ''}")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Quản lý tài khoản Dashboard")
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync-users", help="tạo/cập nhật tài khoản ADMIN và giảng viên từ Moodle")
    sync.add_argument("--password", help="mật khẩu ban đầu cho tài khoản mới")
    sync.add_argument("--reset-password", action="store_true", help="đặt lại mật khẩu cho mọi tài khoản đồng bộ")
    sync.add_argument("--admin", action="append", dest="admins", help="username Moodle được cấp quyền ADMIN (lặp được)")
    pwd = sub.add_parser("set-password", help="đặt mật khẩu cho một tài khoản")
    pwd.add_argument("--username", required=True)
    pwd.add_argument("--password")
    sub.add_parser("list-users", help="liệt kê tài khoản")
    args = parser.parse_args(argv)

    if args.command == "sync-users":
        return sync_users(args.password, args.reset_password, args.admins or ["admin"])
    if args.command == "set-password":
        return set_password(args.username, args.password)
    return list_users()


if __name__ == "__main__":
    sys.exit(main())
