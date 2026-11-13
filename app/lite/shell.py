from __future__ import annotations

import argparse
import code

from app.lite.config import load_lite_settings
from app.lite.store import GardenStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open a Garden OS lite DuckDB shell.")
    parser.add_argument("--no-seed", action="store_true", help="Skip demo data bootstrap.")
    args = parser.parse_args(argv)

    settings = load_lite_settings()
    store = GardenStore(settings.database_path)
    store.initialize(seed=not args.no_seed)
    connection = store.connection()
    conn = connection.__enter__()
    try:
        banner = (
            f"Garden OS lite shell connected to {settings.database_path}.\n"
            "Variables: settings, store, conn\n"
        )
        code.interact(banner=banner, local={"settings": settings, "store": store, "conn": conn})
    finally:
        connection.__exit__(None, None, None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
