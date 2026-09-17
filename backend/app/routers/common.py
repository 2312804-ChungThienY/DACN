"""Endpoint dùng chung: /filters, /etl/status, /health."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import Connection, text

from backend.app.core.config import as_of, today
from backend.app.core.db import get_conn, get_engine
from backend.app.core.security import CurrentUser, get_current_user
from backend.app.repositories import common as common_repo
from backend.app.routers.deps import stamp
from backend.app.schemas.common import EtlJobStatus, FiltersOut, HealthOut
from common.settings import is_clock_frozen

router = APIRouter(tags=["Dùng chung"])


@router.get("/filters", response_model=FiltersOut, summary="Giá trị cho các ô lọc (khoa, năm học, học kỳ)")
def filters(_: CurrentUser = Depends(get_current_user), conn: Connection = Depends(get_conn)) -> dict:
    return {**common_repo.filters(conn, today()), "as_of": as_of(), "data_updated_at": stamp(conn)}


@router.get("/etl/status", response_model=list[EtlJobStatus], summary="Lần chạy gần nhất của từng job ETL")
def etl_status(_: CurrentUser = Depends(get_current_user), conn: Connection = Depends(get_conn)) -> list[dict]:
    return common_repo.etl_status(conn)


@router.get("/health", response_model=HealthOut, summary="Kiểm tra dịch vụ (không cần đăng nhập)")
def health() -> dict:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        database = True
    except Exception:           # noqa: BLE001 – health check chỉ báo trạng thái, không ném lỗi
        database = False
    return {"status": "ok" if database else "degraded", "database": database,
            "as_of": as_of(), "clock_frozen": is_clock_frozen()}
