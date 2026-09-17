"""
Cấu hình ETL (SPEC Phần 4.1): timezone, quy tắc học kỳ, ngưỡng rủi ro, lịch job, giới hạn an toàn cho Moodle.
Mọi ngưỡng nghiệp vụ đặt ở đây để tinh chỉnh khi họp với giảng viên, không rải trong mã nguồn.
"""
from __future__ import annotations

from common.settings import APP_TIMEZONE, TZ  # noqa: F401  (tái xuất cho các module ETL)

# ----------------------------------------------------------------------------- học kỳ (SPEC 1.1)
# Tháng bắt đầu môn học -> học kỳ. HK1: 8–12 (năm học Y–Y+1); HK2: 1–5 và HK3 (hè): 6–7 (năm học Y-1–Y)
SEMESTER_BY_MONTH: dict[int, int] = {8: 1, 9: 1, 10: 1, 11: 1, 12: 1, 1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 3, 7: 3}

# ----------------------------------------------------------------------------- luật rủi ro (SPEC 2.3)
RISK_THRESHOLDS: dict[str, float] = dict(
    absence_yellow=0.15,        # C1: tỷ lệ vắng >= 15% -> 1 điểm
    absence_red=0.30,           # C1: tỷ lệ vắng >= 30% -> 2 điểm
    inactive_yellow_days=7,     # C2: > 7 ngày chưa truy cập -> 1 điểm
    inactive_red_days=14,       # C2: > 14 ngày chưa truy cập (hoặc chưa từng) -> 2 điểm
    low_access_ratio=0.5,       # C2: access_count_14d < 50% trung vị lớp -> 1 điểm
    missing_yellow=0.20,        # C3: tỷ lệ thiếu bài >= 20% -> 1 điểm
    missing_red=0.60,           # C3: tỷ lệ thiếu bài >= 60% -> 2 điểm
)
# Quy tắc xếp mức (đã hiệu chỉnh trên ground truth mock – xem etl/README.md "Hiệu chỉnh luật rủi ro"):
#   RED    : C2 = 2 (chưa từng vào / > 14 ngày)  HOẶC  >= 2 tiêu chí ở mức 2  HOẶC  tổng điểm >= 4
#   YELLOW : tổng điểm >= 1      ·      GREEN : tổng điểm = 0
# (Spec gốc: RED khi có BẤT KỲ tiêu chí = 2 hoặc tổng >= 3 -> Precision(RED) 62.9% < mục tiêu 80%.)
RISK_LEVEL_RULES: dict[str, int | bool] = dict(
    red_if_inactivity_red=True,
    red_min_red_criteria=2,
    red_min_total=4,
)
# risk_score = round(100 × (0.35·C1 + 0.30·C2 + 0.35·C3) / 2)
RISK_WEIGHTS: dict[str, float] = dict(attendance=0.35, inactivity=0.30, assignment=0.35)

# ----------------------------------------------------------------------------- trích xuất Moodle (SPEC 4.1, 4.2)
MOODLE_STATEMENT_TIMEOUT_MS = 60_000     # an toàn cho CSDL Moodle
ANALYTICS_STATEMENT_TIMEOUT_MS = 300_000
TRAFFIC_CHUNK_DAYS = 1                   # tổng hợp log theo lô 1 ngày khi nạp khoảng dài
ONLINE_SLOT_SECONDS = 300                # "online" = hoạt động trong 5 phút
PEAK_PERCENTILE = 0.90                   # is_peak_hour: requests > P90 ...
PEAK_WINDOW_DAYS = 28                    # ... của 28 ngày gần nhất

# ----------------------------------------------------------------------------- vận hành job (SPEC 4.2)
JOB_LOCK_KEYS: dict[str, int] = {        # khóa advisory trên CSDL analytics, chống chạy chồng
    "traffic": 7_424_101,
    "course_progress": 7_424_102,
    "student_risk": 7_424_103,
}
RETRY_DELAYS_SECONDS = (60, 300, 900)    # thử lại 3 lần: 1 – 5 – 15 phút (chỉ khi chạy bằng scheduler)
RISK_SNAPSHOT_RETENTION_DAYS = 180       # bảo trì: giữ snapshot cuối mỗi tuần với dữ liệu cũ hơn
