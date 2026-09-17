"""
Xuất báo cáo PDF bằng ReportLab (khổ A4 ngang, bảng lặp tiêu đề mỗi trang).

Kế hoạch đề xuất Jinja2 + WeasyPrint; WeasyPrint cần thư viện GTK/Pango cài riêng trên Windows nên dùng ReportLab
(thuần Python). Font TrueType có dấu tiếng Việt: mặc định Arial (Windows) hoặc DejaVu Sans (Linux),
đổi bằng BACKEND_PDF_FONT / BACKEND_PDF_FONT_BOLD.
"""
from __future__ import annotations

import threading
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from backend.app.core.config import get_settings
from backend.app.services.formatting import RISK_COLORS, ExportDocument, text_value

PDF_MEDIA_TYPE = "application/pdf"
FONT, FONT_BOLD = "LmsSans", "LmsSans-Bold"
WRAPPED_KINDS = ("text", "list")
NUMERIC_KINDS = ("int", "days", "percent", "decimal")
_font_lock = threading.Lock()


class PdfExportError(RuntimeError):
    """Không tạo được PDF (thường do thiếu font)."""


def _register_fonts() -> None:
    with _font_lock:
        if FONT in pdfmetrics.getRegisteredFontNames():
            return
        settings = get_settings()
        regular, bold = settings.pdf_font, settings.pdf_font_bold
        if not regular or not Path(regular).is_file():
            raise PdfExportError("Không tìm thấy font TrueType hỗ trợ tiếng Việt để xuất PDF. "
                                 "Khai báo đường dẫn file .ttf trong BACKEND_PDF_FONT.")
        pdfmetrics.registerFont(TTFont(FONT, regular))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, bold if bold and Path(bold).is_file() else regular))


def build_pdf(doc: ExportDocument) -> bytes:
    _register_fonts()
    buffer = BytesIO()
    page = landscape(A4)
    margin = 10 * mm
    template = SimpleDocTemplate(buffer, pagesize=page, leftMargin=margin, rightMargin=margin,
                                 topMargin=margin, bottomMargin=12 * mm, title=doc.title, author="LMS Analytics")

    title_style = ParagraphStyle("title", fontName=FONT_BOLD, fontSize=14, leading=18, spaceAfter=4)
    meta_style = ParagraphStyle("meta", fontName=FONT, fontSize=8.5, leading=11, textColor=colors.HexColor("#4B5563"))
    header_style = ParagraphStyle("header", fontName=FONT_BOLD, fontSize=7.5, leading=9, textColor=colors.white)
    cell_style = ParagraphStyle("cell", fontName=FONT, fontSize=7.5, leading=9)

    story = [Paragraph(escape(doc.title), title_style)]
    meta = [f"Thời điểm xuất: {doc.generated_at.strftime('%d/%m/%Y %H:%M')}", f"Số dòng: {len(doc.rows):,}".replace(",", ".")]
    meta += [f"{label}: {value}" for label, value in doc.filters]
    story += [Paragraph(escape(" · ".join(meta)), meta_style), Spacer(0, 4 * mm)]

    total_width = page[0] - 2 * margin
    weight = sum(c.width for c in doc.columns)
    col_widths = [total_width * c.width / weight for c in doc.columns]

    data = [[Paragraph(escape(c.title), header_style) for c in doc.columns]]
    commands = [
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FB")]),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    for index, column in enumerate(doc.columns):
        if column.kind in NUMERIC_KINDS:
            commands.append(("ALIGN", (index, 1), (index, -1), "RIGHT"))

    for row_no, row in enumerate(doc.rows, start=1):
        cells = []
        for index, column in enumerate(doc.columns):
            raw = row.get(column.key)
            text = text_value(raw, column.kind)
            # Chữ (kể cả "Chưa truy cập" trong cột số ngày) được bọc Paragraph để xuống dòng thay vì tràn sang ô bên
            wrap = column.kind in WRAPPED_KINDS or (column.kind == "days" and raw is None)
            cells.append(Paragraph(escape(text), cell_style) if wrap and text else text)
            if column.kind == "risk_level" and row.get(column.key) in RISK_COLORS:
                commands += [("TEXTCOLOR", (index, row_no), (index, row_no), colors.HexColor("#" + RISK_COLORS[row[column.key]])),
                             ("FONTNAME", (index, row_no), (index, row_no), FONT_BOLD)]
        data.append(cells)

    table = LongTable(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle(commands))
    story.append(table)

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawString(margin, 6 * mm, "LMS Analytics – " + doc.title)
        canvas.drawRightString(page[0] - margin, 6 * mm, f"Trang {document.page}")
        canvas.restoreState()

    template.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
