"""
Job nightly_full_rebuild (SPEC 4.2: 01:00 hằng đêm) – chốt số liệu của NGÀY HÔM QUA:
  - snapshot rủi ro và tiến độ môn tại 23:59:59 hôm qua (ghi đè các lần chạy trong ngày),
  - tính lại 24 giờ lưu lượng hôm qua (bắt log ghi trễ) + mẫu online suy ra từ log,
  - đánh dấu is_peak_hour (P90 của 28 ngày).

    python -m etl.jobs.nightly [--as-of ...]
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from datetime import datetime, timedelta

from etl.extract.course_data import extract_course_dataset, start_of_day
from etl.jobs import job_course_progress, job_student_risk, job_traffic
from etl.jobs.runner import JobContext, JobStats, as_of_argument, cli_exit_code, configure_logging, run_job

JOB_NAME = "nightly"
LOCKS = (job_student_risk.JOB_NAME, job_course_progress.JOB_NAME, job_traffic.JOB_NAME)


def compute(ctx: JobContext) -> JobStats:
    today = start_of_day(ctx.as_of)
    yesterday = today - timedelta(days=1)
    day_ctx = replace(ctx, as_of=today - timedelta(seconds=1))

    dataset = extract_course_dataset(ctx.moodle, day_ctx.as_of)
    stats = job_student_risk.compute(day_ctx, dataset)
    stats += job_course_progress.compute(day_ctx, dataset)   # sau risk để đếm đèn giao thông từ snapshot vừa chốt
    stats += job_traffic.compute(day_ctx, from_hour=yesterday, to_hour=today,
                                 snapshot_sessions=False, advance_watermark=False)
    stats.rows_loaded += job_traffic.mark_peak_hours(ctx, yesterday.date(), yesterday.date())
    return stats


def run(as_of: datetime | None = None) -> JobStats | None:
    return run_job(JOB_NAME, compute, locks=LOCKS, as_of=as_of)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Chốt số liệu ngày hôm qua")
    as_of_argument(parser)
    return cli_exit_code(run(parser.parse_args(argv).as_of))


if __name__ == "__main__":
    sys.exit(main())
