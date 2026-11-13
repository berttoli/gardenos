from __future__ import annotations

from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.ids import new_uuid_str
from app.common.models import TimestampMixin
from app.common.pg import ci_text, jsonb_type
from app.database import Base

LABEL_TEMPLATE_TYPES = (
    "sheet",
    "loop",
    "stake",
    "qr-only",
    "calibration",
)


class LabelTemplate(TimestampMixin, Base):
    __tablename__ = "label_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    name: Mapped[str] = mapped_column(ci_text(160), nullable=False, unique=True)
    width_mm: Mapped[float] = mapped_column(Float, nullable=False)
    height_mm: Mapped[float] = mapped_column(Float, nullable=False)
    template_type: Mapped[str] = mapped_column(String(40), nullable=False, default="sheet")
    layout_definition: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
