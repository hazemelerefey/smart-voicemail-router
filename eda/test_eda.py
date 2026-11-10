"""Tests for the Hazem & Ebtihal pair EDA (Phase 1, Smart Voicemail Router).

Every test reads recomputed artifacts (eda_summary.json, the outside-repo
audio inventory), never the source CSVs' own claims. Run with the project
venv: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest eda/test_eda.py -v
"""

import json
import re
import subprocess
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATASET_DIR = Path("/home/hatch/workspace/ai-customer-support/dataset")
CSV_DIR = Path("/home/hatch/workspace/user/files")


def load_summary():
    return json.loads((REPO / "eda" / "eda_summary.json").read_text(encoding="utf-8"))


def load_inventory():
    data = json.loads((DATASET_DIR / "audio_inventory.json").read_text(encoding="utf-8"))
    return data["aggregate"]


# --- Task 1: audio inventory ---

def test_audio_counts():
    inv = load_inventory()
    assert inv["total_files"] == 6522
    assert inv["unreadable"] == []


# --- Task 2: transcript and STT quality ---

def test_transcript_counts():
    s = load_summary()["transcripts"]
    assert s["rows"] == 6024
    assert s["needs_review"] == 133


def test_dup_defect():
    s = load_summary()["transcripts"]
    assert s["dup_text_size_wrong_rows"] == 3


def test_review_consistency():
    s = load_summary()["transcripts"]
    assert s["needs_review_without_reason"] == 0
    assert s["review_reason_without_flag"] == 0


# --- Task 3: duplicates, near-duplicates, labels gap ---

def test_duplicate_groups():
    s = load_summary()["duplicates"]
    assert s["largest_text_norm_group"] >= 9  # "اشتركوا في القناة" group


def test_labels_empty():
    s = load_summary()["labels"]
    assert s["category_non_empty"] == 0
    assert s["sentiment_non_empty"] == 0


# --- Task 5 prep: audio quality (clipping/noise) from inventory_clean ---

def test_audio_quality_stats():
    s = load_summary()["audio_quality"]
    assert s["rows"] == 6522
    assert s["clip_pct_gt0"] == 338
    assert s["silence_pct_gt50"] == 18
    assert s["snr_db_lt10"] == 22
    assert abs(s["duration_total_h"] - 12.63) < 0.01


# --- Task 4: privacy scan, split proposal, figures ---

def test_privacy_counts_only():
    s = load_summary()["privacy"]
    assert isinstance(s["phone_like_rows"], int)
    assert "examples" not in s


def test_split_no_leak():
    s = load_summary()["split"]
    assert s["leaked_duplicate_groups"] == 0
    assert s["train"] + s["dev"] + s["test"] == 6024
