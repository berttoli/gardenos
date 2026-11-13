from __future__ import annotations

import uuid

from app.common.ids import new_uuid_str
from app.config import Settings
from app.database import SessionFactory
from app.plants.services import create_plant, get_or_create_taxon, suggest_display_id


def test_plant_identifier_sequence_advances(
    session_factory: SessionFactory,
    settings: Settings,
) -> None:
    with session_factory() as session:
        taxon = get_or_create_taxon(
            session,
            scientific_name="Acer palmatum",
            display_code="AP",
            common_names=["Japanese maple"],
        )

        first_identifier = suggest_display_id(
            session,
            taxon=taxon,
            cultivar_name="Garnet Tower",
            sequence_width=settings.plant_identifier_sequence_width,
        )
        assert first_identifier == "AP-GT-001"

        create_plant(
            session,
            settings,
            {
                "scientific_name": "Acer palmatum",
                "cultivar_name": "Garnet Tower",
                "common_name": "Japanese maple",
                "status": "active",
                "acquisition_type": "purchased",
            },
        )

        second_identifier = suggest_display_id(
            session,
            taxon=taxon,
            cultivar_name="Garnet Tower",
            sequence_width=settings.plant_identifier_sequence_width,
        )
        assert second_identifier == "AP-GT-002"


def test_uuidv7_helper_returns_version_7() -> None:
    generated = uuid.UUID(new_uuid_str())

    assert generated.version == 7
    assert generated.variant == uuid.RFC_4122
