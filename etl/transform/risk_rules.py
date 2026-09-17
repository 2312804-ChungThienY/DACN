"""
Luật chấm điểm rủi ro "đèn giao thông" – SPEC Phần 2.3.

| Tiêu chí              | 0 (Xanh)                              | 1 (Vàng)                                  | 2 (Đỏ)                               |
| C1 Vắng học           | < 15%                                 | 15% – < 30%                               | >= 30%                               |
| C2 Không tương tác    | vào trong 7 ngày và 14d >= 50% trung vị| 7–14 ngày chưa vào HOẶC 14d < 50% trung vị | chưa từng vào HOẶC > 14 ngày         |
| C3 Thiếu bài tập      | < 20%                                 | 20% – < 60%                               | >= 60%                               |

Xếp mức (RISK_LEVEL_RULES, đã hiệu chỉnh): RED khi C2 = 2 hoặc >= 2 tiêu chí = 2 hoặc tổng >= 4 ·
YELLOW: tổng >= 1 · GREEN: tổng = 0.
risk_score = round(100 × (0.35·C1 + 0.30·C2 + 0.35·C3) / 2), làm tròn half-up.
Chưa có dữ liệu (0 buổi điểm danh / 0 bài tới hạn) -> tiêu chí đó = 0; attendance_status = NO_DATA khi 0 buổi.

So sánh tỷ lệ với ngưỡng bằng phân số chính xác (Fraction) để các ca biên như "vắng đúng 3/10 buổi = 30%"
luôn cho kết quả đúng, không phụ thuộc sai số dấu phẩy động.
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from etl.config import RISK_LEVEL_RULES, RISK_THRESHOLDS, RISK_WEIGHTS

ATTENDANCE_STATUS_BY_SCORE = {0: "OK", 1: "WARN", 2: "CRITICAL"}


def _exact(value: float) -> Fraction:
    return Fraction(str(value))


def _level(numerator: int, denominator: int, yellow: float, red: float) -> int:
    ratio = Fraction(numerator, denominator)
    if ratio >= _exact(red):
        return 2
    if ratio >= _exact(yellow):
        return 1
    return 0


def _validate(r: Mapping) -> None:
    if r["total_sessions"] < 0 or not 0 <= r["absent_sessions"] <= r["total_sessions"]:
        raise ValueError(f"Số buổi không hợp lệ: vắng {r['absent_sessions']}/{r['total_sessions']}")
    if r["total_assignments"] < 0 or not 0 <= r["missing_assignments_count"] <= r["total_assignments"]:
        raise ValueError(f"Số bài không hợp lệ: thiếu {r['missing_assignments_count']}/{r['total_assignments']}")
    days = r["days_since_last_access"]
    if days is not None and days < 0:
        raise ValueError(f"days_since_last_access âm: {days}")
    if r["access_count_14d"] < 0:
        raise ValueError(f"access_count_14d âm: {r['access_count_14d']}")


def score_student(r: Mapping, class_median_14d: float,
                  thresholds: Mapping[str, float] = RISK_THRESHOLDS,
                  weights: Mapping[str, float] = RISK_WEIGHTS,
                  level_rules: Mapping[str, int | bool] = RISK_LEVEL_RULES) -> dict:
    """
    r cần các khóa: total_sessions, absent_sessions, days_since_last_access (None = chưa từng truy cập),
    access_count_14d, total_assignments, missing_assignments_count.
    class_median_14d: trung vị access_count_14d của lớp.
    """
    _validate(r)
    if class_median_14d < 0:
        raise ValueError(f"class_median_14d âm: {class_median_14d}")
    cfg = thresholds
    reasons: list[str] = []

    # ---- C1: vắng học
    c1 = 0
    total_sessions, absent = r["total_sessions"], r["absent_sessions"]
    if total_sessions > 0:
        c1 = _level(absent, total_sessions, cfg["absence_yellow"], cfg["absence_red"])
        if c1:
            reasons.append(f"Vắng {absent}/{total_sessions} buổi ({absent / total_sessions:.0%})")

    # ---- C2: không tương tác
    days = r["days_since_last_access"]
    low_access = class_median_14d > 0 and \
        Fraction(r["access_count_14d"]) < _exact(cfg["low_access_ratio"]) * _exact(class_median_14d)
    if days is None or days > cfg["inactive_red_days"]:
        c2 = 2
    elif days > cfg["inactive_yellow_days"] or low_access:
        c2 = 1
    else:
        c2 = 0
    if days is None:
        reasons.append("Chưa từng truy cập môn học")
    elif c2:
        reasons.append(f"{days} ngày chưa truy cập" if days > cfg["inactive_yellow_days"]
                       else "Tương tác thấp hơn 50% trung vị lớp")

    # ---- C3: thiếu bài tập
    c3 = 0
    total_assign, missing = r["total_assignments"], r["missing_assignments_count"]
    if total_assign > 0:
        c3 = _level(missing, total_assign, cfg["missing_yellow"], cfg["missing_red"])
        if c3:
            reasons.append(f"Thiếu {missing}/{total_assign} bài tập")

    total = c1 + c2 + c3
    red_criteria = sum(score == 2 for score in (c1, c2, c3))
    is_red = ((level_rules["red_if_inactivity_red"] and c2 == 2)
              or red_criteria >= level_rules["red_min_red_criteria"]
              or total >= level_rules["red_min_total"])
    level = "RED" if is_red else "YELLOW" if total >= 1 else "GREEN"
    weighted = (Decimal(str(weights["attendance"])) * c1 + Decimal(str(weights["inactivity"])) * c2
                + Decimal(str(weights["assignment"])) * c3)
    score = int((Decimal(100) * weighted / 2).quantize(Decimal(1), rounding=ROUND_HALF_UP))

    return dict(
        score_attendance=c1, score_inactivity=c2, score_assignment=c3,
        risk_score=score, risk_level=level, risk_reasons=reasons,
        attendance_status="NO_DATA" if total_sessions == 0 else ATTENDANCE_STATUS_BY_SCORE[c1],
    )
