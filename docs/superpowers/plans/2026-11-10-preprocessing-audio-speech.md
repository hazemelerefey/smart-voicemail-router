# Preprocessing: Audio and Speech Evidence (Hazem & Ebtihal pair, Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the EDA-verified dataset into a cleaned, training-ready audio + transcript set for the Hazem & Ebtihal pair, with every disposition recorded and reproducible, and nothing silently altered.

**Architecture:** One deterministic preprocessing pipeline reads the extracted audio + the canonical transcript/inventory CSVs + the EDA summary/split, writes derived artifacts OUTSIDE the repo under `~/workspace/ai-customer-support/dataset/preprocessed/`, and writes scripts, tests, an aggregate summary JSON, and a markdown note into `preprocessing/` on branch `team/audio-speech`. Derived data is never committed.

**Tech Stack:** Python 3.12 (reuse the EDA venv at `~/workspace/ai-customer-support/.venv-eda/` — pandas 2.1.4, pytest 9.2.0), ffmpeg/ffprobe 8.1.2 for resampling and verification, hashlib for content-hash dedup.

**Spec:** EDA note `eda/eda_audio_speech.md` §10 (recommended next decisions), `docs/project/team-allocation.md` §5 (Phase 2 = shared data/interface freeze; a blocked data/privacy gate does not permit model work on unapproved material), locked STT output format v1 (10 columns).

## Global Constraints

- Dataset snapshot is the Drive RAR `الكل ان شاء الله.rar`, SHA256 `3518fdd5edad615bf81fc25657f84c0ae476e41f9b31e09c8ea31995f9284e63`, extracted at `~/workspace/ai-customer-support/dataset/extracted/` (6,522 files). Verify before starting.
- **Canonical files are read-only.** The transcripts CSV (`~/workspace/user/files/transcripts_flagged_14_4zfb.csv`) and inventory CSV must be byte-identical before and after (record SHA256 in the summary). All fixes go into the DERIVED cleaned file only.
- **The 3 wrong `dup_text_size` values are fixed in the derived file by recomputation, marked as proposed pending Ebtihal's confirmation.** Do not present the derived file as the canonical STT output. Do not edit the canonical file.
- **Local only.** No audio, transcripts, or derived data leaves this machine. No external provider, no upload, no Colab.
- **No labels.** Do not invent or assign category/sentiment/urgency. Do not finalize any label.
- **No transcript text in the repo.** The note and summary carry counts, file IDs, and reason codes only. Per-file disposition manifests (with file IDs, no transcript text) live OUTSIDE the repo.
- **Deterministic.** Re-running the pipeline on the same snapshot produces byte-identical derived CSVs and identical manifest hashes. Record the run commands.
- Work on branch `team/audio-speech` only. Commit locally per task; do NOT push (parent verifies, then pushes).
- All numbers in the note must be recomputed by the pipeline/tests, never copied from this plan or the EDA note. Anchors to verify against (not copy): 6,522 total files, 6,024 transcripts, 133 needs_review, 3 dup mismatches, split 4820/602/602 on the full set.

## Decisions fixed by this plan (record them, do not re-decide)

- **Audio standard for training:** 16 kHz mono WAV (Whisper input standard). Only train-ready files are standardized. Loudness is NOT changed; levels are recorded as measured.
- **Blocking quarantine reasons (train_ready = none of these):** `needs_review` flag, >50% silence, SNR < 10 dB, duplicate audio content (content-hash match). Clipping is a NON-blocking flag recorded in `prep_reason`, not a quarantine reason.
- **Dedup by decoded-audio content hash** (SHA256 of ffmpeg-decoded PCM), never by (size, duration). First occurrence kept, later copies quarantined with reason `duplicate_audio`.
- **Prompt normalization:** empty prompt (581 rows) → `none` in the derived file, documented.
- **The 498 excluded files stay excluded.** Record their disposition reasons from the inventory; check whether any are recoverable and report the count, but re-include none without a team decision.
- **Split is recomputed on the train-ready set** (the EDA split covered all 6,024 rows; quarantine removals change the pool). Whole `text_norm` groups stay on one side, 0 leaks, stratified by duration quartile + format, target 80/10/10. The EDA split assignment is superseded for the training pool; say so in the note.

## Decisions NOT made here (open team items, record in the note)

- Adoption of the recomputed `dup_text_size` values as canonical → Ebtihal (co-owner of STT format v1).
- Freezing the recomputed split → team meeting.
- Rights, consent, retention, processing locations → team (still unconfirmed; preprocessing stays local-only).
- Annotation protocol + calibration batch → team meeting.
- Whether quarantined rows re-enter after human review → human review queue, not this phase.

## Review Focus

- A canonical file whose hash changed after the run (must never happen).
- A quarantined row that still lands in the training pool, or a `text_norm` group split across train/dev/test.
- Two train-ready files with identical decoded-audio hashes (dedup missed).
- A standardized WAV whose duration differs from its source by more than 0.1 s, or that is not 16 kHz mono.
- A disposition count that does not reconcile: train_ready + quarantine + excluded must equal 6,522 files / 6,024 transcripts exactly.
- The derived CSV drifting from the locked 10 columns except the two documented preprocessing-only columns (`prep_status`, `prep_reason`).

---

### Task 0: Setup and input verification

**Files:**
- Create: `docs/superpowers/plans/2026-11-10-preprocessing-audio-speech.md` (this plan, already written)
- Create: `preprocessing/GATES.md` (already written, unlazy solo ledger)
- Create: `preprocessing/` directory skeleton

**Interfaces:**
- Consumes: repo at `team/audio-speech`, RAR, extracted audio, canonical CSVs, EDA summary + split assignment
- Produces: verified inputs, recorded canonical hashes, clean branch state

- [ ] **Step 1: Verify the branch and the snapshot**

Run: `git rev-parse --abbrev-ref HEAD && sha256sum ~/workspace/ai-customer-support/dataset/dataset.rar && find ~/workspace/ai-customer-support/dataset/extracted -type f | wc -l`
Expected: `team/audio-speech`, hash `3518fdd5...`, 6522.

- [ ] **Step 2: Record canonical file hashes (before)**

Run: `sha256sum ~/workspace/user/files/transcripts_flagged_14_4zfb.csv ~/workspace/user/files/inventory_clean_13_825a.csv ~/workspace/user/files/stt_results_12_d6z5.csv ~/workspace/user/files/sample_11_laqj.csv > ~/workspace/ai-customer-support/dataset/preprocessed/run_log_hashes.txt` (outside the repo; the file is in `sha256sum -c` format, absolute paths).
Expected: four hashes recorded; `sha256sum -c` on that file passes.

- [ ] **Step 3: Confirm the EDA venv works**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import pandas, pytest; print(pandas.__version__)"`
Expected: version printed. Do not pip-install into system Python.

- [ ] **Step 4: Commit the setup**

Run: `git add docs/superpowers/plans/2026-11-10-preprocessing-audio-speech.md preprocessing/GATES.md && git commit -m "preprocessing: plan and gates for audio-speech preprocessing"`
Expected: commit succeeds; `git status` clean afterwards.

### Task 1: Transcript cleaning (derived file only)

**Files:**
- Create: `preprocessing/clean_transcripts.py`
- Create: `preprocessing/test_preprocessing.py` (tests for this task first)
- Output (outside repo): `~/workspace/ai-customer-support/dataset/preprocessed/transcripts_clean.csv`, `~/workspace/ai-customer-support/dataset/preprocessed/disposition_manifest.csv`

**Interfaces:**
- Consumes: canonical transcripts CSV, inventory CSV, EDA summary (acoustic measures taken as given, per EDA note §10)
- Produces: derived cleaned CSV (10 locked columns + `prep_status` + `prep_reason`), per-file disposition manifest (file IDs + status + reason codes, no transcript text)

- [ ] **Step 1: Write the failing tests**

```python
def test_clean_row_count():
    df = read_clean_csv()
    assert len(df) == 6024

def test_dup_recomputed():
    df = read_clean_csv()
    groups = df.groupby("text_norm")["dup_text_size"]
    assert (df["dup_text_size"] == df["text_norm"].map(df["text_norm"].value_counts())).all()
    assert (df["dup_text_size"] == 3).sum() == 3  # the "شكرا للمشاهدة" rows, fixed by recomputation

def test_prompt_normalized():
    df = read_clean_csv()
    assert (df["prompt"] == "").sum() == 0
    assert (df["prompt"] == "none").sum() == 6024

def test_disposition_reconciles():
    df = read_clean_csv()
    assert df["prep_status"].value_counts().sum() == 6024
    assert set(df["prep_status"]) <= {"train_ready", "quarantine"}

def test_flagged_all_quarantined():
    df = read_clean_csv()
    assert ((df["needs_review"] == True) & (df["prep_status"] != "quarantine")).sum() == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preprocessing/test_preprocessing.py -v`
Expected: FAIL (no cleaned CSV yet).

- [ ] **Step 3: Implement `preprocessing/clean_transcripts.py`**

Read the canonical CSV (never write to it). Recompute `dup_text_size` as the size of each `text_norm` group. Normalize empty prompt to `none`. Set `prep_status`: `quarantine` if `needs_review` is true OR >50% silence OR SNR < 10 dB (measures from inventory_clean, taken as given); else `train_ready`. Set `prep_reason` as a semicolon list of all applicable flags, including non-blocking `clipping` where the inventory flags it. Write the cleaned CSV and the disposition manifest outside the repo. Print a disposition summary (counts per status and per reason).

- [ ] **Step 4: Run tests to verify they pass**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preprocessing/test_preprocessing.py -v`
Expected: PASS. If a count differs from the plan's anchors, stop, investigate, and record the corrected number with evidence; never edit the test to match an unexamined number.

- [ ] **Step 5: Commit**

Run: `git add preprocessing/clean_transcripts.py preprocessing/test_preprocessing.py && git commit -m "preprocessing: transcript cleaning (derived file only)"`
Expected: commit succeeds; no CSVs staged (`git status` shows no data files).

### Task 2: Audio standardization + content-hash dedup

**Files:**
- Create: `preprocessing/standardize_audio.py`
- Modify: `preprocessing/test_preprocessing.py` (add audio tests)
- Output (outside repo): `~/workspace/ai-customer-support/dataset/preprocessed/audio_16k/*.wav`

**Interfaces:**
- Consumes: extracted audio, cleaned CSV (train_ready set), disposition manifest
- Produces: 16 kHz mono WAVs for train-ready files only; updated disposition manifest (duplicates marked `duplicate_audio`, quarantined)

- [ ] **Step 1: Write the failing tests**

```python
def test_standardized_count_matches_train_ready():
    manifest = read_manifest()
    wavs = list(AUDIO_16K.glob("*.wav"))
    assert len(wavs) == (manifest["prep_status"] == "train_ready").sum()

def test_all_wavs_16k_mono():
    bad = [w for w in AUDIO_16K.glob("*.wav") if ffprobe(w)["sample_rate"] != 16000 or ffprobe(w)["channels"] != 1]
    assert bad == []

def test_wav_duration_matches_source():
    assert max_duration_drift_s() <= 0.1

def test_no_duplicate_audio_content():
    hashes = content_hashes_of_train_ready()
    assert len(hashes) == len(set(hashes))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preprocessing/test_preprocessing.py -k audio -v`
Expected: FAIL (no WAVs yet).

- [ ] **Step 3: Implement `preprocessing/standardize_audio.py`**

For each train-ready file: decode with ffmpeg, compute SHA256 of the decoded PCM for dedup BEFORE writing (first occurrence kept; later copies get `prep_status=quarantine`, `prep_reason` gains `duplicate_audio`, and are removed from the train-ready set). Write 16 kHz mono WAV to the derived dir. Verify each WAV with ffprobe (sample rate, channels, duration vs source). Skip quarantined/excluded files. Keep runtime sane: parallelize with 8 workers like the EDA probe; log every skipped file with its reason. Recompute the train-ready count after dedup and record it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preprocessing/test_preprocessing.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add preprocessing/standardize_audio.py preprocessing/test_preprocessing.py && git commit -m "preprocessing: 16kHz mono standardization + content-hash dedup"`
Expected: commit succeeds; no audio files staged.

### Task 3: Split recomputation + excluded-file disposition

**Files:**
- Create: `preprocessing/split_and_exclusions.py`
- Modify: `preprocessing/test_preprocessing.py` (add split + exclusion tests)
- Output (outside repo): `~/workspace/ai-customer-support/dataset/preprocessed/split_train.json`, `split_dev.json`, `split_test.json`, `excluded_disposition.json`

**Interfaces:**
- Consumes: cleaned CSV + manifest after dedup, inventory CSV (exclusion reasons for the 498)
- Produces: split files on the train-ready set only, excluded-file disposition counts

- [ ] **Step 1: Write the failing tests**

```python
def test_split_reconciles_with_train_ready():
    s = load_splits()
    assert len(s["train"]) + len(s["dev"]) + len(s["test"]) == train_ready_count()

def test_split_no_leaked_groups():
    assert leaked_text_norm_groups() == 0

def test_split_ratios():
    s = load_splits()
    total = sum(len(v) for v in s.values())
    assert abs(len(s["train"]) / total - 0.80) < 0.02

def test_excluded_reconciles():
    ex = load_excluded()
    assert sum(ex.values()) == 498
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preprocessing/test_preprocessing.py -k "split or excluded" -v`
Expected: FAIL.

- [ ] **Step 3: Implement `preprocessing/split_and_exclusions.py`**

Split the train-ready set: group by `text_norm` first (whole groups on one side), stratify by duration quartile + format, target 80/10/10, seed fixed and recorded (42). Verify 0 leaked groups. For the 498 excluded files: tabulate exclusion reasons from the inventory CSV, count how many are recoverable in principle (readable audio, excluded for a fixable reason) vs permanently unusable, and record both counts. Re-include none.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preprocessing/test_preprocessing.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add preprocessing/split_and_exclusions.py preprocessing/test_preprocessing.py && git commit -m "preprocessing: split recomputation + excluded-file disposition"`
Expected: commit succeeds.

### Task 4: Summary, note, final verification, handoff

**Files:**
- Create: `preprocessing/preprocessing_summary.json` (aggregate counts only)
- Create: `preprocessing/preprocessing_audio_speech.md`
- Create: `preprocessing/figures/disposition_bar.png` (one chart; matplotlib if available, else record the gap)
- Test: `preprocessing/test_preprocessing.py::test_note_covers_scope`, `test_canonical_unchanged`, `test_no_data_tracked`

**Interfaces:**
- Consumes: summary data, manifests, split files, plan, GATES.md
- Produces: the pair preprocessing note, ready for the team meeting and for model training

- [ ] **Step 1: Write the failing tests**

```python
def test_canonical_unchanged():
    before = load_recorded_hashes()
    after = hash_canonical_files()
    assert before == after

def test_note_covers_scope():
    note = (REPO / "preprocessing/preprocessing_audio_speech.md").read_text()
    for item in ["disposition", "dedup", "split", "quarantine", "ebtihal", "rights", "reproducibility"]:
        assert item in note.lower()

def test_no_data_tracked():
    out = subprocess.check_output(["git", "ls-files"], text=True)
    assert not re.search(r"\.(csv|m4a|mp3|ogg|mp4|wav|aac|opus|mpeg|rar|parquet)$", out, re.M)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preprocessing/test_preprocessing.py -k "note or canonical or tracked" -v`
Expected: FAIL (no note yet).

## Summary JSON schema (exact keys the gates check)

`preprocessing/preprocessing_summary.json` must contain exactly these keys (extra keys allowed only under a `details` object):

```json
{
  "transcripts": {"total": 6024, "train_ready": 0, "quarantine": 0, "dup_fixed_rows": 3, "prompt_normalized_rows": 581},
  "files": {"total": 6522, "excluded": 498, "excluded_recoverable": 0},
  "audio": {"standardized_files": 0, "duplicate_audio_quarantined": 0},
  "split": {"train": 0, "dev": 0, "test": 0, "leaked_groups": 0, "seed": 42}
}
```

Invariants the gates enforce: `train_ready + quarantine == 6024`; `excluded == 498`; `dup_fixed_rows == 3`; `standardized_files == train_ready`; `train + dev + test == train_ready`; `leaked_groups == 0`.

- [ ] **Step 3: Write `preprocessing/preprocessing_audio_speech.md`**

Cover: inputs + canonical hashes, the fixed decisions (16 kHz mono, quarantine rules, content-hash dedup, prompt normalization), disposition tables (train_ready / quarantine / excluded with reason breakdowns), dedup results, split sizes + the fact the EDA split is superseded for the training pool, excluded-file disposition + recoverable count, the open team items (Ebtihal dup confirmation, split freeze, rights/consent, annotation protocol, review queue), assumptions/limitations, and exact reproduction commands. Embed the disposition chart. State where the derived data lives (outside the repo) and that it is not committed.

- [ ] **Step 4: Run the full suite + unlazy gates**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preprocessing/test_preprocessing.py -v` then `node ~/workspace/custom-skills/local-unlazy/scripts/gate-check.mjs --status preprocessing/GATES.md` (approve only commands you wrote and understand, then run the checker).
Expected: all tests PASS; all gates met with evidence, none abandoned without a handoff note.

- [ ] **Step 5: Commit, do NOT push**

Run: `git add preprocessing/ && git commit -m "preprocessing: Hazem & Ebtihal pair preprocessing (Phase 2)" && git status`
Expected: commit succeeds, working tree clean, nothing pushed. Report the branch + commit hash to the parent for verification and push.
