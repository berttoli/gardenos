from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.lite.admin import create_backup
from app.lite.config import load_lite_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Garden OS DuckDB backup archive.")
    parser.add_argument("--output", type=Path, default=None, help="Optional output archive path.")
    args = parser.parse_args(sys.argv[1:])
    settings = load_lite_settings()
    archive_path = create_backup(settings, args.output)
    print(archive_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
