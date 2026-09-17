"""
EXPLAIN (ANALYZE, BUFFERS) các truy vấn chính của Dashboard (SPEC 6.2 dòng "Truy vấn SQL": <= 100 ms mỗi truy vấn,
không Seq Scan trên bảng lớn).

Không viết lại SQL bằng tay: script gọi các endpoint API thật (TestClient), ghi lại MỌI câu SQL mà repository gửi
xuống PostgreSQL (kèm tham số), rồi chạy lại từng câu với EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON).

    python -m perf.explain_queries --dataset x1     # CSDL lms_analytics
    python -m perf.explain_queries --dataset x10    # CSDL lms_analytics_x10 (python -m perf.build_x10 trước)
"""
from __future__ import annotations

import argparse
import os
import re
import statistics
import sys

# "Bảng lớn" xác định theo số dòng thực tế: Seq Scan trên bảng nhỏ (vd fact_course_progress_daily 9.150 dòng)
# là lựa chọn ĐÚNG của planner, không phải lỗi thiếu index.
BIG_TABLE_MIN_ROWS = 100_000
REPEATS = 5


def parse_args(argv):
    parser = argparse.ArgumentParser(description="EXPLAIN ANALYZE truy vấn API")
    parser.add_argument("--dataset", choices=("x1", "x10"), required=True)
    return parser.parse_args(argv)


def walk(plan: dict, found: list[dict]) -> None:
    found.append(plan)
    for child in plan.get("Plans", []):
        walk(child, found)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    from perf.common import X10_ANALYTICS_DB, machine_info, write_result
    if args.dataset == "x10":
        os.environ["ANALYTICS_DB_NAME"] = X10_ANALYTICS_DB
    os.environ.setdefault("BACKEND_JWT_SECRET", "perf-only-secret-" + "x" * 40)

    from fastapi.testclient import TestClient
    from sqlalchemy import event, text

    from backend.app.core.cache import clear_cache
    from backend.app.core.db import get_engine
    from backend.app.core.security import create_access_token
    from backend.app.main import create_app

    engine = get_engine()
    captured: list[tuple[str, str, dict]] = []
    current = {"endpoint": None}

    @event.listens_for(engine, "before_cursor_execute")
    def capture(conn, cursor, statement, parameters, context, executemany):  # noqa: ARG001
        if current["endpoint"] and statement.lstrip().upper().startswith(("SELECT", "WITH")) and "app_user" not in statement:
            captured.append((current["endpoint"], statement, parameters))

    with engine.connect() as conn:
        teacher = conn.execute(text("""SELECT user_id FROM analytics.app_user WHERE role = 'TEACHER' AND is_active
                                       ORDER BY user_id LIMIT 1""")).scalar_one()
        admin = conn.execute(text("SELECT user_id FROM analytics.app_user WHERE role = 'ADMIN' ORDER BY user_id LIMIT 1")).scalar_one()
        course = conn.execute(text("""SELECT course_id FROM analytics.fact_course_progress_daily
                                      WHERE teacher_ids @> ARRAY[CAST(:t AS integer)] ORDER BY stat_date DESC, course_id LIMIT 1"""),
                              {"t": teacher}).scalar_one()
        faculty = conn.execute(text("SELECT faculty_id FROM analytics.fact_course_progress_daily ORDER BY stat_date DESC LIMIT 1")).scalar_one()
        student = conn.execute(text("""SELECT user_id FROM analytics.fact_student_risk_summary WHERE course_id = :c
                                       ORDER BY snapshot_date DESC, risk_score DESC LIMIT 1"""), {"c": course}).scalar_one()
        big_tables = {r[0] for r in conn.execute(text("""
            SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'analytics' AND c.relkind = 'r' AND c.reltuples > :min_rows"""),
            {"min_rows": BIG_TABLE_MIN_ROWS})}
        scale = dict(conn.execute(text("""SELECT (SELECT COUNT(*) FROM analytics.fact_student_risk_summary) AS risk_rows,
                                                 (SELECT COUNT(*) FROM analytics.fact_course_progress_daily) AS progress_rows,
                                                 (SELECT COUNT(DISTINCT course_id) FROM analytics.fact_course_progress_daily) AS courses,
                                                 pg_size_pretty(pg_database_size(current_database())) AS size""")).mappings().one())

    headers_admin = {"Authorization": "Bearer " + create_access_token(admin, "ADMIN")[0]}
    headers_teacher = {"Authorization": "Bearer " + create_access_token(teacher, "TEACHER")[0]}
    base = f"/api/v1/teacher/courses/{course}"
    endpoints = [
        ("admin", "GET /admin/overview/kpis", "/api/v1/admin/overview/kpis"),
        ("admin", "GET /admin/enrollment/by-faculty", "/api/v1/admin/enrollment/by-faculty"),
        ("admin", "GET /admin/enrollment/faculties/{id}/courses", f"/api/v1/admin/enrollment/faculties/{faculty}/courses"),
        ("admin", "GET /admin/enrollment/courses/{id}/students", f"/api/v1/admin/enrollment/courses/{course}/students?status=inactive"),
        ("admin", "GET /admin/traffic/hourly (7 ngày)", "/api/v1/admin/traffic/hourly"),
        ("admin", "GET /admin/traffic/heatmap", "/api/v1/admin/traffic/heatmap?weeks=4"),
        ("admin", "GET /admin/reports/preview (risk, RED)", "/api/v1/admin/reports/preview?report_type=risk&risk_level=RED"),
        ("teacher", "GET /teacher/courses", "/api/v1/teacher/courses"),
        ("teacher", "GET /teacher/courses/{id}/risk-summary", f"{base}/risk-summary"),
        ("teacher", "GET /teacher/courses/{id}/students", f"{base}/students"),
        ("teacher", "GET /teacher/courses/{id}/students?risk_level=RED&search", f"{base}/students?risk_level=RED&search=Nguy"),
        ("teacher", "GET /teacher/courses/{id}/students/{uid}", f"{base}/students/{student}"),
        ("teacher", "GET /teacher/courses/{id}/students/{uid}/compare", f"{base}/students/{student}/compare"),
        ("teacher", "GET /teacher/courses/{id}/progress?granularity=week", f"{base}/progress?granularity=week"),
    ]

    client = TestClient(create_app())
    for role, name, url in endpoints:
        clear_cache()
        current["endpoint"] = name
        response = client.get(url, headers=headers_admin if role == "admin" else headers_teacher)
        current["endpoint"] = None
        if response.status_code != 200:
            raise SystemExit(f"{name}: HTTP {response.status_code} {response.text[:200]}")

    seen, results = set(), []
    with engine.connect() as conn:
        for endpoint, statement, parameters in captured:
            key = (endpoint, statement)
            if key in seen or re.search(r"MAX\(finished_at\)", statement):
                continue
            seen.add(key)
            timings, plan_json = [], None
            for _ in range(REPEATS):
                raw = conn.exec_driver_sql("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement, parameters).scalar_one()
                plan_json = raw[0] if isinstance(raw, list) else raw
                timings.append(plan_json["Planning Time"] + plan_json["Execution Time"])
            nodes: list[dict] = []
            walk(plan_json["Plan"], nodes)
            seq_big = sorted({n.get("Relation Name") for n in nodes
                              if n["Node Type"] == "Seq Scan" and n.get("Relation Name") in big_tables})
            indexes = sorted({n.get("Index Name") for n in nodes if n.get("Index Name")})
            results.append(dict(
                endpoint=endpoint, sql=re.sub(r"\s+", " ", statement).strip()[:400],
                median_ms=round(statistics.median(timings), 2), max_ms=round(max(timings), 2),
                shared_hit_blocks=plan_json["Plan"].get("Shared Hit Blocks"), shared_read_blocks=plan_json["Plan"].get("Shared Read Blocks"),
                node_types=sorted({n["Node Type"] for n in nodes}), indexes=indexes, seq_scan_on_big_tables=seq_big,
                passed=max(timings) <= 100 and not seq_big,
            ))
    results.sort(key=lambda r: -r["median_ms"])
    for r in results:
        flag = "OK " if r["passed"] else "!! "
        print(f"{flag}{r['median_ms']:8.2f} ms  {r['endpoint']:<58} seq={r['seq_scan_on_big_tables'] or '-'} idx={','.join(r['indexes'][:3]) or '-'}")
    write_result(f"explain_{args.dataset}.json", {"dataset": args.dataset, "machine": machine_info(), "scale": scale,
                                                  "repeats": REPEATS, "big_tables": sorted(big_tables),
                                                  "criteria": {"max_ms": 100, "no_seq_scan_on_rows_over": BIG_TABLE_MIN_ROWS},
                                                  "queries": results})
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
