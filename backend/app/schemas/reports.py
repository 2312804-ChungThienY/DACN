from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from backend.app.schemas.common import Page

ReportType = Literal["enrollment", "traffic", "risk"]
ExportFormat = Literal["xlsx", "pdf"]


class ReportColumn(BaseModel):
    key: str
    title: str
    kind: str


class ReportPreviewOut(Page[dict[str, Any]]):
    report_type: ReportType
    title: str
    columns: list[ReportColumn]
    filters: dict[str, Any]
