"""Latency measurement (contracts section 7).

Target: p95 under 10 seconds for clips up to 60 seconds. Every ticket
carries ``stage_timing_ms`` and ``processing_ms``. If latency is over
target, the slowest stage is reported to its owner, never hidden in an
average. Hardware is recorded with every report.
"""

from __future__ import annotations

import math
import os
import platform
import sys
import time
from contextlib import contextmanager
from typing import Callable, Iterator


def percentile(values: list[float], pct: float = 95.0) -> float | None:
    """Nearest-rank percentile. Returns None for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def p95(values: list[float]) -> float | None:
    """95th percentile (nearest-rank)."""
    return percentile(values, 95.0)


class Timer:
    """Wall-clock timer for one pipeline run, per-stage and total."""

    def __init__(self) -> None:
        self._start = time.perf_counter()

    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 2)

    @contextmanager
    def stage(self, _name: str) -> Iterator[Callable[[], float]]:
        """Time one stage; yields a callable returning its elapsed ms."""
        start = time.perf_counter()
        yield lambda: round((time.perf_counter() - start) * 1000, 2)


def hardware_report() -> dict:
    """Hardware / runtime record, attached to every latency report."""
    try:
        mem_total_mb = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 / 1024)
    except (ValueError, OSError, AttributeError):
        mem_total_mb = None
    return {
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count(),
        "memory_total_mb": mem_total_mb,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }


def summarize_latency(
    processing_ms_values: list[float],
    stage_timings: list[dict[str, float]],
    target_ms: float = 10_000.0,
) -> dict:
    """p95 report over a set of runs: total p95, per-stage p95, slowest stage."""
    per_stage: dict[str, list[float]] = {}
    for timings in stage_timings:
        for stage, value in timings.items():
            per_stage.setdefault(stage, []).append(value)
    stage_p95 = {stage: p95(values) for stage, values in per_stage.items()}
    slowest = max(stage_p95, key=lambda s: stage_p95[s] or 0) if stage_p95 else None
    total_p95 = p95(processing_ms_values)
    return {
        "runs": len(processing_ms_values),
        "p95_processing_ms": total_p95,
        "target_ms": target_ms,
        "within_target": total_p95 is not None and total_p95 < target_ms,
        "stage_p95_ms": stage_p95,
        "slowest_stage": slowest,
        "hardware": hardware_report(),
    }
