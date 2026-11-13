from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_load_from_mapping() -> None:
    settings = Settings.from_mapping(
        {
            "APP_NAME": "Garden OS",
            "ENVIRONMENT": "development",
            "SECRET_KEY": "a-very-long-test-secret-key-123456",
            "DATABASE_URL": "postgresql+pg8000://garden:garden@localhost:5432/garden",
            "ADMIN_USERNAME": "root",
            "ADMIN_PASSWORD": "strong-password",
            "ADMIN_FULL_NAME": "Root Admin",
            "SESSION_COOKIE_SECURE": "true",
            "TRUSTED_HOSTS": "localhost,127.0.0.1,[::1],app,frontend,*.example.test",
            "LOGIN_RATE_LIMIT_ATTEMPTS": "7",
        },
    )

    assert settings.app_name == "Garden OS"
    assert settings.environment == "development"
    assert settings.secret_key == "a-very-long-test-secret-key-123456"
    assert settings.database_url.startswith("postgresql+pg8000://")
    assert settings.admin_username == "root"
    assert settings.session_https_only is True
    assert settings.trusted_hosts == (
        "localhost",
        "127.0.0.1",
        "[::1]",
        "app",
        "frontend",
        "*.example.test",
    )
    assert settings.login_rate_limit_attempts == 7
    assert settings.warehouse_db_path == "warehouse/garden-os-warehouse.duckdb"


@pytest.mark.parametrize("missing", ["SECRET_KEY", "ADMIN_PASSWORD", "DATABASE_URL"])
def test_settings_require_explicit_credentials_and_database(missing: str) -> None:
    values = {
        "SECRET_KEY": "synthetic-test-secret-key-not-for-runtime",
        "ADMIN_PASSWORD": "synthetic-test-password-not-for-runtime",
        "DATABASE_URL": "postgresql+pg8000://test:test@localhost/test",
    }
    values.pop(missing)

    with pytest.raises(ValidationError):
        Settings.from_mapping(values)


def test_empty_environment_cannot_start_with_shared_credentials() -> None:
    with pytest.raises(ValidationError):
        Settings.from_mapping({})


def test_validation_errors_do_not_echo_credentials() -> None:
    values = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": "synthetic-test-secret-key-not-for-runtime",
        "ADMIN_PASSWORD": "synthetic-test-password-not-for-runtime",
        "DATABASE_URL": "sqlite:///synthetic-test.db",
    }
    with pytest.raises(ValidationError) as error:
        Settings.from_mapping(values)

    assert values["SECRET_KEY"] not in str(error.value)
    assert values["ADMIN_PASSWORD"] not in str(error.value)
