from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.warehouse.export import export_warehouse_snapshot
from scripts.common import runtime


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the Garden OS warehouse snapshot to DuckDB.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output DuckDB path. Defaults to WAREHOUSE_DB_PATH.",
    )
    args = parser.parse_args(sys.argv[1:])

    settings, engine, session_factory = runtime()
    try:
        output_path = args.output or Path(settings.warehouse_db_path)
        snapshot_path = export_warehouse_snapshot(session_factory, output_path, settings=settings)
        print(snapshot_path)
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
