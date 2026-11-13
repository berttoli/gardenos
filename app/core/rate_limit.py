from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Lock


@dataclass(slots=True)
class LoginRateLimiter:
    max_attempts: int
    window_seconds: int
    _attempts: dict[str, deque[datetime]] = field(default_factory=dict, init=False, repr=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    @property
    def window(self) -> timedelta:
        return timedelta(seconds=self.window_seconds)

    def _prune(self, attempts: deque[datetime], now: datetime) -> None:
        cutoff = now - self.window
        while attempts and attempts[0] < cutoff:
            attempts.popleft()

    def _get_attempts(self, key: str) -> deque[datetime]:
        attempts = self._attempts.get(key)
        if attempts is None:
            attempts = deque()
            self._attempts[key] = attempts
        return attempts

    def is_limited(self, key: str, now: datetime | None = None) -> tuple[bool, int]:
        timestamp = now or datetime.now(UTC)
        with self._lock:
            attempts = self._attempts.get(key)
            if attempts is None:
                return False, 0
            self._prune(attempts, timestamp)
            if len(attempts) < self.max_attempts:
                return False, 0
            retry_after = int((attempts[0] + self.window - timestamp).total_seconds())
            return True, max(retry_after, 1)

    def record_failure(self, key: str, now: datetime | None = None) -> None:
        timestamp = now or datetime.now(UTC)
        with self._lock:
            attempts = self._get_attempts(key)
            self._prune(attempts, timestamp)
            attempts.append(timestamp)

    def clear(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)
