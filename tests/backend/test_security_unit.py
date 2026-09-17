"""Kiểm thử đơn vị không cần CSDL: mật khẩu, JWT, giới hạn đăng nhập, dựng SQL an toàn, định dạng xuất file."""
from __future__ import annotations

import os

os.environ.setdefault("BACKEND_JWT_SECRET", "pytest-only-secret-" + "x" * 40)

from datetime import date, datetime, timezone
from decimal import Decimal

import jwt
import pytest
from fastapi import HTTPException

from backend.app.core.config import get_settings
from backend.app.core.security import (LoginRateLimiter, create_access_token, decode_token, hash_password,
                                       verify_password)
from backend.app.repositories._sql import like_pattern, order_by
from backend.app.services.formatting import excel_value, text_value


def test_password_hash_roundtrip():
    hashed = hash_password("Mật-khẩu@2026")
    assert hashed.startswith("$2") and hashed != "Mật-khẩu@2026"
    assert verify_password("Mật-khẩu@2026", hashed)
    assert not verify_password("mật-khẩu@2026", hashed)


def test_password_limits_and_corrupt_hash():
    with pytest.raises(ValueError):
        hash_password("a" * 73)
    assert not verify_password("a" * 73, hash_password("a" * 72))
    assert not verify_password("anything", "not-a-bcrypt-hash")


def test_token_roundtrip():
    token, expires_in = create_access_token(42, "TEACHER", expires_minutes=5)
    payload = decode_token(token)
    assert payload["sub"] == "42" and payload["role"] == "TEACHER"
    assert expires_in == 300


def test_expired_and_tampered_tokens_are_rejected():
    expired, _ = create_access_token(42, "ADMIN", expires_minutes=-1)
    with pytest.raises(HTTPException) as exc:
        decode_token(expired)
    assert exc.value.status_code == 401 and "hết hạn" in exc.value.detail

    forged = jwt.encode({"sub": "42", "role": "ADMIN", "iat": datetime.now(timezone.utc),
                         "exp": datetime(2999, 1, 1, tzinfo=timezone.utc)}, "wrong-secret-" + "y" * 40, algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        decode_token(forged)
    assert exc.value.status_code == 401

    unsigned = jwt.encode({"sub": "42", "iat": 0, "exp": 32503680000}, key=None, algorithm="none")
    with pytest.raises(HTTPException):
        decode_token(unsigned)


def test_settings_require_long_secret(monkeypatch):
    monkeypatch.setenv("BACKEND_JWT_SECRET", "short")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="BACKEND_JWT_SECRET"):
            get_settings()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_login_rate_limiter_sliding_window():
    now = [1000.0]
    limiter = LoginRateLimiter(max_failures=3, window_seconds=60, clock=lambda: now[0])
    for _ in range(3):
        assert limiter.retry_after("1.1.1.1", "GV.A") == 0
        limiter.record_failure("1.1.1.1", "gv.a")
    assert limiter.retry_after("1.1.1.1", "gv.A") > 0          # không phân biệt hoa thường
    assert limiter.retry_after("2.2.2.2", "gv.a") == 0          # IP khác không bị ảnh hưởng
    now[0] += 61
    assert limiter.retry_after("1.1.1.1", "gv.a") == 0          # hết cửa sổ
    limiter.record_failure("1.1.1.1", "gv.a")
    limiter.reset("1.1.1.1", "gv.a")
    assert limiter.retry_after("1.1.1.1", "gv.a") == 0


def test_like_pattern_escapes_wildcards():
    assert like_pattern(" 50%_a\\b ") == "%50\\%\\_a\\\\b%"


def test_order_by_only_accepts_whitelisted_sorts():
    assert order_by("score", "desc", {"score": "risk_score"}, "user_id") == "risk_score DESC NULLS FIRST, user_id"
    with pytest.raises(ValueError):
        order_by("risk_score; DROP TABLE x", "asc", {"score": "risk_score"}, "user_id")


@pytest.mark.parametrize("value, kind, expected", [
    (1234567, "int", "1.234.567"),
    (Decimal("41.666"), "percent", "41,67"),
    (None, "percent", "–"),                     # chưa có dữ liệu, khác 0%
    (0, "percent", "0,00"),
    (None, "days", "Chưa truy cập"),
    (12, "days", "12"),
    ("RED", "risk_level", "Nguy cơ cao"),
    (["Vắng 5/12 buổi (42%)", "Thiếu 4/5 bài tập"], "list", "Vắng 5/12 buổi (42%); Thiếu 4/5 bài tập"),
    (True, "bool", "Có"),
    (date(2026, 11, 6), "date", "06/11/2026"),
    (datetime(2026, 11, 6, 9, 0), "datetime", "06/11/2026 09:00"),
    (None, "text", ""),
])
def test_text_value(value, kind, expected):
    assert text_value(value, kind) == expected


def test_excel_value_keeps_native_types():
    assert excel_value(Decimal("88.10"), "percent") == pytest.approx(88.1)
    assert excel_value(datetime(2026, 11, 6, 2, 0, tzinfo=timezone.utc), "datetime") == datetime(2026, 11, 6, 9, 0)
    assert excel_value("GREEN", "risk_level") == "An toàn"
    assert excel_value(None, "days") == "Chưa truy cập"
