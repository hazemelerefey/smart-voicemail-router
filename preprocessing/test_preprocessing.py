"""Tests for the Phase 2 preprocessing pipeline (Hazem & Ebtihal pair).

TDD: every test was written before its implementation and watched fail.
Paths point outside the repo: derived data is never committed.
"""
import json
import re
import subprocess
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
PREP_DIR = Path("/home/hatch/workspace/ai-customer-support/dataset/preprocessed")
CLEAN_CSV = PREP_DIR / "transcripts_clean.csv"
MANIFEST_CSV = PREP_DIR / "disposition_manifest.csv"
CANONICAL_CSV = Path("/home/hatch/workspace/user/files/transcripts_flagged_14_4zfb.csv")
INVENTORY_CSV = Path("/home/hatch/workspace/user/files/inventory_clean_13_825a.csv")
AUDIO_16K = PREP_DIR / "audio_16k"
HASH_LOG = PREP_DIR / "run_log_hashes.txt"
SUMMARY_JSON = REPO / "preprocessing/preprocessing_summary.json"
NOTE = REPO / "preprocessing/preprocessing_audio_speech.md"

# The 3 files whose canonical dup_text_size is wrong (stored 1, actual 3).
# File IDs only; no transcript text.
DUP_DEFECT_FILES = [
    "svr-voicemail-corpus\\1015.m4a",
    "svr-voicemail-corpus\\WhatsApp Audio 2025-11-30 at 11.54.59 PM (1).mp4",
    "svr-voicemail-corpus\\AUDIO-2025-11-27-17-01-39.m4a",
]

def read_clean_csv():
    df = pd.read_csv(CLEAN_CSV, dtype=str, encoding="utf-8")
    df["dup_text_size"] = df["dup_text_size"].astype(int)
    df["needs_review"] = df["needs_review"].str.strip().str.lower() == "true"
    return df


def read_manifest():
    return pd.read_csv(MANIFEST_CSV, dtype=str, encoding="utf-8")


def read_canonical_csv():
    df = pd.read_csv(CANONICAL_CSV, dtype=str, encoding="utf-8-sig")
    df["dup_text_size"] = df["dup_text_size"].astype(int)
    return df


# ---------------- Task 1: transcript cleaning ----------------

def test_clean_row_count():
    df = read_clean_csv()
    assert len(df) == 6024


def test_clean_columns_locked_plus_prep():
    # Anchored to the canonical file's columns, not a hand-maintained
    # list: the derived file must carry all 11 canonical columns (the
    # 10 locked v1 columns + prompt, which the canonical CSV retains)
    # plus exactly the two preprocessing-only columns.
    canon = pd.read_csv(CANONICAL_CSV, dtype=str, encoding="utf-8-sig", nrows=0)
    df = pd.read_csv(CLEAN_CSV, dtype=str, encoding="utf-8", nrows=0)
    assert list(df.columns) == list(canon.columns) + ["prep_status", "prep_reason"]


def test_dup_recomputed():
    df = read_clean_csv()
    expected = df["text_norm"].map(df["text_norm"].value_counts())
    assert (df["dup_text_size"] == expected).all()
    # Exactly the 3 known defect rows changed vs canonical.
    canon = read_canonical_csv()
    merged = df.merge(
        canon[["file", "dup_text_size"]], on="file", suffixes=("", "_canon")
    )
    changed = merged[merged["dup_text_size"] != merged["dup_text_size_canon"]]
    assert len(changed) == 3
    assert set(changed["file"]) == set(DUP_DEFECT_FILES)
    assert (df[df["file"].isin(DUP_DEFECT_FILES)]["dup_text_size"] == 3).all()


def test_prompt_normalized():
    df = read_clean_csv()
    assert (df["prompt"].fillna("") == "").sum() == 0
    assert (df["prompt"] == "none").sum() == 6024


def test_disposition_reconciles():
    df = read_clean_csv()
    assert df["prep_status"].value_counts().sum() == 6024
    assert set(df["prep_status"]) <= {"train_ready", "quarantine"}


def test_flagged_all_quarantined():
    df = read_clean_csv()
    assert ((df["needs_review"]) & (df["prep_status"] != "quarantine")).sum() == 0


def test_acoustic_quarantine():
    df = read_clean_csv()
    inv = pd.read_csv(INVENTORY_CSV, dtype=str, encoding="utf-8-sig")
    inv["silence_pct"] = inv["silence_pct"].astype(float)
    inv["snr_db"] = inv["snr_db"].astype(float)
    m = df.merge(inv[["file", "silence_pct", "snr_db"]], on="file", how="left")
    assert ((m["silence_pct"] > 50) & (m["prep_status"] != "quarantine")).sum() == 0
    assert ((m["snr_db"] < 10) & (m["prep_status"] != "quarantine")).sum() == 0
    assert ((m["prep_status"] == "train_ready") & (m["silence_pct"] > 50)).sum() == 0
    assert ((m["prep_status"] == "train_ready") & (m["snr_db"] < 10)).sum() == 0


def test_clipping_is_nonblocking_flag():
    df = read_clean_csv()
    inv = pd.read_csv(INVENTORY_CSV, dtype=str, encoding="utf-8-sig")
    inv["clip_pct"] = inv["clip_pct"].astype(float)
    inv["silence_pct"] = inv["silence_pct"].astype(float)
    inv["snr_db"] = inv["snr_db"].astype(float)
    m = df.merge(
        inv[["file", "clip_pct", "silence_pct", "snr_db"]], on="file", how="left"
    )
    clipped_only = (
        (m["clip_pct"] > 0)
        & (~m["needs_review"])
        & (m["silence_pct"] <= 50)
        & (m["snr_db"] >= 10)
    )
    assert clipped_only.sum() > 0
    assert (m[clipped_only]["prep_status"] == "train_ready").all()
    assert m[clipped_only]["prep_reason"].str.contains("clipping").all()


def test_manifest_reconciles():
    man = read_manifest()
    assert len(man) == 6522
    counts = man["prep_status"].value_counts()
    assert counts.sum() == 6522
    assert (counts.get("excluded", 0)) == 498
    assert counts.get("train_ready", 0) + counts.get("quarantine", 0) == 6024


# ---------------- Task 2: audio standardization + dedup ----------------

def test_all_train_ready_sources_exist():
    # Regression: 3 files ("Café Suprême" *) are NFC in the CSVs but NFD
    # on disk (unrar output); source_path must resolve them.
    import sys

    sys.path.insert(0, str(REPO / "preprocessing"))
    from standardize_audio import source_path

    manifest = read_manifest()
    files = manifest[manifest["prep_status"] == "train_ready"]["file"].tolist()
    missing = [f for f in files if not source_path(f).exists()]
    assert missing == []


def wav_source_file(wav_path):
    """WAV name is '<basename>.wav'; map back to the dataset file path."""
    basename = wav_path.name[: -len(".wav")]
    return "svr-voicemail-corpus\\" + basename


def wav_pcm_sha256(wav_path):
    import hashlib
    import wave

    with wave.open(str(wav_path), "rb") as w:
        return hashlib.sha256(w.readframes(w.getnframes())).hexdigest()


def test_standardized_count_matches_train_ready():
    manifest = read_manifest()
    wavs = list(AUDIO_16K.glob("*.wav"))
    assert len(wavs) == (manifest["prep_status"] == "train_ready").sum()


def test_all_wavs_16k_mono():
    import wave

    wavs = list(AUDIO_16K.glob("*.wav"))
    assert len(wavs) > 0  # guard against a vacuous pass on an empty dir
    bad = []
    for w in wavs:
        with wave.open(str(w), "rb") as f:
            if f.getframerate() != 16000 or f.getnchannels() != 1:
                bad.append(w.name)
    assert bad == []


def test_wav_matches_decoded_audio():
    # Duration is verified against the DECODED PCM, not the inventory
    # duration_s: ffprobe's estimate is unreliable for raw ADTS .aac
    # (0185.aac: ffprobe 7.681 s vs decoded 8.149 s). Every WAV's PCM
    # hash and frame count must match the decode record exactly.
    import wave

    wavs = list(AUDIO_16K.glob("*.wav"))
    assert len(wavs) > 0  # guard against a vacuous pass on an empty dir
    record = json.loads((PREP_DIR / "audio_decode.json").read_text())["files"]
    assert len(record) == len(wavs)
    bad = []
    for w in wavs:
        src = wav_source_file(w)
        rec = record[src]
        with wave.open(str(w), "rb") as f:
            frames = f.getnframes()
            pcm = f.readframes(frames)
        import hashlib

        if frames != rec["samples"] or hashlib.sha256(pcm).hexdigest() != rec["pcm_sha256"]:
            bad.append(w.name)
    assert bad == []


def test_inventory_drift_is_recorded():
    # The inventory-vs-decoded drift is measured and reported, not gated:
    # a drifted file is good audio with a wrong inventory estimate.
    rec = json.loads((PREP_DIR / "audio_decode.json").read_text())
    assert "drift_vs_inventory" in rec
    assert "gt_0.1s" in rec["drift_vs_inventory"]
    assert "by_format" in rec["drift_vs_inventory"]


def test_no_duplicate_audio_content():
    wavs = list(AUDIO_16K.glob("*.wav"))
    assert len(wavs) > 0  # guard against a vacuous pass on an empty dir
    hashes = [wav_pcm_sha256(w) for w in wavs]
    assert len(hashes) == len(set(hashes))


# ---------------- Task 3: split + exclusions ----------------

def load_splits():
    out = {}
    for name in ("train", "val", "test"):
        out[name] = json.loads((PREP_DIR / f"split_{name}.json").read_text())
    return out


def train_ready_count():
    manifest = read_manifest()
    return int((manifest["prep_status"] == "train_ready").sum())


def leaked_text_norm_groups():
    splits = load_splits()
    df = read_clean_csv()
    norm_by_file = dict(zip(df["file"], df["text_norm"]))
    group_side = {}
    leaked = 0
    for side, files in splits.items():
        for f in files:
            g = norm_by_file[f]
            if g in group_side and group_side[g] != side:
                leaked += 1
            group_side[g] = side
    return leaked


def test_split_reconciles_with_train_ready():
    s = load_splits()
    assert len(s["train"]) + len(s["val"]) + len(s["test"]) == train_ready_count()
    # Set identity, not just counts: a split that swapped a quarantined
    # file in for a train-ready file at the same count must fail.
    manifest = read_manifest()
    train_ready = set(manifest[manifest["prep_status"] == "train_ready"]["file"])
    sides = [set(v) for v in s.values()]
    assert sides[0] | sides[1] | sides[2] == train_ready
    assert not (sides[0] & sides[1])
    assert not (sides[0] & sides[2])
    assert not (sides[1] & sides[2])


def test_manifest_agrees_with_clean_csv():
    manifest = read_manifest()
    df = read_clean_csv()
    merged = manifest.merge(
        df[["file", "prep_status"]], on="file", suffixes=("_man", "_csv")
    )
    assert len(merged) == 6024
    assert (merged["prep_status_man"] == merged["prep_status_csv"]).all()


def test_split_no_leaked_groups():
    assert leaked_text_norm_groups() == 0


def test_split_ratios():
    s = load_splits()
    total = sum(len(v) for v in s.values())
    assert abs(len(s["train"]) / total - 0.70) < 0.02


def test_excluded_reconciles():
    ex = json.loads((PREP_DIR / "excluded_disposition.json").read_text())
    assert sum(ex["reasons"].values()) == 498
    assert ex["total"] == 498


# ---------------- Task 4: summary, note, final verification ----------------

def load_recorded_hashes():
    hashes = {}
    for line in HASH_LOG.read_text().splitlines():
        h, path = line.split(None, 1)
        hashes[path.strip()] = h
    return hashes


def hash_canonical_files():
    import hashlib

    out = {}
    for path in load_recorded_hashes():
        out[path] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return out


def test_canonical_unchanged():
    before = load_recorded_hashes()
    after = hash_canonical_files()
    assert before == after


def test_decoded_total_duration_anchored_to_eda():
    # Independent anchor for WAV duration: the decoded train-ready total
    # plus the quarantined files' inventory durations must match EDA's
    # kept total (11.685 h) within ±60 s. The 60 s tolerance covers the
    # known ffprobe estimation error on .aac (measured gap 19.5 s) while
    # still catching any systematic decode failure; single-file errors
    # are caught by the per-file PCM hash + frame checks.
    eda = json.loads((REPO / "eda/eda_summary.json").read_text())
    eda_kept_s = eda["audio_quality"]["duration_kept_h"] * 3600
    decode = json.loads((PREP_DIR / "audio_decode.json").read_text())
    decoded_total = sum(v["duration_s"] for v in decode["files"].values())
    clean_df = read_clean_csv()
    inv = pd.read_csv(INVENTORY_CSV, dtype=str, encoding="utf-8-sig")
    q_files = set(clean_df[clean_df["prep_status"] == "quarantine"]["file"])
    q_inv = inv[inv["file"].isin(q_files)]["duration_s"].astype(float).sum()
    assert abs(decoded_total + q_inv - eda_kept_s) <= 60


def test_summary_schema_invariants():
    s = json.loads(SUMMARY_JSON.read_text())
    assert s["transcripts"]["train_ready"] + s["transcripts"]["quarantine"] == 6024
    assert s["transcripts"]["total"] == 6024
    assert s["transcripts"]["dup_fixed_rows"] == 3
    assert s["transcripts"]["prompt_normalized_rows"] == 581
    assert s["files"]["total"] == 6522
    assert s["files"]["excluded"] == 498
    assert s["audio"]["standardized_files"] == s["transcripts"]["train_ready"]
    assert (
        s["split"]["train"] + s["split"]["val"] + s["split"]["test"]
        == s["transcripts"]["train_ready"]
    )
    assert s["split"]["leaked_groups"] == 0
    assert s["split"]["seed"] == 42


def test_note_covers_scope():
    note = NOTE.read_text()
    for item in [
        "disposition", "dedup", "split", "quarantine",
        "ebtihal", "rights", "reproducibility",
    ]:
        assert item in note.lower()


def test_no_data_tracked():
    out = subprocess.check_output(["git", "ls-files"], text=True)
    assert not re.search(r"\.(csv|m4a|mp3|ogg|mp4|wav|aac|opus|mpeg|rar|parquet)$", out, re.M)
