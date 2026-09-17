"""
Job traffic (SPEC 4.2: mỗi 5 phút):
  - Log mới theo watermark (id) -> tính lại toàn bộ các giờ bị ảnh hưởng + giờ hiện tại và giờ trước.
  - Mẫu online: chụp mdl_sessions tại AS_OF (SESSIONS) + suy ra từ log cho các khung 5 phút đã đóng (LOGSTORE,
    không ghi đè SESSIONS) -> tính lại peak/avg online của các giờ đó.
  - Cập nhật watermark trong CÙNG transaction với dữ liệu nạp.

    python -m etl.jobs.job_traffic [--as-of ...]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import text

from etl.config import APP_TIMEZONE, ONLINE_SLOT_SECONDS, TRAFFIC_CHUNK_DAYS, TZ
from etl.db import read_frame
from etl.extract import load_sql as extract_sql
from etl.jobs.runner import JobContext, JobStats, as_of_argument, cli_exit_code, configure_logging, run_job
from etl.load import load_sql
from etl.load.upsert import copy_to_temp, upsert
from etl.transform.traffic import (SNAPSHOT_COLUMNS, TRAFFIC_COLUMNS, TRAFFIC_KEYS, hourly_rows, online_rows,
                                   time_range)

JOB_NAME = "traffic"
LOGIN_EVENT = "\\core\\event\\user_loggedin"
FAILED_LOGIN_EVENT = "\\core\\event\\user_login_failed"
HOUR = timedelta(hours=1)
SLOT = timedelta(seconds=ONLINE_SLOT_SECONDS)


def floor_hour(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


def local_naive(moment: datetime) -> datetime:
    """datetime có múi giờ -> giờ địa phương không kèm múi giờ (kiểu TIMESTAMP của bảng fact)."""
    return moment.astimezone(TZ).replace(tzinfo=None)


def _epoch(moment: datetime) -> int:
    return int(moment.timestamp())


def compute(ctx: JobContext, *, from_hour: datetime | None = None, to_hour: datetime | None = None,
            snapshot_sessions: bool = True, advance_watermark: bool = True) -> JobStats:
    """
    Không truyền from_hour/to_hour: chế độ tăng dần theo watermark.
    Có truyền (datetime có múi giờ, đầu giờ): tính lại đúng khoảng đó (nightly / backfill).
    """
    as_of_ts = ctx.as_of_ts
    limit = floor_hour(ctx.as_of) + HOUR                       # không tạo dòng cho giờ tương lai

    with ctx.analytics.connect() as conn:
        last_id = conn.execute(text("SELECT last_log_id FROM analytics.etl_watermark WHERE job_name = :job"),
                               {"job": JOB_NAME}).scalar() or 0

    with ctx.moodle.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        max_id = int(read_frame(conn, extract_sql("max_log_id"))["max_id"].iat[0])
        if from_hour is None:
            new = read_frame(conn, extract_sql("new_log_range"), {"last_id": last_id, "max_id": max_id}).iloc[0]
            new_logs = int(new["new_logs"])
            start = floor_hour(ctx.as_of) - HOUR
            if new_logs:
                start = min(start, floor_hour(datetime.fromtimestamp(int(new["min_ts"]), TZ)))
            end = limit
        else:
            new_logs = 0
            start, end = from_hour, min(to_hour, limit)
        if start >= end:
            return JobStats()

        # Lưu lượng theo giờ, tổng hợp theo lô ngày
        frames, chunk = [], start
        while chunk < end:
            chunk_end = min(chunk + timedelta(days=TRAFFIC_CHUNK_DAYS), end)
            frames.append(read_frame(conn, extract_sql("traffic_hourly"), {
                "from_ts": _epoch(chunk), "to_ts": _epoch(chunk_end), "tz": APP_TIMEZONE,
                "login_event": LOGIN_EVENT, "failed_login_event": FAILED_LOGIN_EVENT}))
            chunk = chunk_end
        hourly = pd.concat(frames, ignore_index=True)

        # Mẫu online từ log: chỉ các khung 5 phút đã kết thúc trước AS_OF (giây AS_OF tính là đã qua)
        closed_end_ts = min(_epoch(end), (as_of_ts + 1) // ONLINE_SLOT_SECONDS * ONLINE_SLOT_SECONDS)
        closed_end = datetime.fromtimestamp(closed_end_ts, TZ)
        samples = read_frame(conn, extract_sql("online_logstore"), {
            "from_ts": _epoch(start), "to_ts": closed_end_ts, "slot": ONLINE_SLOT_SECONDS, "tz": APP_TIMEZONE,
        }) if closed_end_ts > _epoch(start) else pd.DataFrame(columns=["slot_start", "online_users"])

        session_online = None
        if snapshot_sessions:
            session_online = int(read_frame(conn, extract_sql("online_sessions"),
                                            {"as_of": as_of_ts, "window": ONLINE_SLOT_SECONDS})["online_users"].iat[0])

    hours = time_range(local_naive(start), local_naive(end), HOUR)
    traffic = hourly_rows(hourly, hours, ctx.run_id)
    snapshots = online_rows(samples, time_range(local_naive(start), local_naive(closed_end), SLOT), "LOGSTORE", ctx.run_id)
    if session_online is not None:
        # Khung của ảnh chụp: [AS_OF - 5 phút, AS_OF] gán vào đầu khung 5 phút chứa AS_OF - 5 phút
        slot = local_naive(datetime.fromtimestamp((as_of_ts - ONLINE_SLOT_SECONDS) // ONLINE_SLOT_SECONDS
                                                  * ONLINE_SLOT_SECONDS, TZ))
        snapshots = [s for s in snapshots if s["slot_start"] != slot]
        snapshots.append(dict(slot_start=slot, online_users=session_online, source="SESSIONS", etl_run_id=ctx.run_id))

    with ctx.analytics.begin() as conn:
        changed = upsert(conn, "fact_server_traffic_hourly", TRAFFIC_COLUMNS, traffic, TRAFFIC_KEYS)
        copy_to_temp(conn, "etl_online_snapshot", SNAPSHOT_COLUMNS, snapshots)
        conn.execute(text(load_sql("merge_online_snapshot")))
        changed += conn.execute(text(load_sql("aggregate_online")), {
            "from_hour": local_naive(start), "to_hour": local_naive(end), "run_id": ctx.run_id}).rowcount
        if advance_watermark:
            conn.execute(text("""
                INSERT INTO analytics.etl_watermark (job_name, last_log_id, last_run_at)
                VALUES (:job, :max_id, now())
                ON CONFLICT (job_name) DO UPDATE
                SET last_log_id = GREATEST(analytics.etl_watermark.last_log_id, EXCLUDED.last_log_id),
                    last_run_at = EXCLUDED.last_run_at"""), {"job": JOB_NAME, "max_id": max_id})

    extracted = new_logs if from_hour is None else int(hourly["total_requests"].sum()) if not hourly.empty else 0
    return JobStats(rows_extracted=extracted, rows_loaded=changed)


def mark_peak_hours(ctx: JobContext, from_date, to_date) -> int:
    from etl.config import PEAK_PERCENTILE, PEAK_WINDOW_DAYS
    with ctx.analytics.begin() as conn:
        return conn.execute(text(load_sql("mark_peak_hours")), {
            "from_date": from_date, "to_date": to_date,
            "percentile": PEAK_PERCENTILE, "window_days": PEAK_WINDOW_DAYS}).rowcount


def run(as_of: datetime | None = None) -> JobStats | None:
    return run_job(JOB_NAME, compute, locks=[JOB_NAME], as_of=as_of)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Cập nhật lưu lượng truy cập theo giờ và người dùng online")
    as_of_argument(parser)
    return cli_exit_code(run(parser.parse_args(argv).as_of))


if __name__ == "__main__":
    sys.exit(main())
