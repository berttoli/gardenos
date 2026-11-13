from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.common.forms import optional_str, parse_datetime, parse_decimal, parse_int
from app.observations.models import HealthAssessment, Measurement, Observation, Treatment
from app.plants.models import Plant

OBSERVATION_TYPES = (
    "routine",
    "monthly_review",
    "shipping_arrival",
    "pest",
    "disease",
    "damage",
    "growth",
    "dormancy",
    "flowering",
    "fruiting",
    "transplant",
    "treatment_response",
    "custom",
)

HEALTH_FIELDS = (
    "leaf_color",
    "leaf_integrity",
    "leaf_density",
    "new_growth",
    "branch_vigor",
    "stem_bark_health",
    "root_vigor",
    "hydration",
    "pest_freedom",
    "disease_freedom",
    "overall_vigor",
)


def _validate_score(value: Any, field_name: str) -> int | None:
    score = parse_int(value)
    if score is None:
        return None
    if score < 0 or score > 10:
        raise ValueError(f"{field_name} must be between 0 and 10.")
    return score


def _assessment_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    nested = payload.get("assessment")
    if isinstance(nested, Mapping):
        return dict(nested)
    return {
        key: payload[key]
        for key in HEALTH_FIELDS
        + ("manual_score", "confidence", "symptoms", "suspected_causes", "recommended_actions")
        if key in payload
    }


def health_assessment_score(assessment: HealthAssessment) -> float | None:
    values = [
        getattr(assessment, field)
        for field in HEALTH_FIELDS
        if getattr(assessment, field) is not None
    ]
    if not values:
        return None
    return round(sum(int(value) for value in values) / len(values), 2)


def create_observation(session: Session, plant: Plant, payload: Mapping[str, Any]) -> Observation:
    observation_type = optional_str(payload.get("observation_type")) or "routine"
    if observation_type not in OBSERVATION_TYPES:
        raise ValueError(f"Invalid observation type: {observation_type}.")

    observed_at = parse_datetime(payload.get("observed_at")) or datetime.now(UTC)
    observation = Observation(
        plant=plant,
        observed_at=observed_at,
        observation_type=observation_type,
        summary=optional_str(payload.get("summary")),
        notes=optional_str(payload.get("notes")),
        observer=optional_str(payload.get("observer")),
        weather_notes=optional_str(payload.get("weather_notes")),
        location_id=optional_str(payload.get("location_id")),
        overall_health_score=parse_decimal(payload.get("overall_health_score")),
    )
    session.add(observation)

    assessment_payload = _assessment_payload(payload)
    if assessment_payload:
        assessment = HealthAssessment(
            observation=observation,
            leaf_color=_validate_score(assessment_payload.get("leaf_color"), "leaf_color"),
            leaf_integrity=_validate_score(
                assessment_payload.get("leaf_integrity"), "leaf_integrity"
            ),
            leaf_density=_validate_score(assessment_payload.get("leaf_density"), "leaf_density"),
            new_growth=_validate_score(assessment_payload.get("new_growth"), "new_growth"),
            branch_vigor=_validate_score(assessment_payload.get("branch_vigor"), "branch_vigor"),
            stem_bark_health=_validate_score(
                assessment_payload.get("stem_bark_health"), "stem_bark_health"
            ),
            root_vigor=_validate_score(assessment_payload.get("root_vigor"), "root_vigor"),
            hydration=_validate_score(assessment_payload.get("hydration"), "hydration"),
            pest_freedom=_validate_score(assessment_payload.get("pest_freedom"), "pest_freedom"),
            disease_freedom=_validate_score(
                assessment_payload.get("disease_freedom"), "disease_freedom"
            ),
            overall_vigor=_validate_score(assessment_payload.get("overall_vigor"), "overall_vigor"),
            manual_score=parse_decimal(assessment_payload.get("manual_score")),
            confidence=parse_decimal(assessment_payload.get("confidence")),
            symptoms=optional_str(assessment_payload.get("symptoms")),
            suspected_causes=optional_str(assessment_payload.get("suspected_causes")),
            recommended_actions=optional_str(assessment_payload.get("recommended_actions")),
        )
        assessment.calculated_score = health_assessment_score(assessment)
        if observation.overall_health_score is None:
            observation.overall_health_score = (
                assessment.manual_score or assessment.calculated_score
            )
        session.add(assessment)

    session.flush()
    return observation


def record_measurement(session: Session, plant: Plant, payload: Mapping[str, Any]) -> Measurement:
    measurement = Measurement(
        plant=plant,
        measured_at=parse_datetime(payload.get("measured_at")) or datetime.now(UTC),
        height=parse_decimal(payload.get("height")),
        canopy_width=parse_decimal(payload.get("canopy_width")),
        trunk_diameter=parse_decimal(payload.get("trunk_diameter")),
        measurement_height=parse_decimal(payload.get("measurement_height")),
        root_flare_width=parse_decimal(payload.get("root_flare_width")),
        pot_weight=parse_decimal(payload.get("pot_weight")),
        soil_moisture=parse_decimal(payload.get("soil_moisture")),
        soil_ph=parse_decimal(payload.get("soil_ph")),
        soil_temperature=parse_decimal(payload.get("soil_temperature")),
        notes=optional_str(payload.get("notes")),
    )
    session.add(measurement)
    session.flush()
    return measurement


def record_treatment(session: Session, plant: Plant, payload: Mapping[str, Any]) -> Treatment:
    treatment = Treatment(
        plant=plant,
        observation_id=optional_str(payload.get("observation_id")),
        treatment_type=optional_str(payload.get("treatment_type")) or "custom",
        product_name=optional_str(payload.get("product_name")),
        active_ingredient=optional_str(payload.get("active_ingredient")),
        dosage=optional_str(payload.get("dosage")),
        application_method=optional_str(payload.get("application_method")),
        applied_at=parse_datetime(payload.get("applied_at")) or datetime.now(UTC),
        follow_up_date=parse_datetime(payload.get("follow_up_date")),
        notes=optional_str(payload.get("notes")),
        result=optional_str(payload.get("result")),
    )
    session.add(treatment)
    session.flush()
    return treatment


def recent_observations(session: Session, *, limit: int = 8) -> list[Observation]:
    stmt = (
        select(Observation)
        .options(
            selectinload(Observation.plant),
            selectinload(Observation.assessment),
            selectinload(Observation.location),
        )
        .order_by(desc(Observation.observed_at))
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def latest_measurements(session: Session, plant_id: str, *, limit: int = 12) -> list[Measurement]:
    stmt = (
        select(Measurement)
        .where(Measurement.plant_id == plant_id)
        .order_by(desc(Measurement.measured_at))
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def health_trends(
    session: Session, plant_id: str, *, limit: int = 12
) -> dict[str, list[dict[str, Any]]]:
    observations = list(
        session.scalars(
            select(Observation)
            .where(Observation.plant_id == plant_id)
            .options(selectinload(Observation.assessment))
            .order_by(desc(Observation.observed_at))
            .limit(limit),
        ).all(),
    )
    measurements = latest_measurements(session, plant_id, limit=limit)
    return {
        "health": [
            {
                "at": observation.observed_at,
                "score": float(observation.overall_health_score)
                if observation.overall_health_score is not None
                else (
                    float(observation.assessment.manual_score)
                    if observation.assessment and observation.assessment.manual_score is not None
                    else float(observation.assessment.calculated_score)
                    if observation.assessment
                    and observation.assessment.calculated_score is not None
                    else None
                ),
            }
            for observation in reversed(observations)
        ],
        "measurements": [
            {
                "at": measurement.measured_at,
                "height": float(measurement.height) if measurement.height is not None else None,
                "canopy_width": float(measurement.canopy_width)
                if measurement.canopy_width is not None
                else None,
                "trunk_diameter": float(measurement.trunk_diameter)
                if measurement.trunk_diameter is not None
                else None,
                "soil_moisture": float(measurement.soil_moisture)
                if measurement.soil_moisture is not None
                else None,
            }
            for measurement in reversed(measurements)
        ],
    }
