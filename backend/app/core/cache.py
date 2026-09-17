"""
Cache TTL trong bộ nhớ cho các endpoint KPI (SPEC 5.1: cachetools, 60 giây).

Chỉ cache kết quả của hàm repository thuần (tham số là giá trị băm được, không phải Connection).
Khóa cache gồm tên hàm + tham số, nên AS_OF khác nhau (truyền vào tham số) không dùng lẫn kết quả.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from cachetools import TTLCache

from backend.app.core.config import get_settings

F = TypeVar("F", bound=Callable[..., Any])

_lock = threading.Lock()
_cache: TTLCache | None = None


def _store() -> TTLCache:
    global _cache
    if _cache is None:
        _cache = TTLCache(maxsize=2048, ttl=get_settings().cache_ttl_seconds)
    return _cache


def cached(func: F) -> F:
    """Cache theo (tên hàm, args, kwargs) – dùng cho hàm nhận conn làm tham số đầu tiên (bị bỏ khỏi khóa)."""
    @wraps(func)
    def wrapper(conn, *args, **kwargs):
        key = (func.__module__, func.__qualname__, args, tuple(sorted(kwargs.items())))
        store = _store()
        with _lock:
            if key in store:
                return store[key]
        value = func(conn, *args, **kwargs)
        with _lock:
            store[key] = value
        return value
    return wrapper  # type: ignore[return-value]


def clear_cache() -> None:
    with _lock:
        _store().clear()
