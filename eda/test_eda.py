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
