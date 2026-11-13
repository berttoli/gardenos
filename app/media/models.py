from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.ids import new_uuid_str
from app.common.models import TimestampMixin
from app.common.pg import jsonb_type
from app.database import Base

MEDIA_VIEW_TYPES = (
    "whole_plant",
    "canopy",
    "leaf_upper",
    "leaf_lower",
    "trunk",
    "graft_union",
    "root_flare",
    "roots",
    "soil",
    "pest",
    "disease",
    "damage",
    "flower",
    "fruit",
    "location",
    "label",
    "other",
)


class MediaAsset(TimestampMixin, Base):
    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), nullable=False)
    observation_id: Mapped[str | None] = mapped_column(ForeignKey("observations.id"), nullable=True)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(80), nullable=False, default="image")
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    view_type: Mapped[str] = mapped_column(String(40), nullable=False, default="other")
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    asset_metadata: Mapped[dict[str, object] | None] = mapped_column(
        "metadata",
        jsonb_type(),
        nullable=True,
    )

    plant = relationship("Plant", back_populates="media_assets")
    observation = relationship("Observation", back_populates="media_assets")
