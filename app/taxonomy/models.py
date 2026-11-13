from __future__ import annotations

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.ids import new_uuid_str
from app.common.models import TimestampMixin
from app.common.pg import ci_text, jsonb_type
from app.database import Base


class Taxon(TimestampMixin, Base):
    __tablename__ = "taxa"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    family: Mapped[str | None] = mapped_column(String(120), nullable=True)
    genus: Mapped[str] = mapped_column(String(120), nullable=False)
    species: Mapped[str | None] = mapped_column(String(120), nullable=True)
    subspecies: Mapped[str | None] = mapped_column(String(120), nullable=True)
    variety: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cultivar: Mapped[str | None] = mapped_column(String(120), nullable=True)
    scientific_name: Mapped[str] = mapped_column(ci_text(255), unique=True, nullable=False)
    common_names: Mapped[list[str]] = mapped_column(jsonb_type(), default=list, nullable=False)
    native_range: Mapped[str | None] = mapped_column(Text, nullable=True)
    hardiness_min: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hardiness_max: Mapped[str | None] = mapped_column(String(32), nullable=True)
    default_care_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("care_profiles.id"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_code: Mapped[str | None] = mapped_column(String(24), nullable=True)

    default_care_profile = relationship("CareProfile", back_populates="taxa")

    def as_common_names(self) -> list[str]:
        return list(self.common_names)


class CareProfile(TimestampMixin, Base):
    __tablename__ = "care_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    name: Mapped[str] = mapped_column(ci_text(160), unique=True, nullable=False)
    watering_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    sun_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    soil_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    fertilizer_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    pruning_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    winter_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    repotting_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    propagation_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    warning_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_sun: Mapped[str | None] = mapped_column(String(80), nullable=True)
    minimum_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    maximum_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_soil_ph_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_soil_ph_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    moisture_preference: Mapped[str | None] = mapped_column(String(80), nullable=True)
    humidity_preference: Mapped[str | None] = mapped_column(String(80), nullable=True)
    wind_tolerance: Mapped[str | None] = mapped_column(String(80), nullable=True)

    taxa = relationship("Taxon", back_populates="default_care_profile")
    plants = relationship("Plant", back_populates="care_profile")
