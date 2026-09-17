"""Tạo response tải file báo cáo (Excel/PDF) – dùng chung cho Admin 1.3 và export của giảng viên."""
from __future__ import annotations

import re
from datetime import datetime
from http import HTTPStatus
from urllib.parse import quote

from fastapi import HTTPException, Response
from sqlalchemy import Connection

from backend.app.core.config import TZ, as_of, get_settings, today
from backend.app.repositories import reports as reports_repo
from backend.app.routers.deps import stamp, unprocessable
from backend.app.services.export_excel import XLSX_MEDIA_TYPE, build_xlsx
from backend.app.services.export_pdf import PDF_MEDIA_TYPE, PdfExportError, build_pdf
from backend.app.services.formatting import ExportDocument

_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]+")


def export_response(conn: Connection, filters: reports_repo.ReportFilters, fmt: str, *, title: str,
                    filename_stem: str, description: list[tuple[str, str]]) -> Response:
    settings = get_settings()
    limit = settings.pdf_max_rows if fmt == "pdf" else settings.excel_max_rows
    rows = reports_repo.rows_for_export(conn, filters, today(), limit)
    if len(rows) > limit:
        hint = " hoặc chọn xuất Excel" if fmt == "pdf" else ""
        raise unprocessable(f"Báo cáo có hơn {limit:,} dòng, vượt giới hạn xuất {fmt.upper()}. "
                            f"Hãy thu hẹp bộ lọc{hint}.".replace(",", "."))

    updated = stamp(conn)
    doc = ExportDocument(
        title=title, columns=reports_repo.report_columns(filters.report_type), rows=rows,
        filters=[("Dữ liệu tính đến", as_of().strftime("%d/%m/%Y %H:%M")), *description],
        generated_at=datetime.now(TZ))
    try:
        content, media_type = (build_pdf(doc), PDF_MEDIA_TYPE) if fmt == "pdf" else (build_xlsx(doc), XLSX_MEDIA_TYPE)
    except PdfExportError as exc:
        raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc)) from exc

    filename = f"{_UNSAFE.sub('_', filename_stem).strip('_')}.{fmt}"
    headers = {"Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}"}
    if updated is not None:
        headers["X-Data-Updated-At"] = updated.isoformat()
    return Response(content=content, media_type=media_type, headers=headers)
