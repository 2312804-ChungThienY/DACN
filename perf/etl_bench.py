"""
Đo thời gian ETL trên Moodle ~2.000 SV / ~10.000 lượt ghi danh (SPEC 6.2 dòng "ETL": traffic < 30 s,
risk < 5 phút, nightly < 20 phút).

Dùng CSDL riêng moodle_src_x4 và lms_analytics_etlbench – không đụng dữ liệu demo.

    python -m perf.etl_bench prepare     # (không đo) migrate, sinh cấu trúc + hành vi, backfill 1 ngày để đặt watermark
    python -m perf.etl_bench measure     # đo từng job 3 lần -> perf/results/etl_bench.json
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from datetime import timedelta

import psycopg

from common.settings import resolve_as_of
from database.config import load_db_config
from perf.common import ETL_ANALYTICS_DB, ETL_MOODLE_DB, WORK_DIR, child_env, machine_info, run, write_result

N_STUDENTS = 2_000
RUNS = 3
JOBS = [
    ("traffic", ["etl.jobs.job_traffic"], "mỗi 5 phút", 30),
    ("student_risk", ["etl.jobs.job_student_risk"], "2 giờ/lần", 300),
    ("course_progress", ["etl.jobs.job_course_progress"], "mỗi giờ", None),
    ("nightly", ["etl.jobs.nightly"], "01:00 hằng đêm", 1200),
]


def bench_env() -> dict[str, str]:
    return child_env(MOODLE_DB_NAME=ETL_MOODLE_DB, ANALYTICS_DB_NAME=ETL_ANALYTICS_DB,
                     MOCK_N_STUDENTS=str(N_STUDENTS), MOCK_OUTPUT_DIR=str(WORK_DIR / "etl_bench_output"))


def prepare() -> None:
    env = bench_env()
    timings = {
        "migrate_moodle": run(["database.migrate", "up", "--target", "moodle"], env),
        "migrate_analytics": run(["database.migrate", "up", "--target", "analytics"], env),
        "seed_structure": run(["mockdata.seed_structure", "--reset"], env),
        "generate_activity": run(["mockdata.generate_activity", "--reset"], env),
    }
    day_before = (resolve_as_of() - timedelta(days=1)).date().isoformat()
    timings["backfill_2_days"] = run(["etl.jobs.backfill", "--from", day_before], env)
    print({k: round(v, 1) for k, v in timings.items()})


def source_scale() -> dict:
    cfg = load_db_config("MOODLE_DB")
    as_of = int(resolve_as_of().timestamp())
    with psycopg.connect(**cfg.conninfo(dbname=ETL_MOODLE_DB, application_name="lms-perf-etl")) as conn:
        return {
            "students": conn.execute("""SELECT COUNT(DISTINCT ra.userid) FROM mdl_role_assignments ra
                                        JOIN mdl_role r ON r.id = ra.roleid AND r.shortname = 'student'""").fetchone()[0],
            "active_enrolments": conn.execute("""SELECT COUNT(*) FROM mdl_user_enrolments ue JOIN mdl_enrol e ON e.id = ue.enrolid
                                                 WHERE ue.status = 0 AND e.status = 0 AND ue.timestart <= %s
                                                   AND (ue.timeend = 0 OR ue.timeend > %s)""", (as_of, as_of)).fetchone()[0],
            "courses": conn.execute("SELECT COUNT(*) FROM mdl_course WHERE id <> 1").fetchone()[0],
            "logstore_rows": conn.execute("SELECT COUNT(*) FROM mdl_logstore_standard_log").fetchone()[0],
            "database_size": conn.execute("SELECT pg_size_pretty(pg_database_size(current_database()))").fetchone()[0],
        }


def logged_runs(job_name: str, limit: int) -> list[dict]:
    cfg = load_db_config("ANALYTICS_DB")
    with psycopg.connect(**cfg.conninfo(dbname=ETL_ANALYTICS_DB, application_name="lms-perf-etl")) as conn:
        rows = conn.execute("""SELECT run_id, status, EXTRACT(EPOCH FROM finished_at - started_at), rows_extracted, rows_loaded
                               FROM analytics.etl_run_log WHERE job_name = %s ORDER BY run_id DESC LIMIT %s""",
                            (job_name, limit)).fetchall()
    return [dict(run_id=r[0], status=r[1], seconds=float(r[2]), rows_extracted=r[3], rows_loaded=r[4]) for r in rows]


def measure() -> None:
    env = bench_env()
    scale = source_scale()
    print(f"Quy mô nguồn: {scale}")
    results = []
    for job_name, module, schedule, target in JOBS:
        wall = []
        for i in range(RUNS):
            t0 = time.perf_counter()
            run(module, env, label=f"{job_name} lần {i + 1}")
            wall.append(time.perf_counter() - t0)
        logged = list(reversed(logged_runs(job_name, RUNS)))
        job_seconds = [r["seconds"] for r in logged]
        results.append(dict(
            job=job_name, schedule=schedule, target_seconds=target, runs=RUNS,
            job_seconds=job_seconds, job_median_seconds=statistics.median(job_seconds),
            process_seconds=wall, rows=logged,
            passed=None if target is None else max(job_seconds) < target,
        ))
        print(f"  {job_name:<16} median {statistics.median(job_seconds):7.2f}s  (mục tiêu {target or '–'}s)", flush=True)
    write_result("etl_bench.json", {"machine": machine_info(), "as_of": resolve_as_of(), "source": scale,
                                    "note": "job_seconds lấy từ etl_run_log (không gồm thời gian khởi động Python)",
                                    "jobs": results})


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Đo thời gian ETL trên dữ liệu ~10.000 lượt ghi danh")
    parser.add_argument("command", choices=("prepare", "measure"))
    args = parser.parse_args(argv)
    prepare() if args.command == "prepare" else measure()
    return 0


if __name__ == "__main__":
    sys.exit(main())
