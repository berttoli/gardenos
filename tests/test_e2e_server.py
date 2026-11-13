from __future__ import annotations

import pytest

from scripts.e2e_server import validate_postgres_url


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://fixture:fixture@production.example/gardenos_e2e_test",
        "postgresql://fixture:fixture@127.0.0.1/garden",
        "postgresql://fixture:fixture@127.0.0.1/gardenos_e2e_test?host=production.example",
        "postgresql://fixture:fixture@127.0.0.1/gardenos_e2e_test?database=garden",
        "postgresql:///gardenos_e2e_test",
        "sqlite:///gardenos_e2e_test",
    ],
)
def test_browser_runner_rejects_nonisolated_database_targets(database_url: str) -> None:
    with pytest.raises(ValueError, match="must target an empty PostgreSQL database"):
        validate_postgres_url(database_url)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_browser_runner_accepts_only_dedicated_local_postgres_database(host: str) -> None:
    url = validate_postgres_url(f"postgresql://fixture:fixture@{host}:5432/gardenos_e2e_test")
    assert url.drivername == "postgresql+pg8000"
    assert url.database == "gardenos_e2e_test"
    assert url.host == host
