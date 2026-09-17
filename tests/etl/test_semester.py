"""Kiểm thử quy tắc suy ra năm học / học kỳ (SPEC 1.1)."""
from datetime import datetime

import pytest

from common.settings import TZ
from etl.transform.semester import academic_term


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        (datetime(2026, 9, 7, tzinfo=TZ), ("2026-2027", 1)),
        (datetime(2026, 8, 1, tzinfo=TZ), ("2026-2027", 1)),
        (datetime(2026, 12, 31, 23, 0, tzinfo=TZ), ("2026-2027", 1)),
        (datetime(2027, 1, 4, tzinfo=TZ), ("2026-2027", 2)),
        (datetime(2027, 5, 31, tzinfo=TZ), ("2026-2027", 2)),
        (datetime(2027, 6, 1, tzinfo=TZ), ("2026-2027", 3)),
        (datetime(2027, 7, 31, tzinfo=TZ), ("2026-2027", 3)),
    ],
)
def test_academic_term(start, expected):
    assert academic_term(start) == expected


def test_epoch_uses_local_timezone():
    # 31/07/2026 18:00 UTC = 01/08/2026 01:00 giờ Việt Nam -> đã sang HK1
    assert academic_term(int(datetime(2026, 7, 31, 18, 0, tzinfo=TZ.__class__("UTC")).timestamp())) == ("2026-2027", 1)


@pytest.mark.parametrize("bad", [0, -5, datetime(2026, 9, 7)])
def test_invalid_start_raises(bad):
    with pytest.raises(ValueError):
        academic_term(bad)
