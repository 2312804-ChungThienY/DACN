"""
Backfill (SPEC 4.2 – chạy thủ công lần đầu): nạp lại lịch sử từ ngày --from tới AS_OF.
  - Mỗi ngày: snapshot rủi ro + tiến độ môn chốt lúc 23:59:59 (ngày cuối cùng chốt tại AS_OF).
  - Lưu lượng theo giờ + mẫu online cho cả khoảng, chụp mdl_sessions tại AS_OF, đặt watermark.
  - Đánh dấu giờ cao điểm cho cả khoảng.
Chạy lại nhiều lần cho cùng kết quả (UPSERT).

    python -m etl.jobs.backfill --from 2026-09-07 [--as-of ...]
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from datetime import date, datetime, time, timedelta

from etl.config import TZ
from etl.extract.course_data import extract_course_dataset
from etl.jobs import job_course_progress, job_student_risk, job_traffic
from etl.jobs.runner import JobContext, JobStats, as_of_argument, cli_exit_code, configure_logging, run_job

JOB_NAME = "backfill"
LOCKS = (job_student_risk.JOB_NAME, job_course_progress.JOB_NAME, job_traffic.JOB_NAME)
log = logging.getLogger("etl.backfill")


def compute(ctx: JobContext, from_date: date) -> JobStats:
    if from_date > ctx.as_of.date():
        raise ValueError(f"--from {from_date} muộn hơn AS_OF {ctx.as_of.date()}")

    stats = JobStats()
    day = from_date
    while day <= ctx.as_of.date():
        day_ctx = replace(ctx, as_of=min(datetime.combine(day, time(23, 59, 59), TZ), ctx.as_of))
        dataset = extract_course_dataset(ctx.moodle, day_ctx.as_of)
        stats += job_student_risk.compute(day_ctx, dataset)
        stats += job_course_progress.compute(day_ctx, dataset)
        log.info("  %s: %d môn, %d lượt ghi danh", day, len(dataset.courses), len(dataset.enrolments))
        day += timedelta(days=1)

    stats += job_traffic.compute(ctx, from_hour=datetime.combine(from_date, time(0), TZ),
                                 to_hour=job_traffic.floor_hour(ctx.as_of) + timedelta(hours=1),
                                 snapshot_sessions=True, advance_watermark=True)
    stats.rows_loaded += job_traffic.mark_peak_hours(ctx, from_date, ctx.as_of.date())
    return stats


def run(from_date: date, as_of: datetime | None = None) -> JobStats | None:
    return run_job(JOB_NAME, lambda ctx: compute(ctx, from_date), locks=LOCKS, as_of=as_of)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Nạp lại lịch sử cho 3 bảng fact")
    parser.add_argument("--from", dest="from_date", required=True, type=date.fromisoformat,
                        help="ngày bắt đầu nạp, dạng YYYY-MM-DD (vd 2026-09-07)")
    as_of_argument(parser)
    args = parser.parse_args(argv)
    return cli_exit_code(run(args.from_date, args.as_of))


if __name__ == "__main__":
    sys.exit(main())
