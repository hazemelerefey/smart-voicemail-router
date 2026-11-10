"""Task 1: transcript cleaning — DERIVED file only.

Reads the canonical transcripts + inventory CSVs (never writes to them),
recomputes dup_text_size from text_norm group sizes, normalizes empty
prompt to "none", assigns prep_status/prep_reason, and writes:
  - dataset/preprocessed/transcripts_clean.csv (10 locked columns + prep_*)
  - dataset/preprocessed/disposition_manifest.csv (all 6522 files)

Quarantine (blocking): needs_review, silence_pct > 50, snr_db < 10.
Clipping (clip_pct > 0) is a NON-blocking flag recorded in prep_reason.
Excluded files (498, not in the transcripts CSV) stay excluded with their
inventory exclude_reason recorded in the manifest.

Deterministic: same snapshot + same code => byte-identical outputs.
Run: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python preprocessing/clean_transcripts.py
"""
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
PREP_DIR = Path("/home/hatch/workspace/ai-customer-support/dataset/preprocessed")
CANONICAL_CSV = Path("/home/hatch/workspace/user/files/transcripts_flagged_14_4zfb.csv")
INVENTORY_CSV = Path("/home/hatch/workspace/user/files/inventory_clean_13_825a.csv")
CLEAN_CSV = PREP_DIR / "transcripts_clean.csv"
MANIFEST_CSV = PREP_DIR / "disposition_manifest.csv"

LOCKED_COLUMNS = [
    "file", "text", "model", "max_no_speech_prob", "min_avg_logprob",
    "prompt", "error", "text_norm", "review_reasons", "needs_review",
    "dup_text_size",
]

# Fixed order for prep_reason flags (deterministic output).
REASON_ORDER = ["needs_review", "silence_gt_50pct", "snr_lt_10db", "clipping"]


def load_inputs():
    transcripts = pd.read_csv(CANONICAL_CSV, dtype=str, encoding="utf-8-sig")
    inventory = pd.read_csv(INVENTORY_CSV, dtype=str, encoding="utf-8-sig")
    return transcripts, inventory


def clean(transcripts, inventory):
    df = transcripts.copy()
    # Recompute dup_text_size from text_norm group sizes (fixes the 3 wrong rows).
    df["dup_text_size"] = df["text_norm"].map(df["text_norm"].value_counts()).astype(int)
    # Normalize empty prompt to "none".
    df["prompt"] = df["prompt"].fillna("")
    df.loc[df["prompt"] == "", "prompt"] = "none"

    # Acoustic measures from the inventory, taken as given (EDA §10).
    inv = inventory.copy()
    inv["silence_pct"] = inv["silence_pct"].astype(float)
    inv["snr_db"] = inv["snr_db"].astype(float)
    inv["clip_pct"] = inv["clip_pct"].astype(float)
    inv["needs_review_flag"] = False
    df = df.merge(
        inv[["file", "silence_pct", "snr_db", "clip_pct"]], on="file", how="left"
    )
    if df[["silence_pct", "snr_db", "clip_pct"]].isna().any().any():
        missing = df[df["silence_pct"].isna()]["file"].tolist()
        raise ValueError(f"transcript rows missing inventory measures: {missing}")

    needs_review = df["needs_review"].str.strip().str.lower() == "true"
    silence = df["silence_pct"] > 50
    low_snr = df["snr_db"] < 10
    clipping = df["clip_pct"] > 0

    df["prep_status"] = "train_ready"
    df.loc[needs_review | silence | low_snr, "prep_status"] = "quarantine"

    def reasons(row):
        flags = []
        if row["_needs_review"]:
            flags.append("needs_review")
        if row["_silence"]:
            flags.append("silence_gt_50pct")
        if row["_low_snr"]:
            flags.append("snr_lt_10db")
        if row["_clipping"]:
            flags.append("clipping")
        return ";".join(flags)

    df["_needs_review"] = needs_review
    df["_silence"] = silence
    df["_low_snr"] = low_snr
    df["_clipping"] = clipping
    df["prep_reason"] = df.apply(reasons, axis=1)
    df = df.drop(columns=["_needs_review", "_silence", "_low_snr", "_clipping",
                          "silence_pct", "snr_db", "clip_pct"])
    return df[LOCKED_COLUMNS + ["prep_status", "prep_reason"]]


def build_manifest(clean_df, inventory):
    """All 6522 files: transcript rows carry their disposition, the 498
    excluded files carry prep_status=excluded + their inventory reason."""
    status = clean_df.set_index("file")["prep_status"]
    reason = clean_df.set_index("file")["prep_reason"]
    rows = []
    for _, inv_row in inventory.iterrows():
        f = inv_row["file"]
        if f in status.index:
            rows.append({"file": f, "prep_status": status[f], "prep_reason": reason[f]})
        else:
            rows.append({
                "file": f,
                "prep_status": "excluded",
                "prep_reason": inv_row["exclude_reason"] or "excluded_no_reason",
            })
    return pd.DataFrame(rows, columns=["file", "prep_status", "prep_reason"])


def main():
    transcripts, inventory = load_inputs()
    clean_df = clean(transcripts, inventory)
    manifest = build_manifest(clean_df, inventory)

    PREP_DIR.mkdir(parents=True, exist_ok=True)
    clean_df.to_csv(CLEAN_CSV, index=False, encoding="utf-8", lineterminator="\n")
    manifest.to_csv(MANIFEST_CSV, index=False, encoding="utf-8", lineterminator="\n")

    print(f"transcripts: {len(clean_df)} rows")
    print("prep_status counts:")
    print(clean_df["prep_status"].value_counts().to_string())
    print("prep_reason counts (transcript rows):")
    print(clean_df["prep_reason"].value_counts().to_string())
    print("manifest rows:", len(manifest))
    print("manifest prep_status counts:")
    print(manifest["prep_status"].value_counts().to_string())
    print(f"wrote {CLEAN_CSV}")
    print(f"wrote {MANIFEST_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
