from __future__ import annotations

from app.main import create_app


def test_openapi_metadata_uses_v1() -> None:
    app = create_app()

    schema = app.openapi()

    assert schema["info"]["version"] == "v1"
    assert schema["info"]["title"] == "Garden OS"
    assert "auth" in {tag["name"] for tag in schema["tags"]}
    assert "platform" in {tag["name"] for tag in schema["tags"]}
