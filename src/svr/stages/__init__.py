"""Pipeline stages (contracts section 1).

One module per stage, each with a clear input and output. Phase 1 stages
are mocks with fixed values from the contracts section 9 fixture. Phase 2
replaces each mock in place, behind the same function signature, as the
real components land (Sira audio, Lama text, Ibthal ticket generator).
"""

from __future__ import annotations
