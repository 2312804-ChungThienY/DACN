"""
LMS Analytics API (SPEC 5.1).

    python -m uvicorn backend.app.main:app --reload --port 8000
    Swagger UI: http://localhost:8000/api/docs
"""
from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import get_settings
from backend.app.routers import admin, auth, common, reports, teacher

API_PREFIX = "/api/v1"

DESCRIPTION = """
API cho Dashboard trực quan hóa dữ liệu LMS Moodle. Dữ liệu đọc từ CSDL phân tích `lms_analytics` do ETL nạp.

* Xác thực: `POST /api/v1/auth/login` → dùng `Authorization: Bearer <token>`.
* "Hôm nay" tính theo `LMS_AS_OF` (chế độ demo) hoặc thời gian thực.
* Mỗi response có `data_updated_at`: thời điểm ETL chạy thành công gần nhất.
"""


def create_app() -> FastAPI:
    settings = get_settings()          # kiểm tra cấu hình ngay khi khởi động
    app = FastAPI(title="LMS Analytics API", version="1.0.0", description=DESCRIPTION,
                  docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
                       allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"],
                       expose_headers=["Content-Disposition", "X-Process-Time-Ms", "X-Data-Updated-At"])

    @app.middleware("http")
    async def process_time(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Process-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
        # Header bảo mật cơ bản (SPEC 6.3). API trả dữ liệu cá nhân sinh viên -> không cho trình duyệt/proxy lưu cache.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith(API_PREFIX):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    for module in (auth, common, admin, reports, teacher):
        app.include_router(module.router, prefix=API_PREFIX)
    return app


app = create_app()
