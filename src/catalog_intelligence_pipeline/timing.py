"""Lightweight timing helpers used for profiling and benchmarks."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter


class TimingTracker:
    """Collects elapsed milliseconds for named stages."""

    def __init__(self) -> None:
        self._durations: defaultdict[str, float] = defaultdict(float)

    @contextmanager
    def context(self, name: str) -> Iterator[None]:
        start = perf_counter()
        try:
            yield
        finally:
            self._durations[name] += (perf_counter() - start) * 1000

    def reset(self) -> None:
        """Clear recorded timings."""

        self._durations.clear()

    def as_dict(self) -> dict[str, float]:
        """Return a shallow copy of the durations map."""

        return dict(self._durations)

    def total_ms(self) -> float:
        """Return the total elapsed time across all stages."""

        return sum(self._durations.values())
