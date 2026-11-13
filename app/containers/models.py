from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.ids import new_uuid_str
from app.common.models import TimestampMixin
from app.common.pg import ci_text
from app.database import Base


class Container(TimestampMixin, Base):
    __tablename__ = "containers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    identifier: Mapped[str] = mapped_column(ci_text(120), unique=True, nullable=False)
    container_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    material: Mapped[str | None] = mapped_column(String(80), nullable=True)
    shape: Mapped[str | None] = mapped_column(String(80), nullable=True)
    diameter: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[float | None] = mapped_column(Float, nullable=True)
    length: Mapped[float | None] = mapped_column(Float, nullable=True)
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    drainage_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    soil_mix_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    date_last_repot: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    plants = relationship("Plant", back_populates="container")
