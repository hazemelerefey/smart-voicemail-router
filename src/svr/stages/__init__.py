"""Pipeline stages (contracts section 1).

One module per stage, each with a clear input and output. Phase 1 inference
stages use fixed values from the contracts section 9 fixture; triage applies
Ibthal's explainable routing logic to the fictional seeded demo agents. Phase 2
replaces mock inference in place, behind the same function signatures, as the
real components land (Sira audio and Lama text).
"""

from __future__ import annotations
