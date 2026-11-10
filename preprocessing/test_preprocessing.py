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
    "الكل ان شاء الله\\1015.m4a",
    "الكل ان شاء الله\\WhatsApp Audio 2025-11-30 at 11.54.59 PM (1).mp4",
    "الكل ان شاء الله\\AUDIO-2025-11-27-17-01-39.m4a",
]

LOCKED_COLUMNS = [
    "file", "text", "model", "max_no_speech_prob", "min_avg_logprob",
    "prompt", "error", "text_norm", "review_reasons", "needs_review",
    "dup_text_size",
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
    df = pd.read_csv(CLEAN_CSV, dtype=str, encoding="utf-8", nrows=0)
    assert list(df.columns) == LOCKED_COLUMNS + ["prep_status", "prep_reason"]


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
