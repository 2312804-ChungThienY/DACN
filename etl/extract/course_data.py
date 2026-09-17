"""
Trích xuất bộ dữ liệu của các môn đang diễn ra tại một thời điểm AS_OF.

Dùng chung cho job rủi ro sinh viên và job tiến độ môn học. Mọi truy vấn chạy trong MỘT transaction
REPEATABLE READ chỉ đọc, nên các bảng được đọc trên cùng một ảnh chụp dữ liệu, không lệch nhau.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from sqlalchemy import Engine

from etl.db import read_frame
from etl.extract import load_sql

DATASET_QUERIES = ("enrolments", "interaction", "weekly_activity", "attendance", "assignments", "completion",
                   "submissions_day")

# Cột epoch có thể NULL. Nếu MỌI dòng đều NULL (vd đầu học kỳ chưa có bài nộp), pandas suy ra kiểu object/None
# thay vì số -> ép về kiểu số nguyên nullable Int64 để Transform luôn nhận cùng một kiểu dữ liệu.
NULLABLE_EPOCH_COLUMNS: dict[str, tuple[str, ...]] = {
    "interaction": ("last_access_ts",),
    "assignments": ("submitted_ts",),
}


@dataclass
class CourseDataset:
    as_of: datetime            # thời điểm tham chiếu (có múi giờ địa phương)
    day_start: datetime        # 00:00 cùng ngày với as_of
    courses: pd.DataFrame
    enrolments: pd.DataFrame
    interaction: pd.DataFrame
    weekly_activity: pd.DataFrame
    attendance: pd.DataFrame
    assignments: pd.DataFrame
    completion: pd.DataFrame
    submissions_day: pd.DataFrame

    def __post_init__(self) -> None:
        for frame_name, columns in NULLABLE_EPOCH_COLUMNS.items():
            df = getattr(self, frame_name)
            present = {c: df[c].astype("Int64") for c in columns if c in df.columns}
            if present:
                setattr(self, frame_name, df.assign(**present))

    @property
    def as_of_ts(self) -> int:
        return int(self.as_of.timestamp())

    @property
    def course_ids(self) -> list[int]:
        return [int(x) for x in self.courses["course_id"]]

    @property
    def source_rows(self) -> int:
        return sum(len(getattr(self, name)) for name in ("courses",) + DATASET_QUERIES)


def start_of_day(moment: datetime) -> datetime:
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def extract_course_dataset(moodle: Engine, as_of: datetime) -> CourseDataset:
    day_start = start_of_day(as_of)
    params = {"as_of": int(as_of.timestamp()), "day_start": int(day_start.timestamp())}
    with moodle.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        courses = read_frame(conn, load_sql("courses"), params)
        params["course_ids"] = [int(x) for x in courses["course_id"]]
        frames = {name: read_frame(conn, load_sql(name), params) for name in DATASET_QUERIES}
    return CourseDataset(as_of=as_of, day_start=day_start, courses=courses, **frames)
