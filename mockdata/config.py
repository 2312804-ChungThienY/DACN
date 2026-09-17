"""
Tham số sinh dữ liệu giả lập – SPEC Phần 3.2.

Quy mô đã thống nhất (thu hẹp so với spec): chỉ Khoa Công nghệ Thông tin, 15 môn, 500 sinh viên.
Hồ sơ hành vi, trọng số giờ/thứ, hệ số cao điểm giữ nguyên theo spec.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import numpy as np

from common.settings import TZ

RANDOM_SEED = 2026

# ----------------------------------------------------------------------------- học kỳ
SEMESTER_START = datetime(2026, 9, 7, tzinfo=TZ)          # Thứ 2, HK1 2026-2027
SEMESTER_WEEKS = 15
SEMESTER_END = SEMESTER_START + timedelta(weeks=SEMESTER_WEEKS)
STRUCTURE_CREATED_AT = SEMESTER_START - timedelta(days=21)  # thời điểm tạo khóa học/tài khoản
ENROL_START = SEMESTER_START - timedelta(days=7)

DAY = 86_400
WEEK = 7 * DAY

# ----------------------------------------------------------------------------- tổ chức
MOCK_IP_PREFIX = "10.99."                                  # dấu hiệu nhận biết dữ liệu giả lập
STUDENT_EMAIL_DOMAIN = "student.dlu.edu.vn"
STAFF_EMAIL_DOMAIN = "dlu.edu.vn"

FACULTY = ("CNTT", "Khoa Công nghệ Thông tin")

# (mã bộ môn, tên bộ môn, [(mã môn, tên môn)])  – bộ môn là danh mục cấp 2 dưới Khoa
DEPARTMENTS: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("KHMT", "Bộ môn Khoa học Máy tính", [
        ("IT001", "Nhập môn lập trình"),
        ("IT002", "Toán rời rạc"),
        ("IT003", "Cấu trúc dữ liệu và giải thuật"),
        ("IT010", "Trí tuệ nhân tạo"),
    ]),
    ("HTTT", "Bộ môn Hệ thống Thông tin", [
        ("IT004", "Cơ sở dữ liệu"),
        ("IT005", "Hệ quản trị cơ sở dữ liệu"),
        ("IT006", "Phân tích thiết kế hệ thống thông tin"),
        ("IT011", "Kho dữ liệu và khai phá dữ liệu"),
    ]),
    ("KTPM", "Bộ môn Kỹ thuật Phần mềm", [
        ("IT007", "Lập trình hướng đối tượng"),
        ("IT008", "Công nghệ phần mềm"),
        ("IT009", "Lập trình Web"),
        ("IT012", "Kiểm thử phần mềm"),
    ]),
    ("MMT", "Bộ môn Mạng máy tính và Truyền thông", [
        ("IT013", "Mạng máy tính"),
        ("IT014", "Hệ điều hành"),
        ("IT015", "An toàn thông tin"),
    ]),
]

ACADEMIC_TERM_TAG = "HK1_2026-2027"

# (username, họ + đệm, tên)
TEACHERS: list[tuple[str, str, str]] = [
    ("gv.tranminhhung", "Trần Minh", "Hùng"),
    ("gv.nguyenthilan", "Nguyễn Thị", "Lan"),
    ("gv.lequocbao", "Lê Quốc", "Bảo"),
    ("gv.phamthuha", "Phạm Thu", "Hà"),
    ("gv.vothanhtam", "Võ Thanh", "Tâm"),
    ("gv.dangngocanh", "Đặng Ngọc", "Ánh"),
    ("gv.buiducthang", "Bùi Đức", "Thắng"),
    ("gv.hohaiyen", "Hồ Hải", "Yến"),
]

# mã môn -> (chỉ số GV chính [editingteacher], các chỉ số GV trợ giảng [teacher])
COURSE_TEACHERS: dict[str, tuple[int, tuple[int, ...]]] = {
    "IT001": (0, (7,)), "IT002": (0, ()), "IT003": (1, ()), "IT010": (1, ()),
    "IT004": (2, (6,)), "IT005": (2, ()), "IT006": (3, ()), "IT011": (3, ()),
    "IT007": (4, ()), "IT008": (4, ()), "IT009": (5, (7,)), "IT012": (5, ()),
    "IT013": (6, ()), "IT014": (6, ()), "IT015": (7, ()),
}

# ----------------------------------------------------------------------------- sinh viên & ghi danh
# Ghi đè được bằng MOCK_N_STUDENTS – chỉ dùng cho bộ dữ liệu đo hiệu năng ETL (perf/etl_bench.py, CSDL riêng)
N_STUDENTS = int(os.getenv("MOCK_N_STUDENTS", "500"))
STUDENT_CODE_START = 2212001
COURSES_PER_STUDENT = (4, 6)
SUSPENDED_STUDENTS = 4            # mdl_user.suspended = 1 (ETL phải loại)
DELETED_STUDENTS = 2              # mdl_user.deleted = 1 (ETL phải loại)
SUSPENDED_ENROLMENT_RATE = 0.02   # mdl_user_enrolments.status = 1 ("hủy/tạm dừng ghi danh")
EXPIRED_ENROLMENT_RATE = 0.01     # timeend rơi vào tuần 3 của học kỳ
EXPIRED_AFTER_WEEKS = 3

# ----------------------------------------------------------------------------- nội dung môn học
ASSIGNMENTS_PER_COURSE = (5, 8)
ASSIGNMENT_DUE_WEEKS = (3, 14)          # hạn nộp rải đều từ tuần 3 tới tuần 14 (Chủ nhật 23:59)
ASSIGNMENT_OPEN_DAYS = 14               # mở nộp trước hạn 14 ngày
ATTENDANCE_SESSIONS_PER_WEEK = (1, 2)
ATTENDANCE_SLOT_HOURS = (7, 13)         # buổi sáng 07:00 hoặc chiều 13:00
TEAM_SUBMISSION_COURSES = ("IT008", "IT009")   # ca biên: bài nộp theo nhóm
TEAM_SIZE = 4
LAB_GROUP_COURSES = ("IT013",)                 # ca biên: buổi điểm danh gắn nhóm (groupid <> 0)
LAB_GROUPS = 2
NO_ATTENDANCE_SESSION_COURSES = ("IT015",)     # ca biên: môn chưa có buổi điểm danh

# ----------------------------------------------------------------------------- hồ sơ hành vi (SPEC 3.2)
PROFILES: dict[str, float] = {"GREEN": 0.65, "YELLOW": 0.20, "RED": 0.15}
PROFILE_CONSISTENCY = 0.80   # 80% cặp SV–môn giữ hồ sơ chung của SV

BEHAVIOR: dict[str, dict] = {
    "GREEN":  dict(sessions_per_week=(4, 9), attend=0.95, submit=0.95, late=0.05, never=0.00, dropout=0.00, post_rate=0.05),
    "YELLOW": dict(sessions_per_week=(1, 4), attend=0.80, submit=0.70, late=0.25, never=0.00, dropout=0.10, post_rate=0.03),
    "RED":    dict(sessions_per_week=(0, 1), attend=0.50, submit=0.30, late=0.40, never=0.35, dropout=0.30, post_rate=0.02),
}
RED_MAX_SUBMIT_RATIO = 0.40      # RED: nộp tối đa 40% số bài đã tới hạn (đảm bảo thiếu ≥ 60%)
RED_FUTURE_SUBMIT_PROB = 0.30
DROPOUT_FROM_WEEK_INDEX = 6      # "bỏ dần": hoạt động giảm từ tuần thứ 7 (chỉ số 0-based = 6)
DROPOUT_ACTIVITY_DIVISOR = 3
DROPOUT_ATTEND_FACTOR = 0.60
DROPOUT_SUBMIT_FACTOR = 0.30

# ----------------------------------------------------------------------------- phân bổ thời gian (SPEC 3.2)
HOUR_WEIGHTS = np.array([.3, .2, .1, .1, .1, .2, .6, 1.5, 3.0, 3.2, 3.0, 2.0,
                         1.0, 1.5, 3.0, 3.2, 2.8, 1.8, 1.2, 1.4, 1.8, 1.6, 1.0, .6])
HOUR_P = HOUR_WEIGHTS / HOUR_WEIGHTS.sum()
DOW_WEIGHTS = np.array([1, 1, 1, 1, 1, .5, .4])   # Thứ 2 ... Chủ nhật
DOW_P = DOW_WEIGHTS / DOW_WEIGHTS.sum()
MIDTERM_WEEK = 8                  # tuần 8 (1-based) – thi giữa kỳ
MIDTERM_FACTOR = 1.5
DEADLINE_WINDOW_DAYS = 2          # 48 giờ trước hạn nộp
DEADLINE_FACTOR = 2.5

# ----------------------------------------------------------------------------- chi tiết phiên truy cập
ACTIONS_PER_SESSION = (3, 15)     # thao tác trong môn mỗi phiên (không tính sự kiện đăng nhập)
ACTION_GAP_SECONDS = (20, 180)
MOBILE_SESSION_RATE = 0.10        # origin = 'ws' (ứng dụng Moodle Mobile)
FAILED_LOGIN_RATE = 0.005
ACTION_MIX = dict(page=0.55, assign=0.25)   # phần còn lại: xem diễn đàn / đăng bài (post_rate)
NEW_SUBMISSION_ROW_RATE = 0.30    # SV mở bài tập nhưng chưa nộp -> dòng status = 'new'
MISSING_ATTENDANCE_LOG_RATE = 0.01
ATTENDANCE_TAKEN_DELAY = 900      # GV điểm danh sau 15 phút đầu buổi
ONLINE_SESSION_TIMEOUT = 1800     # mdl_sessions: phiên còn hiệu lực trong 30 phút
