"""Tài khoản Dashboard (analytics.app_user)."""
from __future__ import annotations

from sqlalchemy import Connection

from backend.app.core.db import fetch_one


def find_by_username(conn: Connection, username: str) -> dict | None:
    return fetch_one(conn, """
        SELECT user_id, username, full_name, email, role, password_hash, is_active
        FROM analytics.app_user WHERE lower(username) = lower(:username)""", {"username": username})
