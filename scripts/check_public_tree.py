"""Check Git's publication list without printing potentially sensitive contents."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIRECTORIES = {
    ".local-planning",
    ".openai",
    ".wrangler",
    ".venv",
    "node_modules",
    "__pycache__",
    "backups",
    "warehouse",
    "exports",
    "reports",
    "deliverables",
    "archive",
    "archives",
}
PRIVATE_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".duckdb",
    ".parquet",
    ".csv",
    ".tsv",
    ".jsonl",
    ".zip",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".log",
}
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    "cloud access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "API token": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"),
    "personal home path": re.compile(r"(?:/Users/|/home/)[A-Za-z0-9_.-]+/"),
}


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    failures: list[str] = []
    filenames = [name for name in result.stdout.decode().split("\0") if name]
    for filename in filenames:
        path = Path(filename)
        if (
            path.parts[0] in PRIVATE_DIRECTORIES
            or any(
                part in {".openai", ".wrangler", ".venv", "node_modules", "__pycache__"}
                for part in path.parts
            )
            or path.suffix in PRIVATE_SUFFIXES
            or (path.name.startswith(".env") and path.name != ".env.example")
            or path.name in {".gitmodules", "compose.override.yaml", "compose.override.yml"}
        ):
            failures.append(f"{filename}: private/generated artifact")
            continue
        # Read the index blob so an unstaged replacement cannot hide staged content.
        blob = subprocess.run(
            ["git", "show", f":{filename}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        if b"\x00" in blob:
            failures.append(f"{filename}: binary requires an explicit publication review")
            continue
        content = blob.decode("utf-8")
        for category, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                failures.append(f"{filename}: {category}")
    if failures:
        print("Public tree check failed (matched values are intentionally omitted):")
        print("\n".join(failures))
        return 1
    print(f"Public tree check passed for {len(filenames)} tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
