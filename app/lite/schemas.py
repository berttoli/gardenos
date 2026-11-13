from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LitePayloadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlantCreate(LitePayloadModel):
    display_id: str | None = None
    scientific_name: str
    common_name: str | None = None
    status: str = "active"
    acquisition_type: str = "unknown"
    accession_date: date | None = None
    source_name: str | None = None
    source_reference: str | None = None
    zone_id: str | None = None
    zone_name: str | None = None
    location_name: str | None = None
    container_identifier: str | None = None
    notes: str | None = None


class PlantUpdate(LitePayloadModel):
    scientific_name: str | None = None
    common_name: str | None = None
    status: str | None = None
    acquisition_type: str | None = None
    accession_date: date | None = None
    source_name: str | None = None
    source_reference: str | None = None
    zone_id: str | None = None
    zone_name: str | None = None
    location_name: str | None = None
    container_identifier: str | None = None
    notes: str | None = None
    archived_at: datetime | None = None


class ObservationCreate(LitePayloadModel):
    plant: str
    observed_at: datetime | None = None
    observation_type: str = "routine"
    summary: str | None = None
    notes: str | None = None
    health_score: float | None = None
    moisture: float | None = None
    temperature: float | None = None
    zone_id: str | None = None
    zone_name: str | None = None
    location_name: str | None = None


class TaskCreate(LitePayloadModel):
    title: str
    plant: str | None = None
    task_type: str = "custom"
    priority: int = 3
    due_at: datetime | None = None
    zone_id: str | None = None
    zone_name: str | None = None
    location_name: str | None = None
    notes: str | None = None


class TaskComplete(LitePayloadModel):
    completed_at: datetime | None = None
    notes: str | None = None


class ConversationCreate(LitePayloadModel):
    title: str = "Garden chat"
    description: str | None = None


class ZoneCreate(LitePayloadModel):
    name: str
    zone_type: str = "zone"
    parent_id: str | None = None
    description: str | None = None
    sun_exposure: str | None = None
    soil_type: str | None = None
    drainage: str | None = None
    moisture_tendency: str | None = None
    slope: str | None = None
    wind_exposure: str | None = None
    irrigation_availability: str | None = None
    coordinates: dict[str, Any] | None = None
    photo_path: str | None = None
    notes: str | None = None


class ZoneUpdate(LitePayloadModel):
    name: str | None = None
    zone_type: str | None = None
    parent_id: str | None = None
    description: str | None = None
    sun_exposure: str | None = None
    soil_type: str | None = None
    drainage: str | None = None
    moisture_tendency: str | None = None
    slope: str | None = None
    wind_exposure: str | None = None
    irrigation_availability: str | None = None
    coordinates: dict[str, Any] | None = None
    photo_path: str | None = None
    notes: str | None = None


class MessageCreate(LitePayloadModel):
    role: Literal["system", "user", "assistant"]
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SqlQuery(LitePayloadModel):
    sql: str
    params: list[Any] = Field(default_factory=list)


class FunctionInvocation(LitePayloadModel):
    payload: dict[str, Any] = Field(default_factory=dict)
