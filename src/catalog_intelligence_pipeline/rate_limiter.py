"""Simple in-memory token bucket rate limiter."""

from __future__ import annotations

from threading import Lock
from time import monotonic


class TokenBucket:
    """Token bucket limiter that refills continuously."""

    def __init__(self, rate_per_minute: int) -> None:
        if rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be > 0")
        self._capacity = rate_per_minute
        self._tokens = float(rate_per_minute)
        self._refill_per_second = rate_per_minute / 60.0
        self._updated_at = monotonic()
        self._lock = Lock()

    def consume(self, amount: int = 1) -> bool:
        """Attempt to consume tokens; returns True when allowed."""

        if amount <= 0:
            return True

        with self._lock:
            now = monotonic()
            elapsed = now - self._updated_at
            self._updated_at = now
            self._tokens = min(
                self._capacity,
                self._tokens + elapsed * self._refill_per_second,
            )
            if self._tokens >= amount:
                self._tokens -= amount
                return True
            return False

    def reset(self) -> None:
        """Restore the bucket to its full capacity."""

        with self._lock:
            self._tokens = float(self._capacity)
            self._updated_at = monotonic()
