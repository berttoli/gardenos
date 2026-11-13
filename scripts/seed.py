from __future__ import annotations

import json

from app.lite.admin import seed_database
from app.lite.config import load_lite_settings


def main() -> int:
    settings = load_lite_settings()
    summary = seed_database(settings)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
