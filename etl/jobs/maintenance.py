"""
Job weekly_maintenance (SPEC 4.2: Chủ nhật 03:00):
  - Snapshot rủi ro cũ hơn 180 ngày: chỉ giữ snapshot cuối mỗi tuần.
  - VACUUM (ANALYZE) các bảng fact.

    python -m etl.jobs.maintenance [--as-of ...]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta

from sqlalchemy import text

from etl.config import RISK_SNAPSHOT_RETENTION_DAYS
from etl.jobs import job_course_progress, job_student_risk, job_traffic
from etl.jobs.runner import JobContext, JobStats, as_of_argument, cli_exit_code, configure_logging, run_job
from etl.load import load_sql

JOB_NAME = "maintenance"
LOCKS = (job_student_risk.JOB_NAME, job_course_progress.JOB_NAME, job_traffic.JOB_NAME)
VACUUM_TABLES = ("fact_student_risk_summary", "fact_course_progress_daily", "fact_server_traffic_hourly",
                 "etl_online_snapshot")


def compute(ctx: JobContext) -> JobStats:
    cutoff = ctx.as_of.date() - timedelta(days=RISK_SNAPSHOT_RETENTION_DAYS)
    with ctx.analytics.begin() as conn:
        pruned = conn.execute(text(load_sql("prune_risk_snapshots")), {"cutoff": cutoff}).rowcount
    # VACUUM không chạy được trong transaction -> kết nối AUTOCOMMIT; tên bảng là hằng số trong mã nguồn
    with ctx.analytics.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for table in VACUUM_TABLES:
            conn.execute(text(f"VACUUM (ANALYZE) analytics.{table}"))
    return JobStats(rows_loaded=pruned)


def run(as_of: datetime | None = None) -> JobStats | None:
    return run_job(JOB_NAME, compute, locks=LOCKS, as_of=as_of)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Bảo trì hằng tuần CSDL phân tích")
    as_of_argument(parser)
    return cli_exit_code(run(parser.parse_args(argv).as_of))


if __name__ == "__main__":
    sys.exit(main())
