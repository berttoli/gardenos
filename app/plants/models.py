from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.ids import new_uuid_str
from app.common.models import TimestampMixin
from app.common.pg import ci_text
from app.database import Base

PLANT_STATUSES = (
    "quarantine",
    "active",
    "dormant",
    "propagation",
    "declining",
    "dead",
    "gifted",
    "sold",
    "removed",
    "archived",
)

ACQUISITION_TYPES = (
    "purchased",
    "gifted",
    "seed-grown",
    "cutting",
    "air-layer",
    "division",
    "graft",
    "found",
    "transplanted",
    "unknown",
)


class Plant(TimestampMixin, Base):
    __tablename__ = "plants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    display_id: Mapped[str] = mapped_column(ci_text(48), unique=False, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    accession_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    acquisition_type: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    purchase_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(180), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    taxon_id: Mapped[str | None] = mapped_column(ForeignKey("taxa.id"), nullable=True)
    cultivar_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    common_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    care_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("care_profiles.id"), nullable=True
    )

    current_location_id: Mapped[str | None] = mapped_column(
        ForeignKey("locations.id"), nullable=True
    )
    container_id: Mapped[str | None] = mapped_column(ForeignKey("containers.id"), nullable=True)
    parent_plant_id: Mapped[str | None] = mapped_column(ForeignKey("plants.id"), nullable=True)
    rootstock_plant_id: Mapped[str | None] = mapped_column(ForeignKey("plants.id"), nullable=True)

    is_grafted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    graft_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_edible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_toxic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pollinator_value: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    wildlife_value: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    taxon = relationship("Taxon")
    care_profile = relationship("CareProfile", back_populates="plants")
    current_location = relationship("Location", back_populates="plants")
    container = relationship("Container", back_populates="plants")
    parent_plant = relationship("Plant", remote_side="Plant.id", foreign_keys=[parent_plant_id])
    rootstock_plant = relationship(
        "Plant", remote_side="Plant.id", foreign_keys=[rootstock_plant_id]
    )
    aliases = relationship(
        "PlantIdentifierAlias", back_populates="plant", cascade="all, delete-orphan"
    )
    location_history = relationship(
        "PlantLocationHistory",
        back_populates="plant",
        cascade="all, delete-orphan",
    )
    container_history = relationship(
        "PlantContainerHistory",
        back_populates="plant",
        cascade="all, delete-orphan",
    )
    status_history = relationship(
        "PlantStatusHistory",
        back_populates="plant",
        cascade="all, delete-orphan",
    )
    observations = relationship("Observation", back_populates="plant", cascade="all, delete-orphan")
    measurements = relationship("Measurement", back_populates="plant", cascade="all, delete-orphan")
    treatments = relationship("Treatment", back_populates="plant", cascade="all, delete-orphan")
    media_assets = relationship("MediaAsset", back_populates="plant", cascade="all, delete-orphan")
    propagation_children = relationship(
        "PropagationEvent",
        foreign_keys="PropagationEvent.source_plant_id",
        back_populates="source_plant",
    )
    propagation_descendants = relationship(
        "PropagationEvent",
        foreign_keys="PropagationEvent.new_plant_id",
        back_populates="new_plant",
    )
    task_occurrences = relationship("TaskOccurrence", back_populates="plant")


Index(
    "uq_plants_display_id_active",
    Plant.__table__.c.display_id,
    unique=True,
    postgresql_where=Plant.__table__.c.archived_at.is_(None),
)


class PlantIdentifierAlias(TimestampMixin, Base):
    __tablename__ = "plant_identifier_aliases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), nullable=False)
    identifier: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    identifier_type: Mapped[str] = mapped_column(String(40), nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    plant = relationship("Plant", back_populates="aliases")


class PlantLocationHistory(TimestampMixin, Base):
    __tablename__ = "plant_location_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), nullable=False)
    from_location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    to_location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    moved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    plant = relationship("Plant", back_populates="location_history")


class PlantContainerHistory(TimestampMixin, Base):
    __tablename__ = "plant_container_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), nullable=False)
    from_container_id: Mapped[str | None] = mapped_column(
        ForeignKey("containers.id"), nullable=True
    )
    to_container_id: Mapped[str | None] = mapped_column(ForeignKey("containers.id"), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    plant = relationship("Plant", back_populates="container_history")


class PlantStatusHistory(TimestampMixin, Base):
    __tablename__ = "plant_status_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    new_status: Mapped[str] = mapped_column(String(40), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    plant = relationship("Plant", back_populates="status_history")
