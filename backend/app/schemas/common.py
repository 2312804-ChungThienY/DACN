"""Schema dùng chung: phân trang, dấu thời gian dữ liệu, bộ lọc, trạng thái ETL."""
from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T")
RiskLevel = Literal["RED", "YELLOW", "GREEN"]


class Stamped(BaseModel):
    data_updated_at: datetime | None = None   # thời điểm ETL chạy thành công gần nhất


class ItemList(Stamped, Generic[T]):
    items: list[T]


class Page(Stamped, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class Faculty(BaseModel):
    id: int
    name: str


class Term(BaseModel):
    academic_year: str
    semester: int


class FiltersOut(Stamped):
    faculties: list[Faculty]
    academic_years: list[str]
    semesters: list[int]
    current: Term
    as_of: datetime


class EtlJobStatus(BaseModel):
    job_name: str
    last_success_at: datetime | None
    status: str | None
    started_at: datetime | None
    finished_at: datetime | None


class HealthOut(BaseModel):
    status: str
    database: bool
    as_of: datetime
    clock_frozen: bool
