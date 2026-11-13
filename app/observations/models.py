from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.ids import new_uuid_str
from app.common.models import TimestampMixin
from app.database import Base


class Observation(TimestampMixin, Base):
    __tablename__ = "observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observation_type: Mapped[str] = mapped_column(String(40), nullable=False, default="routine")
    summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_health_score: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    observer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    weather_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True)

    plant = relationship("Plant", back_populates="observations")
    location = relationship("Location")
    assessment = relationship(
        "HealthAssessment",
        uselist=False,
        back_populates="observation",
        cascade="all, delete-orphan",
    )
    media_assets = relationship("MediaAsset", back_populates="observation")
    treatments = relationship("Treatment", back_populates="observation")


class HealthAssessment(TimestampMixin, Base):
    __tablename__ = "health_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    observation_id: Mapped[str] = mapped_column(
        ForeignKey("observations.id"), unique=True, nullable=False
    )
    leaf_color: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leaf_integrity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leaf_density: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_growth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    branch_vigor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stem_bark_health: Mapped[int | None] = mapped_column(Integer, nullable=True)
    root_vigor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hydration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pest_freedom: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disease_freedom: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_vigor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calculated_score: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    manual_score: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    symptoms: Mapped[str | None] = mapped_column(Text, nullable=True)
    suspected_causes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_actions: Mapped[str | None] = mapped_column(Text, nullable=True)

    observation = relationship("Observation", back_populates="assessment")


class Measurement(TimestampMixin, Base):
    __tablename__ = "measurements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    height: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    canopy_width: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    trunk_diameter: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    measurement_height: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    root_flare_width: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    pot_weight: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    soil_moisture: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    soil_ph: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    soil_temperature: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    plant = relationship("Plant", back_populates="measurements")


class Treatment(TimestampMixin, Base):
    __tablename__ = "treatments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), nullable=False)
    observation_id: Mapped[str | None] = mapped_column(ForeignKey("observations.id"), nullable=True)
    treatment_type: Mapped[str] = mapped_column(String(80), nullable=False)
    product_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    active_ingredient: Mapped[str | None] = mapped_column(String(160), nullable=True)
    dosage: Mapped[str | None] = mapped_column(String(160), nullable=True)
    application_method: Mapped[str | None] = mapped_column(String(160), nullable=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    follow_up_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)

    plant = relationship("Plant", back_populates="treatments")
    observation = relationship("Observation", back_populates="treatments")
