from __future__ import annotations

import pytest

from app.config import Settings
from app.database import SessionFactory
from app.plants.services import (
    PlantError,
    create_plant,
    get_or_create_taxon,
    update_plant,
)


def test_prevent_lineage_cycles(
    session_factory: SessionFactory,
    settings: Settings,
) -> None:
    with session_factory() as session:
        get_or_create_taxon(
            session,
            scientific_name="Acer palmatum",
            display_code="AP",
            common_names=["Japanese maple"],
        )
        parent = create_plant(
            session,
            settings,
            {
                "scientific_name": "Acer palmatum",
                "cultivar_name": "Mother Tree",
                "common_name": "Japanese maple",
                "status": "active",
                "acquisition_type": "purchased",
            },
        )
        child = create_plant(
            session,
            settings,
            {
                "scientific_name": "Acer palmatum",
                "cultivar_name": "Mother Tree",
                "common_name": "Japanese maple",
                "status": "active",
                "acquisition_type": "cutting",
                "parent_plant_id": parent.id,
            },
        )

        with pytest.raises(PlantError, match="lineage cycle"):
            update_plant(session, parent, {"parent_plant_id": child.id}, settings)
