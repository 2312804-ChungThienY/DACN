"""Xóa các can thiệp do bộ E2E tạo (nội dung bắt đầu bằng "[e2e]") trong CSDL phân tích đang cấu hình."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import psycopg  # noqa: E402

from database.config import load_db_config  # noqa: E402

with psycopg.connect(**load_db_config("ANALYTICS_DB").conninfo(application_name="lms-e2e-cleanup")) as conn:
    deleted = conn.execute("DELETE FROM analytics.intervention_log WHERE content LIKE %s", ("[e2e]%",)).rowcount
print(f"[e2e] Đã xóa {deleted} can thiệp do E2E tạo.")
