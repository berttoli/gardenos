from __future__ import annotations

from io import BytesIO
from typing import Any

try:  # pragma: no cover - exercised in integration tests when installed
    import qrcode as _qrcode
    from qrcode.constants import ERROR_CORRECT_L as _ERROR_CORRECT_L
    from qrcode.image.svg import SvgImage as _SvgImage
except Exception:  # pragma: no cover - fallback path for minimal environments
    _qrcode = None
    _ERROR_CORRECT_L = None
    _SvgImage = None

qrcode: Any | None = _qrcode
ERROR_CORRECT_L: Any | None = _ERROR_CORRECT_L
SvgImage: Any | None = _SvgImage


def _fallback_svg(data: str) -> str:
    escaped = (
        data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 210 210" '
        'role="img" aria-label="QR placeholder">\n'
        '  <rect width="210" height="210" fill="#fff"/>\n'
        '  <rect x="10" y="10" width="190" height="190" fill="#f3efe7" '
        'stroke="#1f1a17" stroke-width="4"/>\n'
        '  <text x="105" y="98" text-anchor="middle" font-family="monospace" '
        'font-size="14" fill="#1f1a17">QR unavailable</text>\n'
        f'  <text x="105" y="122" text-anchor="middle" font-family="monospace" '
        f'font-size="10" fill="#5f564c">{escaped}</text>\n'
        "</svg>"
    )


def qr_svg(data: str) -> str:
    if qrcode is None:
        return _fallback_svg(data)

    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_L, border=4, box_size=10)
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(image_factory=SvgImage)
    buffer = BytesIO()
    image.save(buffer)
    return buffer.getvalue().decode("utf-8")


def qr_png(data: str) -> bytes:
    if qrcode is None:
        raise RuntimeError("qrcode is not installed.")

    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_L, border=4, box_size=10)
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image()
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
