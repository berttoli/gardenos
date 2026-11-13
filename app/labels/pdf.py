from __future__ import annotations

from io import BytesIO
from typing import Any

from app.labels.qr import qr_png

try:  # pragma: no cover - exercised when reportlab is installed
    from reportlab.lib.utils import ImageReader as _ImageReader
    from reportlab.pdfgen import canvas as _canvas
except Exception:  # pragma: no cover - fallback in minimal environments
    _ImageReader = None
    _canvas = None

ImageReader: Any | None = _ImageReader
canvas: Any | None = _canvas


def _mm_to_points(value_mm: float) -> float:
    return value_mm * 72.0 / 25.4


def label_pdf_bytes(
    *,
    title_lines: list[str],
    subtitle_lines: list[str],
    display_id: str,
    target_url: str,
    width_mm: float,
    height_mm: float,
    template_type: str = "sheet",
) -> bytes:
    if canvas is None or ImageReader is None:
        raise RuntimeError("reportlab is not installed.")

    width_pt = _mm_to_points(width_mm)
    height_pt = _mm_to_points(height_mm)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(width_pt, height_pt))
    pdf.setTitle(display_id)
    pdf.setAuthor("Garden OS")

    if template_type == "calibration":
        _draw_calibration_page(pdf, width_pt, height_pt)
    else:
        _draw_label_page(
            pdf,
            title_lines,
            subtitle_lines,
            display_id,
            target_url,
            width_pt,
            height_pt,
            template_type,
        )

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _draw_label_page(
    pdf: Any,
    title_lines: list[str],
    subtitle_lines: list[str],
    display_id: str,
    target_url: str,
    width_pt: float,
    height_pt: float,
    template_type: str,
) -> None:
    del template_type
    pdf.setStrokeColorRGB(0.15, 0.12, 0.1)
    pdf.setFillColorRGB(0.12, 0.1, 0.09)
    margin = 12
    qr_side = min(width_pt, height_pt) * 0.42
    qr_x = width_pt - margin - qr_side
    qr_y = height_pt - margin - qr_side
    reader = ImageReader
    assert reader is not None
    qr_image = reader(BytesIO(qr_png(target_url)))
    pdf.drawImage(qr_image, qr_x, qr_y, qr_side, qr_side, preserveAspectRatio=True, mask="auto")

    text_x = margin
    text_top = height_pt - margin - 18
    pdf.setFont("Helvetica-Bold", 16)
    for line in title_lines:
        pdf.drawString(text_x, text_top, line)
        text_top -= 18

    pdf.setFont("Helvetica", 10)
    text_top -= 4
    for line in subtitle_lines:
        pdf.drawString(text_x, text_top, line)
        text_top -= 13

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(text_x, margin + 22, display_id)


def _draw_calibration_page(pdf: Any, width_pt: float, height_pt: float) -> None:
    pdf.setStrokeColorRGB(0.15, 0.12, 0.1)
    pdf.setFillColorRGB(0.12, 0.1, 0.09)
    pdf.setFont("Helvetica", 9)
    margin = 24
    step = 36
    for x in range(margin, int(width_pt - margin) + 1, step):
        pdf.line(x, margin, x, height_pt - margin)
        pdf.drawString(x - 4, margin - 12, str(round((x - margin) / 72, 1)))
    for y in range(margin, int(height_pt - margin) + 1, step):
        pdf.line(margin, y, width_pt - margin, y)
        pdf.drawString(4, y - 3, str(round((y - margin) / 72, 1)))
    pdf.setLineWidth(1.5)
    pdf.rect(margin, margin, width_pt - 2 * margin, height_pt - 2 * margin)
