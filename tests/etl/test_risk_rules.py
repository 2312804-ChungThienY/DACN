"""Kiểm thử đơn vị luật rủi ro (SPEC 2.3, 6.1: >= 20 ca biên, 100% pass). Không cần CSDL."""
from __future__ import annotations

import pytest

from etl.transform.risk_rules import score_student


def student(**overrides) -> dict:
    """SV mặc định an toàn: đi học đủ, vào môn hôm qua, nộp đủ bài, tương tác bằng trung vị lớp."""
    row = dict(total_sessions=10, absent_sessions=0, days_since_last_access=1, access_count_14d=20,
               total_assignments=5, missing_assignments_count=0)
    row.update(overrides)
    return row


MEDIAN = 20


# ----------------------------------------------------------------------------- C1: vắng học
@pytest.mark.parametrize(
    ("absent", "total", "expected"),
    [
        (0, 10, 0),
        (1, 10, 0),       # 10% < 15%
        (3, 20, 1),       # đúng 15% -> vàng
        (2, 10, 1),       # 20%
        (29, 100, 1),     # 29% vẫn vàng
        (3, 10, 2),       # đúng 30% -> đỏ (ca biên SPEC)
        (5, 12, 2),       # 41.7%
        (10, 10, 2),
    ],
)
def test_attendance_criterion_boundaries(absent, total, expected):
    result = score_student(student(absent_sessions=absent, total_sessions=total), MEDIAN)
    assert result["score_attendance"] == expected


def test_no_attendance_sessions_is_no_data_and_zero_score():
    result = score_student(student(total_sessions=0, absent_sessions=0), MEDIAN)
    assert result["score_attendance"] == 0
    assert result["attendance_status"] == "NO_DATA"
    assert result["risk_level"] == "GREEN"


@pytest.mark.parametrize(("absent", "status"), [(0, "OK"), (2, "WARN"), (3, "CRITICAL")])
def test_attendance_status_mapping(absent, status):
    assert score_student(student(absent_sessions=absent), MEDIAN)["attendance_status"] == status


# ----------------------------------------------------------------------------- C2: không tương tác
@pytest.mark.parametrize(
    ("days", "access_14d", "median", "expected"),
    [
        (0, 20, 20, 0),
        (7, 20, 20, 0),       # đúng 7 ngày vẫn là "trong 7 ngày"
        (8, 20, 20, 1),       # > 7 ngày
        (14, 20, 20, 1),      # đúng 14 ngày vẫn vàng
        (15, 20, 20, 2),      # > 14 ngày -> đỏ
        (None, 0, 20, 2),     # chưa từng truy cập
        (1, 9, 20, 1),        # 9 < 50% × 20
        (1, 10, 20, 0),       # đúng 50% trung vị -> không thấp
        (1, 0, 0, 0),         # trung vị lớp = 0 -> không xét tương tác thấp
        (1, 3, 7, 1),         # 3 < 3.5 (trung vị lẻ)
        (1, 4, 7, 0),
    ],
)
def test_inactivity_criterion(days, access_14d, median, expected):
    result = score_student(student(days_since_last_access=days, access_count_14d=access_14d), median)
    assert result["score_inactivity"] == expected


def test_inactivity_reasons():
    assert score_student(student(days_since_last_access=None, access_count_14d=0), MEDIAN)["risk_reasons"] == \
        ["Chưa từng truy cập môn học"]
    assert score_student(student(days_since_last_access=16), MEDIAN)["risk_reasons"] == ["16 ngày chưa truy cập"]
    assert score_student(student(days_since_last_access=2, access_count_14d=1), MEDIAN)["risk_reasons"] == \
        ["Tương tác thấp hơn 50% trung vị lớp"]


# ----------------------------------------------------------------------------- C3: thiếu bài
@pytest.mark.parametrize(
    ("missing", "total", "expected"),
    [
        (0, 5, 0),
        (1, 6, 0),        # 16.7%
        (1, 5, 1),        # đúng 20%
        (2, 5, 1),        # 40%
        (3, 5, 2),        # đúng 60% = bỏ 3/5 bài (ca biên SPEC)
        (5, 5, 2),
        (0, 0, 0),        # chưa có bài tới hạn
    ],
)
def test_assignment_criterion(missing, total, expected):
    result = score_student(student(missing_assignments_count=missing, total_assignments=total), MEDIAN)
    assert result["score_assignment"] == expected


# ----------------------------------------------------------------------------- tổng hợp mức & điểm
@pytest.mark.parametrize(
    ("overrides", "level", "score"),
    [
        ({}, "GREEN", 0),
        ({"absent_sessions": 2}, "YELLOW", 18),                                   # C1=1: 17.5 -> 18 (half-up)
        ({"days_since_last_access": 9}, "YELLOW", 15),                            # C2=1
        ({"missing_assignments_count": 1}, "YELLOW", 18),                         # C3=1
        ({"absent_sessions": 2, "days_since_last_access": 9}, "YELLOW", 33),      # tổng 2: 32.5 -> 33
        ({"absent_sessions": 2, "days_since_last_access": 9, "missing_assignments_count": 1}, "YELLOW", 50),  # tổng 3
        ({"absent_sessions": 3}, "YELLOW", 35),                                   # chỉ C1 = 2
        ({"missing_assignments_count": 3}, "YELLOW", 35),                         # chỉ C3 = 2
        ({"absent_sessions": 3, "missing_assignments_count": 1}, "YELLOW", 53),   # 2 + 1 = 3: 52.5 -> 53
        ({"absent_sessions": 3, "missing_assignments_count": 3}, "RED", 70),      # 2 tiêu chí = 2
        ({"absent_sessions": 3, "days_since_last_access": 9, "missing_assignments_count": 1}, "RED", 68),  # tổng 4
        ({"days_since_last_access": None, "access_count_14d": 0}, "RED", 30),     # C2 = 2: chưa từng truy cập
        ({"days_since_last_access": 16}, "RED", 30),                              # C2 = 2: > 14 ngày
        ({"absent_sessions": 5, "days_since_last_access": None, "access_count_14d": 0,
          "missing_assignments_count": 5}, "RED", 100),
    ],
)
def test_level_and_score(overrides, level, score):
    result = score_student(student(**overrides), MEDIAN)
    assert (result["risk_level"], result["risk_score"]) == (level, score)


def test_reasons_for_full_red_student():
    result = score_student(student(absent_sessions=5, total_sessions=12, days_since_last_access=16,
                                   missing_assignments_count=4), MEDIAN)
    assert result["risk_reasons"] == ["Vắng 5/12 buổi (42%)", "16 ngày chưa truy cập", "Thiếu 4/5 bài tập"]


def test_original_spec_level_rule_is_still_configurable():
    spec_rule = dict(red_if_inactivity_red=True, red_min_red_criteria=1, red_min_total=3)
    assert score_student(student(absent_sessions=3), MEDIAN, level_rules=spec_rule)["risk_level"] == "RED"
    assert score_student(student(absent_sessions=2, days_since_last_access=9, missing_assignments_count=1),
                         MEDIAN, level_rules=spec_rule)["risk_level"] == "RED"


def test_custom_thresholds_are_respected():
    thresholds = dict(absence_yellow=0.10, absence_red=0.50, inactive_yellow_days=3, inactive_red_days=30,
                      low_access_ratio=0.5, missing_yellow=0.20, missing_red=0.60)
    result = score_student(student(absent_sessions=1, days_since_last_access=20), MEDIAN, thresholds=thresholds)
    assert (result["score_attendance"], result["score_inactivity"]) == (1, 1)


# ----------------------------------------------------------------------------- dữ liệu đầu vào sai -> báo lỗi
@pytest.mark.parametrize(
    "overrides",
    [
        {"absent_sessions": 11},
        {"absent_sessions": -1},
        {"missing_assignments_count": 6},
        {"days_since_last_access": -2},
        {"access_count_14d": -1},
    ],
)
def test_invalid_input_raises(overrides):
    with pytest.raises(ValueError):
        score_student(student(**overrides), MEDIAN)


def test_negative_median_raises():
    with pytest.raises(ValueError):
        score_student(student(), -1)
