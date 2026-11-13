from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.ids import new_uuid_str
from app.common.models import TimestampMixin
from app.database import Base


class Location(TimestampMixin, Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    location_type: Mapped[str] = mapped_column(String(40), nullable=False, default="temporary")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation: Mapped[float | None] = mapped_column(Float, nullable=True)
    sun_exposure: Mapped[str | None] = mapped_column(String(80), nullable=True)
    wind_exposure: Mapped[str | None] = mapped_column(String(80), nullable=True)
    irrigation_zone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    microclimate_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    parent = relationship("Location", remote_side="Location.id", back_populates="children")
    children = relationship("Location", back_populates="parent")
    plants = relationship("Plant", back_populates="current_location")


Index(
    "ix_locations_name_trgm",
    Location.__table__.c.name,
    postgresql_using="gin",
    postgresql_ops={"name": "gin_trgm_ops"},
)
