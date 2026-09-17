"""
Job student_risk (SPEC 4.2: mỗi 2 giờ 07h–21h): tính snapshot rủi ro hôm nay (ghi đè) cho các môn đang diễn ra.

    python -m etl.jobs.job_student_risk [--as-of 2026-11-06T10:30:00+07:00]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from sqlalchemy import text

from etl.extract.course_data import CourseDataset, extract_course_dataset
from etl.jobs.runner import JobContext, JobStats, as_of_argument, cli_exit_code, configure_logging, run_job
from etl.load import load_sql
from etl.load.upsert import upsert
from etl.transform.student_risk import (RISK_COLUMNS, RISK_JSON_COLUMNS, RISK_KEYS, build_risk_rows,
                                        student_metrics)

JOB_NAME = "student_risk"


def compute(ctx: JobContext, dataset: CourseDataset | None = None) -> JobStats:
    ds = dataset if dataset is not None else extract_course_dataset(ctx.moodle, ctx.as_of)
    rows = build_risk_rows(ds, student_metrics(ds), ctx.run_id)
    with ctx.analytics.begin() as conn:
        changed = upsert(conn, "fact_student_risk_summary", RISK_COLUMNS, rows, RISK_KEYS,
                         json_columns=RISK_JSON_COLUMNS)
        removed = conn.execute(text(load_sql("delete_stale_risk")),
                               {"snapshot_date": ds.as_of.date(), "course_ids": ds.course_ids}).rowcount
    return JobStats(rows_extracted=ds.source_rows, rows_loaded=changed + removed)


def run(as_of: datetime | None = None) -> JobStats | None:
    return run_job(JOB_NAME, compute, locks=[JOB_NAME], as_of=as_of)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Tính snapshot rủi ro sinh viên")
    as_of_argument(parser)
    return cli_exit_code(run(parser.parse_args(argv).as_of))


if __name__ == "__main__":
    sys.exit(main())
