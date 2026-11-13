from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.labels.models import LabelTemplate
from app.labels.pdf import label_pdf_bytes
from app.labels.qr import qr_svg
from app.plants.models import Plant

DEFAULT_LABEL_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "name": "Compact nursery loop",
        "width_mm": 50.0,
        "height_mm": 25.0,
        "template_type": "loop",
        "layout_definition": {"kind": "compact", "qr_ratio": 0.55},
        "is_default": True,
    },
    {
        "name": "Pot stake",
        "width_mm": 70.0,
        "height_mm": 120.0,
        "template_type": "stake",
        "layout_definition": {"kind": "vertical", "qr_ratio": 0.35},
        "is_default": False,
    },
    {
        "name": "Letter sheet",
        "width_mm": 215.9,
        "height_mm": 279.4,
        "template_type": "sheet",
        "layout_definition": {"kind": "sheet", "qr_ratio": 0.32, "columns": 2, "rows": 4},
        "is_default": False,
    },
    {
        "name": "Calibration sheet",
        "width_mm": 215.9,
        "height_mm": 279.4,
        "template_type": "calibration",
        "layout_definition": {"kind": "calibration"},
        "is_default": False,
    },
)


class LabelError(ValueError):
    pass


def ensure_default_label_templates(session: Session) -> list[LabelTemplate]:
    existing = session.scalar(select(LabelTemplate).limit(1))
    if existing is not None:
        return list(session.scalars(select(LabelTemplate)).all())

    templates: list[LabelTemplate] = []
    for spec in DEFAULT_LABEL_TEMPLATES:
        template = LabelTemplate(**spec)
        templates.append(template)
        session.add(template)
    session.flush()
    return templates


def default_label_template(session: Session) -> LabelTemplate:
    template = session.scalar(select(LabelTemplate).where(LabelTemplate.is_default.is_(True)))
    if template is None:
        templates = ensure_default_label_templates(session)
        for candidate in templates:
            if candidate.is_default:
                return candidate
        if not templates:
            raise LabelError("No label templates available.")
        return templates[0]
    return template


def label_title_lines(plant: Plant) -> list[str]:
    lines = [plant.taxon.scientific_name if plant.taxon else "Unclassified plant"]
    cultivar = plant.cultivar_name or (plant.taxon.cultivar if plant.taxon else None)
    if cultivar:
        lines.append(f"'{cultivar}'")
    return lines


def label_subtitle_lines(plant: Plant) -> list[str]:
    lines: list[str] = [plant.display_id]
    if plant.common_name:
        lines.append(plant.common_name)
    if plant.accession_date:
        lines.append(f"Acquired {plant.accession_date:%Y-%m}")
    return lines


def label_public_url(plant: Plant) -> str:
    return f"/p/{plant.display_id}"


def label_preview_data(plant: Plant, template: LabelTemplate) -> dict[str, Any]:
    return {
        "plant": plant,
        "template": template,
        "title_lines": label_title_lines(plant),
        "subtitle_lines": label_subtitle_lines(plant),
        "public_url": label_public_url(plant),
        "qr_svg": qr_svg(label_public_url(plant)),
    }


def label_pdf_data(plant: Plant, template: LabelTemplate) -> bytes:
    return label_pdf_bytes(
        title_lines=label_title_lines(plant),
        subtitle_lines=label_subtitle_lines(plant),
        display_id=plant.display_id,
        target_url=label_public_url(plant),
        width_mm=template.width_mm,
        height_mm=template.height_mm,
        template_type=template.template_type,
    )


def calibration_pdf_data(template: LabelTemplate) -> bytes:
    return label_pdf_bytes(
        title_lines=["Calibration page"],
        subtitle_lines=["Use this sheet to verify printed dimensions."],
        display_id="CALIBRATION",
        target_url="about:blank",
        width_mm=template.width_mm,
        height_mm=template.height_mm,
        template_type="calibration",
    )
