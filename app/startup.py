from __future__ import annotations

import os
import subprocess
import sys

from app.config import Settings


def run_database_migrations(settings: Settings) -> None:
    if settings.environment == "test":
        return
    if os.environ.get("GARDENOS_SKIP_STARTUP_MIGRATIONS") == "1":
        return

    env = os.environ.copy()
    env["DATABASE_URL"] = settings.database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env=env,
    )
