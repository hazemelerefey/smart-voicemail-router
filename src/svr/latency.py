"""Latency measurement (contracts section 7).

Target: p95 under 10 seconds for clips up to 60 seconds. Every ticket
carries ``stage_timing_ms`` and ``processing_ms``. The slowest stage is
named in the report, never hidden in an average. Hardware is recorded
with every report.

``processing_ms`` covers the pipeline run only: upload transfer time,
intake measurement time, and queue time are excluded, so the report
understates the end-to-end time a client experiences. That is a known
limitation of the Phase 1 measurement, not a bug in the report.
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
    if pct < 0 or pct > 100:
        raise ValueError(f"percentile must be between 0 and 100, got {pct}")
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
        self.stage_timings: dict[str, float] = {}

    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 2)

    @contextmanager
    def stage(self, name: str) -> Iterator[Callable[[], float]]:
        """Time one stage; yields a callable returning its elapsed ms.

        The value freezes when the ``with`` block exits, so calling the
        callable later never inflates the stage time with later work. The
        frozen value is also recorded on ``stage_timings`` under the
        stage name.
        """
        start = time.perf_counter()
        frozen: dict[str, float] = {}

        def _elapsed() -> float:
            if "value" in frozen:
                return frozen["value"]
            return round((time.perf_counter() - start) * 1000, 2)

        yield _elapsed
        frozen["value"] = round((time.perf_counter() - start) * 1000, 2)
        self.stage_timings[name] = frozen["value"]


def hardware_report() -> dict:
    """Hardware / runtime record, attached to every latency report.

    ``cpu_count`` and ``memory_total_mb`` are null when the platform does
    not expose them (rare on the demo hosts); a null there means
    "unknown", not zero.
    """
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
    """p95 report over a set of runs: total p95, per-stage p95, slowest stage.

    ``within_target`` is null when there are no runs: a report with no
    data is not a target breach.
    """
    if len(processing_ms_values) != len(stage_timings):
        raise ValueError(
            "processing_ms_values and stage_timings must have the same "
            f"length (got {len(processing_ms_values)} and "
            f"{len(stage_timings)})"
        )
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
        "within_target": None if total_p95 is None else total_p95 < target_ms,
        "stage_p95_ms": stage_p95,
        "slowest_stage": slowest,
        "hardware": hardware_report(),
    }
