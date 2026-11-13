from __future__ import annotations

import re

STOPWORDS = {"and", "the", "of", "a", "an", "for", "in", "on", "at", "to"}


def compact_code(value: str | None, *, fallback: str = "UNK", max_length: int = 3) -> str:
    if value is None:
        return fallback
    words = [token for token in re.split(r"[^A-Za-z0-9]+", value.strip()) if token]
    if not words:
        return fallback
    letters = [word[0] for word in words if word.casefold() not in STOPWORDS]
    if len(letters) >= 2:
        return "".join(letters)[:max_length].upper()
    cleaned = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    if len(cleaned) >= max_length:
        return cleaned[:max_length]
    return cleaned or fallback
