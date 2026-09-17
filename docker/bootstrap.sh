#!/bin/sh
# Khởi tạo một lần cho docker compose (dịch vụ "init"):
#   migrate 2 CSDL -> (nếu CSDL phân tích còn trống) sinh mock data + ETL backfill -> đồng bộ tài khoản Dashboard.
# Chạy lại an toàn: dữ liệu đã có thì bỏ qua bước sinh mock/backfill.
set -eu

echo "[init] Áp dụng migration..."
python -m database.migrate up --target analytics
python -m database.migrate up --target moodle

HAS_DATA=$(python - <<'EOF'
import psycopg
from database.config import load_db_config
with psycopg.connect(**load_db_config("ANALYTICS_DB").conninfo()) as conn:
    print(conn.execute("SELECT COUNT(*) FROM analytics.fact_course_progress_daily").fetchone()[0])
EOF
)

if [ "$HAS_DATA" -gt 0 ]; then
    echo "[init] CSDL phân tích đã có $HAS_DATA dòng tiến độ – bỏ qua sinh mock data và backfill."
else
    echo "[init] Sinh mock data (Khoa CNTT, 15 môn, 500 SV)..."
    python -m mockdata.seed_structure --reset
    python -m mockdata.generate_activity --reset
    echo "[init] ETL backfill từ ${BACKFILL_FROM}..."
    python -m etl.jobs.backfill --from "${BACKFILL_FROM}"
fi

echo "[init] Đồng bộ tài khoản Dashboard (admin + giảng viên)..."
python -m backend.app.cli sync-users
echo "[init] Hoàn tất."
