"""Timing and RSS logging for batch runs."""

from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

from sanitycheck.models import RunProfile

logger = logging.getLogger(__name__)

try:
    import psutil

    def _rss_bytes() -> int | None:
        return int(psutil.Process().memory_info().rss)

except Exception:  # pragma: no cover - optional dependency

    def _rss_bytes() -> int | None:
        return None


T = TypeVar("T")


def log_run(label: str, fn: Callable[[], T]) -> tuple[T, RunProfile]:
    """Execute ``fn``, return its result and a RunProfile with elapsed seconds and RSS."""
    t0 = time.perf_counter()
    out = fn()
    elapsed = time.perf_counter() - t0
    rss = _rss_bytes()
    prof = RunProfile(label=label, seconds=elapsed, rss_bytes_after=rss)
    rss_mb = f"{rss / 1024 / 1024:.1f} MB" if rss is not None else "n/a"
    logger.info(
        "profile %s: %.2fs, RSS_after=%s",
        label,
        elapsed,
        rss_mb,
    )
    return out, prof
