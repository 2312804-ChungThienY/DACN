"""Tiện ích dùng chung cho các script đo hiệu năng: chạy lệnh con với CSDL riêng, ghi kết quả JSON."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "perf" / "results"
WORK_DIR = PROJECT_ROOT / "perf" / ".work"

# Tên CSDL riêng cho đo hiệu năng – không bao giờ trùng CSDL demo (lms_analytics / moodle_src)
X10_ANALYTICS_DB = "lms_analytics_x10"
ETL_MOODLE_DB = "moodle_src_x4"
ETL_ANALYTICS_DB = "lms_analytics_etlbench"
PROTECTED_DATABASES = {"lms_analytics", "moodle_src", "postgres"}


def child_env(**overrides: str) -> dict[str, str]:
    for key, value in overrides.items():
        if key.endswith("_DB_NAME") and value in PROTECTED_DATABASES:
            raise SystemExit(f"Từ chối chạy đo hiệu năng trên CSDL demo {value!r}")
    env = dict(os.environ)
    env.update(overrides)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run(module_args: list[str], env: dict[str, str], *, label: str | None = None) -> float:
    """Chạy `python -m ...` ở thư mục gốc dự án; trả về số giây. Lỗi -> dừng script."""
    started = time.perf_counter()
    print(f"$ python -m {' '.join(module_args)}", flush=True)
    result = subprocess.run([sys.executable, "-m", *module_args], cwd=PROJECT_ROOT, env=env)
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        raise SystemExit(f"Lệnh thất bại (mã {result.returncode}): {label or ' '.join(module_args)}")
    return elapsed


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Không chuyển được {type(value)} sang JSON")


def write_result(name: str, payload: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    print(f"Đã ghi {path}")
    return path


def machine_info() -> dict:
    import platform
    return {"platform": platform.platform(), "python": platform.python_version(), "processor": platform.processor(),
            "cpu_count": os.cpu_count(), "measured_at": datetime.now().isoformat(timespec="seconds")}
