from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.lite.admin import verify_backup


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Garden OS DuckDB backup archive.")
    parser.add_argument("backup", type=Path, help="Path to the backup archive.")
    args = parser.parse_args(sys.argv[1:])
    manifest = verify_backup(args.backup)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
