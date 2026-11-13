from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.lite.admin import restore_backup
from app.lite.config import load_lite_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a Garden OS DuckDB backup archive.")
    parser.add_argument("backup", type=Path, help="Path to the backup archive.")
    args = parser.parse_args(sys.argv[1:])
    settings = load_lite_settings()
    manifest = restore_backup(settings, args.backup)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
