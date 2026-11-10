"""Task 3: split recomputation + excluded-file disposition.

Split: the train-ready set only (the EDA split covered all 6,024 rows;
quarantine removals change the pool, so the EDA split is superseded for
the training pool). Whole text_norm groups stay on one side (0 leaks),
stratified by duration quartile + format, target 80/10/10, seed 42.
Deterministic: groups sorted, shuffled with random.Random(42) per
stratum, greedy assignment to the side furthest below its target share.

Excluded files (498): disposition reasons tabulated from the inventory.
Recoverable in principle = readable audio + a reason a defined operation
could rescue (low_snr -> denoise, clipped -> declip/tolerate, too_long
-> chunk, mostly_silence -> trim silence). Permanently unusable =
duplicate (content already in the pool via the kept copy) and too_short
(no content to recover). Re-include NONE without a team decision.

Outputs (outside the repo):
  - dataset/preprocessed/split_train.json, split_dev.json, split_test.json
  - dataset/preprocessed/excluded_disposition.json

Run: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python preprocessing/split_and_exclusions.py
"""
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
PREP_DIR = Path("/home/hatch/workspace/ai-customer-support/dataset/preprocessed")
CLEAN_CSV = PREP_DIR / "transcripts_clean.csv"
MANIFEST_CSV = PREP_DIR / "disposition_manifest.csv"
INVENTORY_CSV = Path("/home/hatch/workspace/user/files/inventory_clean_13_825a.csv")

SEED = 42
TARGETS = {"train": 0.80, "dev": 0.10, "test": 0.10}

# Reasons a defined operation could rescue (denoise / declip-tolerate /
# chunk / trim-silence). Duplicates add no new content; too_short has
# no content to recover.
RECOVERABLE_REASONS = {"low_snr", "clipped", "too_long", "mostly_silence"}


def compute_split(clean_df, inventory):
    """Group-aware stratified split. Returns {side: [file, ...]} (sorted)."""
    inv = inventory.copy()
    inv["duration_s"] = inv["duration_s"].astype(float)
    dur = dict(zip(inv["file"], inv["duration_s"]))
    fmt = dict(zip(inv["file"], inv["ext"]))

    train_ready = clean_df[clean_df["prep_status"] == "train_ready"]
    total = len(train_ready)
    quartiles = train_ready["file"].map(dur).quantile([0.25, 0.5, 0.75])
    q1, q2, q3 = quartiles[0.25], quartiles[0.5], quartiles[0.75]

    def quartile(d):
        if d <= q1:
            return 0
        if d <= q2:
            return 1
        if d <= q3:
            return 2
        return 3

    # Whole text_norm groups; stratum = (duration quartile of the group's
    # median duration, modal format of the group's files).
    groups = defaultdict(list)
    for _, row in train_ready.iterrows():
        groups[row["text_norm"]].append(row["file"])
    strata = defaultdict(list)
    for norm, files in groups.items():
        ds = sorted(dur[f] for f in files)
        median_d = ds[len(ds) // 2]
        modal_fmt = Counter(fmt[f] for f in files).most_common(1)[0][0]
        strata[(quartile(median_d), modal_fmt)].append(files)

    target_counts = {s: round(TARGETS[s] * total) for s in TARGETS}
    counts = Counter()
    splits = {s: [] for s in TARGETS}
    rng = random.Random(SEED)
    for stratum in sorted(strata):
        members = sorted(strata[stratum], key=lambda fs: fs[0])
        rng.shuffle(members)
        for files in members:
            # Side furthest below its target share (by file count).
            side = min(
                TARGETS,
                key=lambda s: counts[s] / max(target_counts[s], 1),
            )
            splits[side].extend(files)
            counts[side] += len(files)
    return {s: sorted(v) for s, v in splits.items()}


def excluded_disposition(inventory):
    ex = inventory[inventory["exclude_reason"].fillna("") != ""]
    reasons = Counter(ex["exclude_reason"])
    recoverable = sum(n for r, n in reasons.items() if r in RECOVERABLE_REASONS)
    return {
        "total": int(len(ex)),
        "reasons": dict(sorted(reasons.items())),
        "recoverable": int(recoverable),
        "permanently_unusable": int(len(ex) - recoverable),
        "recoverable_reasons": sorted(RECOVERABLE_REASONS),
    }


def main():
    clean_df = pd.read_csv(CLEAN_CSV, dtype=str, encoding="utf-8")
    inventory = pd.read_csv(INVENTORY_CSV, dtype=str, encoding="utf-8-sig")

    splits = compute_split(clean_df, inventory)
    for side, files in splits.items():
        (PREP_DIR / f"split_{side}.json").write_text(
            json.dumps(files, indent=1, sort_keys=True)
        )
        print(f"split {side}: {len(files)} files")

    ex = excluded_disposition(inventory)
    (PREP_DIR / "excluded_disposition.json").write_text(
        json.dumps(ex, indent=1, sort_keys=True)
    )
    print(f"excluded: {ex['total']} {ex['reasons']}")
    print(f"recoverable: {ex['recoverable']}, "
          f"permanently unusable: {ex['permanently_unusable']}")

    # Leak check: no text_norm group spans two sides.
    norm = dict(zip(clean_df["file"], clean_df["text_norm"]))
    seen = {}
    leaked = 0
    for side, files in splits.items():
        for f in files:
            g = norm[f]
            if g in seen and seen[g] != side:
                leaked += 1
            seen[g] = side
    print(f"leaked text_norm groups: {leaked}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
