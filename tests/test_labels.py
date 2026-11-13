from __future__ import annotations

from app.database import SessionFactory
from app.labels.services import (
    DEFAULT_LABEL_TEMPLATES,
    default_label_template,
    ensure_default_label_templates,
)


def test_default_label_templates_are_seeded(session_factory: SessionFactory) -> None:
    with session_factory() as session:
        templates = ensure_default_label_templates(session)

        assert len(templates) == len(DEFAULT_LABEL_TEMPLATES)
        assert {template.name for template in templates} == {
            spec["name"] for spec in DEFAULT_LABEL_TEMPLATES
        }
        assert default_label_template(session).name == "Compact nursery loop"
