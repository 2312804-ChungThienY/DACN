"""Transform: lưu lượng theo giờ và mẫu online 5 phút, bổ sung giá trị 0 cho giờ/khung không có sự kiện."""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

TRAFFIC_KEYS = ("stat_hour",)
TRAFFIC_COLUMNS = ("stat_hour", "total_requests", "unique_users", "login_count", "failed_login_count",
                   "ws_requests", "etl_run_id")
SNAPSHOT_COLUMNS = ("slot_start", "online_users", "source", "etl_run_id")
_METRICS = TRAFFIC_COLUMNS[1:-1]


def time_range(start: datetime, end: datetime, step: timedelta) -> list[datetime]:
    """[start, end) theo bước step (datetime giờ địa phương không kèm múi giờ)."""
    values, current = [], start
    while current < end:
        values.append(current)
        current += step
    return values


def _by_timestamp(frame: pd.DataFrame, column: str) -> dict[datetime, tuple]:
    return {pd.Timestamp(row[0]).to_pydatetime(): row[1:] for row in frame.itertuples(index=False, name=None)} \
        if not frame.empty else {}


def hourly_rows(aggregates: pd.DataFrame, hours: list[datetime], run_id: int) -> list[dict]:
    found = _by_timestamp(aggregates[["stat_hour", *_METRICS]], "stat_hour")
    rows = []
    for hour in hours:
        values = found.get(hour, (0,) * len(_METRICS))
        rows.append(dict(stat_hour=hour, **{m: int(v) for m, v in zip(_METRICS, values)}, etl_run_id=run_id))
    return rows


def online_rows(samples: pd.DataFrame, slots: list[datetime], source: str, run_id: int) -> list[dict]:
    found = _by_timestamp(samples[["slot_start", "online_users"]], "slot_start")
    return [dict(slot_start=slot, online_users=int(found.get(slot, (0,))[0]), source=source, etl_run_id=run_id)
            for slot in slots]
