"""Tests for dataset preparation. All claims in the notebook are re-verified here
from the artifacts outside the repo. No em dashes or en dashes anywhere."""

import json
import re
import subprocess
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
PREPARED = Path("/home/hatch/workspace/ai-customer-support/dataset/prepared")
USER_FILES = Path("/home/hatch/workspace/user/files")
PREPROCESSED = Path("/home/hatch/workspace/ai-customer-support/dataset/preprocessed")


def load_audit():
    with open(PREPARED / "audit_summary.json") as f:
        return json.load(f)


def load_clusters():
    with open(PREPARED / "cluster_results.json") as f:
        return json.load(f)


def load_taxonomy():
    with open(REPO / "preparation" / "taxonomy_proposal.md") as f:
        return f.read()


def load_recovery_manifest():
    with open(PREPARED / "recovery_manifest.json") as f:
        return json.load(f)


def load_chunk_map():
    with open(PREPARED / "long_file_chunks.json") as f:
        return json.load(f)


def load_calibration_batch():
    with open(PREPARED / "calibration_batch.json") as f:
        return json.load(f)


def load_readiness():
    with open(REPO / "preparation" / "preparation_summary.json") as f:
        return json.load(f)


def load_recorded_hashes():
    recorded = {}
    for line in (PREPARED / "run_log_hashes.txt").read_text().splitlines():
        h, p = line.split(None, 1)
        recorded[p.strip()] = h
    return recorded


def hash_canonical_files():
    out = subprocess.check_output(
        ["sha256sum", "-c", str(PREPARED / "run_log_hashes.txt")], text=True
    )
    return out


def read_corrected_inventory():
    return pd.read_csv(PREPARED / "inventory_corrected.csv")


# ---------------- Task 1: issue audit ----------------


def test_audit_reconciles():
    a = load_audit()
    assert a["files"]["total"] == 6522
    assert a["transcripts"]["total"] == 6024
    assert a["disposition"]["train_ready"] + a["disposition"]["quarantine"] == 6024
    assert a["disposition"]["excluded"] == 498


def test_audit_covers_all_issues():
    a = load_audit()
    for issue in ["labels", "quarantine", "recoverable", "duration_drift",
                  "clipping", "low_snr", "long_file", "speaker_awareness",
                  "transcript_quality", "dup_confirmation", "rights",
                  "glossary", "normalization"]:
        assert issue in a["issues"]


def test_quarantine_breakdown():
    a = load_audit()["issues"]["quarantine"]
    assert a["needs_review"] == 133
    assert a["total"] == 143


# ---------------- Task 2: deterministic fixes ----------------


def test_duration_drift_fixed():
    inv = read_corrected_inventory()
    assert max(abs(inv["duration_s"] - inv["duration_decoded_s"])) <= 0.01


def test_recovered_files_verified():
    m = load_recovery_manifest()
    assert m["recovered"] + m["unrecoverable"] == 26
    for f in m["files"]:
        assert f["verified"] is True


def test_long_file_chunked():
    ch = load_chunk_map()
    assert all(seg["duration_s"] <= 60.0 for seg in ch["segments"])
    assert abs(sum(seg["duration_s"] for seg in ch["segments"]) - 125.92) < 1.0


# ---------------- Task 3: taxonomy discovery ----------------


def test_clusters_cover_train_ready():
    c = load_clusters()
    assert sum(c["sizes"].values()) == 5881
    assert all(s > 0 for s in c["sizes"].values())


def test_taxonomy_has_evidence():
    t = load_taxonomy()
    c = load_clusters()
    assert "approved" in t.lower()
    for cand in c["candidates"]:
        assert cand["cluster_id"] in c["clusters"]
        assert len(cand["top_terms"]) >= 5
        assert cand["status"] == "proposed"


# ---------------- Task 4: annotation package + readiness ----------------


def test_annotation_package():
    g = (REPO / "preparation/annotation_guide_draft.md").read_text()
    for field in ["complaint_category", "complaint_urgency", "customer_state"]:
        assert field in g
    assert "APPROVED" in g
    assert "Hazem and Ebtihal" in g
    cal = load_calibration_batch()
    assert len(cal) == 100


def test_readiness_tracks():
    r = load_readiness()
    assert r["tracks"]["asr"]["status"] in ("ready", "blocked")
    assert r["tracks"]["router"]["status"] == "blocked"
    assert r["tracks"]["router"]["blockers"]


def test_canonical_unchanged():
    out = hash_canonical_files()
    assert out.count(": OK") == 4


def test_no_data_tracked():
    out = subprocess.check_output(["git", "ls-files"], text=True, cwd=REPO)
    assert not re.search(r"\.(csv|m4a|mp3|ogg|mp4|wav|aac|opus|mpeg|rar|parquet)$", out, re.M)
