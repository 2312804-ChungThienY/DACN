"""
Job course_progress (SPEC 4.2: mỗi giờ): số liệu tiến độ trong ngày (stat_date = hôm nay) của các môn đang diễn ra.

    python -m etl.jobs.job_course_progress [--as-of ...]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from etl.db import read_frame
from etl.extract.course_data import CourseDataset, extract_course_dataset
from etl.jobs.runner import JobContext, JobStats, as_of_argument, cli_exit_code, configure_logging, run_job
from etl.load import load_sql
from etl.load.upsert import upsert
from etl.transform.course_progress import (PROGRESS_COLUMNS, PROGRESS_JSON_COLUMNS, PROGRESS_KEYS,
                                           build_progress_rows)
from etl.transform.student_risk import student_metrics

JOB_NAME = "course_progress"


def compute(ctx: JobContext, dataset: CourseDataset | None = None) -> JobStats:
    ds = dataset if dataset is not None else extract_course_dataset(ctx.moodle, ctx.as_of)
    metrics = student_metrics(ds)
    with ctx.analytics.begin() as conn:
        counts = read_frame(conn, load_sql("risk_level_counts"),
                            {"course_ids": ds.course_ids, "stat_date": ds.as_of.date()})
        risk_counts = {int(r.course_id): (int(r.red_count), int(r.yellow_count), int(r.green_count))
                       for r in counts.itertuples(index=False)}
        rows = build_progress_rows(ds, metrics, risk_counts, ctx.run_id)
        changed = upsert(conn, "fact_course_progress_daily", PROGRESS_COLUMNS, rows, PROGRESS_KEYS,
                         json_columns=PROGRESS_JSON_COLUMNS)
    return JobStats(rows_extracted=ds.source_rows, rows_loaded=changed)


def run(as_of: datetime | None = None) -> JobStats | None:
    return run_job(JOB_NAME, compute, locks=[JOB_NAME], as_of=as_of)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Tính tiến độ môn học trong ngày")
    as_of_argument(parser)
    return cli_exit_code(run(parser.parse_args(argv).as_of))


if __name__ == "__main__":
    sys.exit(main())
