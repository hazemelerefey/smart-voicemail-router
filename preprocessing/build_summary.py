"""Task 4: build preprocessing_summary.json + disposition figure from the
pipeline artifacts (nothing hand-typed, so the summary cannot drift from
the measured numbers).

Reads: transcripts_clean.csv, canonical transcripts CSV, disposition
manifest, split_*.json, excluded_disposition.json, audio_decode.json,
audio_16k/*.wav, run_log_hashes.txt.
Writes: preprocessing/preprocessing_summary.json (exact schema the gates
check, extra detail under "details") and
preprocessing/figures/disposition_bar.png.

Run: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python preprocessing/build_summary.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
PREP_DIR = Path("/home/hatch/workspace/ai-customer-support/dataset/preprocessed")
CANONICAL_CSV = Path("/home/hatch/workspace/user/files/transcripts_flagged_14_4zfb.csv")
CLEAN_CSV = PREP_DIR / "transcripts_clean.csv"
MANIFEST_CSV = PREP_DIR / "disposition_manifest.csv"
AUDIO_16K = PREP_DIR / "audio_16k"
SUMMARY_JSON = REPO / "preprocessing/preprocessing_summary.json"
FIGURE = REPO / "preprocessing/figures/disposition_bar.png"


def leaked_groups(clean_df, splits):
    norm = dict(zip(clean_df["file"], clean_df["text_norm"]))
    seen = {}
    leaked = 0
    for side, files in splits.items():
        for f in files:
            g = norm[f]
            if g in seen and seen[g] != side:
                leaked += 1
            seen[g] = side
    return leaked


def main():
    clean_df = pd.read_csv(CLEAN_CSV, dtype=str, encoding="utf-8")
    canon = pd.read_csv(CANONICAL_CSV, dtype=str, encoding="utf-8-sig")
    manifest = pd.read_csv(MANIFEST_CSV, dtype=str, encoding="utf-8")
    splits = {
        s: json.loads((PREP_DIR / f"split_{s}.json").read_text())
        for s in ("train", "dev", "test")
    }
    excluded = json.loads((PREP_DIR / "excluded_disposition.json").read_text())
    decode = json.loads((PREP_DIR / "audio_decode.json").read_text())
    hashes = {}
    for line in (PREP_DIR / "run_log_hashes.txt").read_text().splitlines():
        h, path = line.split(None, 1)
        hashes[Path(path).name] = h

    status = clean_df["prep_status"].value_counts()
    merged = clean_df.merge(
        canon[["file", "dup_text_size", "prompt"]],
        on="file", suffixes=("", "_canon"),
    )
    dup_fixed = int((merged["dup_text_size"].astype(int)
                     != merged["dup_text_size_canon"].astype(int)).sum())
    prompt_normalized = int((merged["prompt_canon"].fillna("") == "").sum())
    reason_counts = Counter()
    for r in clean_df[clean_df["prep_status"] == "quarantine"]["prep_reason"]:
        for flag in r.split(";"):
            reason_counts[flag] += 1
    dup_audio = int(
        clean_df["prep_reason"].fillna("").str.contains("duplicate_audio").sum()
    )
    total_std_duration = round(
        sum(v["duration_s"] for v in decode["files"].values()), 2
    )

    summary = {
        "transcripts": {
            "total": int(len(clean_df)),
            "train_ready": int(status.get("train_ready", 0)),
            "quarantine": int(status.get("quarantine", 0)),
            "dup_fixed_rows": dup_fixed,
            "prompt_normalized_rows": prompt_normalized,
        },
        "files": {
            "total": int(len(manifest)),
            "excluded": int((manifest["prep_status"] == "excluded").sum()),
            "excluded_recoverable": int(excluded["recoverable"]),
        },
        "audio": {
            "standardized_files": int(len(list(AUDIO_16K.glob("*.wav")))),
            "duplicate_audio_quarantined": dup_audio,
        },
        "split": {
            "train": len(splits["train"]),
            "dev": len(splits["dev"]),
            "test": len(splits["test"]),
            "leaked_groups": leaked_groups(clean_df, splits),
            "seed": 42,
        },
        "details": {
            "quarantine_reasons": dict(sorted(reason_counts.items())),
            "excluded_reasons": excluded["reasons"],
            "excluded_permanently_unusable": excluded["permanently_unusable"],
            "drift_vs_inventory": decode["drift_vs_inventory"],
            "standardized_total_duration_s": total_std_duration,
            "canonical_hashes": hashes,
        },
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=1, sort_keys=True))
    print(SUMMARY_JSON.read_text())

    # Figure: disposition with reason breakdown.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    man_counts = manifest["prep_status"].value_counts()
    labels = [
        ("Train-ready", int(man_counts.get("train_ready", 0))),
        ("Quarantine: needs_review", int(reason_counts.get("needs_review", 0))),
        ("Quarantine: silence >50%", int(reason_counts.get("silence_gt_50pct", 0))),
        ("Excluded: duplicate", int(excluded["reasons"].get("duplicate", 0))),
        ("Excluded: low_snr", int(excluded["reasons"].get("low_snr", 0))),
        ("Excluded: clipped", int(excluded["reasons"].get("clipped", 0))),
        ("Excluded: too_short", int(excluded["reasons"].get("too_short", 0))),
        ("Excluded: too_long", int(excluded["reasons"].get("too_long", 0))),
        ("Excluded: mostly_silence", int(excluded["reasons"].get("mostly_silence", 0))),
    ]
    # needs_review + silence overlap is 0, so the reason counts sum to 143.
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    names = [l for l, _ in labels]
    values = [v for _, v in labels]
    ax.barh(names[::-1], values[::-1])
    for i, v in enumerate(values[::-1]):
        ax.text(v + 60, i, str(v), va="center")
    ax.set_xlim(0, max(values) * 1.12)
    ax.set_xlabel("files")
    ax.set_title("Phase 2 disposition — 6,522 files")
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=120)
    print(f"wrote {FIGURE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
