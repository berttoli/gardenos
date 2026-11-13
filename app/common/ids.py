from __future__ import annotations

import secrets
import time
import uuid


def generate_standard_uuidv7() -> uuid.UUID:
    """Generate a UUIDv7, using stdlib support when available."""
    uuid7 = getattr(uuid, "uuid7", None)
    if callable(uuid7):
        return uuid7()

    now_ms = int(time.time() * 1000)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    uuid_int = (now_ms << 80) | (7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return uuid.UUID(int=uuid_int)


def new_uuid() -> uuid.UUID:
    return generate_standard_uuidv7()


def new_uuid_str() -> str:
    return str(new_uuid())
