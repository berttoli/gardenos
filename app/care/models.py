from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.ids import new_uuid_str
from app.common.models import TimestampMixin
from app.database import Base

TASK_TYPES = (
    "inspect",
    "water",
    "fertilize",
    "prune",
    "repot",
    "photograph",
    "measure",
    "treat",
    "harvest",
    "propagate",
    "move",
    "winterize",
    "clean",
    "custom",
)

TASK_SCOPES = ("plant", "taxon", "location", "collection", "garden")


class TaskDefinition(TimestampMixin, Base):
    __tablename__ = "task_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(String(40), nullable=False, default="custom")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False, default="garden")
    scope_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    recurrence_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    seasonal_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    seasonal_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_behavior: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    occurrences = relationship("TaskOccurrence", back_populates="task_definition")


class TaskOccurrence(TimestampMixin, Base):
    __tablename__ = "task_occurrences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    task_definition_id: Mapped[str] = mapped_column(
        ForeignKey("task_definitions.id"), nullable=False
    )
    plant_id: Mapped[str | None] = mapped_column(ForeignKey("plants.id"), nullable=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    skipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    task_definition = relationship("TaskDefinition", back_populates="occurrences")
    plant = relationship("Plant", back_populates="task_occurrences")


Index(
    "ix_task_definitions_title_trgm",
    TaskDefinition.__table__.c.title,
    postgresql_using="gin",
    postgresql_ops={"title": "gin_trgm_ops"},
)
