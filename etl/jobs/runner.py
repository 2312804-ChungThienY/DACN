"""
Khung chạy job ETL (SPEC 4.1 – "Luồng mỗi job"):
  1. pg_try_advisory_lock: job trùng đang chạy -> bỏ qua lượt này.
  2. Ghi etl_run_log RUNNING.
  3-5. Extract / Transform / Load do hàm work(ctx) của từng job thực hiện.
  6. Ghi etl_run_log SUCCESS hoặc FAILED (kèm lỗi) – lỗi luôn được ném tiếp, không bị nuốt.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine, text

from common.settings import parse_as_of, resolve_as_of
from etl.config import JOB_LOCK_KEYS, RETRY_DELAYS_SECONDS
from etl.db import analytics_engine, moodle_engine

log = logging.getLogger("etl")


@dataclass(frozen=True)
class JobContext:
    job_name: str
    run_id: int
    as_of: datetime

    @property
    def as_of_ts(self) -> int:
        return int(self.as_of.timestamp())

    @property
    def moodle(self) -> Engine:
        return moodle_engine()

    @property
    def analytics(self) -> Engine:
        return analytics_engine()


@dataclass
class JobStats:
    rows_extracted: int = 0
    rows_loaded: int = 0

    def __add__(self, other: "JobStats") -> "JobStats":
        return JobStats(self.rows_extracted + other.rows_extracted, self.rows_loaded + other.rows_loaded)


def _start_run(engine: Engine, job_name: str) -> int:
    with engine.begin() as conn:
        return conn.execute(text("INSERT INTO analytics.etl_run_log (job_name) VALUES (:job) RETURNING run_id"),
                            {"job": job_name}).scalar_one()


def _finish_run(engine: Engine, run_id: int, status: str, stats: JobStats | None = None,
                error: str | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE analytics.etl_run_log
            SET status = :status, finished_at = clock_timestamp(),
                rows_extracted = :extracted, rows_loaded = :loaded, error_message = :error
            WHERE run_id = :run_id"""),
            {"status": status, "extracted": stats.rows_extracted if stats else None,
             "loaded": stats.rows_loaded if stats else None, "error": error, "run_id": run_id})


def run_job(job_name: str, work: Callable[[JobContext], JobStats], *, locks: Sequence[str],
            as_of: datetime | None = None) -> JobStats | None:
    """Chạy work(ctx) với khóa advisory + nhật ký. Trả về None nếu bị bỏ qua vì job khác đang giữ khóa."""
    moment = resolve_as_of(as_of)
    engine = analytics_engine()
    with engine.connect() as lock_conn:
        held: list[int] = []
        try:
            for name in locks:
                key = JOB_LOCK_KEYS[name]
                if not lock_conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}).scalar_one():
                    log.warning("Bỏ qua %s: job '%s' đang chạy (khóa advisory %s bận)", job_name, name, key)
                    return None
                held.append(key)
            lock_conn.commit()

            run_id = _start_run(engine, job_name)
            log.info("Bắt đầu %s (run_id=%s, as_of=%s)", job_name, run_id, moment.isoformat())
            started = time.perf_counter()
            try:
                stats = work(JobContext(job_name=job_name, run_id=run_id, as_of=moment))
            except Exception as exc:
                _finish_run(engine, run_id, "FAILED", error=f"{type(exc).__name__}: {exc}")
                log.exception("Job %s (run_id=%s) thất bại", job_name, run_id)
                raise
            _finish_run(engine, run_id, "SUCCESS", stats)
            log.info("Hoàn tất %s (run_id=%s) sau %.1fs: extracted=%s loaded=%s", job_name, run_id,
                     time.perf_counter() - started, stats.rows_extracted, stats.rows_loaded)
            return stats
        finally:
            for key in held:
                lock_conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
            lock_conn.commit()


def run_with_retries(job: Callable[[], object], name: str,
                     delays: Sequence[int] = RETRY_DELAYS_SECONDS) -> object:
    """Dùng cho scheduler: thử lại theo backoff (mặc định 1–5–15 phút); hết lượt thì ném lỗi cuối cùng."""
    for attempt in range(len(delays) + 1):
        try:
            return job()
        except Exception:
            if attempt == len(delays):
                log.error("Job %s thất bại sau %d lần thử", name, attempt + 1)
                raise
            log.warning("Job %s lỗi, thử lại lần %d sau %ss", name, attempt + 1, delays[attempt])
            time.sleep(delays[attempt])
    raise AssertionError("unreachable")


def configure_logging() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")


def as_of_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--as-of", type=parse_as_of, default=None,
                        help="thời điểm tham chiếu ISO 8601 (mặc định: LMS_AS_OF trong .env, trống = hiện tại)")


def cli_exit_code(stats: JobStats | None) -> int:
    """0 = thành công, 3 = bị bỏ qua do job khác đang chạy. Lỗi được ném ra ngoài (mã thoát 1)."""
    return 0 if stats is not None else 3
