"""
Đo thời gian xuất báo cáo (SPEC 6.2 dòng "Export": Excel 10.000 dòng, PDF 500 dòng < 5 giây).

    python -m perf.export_bench

- Excel: báo cáo cảnh báo toàn bộ trên bộ x10 (~23.800 dòng, gấp 2,4 lần mục tiêu 10.000).
- PDF: báo cáo cảnh báo mức Nguy cơ cao trên bộ x1 (408 dòng, gần mục tiêu 500) và toàn bộ x1 (2.383 dòng).
Mỗi trường hợp chạy 3 lần qua API thật (TestClient), lấy thời gian phản hồi đầy đủ.
"""
from __future__ import annotations

import os
import statistics
import subprocess
import sys
import time

CASES = [
    # (tên, bộ dữ liệu, tham số, mục tiêu giây)
    ("excel_risk_all_x10", "x10", {"report_type": "risk", "format": "xlsx"}, 5.0),
    ("pdf_risk_red_x1", "x1", {"report_type": "risk", "format": "pdf", "risk_level": "RED"}, 5.0),
    ("pdf_risk_all_x1", "x1", {"report_type": "risk", "format": "pdf"}, None),
]
RUNS = 3


def measure_in_child(dataset: str) -> None:
    """Chạy trong tiến trình con để ANALYTICS_DB_NAME có hiệu lực trước khi import backend."""
    from perf.common import X10_ANALYTICS_DB
    if dataset == "x10":
        os.environ["ANALYTICS_DB_NAME"] = X10_ANALYTICS_DB
    os.environ.setdefault("BACKEND_JWT_SECRET", "perf-only-secret-" + "x" * 40)
    import json

    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from backend.app.core.db import get_engine
    from backend.app.core.security import create_access_token
    from backend.app.main import create_app

    with get_engine().connect() as conn:
        admin = conn.execute(text("SELECT user_id FROM analytics.app_user WHERE role = 'ADMIN' ORDER BY user_id LIMIT 1")).scalar_one()
    headers = {"Authorization": "Bearer " + create_access_token(admin, "ADMIN")[0]}
    client = TestClient(create_app())
    out = []
    for name, case_dataset, params, target in CASES:
        if case_dataset != dataset:
            continue
        seconds, size, rows = [], 0, None
        for _ in range(RUNS):
            t0 = time.perf_counter()
            res = client.get("/api/v1/admin/reports/export", params=params, headers=headers)
            seconds.append(time.perf_counter() - t0)
            if res.status_code != 200:
                raise SystemExit(f"{name}: HTTP {res.status_code} {res.text[:200]}")
            size = len(res.content)
        preview = client.get("/api/v1/admin/reports/preview", params={k: v for k, v in params.items() if k != "format"} | {"page_size": 1},
                             headers=headers).json()
        rows = preview["total"]
        out.append(dict(case=name, dataset=dataset, rows=rows, runs=RUNS, seconds=[round(s, 3) for s in seconds],
                        median_seconds=round(statistics.median(seconds), 3), size_kb=round(size / 1024),
                        target_seconds=target, passed=None if target is None else max(seconds) < target))
    print("RESULT_JSON=" + json.dumps(out, ensure_ascii=False))


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    if len(sys.argv) > 2 and sys.argv[1] == "--child":
        measure_in_child(sys.argv[2])
        return 0
    import json

    from perf.common import PROJECT_ROOT, machine_info, write_result
    results = []
    for dataset in ("x1", "x10"):
        proc = subprocess.run([sys.executable, "-m", "perf.export_bench", "--child", dataset], cwd=PROJECT_ROOT,
                              capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        if proc.returncode != 0:
            print(proc.stdout, proc.stderr)
            raise SystemExit(f"Đo export {dataset} thất bại")
        line = next(l for l in proc.stdout.splitlines() if l.startswith("RESULT_JSON="))
        results += json.loads(line.removeprefix("RESULT_JSON="))
    for r in results:
        flag = "–  " if r["passed"] is None else ("OK " if r["passed"] else "!! ")
        print(f"{flag}{r['case']:<22} {r['rows']:>7,} dòng  median {r['median_seconds']:.2f}s  ({r['size_kb']} KB)")
    write_result("export_bench.json", {"machine": machine_info(), "cases": results})
    return 0


if __name__ == "__main__":
    sys.exit(main())
