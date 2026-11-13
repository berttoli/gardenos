from __future__ import annotations

import re
from pathlib import Path


def test_compose_and_browser_ci_use_the_same_pinned_database_image() -> None:
    root = Path(__file__).resolve().parents[1]
    image_pattern = re.compile(r"image:\s+(postgres:\S+)")
    compose = image_pattern.search((root / "compose.yaml").read_text())
    workflow = image_pattern.search((root / ".github/workflows/test.yml").read_text())
    assert compose is not None and workflow is not None
    assert compose.group(1) == workflow.group(1), "Update the deployment and CI image together."
    assert re.fullmatch(
        r"postgres:16\.\d+-alpine\d+\.\d+@sha256:[a-f0-9]{64}", compose.group(1)
    ), "Keep the supported PostgreSQL major, exact patch/base tag, and image-index digest."
