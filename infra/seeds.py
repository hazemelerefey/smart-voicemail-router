"""Seed handling and aggregation across seeds.

- set_global_seed(seed): seeds Python, NumPy, and PyTorch if it is installed.
- run_over_seeds(fn, seeds): runs fn(seed) once per seed, in order.
- summarize(values, ddof): mean and std over seeds. The ddof used is stored in
  the result, so every reported std says which formula produced it.
- summarize_metrics(per_seed_metrics, ddof): the same, for a dict of metrics.

The seeds themselves come from shared_config.json (see shared_config.py).
This module does not hard-code them.
"""
import math
import random
import sys

import numpy as np


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _check_seed(seed):
    if not _is_int(seed) or seed < 0:
        raise ValueError(f"seed must be a non-negative integer, got {seed!r}")


def set_global_seed(seed):
    """Seed Python, NumPy and (if installed) PyTorch.

    This does not replace passing random_state=seed to scikit-learn objects.
    Code that accepts a seed argument should still receive it explicitly.
    """
    _check_seed(seed)
    random.seed(seed)
    np.random.seed(seed)
    # PyTorch is optional here: this project's infra must work without it.
    torch = sys.modules.get("torch")
    if torch is None:
        try:
                        import torch  # pyright: ignore[reportMissingImports]
        except ImportError:
            torch = None
    if torch is not None:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)


def run_over_seeds(fn, seeds):
    """Call fn(seed) once per seed, in the given order.

    The global seed is set before each call. Returns a list of
    {"seed": seed, "result": fn(seed)} records.
    """
    seeds = list(seeds)
    if not seeds:
        raise ValueError("seeds must not be empty")
    for s in seeds:
        _check_seed(s)
    if len(set(seeds)) != len(seeds):
        raise ValueError(f"seeds has duplicates: {seeds}")
    records = []
    for s in seeds:
        set_global_seed(s)
        records.append({"seed": s, "result": fn(s)})
    return records


def summarize(values, ddof=1):
    """Mean and std of values across seeds. ddof is recorded in the result."""
    if ddof not in (0, 1):
        raise ValueError(f"ddof must be 0 or 1, got {ddof!r}")
    values = list(values)
    for v in values:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError(f"values must be finite numbers, got {v!r}")
    if len(values) <= ddof:
        raise ValueError(f"need more than {ddof} value(s) to compute std with ddof={ddof}")
    return {
        "mean": float(np.mean(values)),
        "std": float(np.std(values, ddof=ddof)),
        "ddof": ddof,
        "n": len(values),
    }


def summarize_metrics(per_seed_metrics, ddof=1):
    """per_seed_metrics: one {metric_name: value} dict per seed.

    Returns {metric_name: summarize(...)}. Every seed must report exactly the
    same metric names.
    """
    per_seed_metrics = list(per_seed_metrics)
    if not per_seed_metrics:
        raise ValueError("per_seed_metrics must not be empty")
    names = set(per_seed_metrics[0])
    for m in per_seed_metrics:
        if set(m) != names:
            raise ValueError(
                f"seeds report different metrics: {sorted(names)} vs {sorted(m)}"
            )
    return {n: summarize([m[n] for m in per_seed_metrics], ddof=ddof) for n in sorted(names)}