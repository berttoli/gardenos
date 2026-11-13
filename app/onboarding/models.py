from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.ids import new_uuid_str
from app.common.models import TimestampMixin
from app.common.pg import jsonb_type
from app.database import Base


class OnboardingDraft(TimestampMixin, Base):
    __tablename__ = "onboarding_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)
    draft_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    plant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state: Mapped[dict[str, object]] = mapped_column(
        jsonb_type(),
        nullable=False,
        default=dict,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    abandoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
