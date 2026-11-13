from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.ids import new_uuid_str
from app.common.models import TimestampMixin
from app.database import Base

PROPAGATION_METHODS = (
    "seed",
    "softwood_cutting",
    "semi_hardwood_cutting",
    "hardwood_cutting",
    "air_layer",
    "ground_layer",
    "division",
    "graft",
    "approach_graft",
    "root_cutting",
    "tissue_culture",
    "unknown",
)


class PropagationEvent(TimestampMixin, Base):
    __tablename__ = "propagation_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    source_plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), nullable=False)
    new_plant_id: Mapped[str | None] = mapped_column(ForeignKey("plants.id"), nullable=True)
    method: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    separated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rooted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="in_progress")
    material_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cutting_length: Mapped[float | None] = mapped_column(Float, nullable=True)
    cutting_diameter: Mapped[float | None] = mapped_column(Float, nullable=True)
    node_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    medium: Mapped[str | None] = mapped_column(String(120), nullable=True)
    hormone: Mapped[str | None] = mapped_column(String(120), nullable=True)
    environment: Mapped[str | None] = mapped_column(Text, nullable=True)
    success_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_plant = relationship(
        "Plant", foreign_keys=[source_plant_id], back_populates="propagation_children"
    )
    new_plant = relationship(
        "Plant", foreign_keys=[new_plant_id], back_populates="propagation_descendants"
    )
