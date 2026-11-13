from __future__ import annotations

import subprocess
import sys

from app.config import Settings
from app.startup import run_database_migrations


def test_run_database_migrations_invokes_alembic(monkeypatch) -> None:
    calls: list[list[str]] = []
    seen_env: dict[str, str] = {}

    def fake_run(
        cmd: list[str],
        *,
        check: bool,
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        seen_env.update(env)
        assert check is True
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setenv("DATABASE_URL", "postgresql+pg8000://example")
    monkeypatch.delenv("GARDENOS_SKIP_STARTUP_MIGRATIONS", raising=False)
    monkeypatch.setattr(subprocess, "run", fake_run)

    run_database_migrations(
        Settings.from_mapping(
            {
                "DATABASE_URL": "postgresql+pg8000://garden:garden@postgres:5432/garden",
                "SECRET_KEY": "synthetic-test-secret-key-not-for-runtime",
                "ADMIN_PASSWORD": "synthetic-test-password-not-for-runtime",
            },
        ),
    )

    assert calls == [[sys.executable, "-m", "alembic", "upgrade", "head"]]
    assert seen_env["DATABASE_URL"] == "postgresql+pg8000://garden:garden@postgres:5432/garden"
