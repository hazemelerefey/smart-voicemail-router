# EDA: Audio and Speech Evidence (Hazem & Ebtihal pair) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the Hazem & Ebtihal pair EDA note for Phase 1 of Smart Voicemail Router, from the authorized dataset snapshot, covering the team-allocation §3 checklist.

**Architecture:** One reproducible Python EDA script reads the extracted audio + the four analysis CSVs, writes aggregate stats to `eda/eda_summary.json`, charts to `eda/figures/`, and a markdown note to `eda/eda_audio_speech.md`. No model training, no label finalization, no audio or transcripts committed.

**Tech Stack:** Python 3.10+ (stdlib csv/statistics/hashlib + pandas if already installed, else stdlib only), ffprobe/ffmpeg for audio probing, matplotlib for charts if available (else skip charts and say so), pytest for checks.

**Spec:** `docs/project/team-allocation.md` §3 (shared EDA checklist, 8 items), `docs/project/PRD.md` §3 (field separation: category / urgency / customer state / queue priority are distinct), README Data boundary. Locked STT output format v1: 10 columns `file, model, text, text_norm, min_avg_logprob, max_no_speech_prob, needs_review, review_reasons, dup_text_size, error` (see `~/workspace/your_files/stt-output-shape-v3.xlsx`).

## Global Constraints

- Dataset snapshot is the Drive RAR `svr-voicemail-corpus.rar`, 735,052,270 bytes, SHA256 `3518fdd5edad615bf81fc25657f84c0ae476e41f9b31e09c8ea31995f9284e63`, local copy `~/workspace/ai-customer-support/dataset/dataset.rar`. Extract only to `~/workspace/ai-customer-support/dataset/extracted/` (outside the repo).
- Never commit audio, CSVs, transcripts, or the RAR. Copy `.gitignore` from `origin/master` into this branch first; verify with `git status` before every commit.
- EDA note is aggregate statistics only. No raw transcript lines, no phone numbers, no names, no audio. PII checks are counts of patterns, never examples.
- Do not finalize labels. Category/sentiment are empty everywhere; propose an annotation protocol, do not invent classes.
- STT format v1 is locked and co-owned by Ebtihal; do not change it. Known defect to verify, not silently fix: `dup_text_size` wrong on 3 rows ("شكرا للمشاهدة" should be 3, not 1).
- Work on branch `team/audio-speech` only. Commit locally; do NOT push (parent verifies, then pushes).
- All numbers in the note must be recomputed by the script, never copied from memory. Expected anchors to verify against (not to copy): 6,522 total files, 498 excluded, 6,024 transcripts, 133 need review, 20-row eval whisper-large-v3 WER 0.29 vs turbo 0.35.

## Review Focus

- A file counted in the inventory but unreadable by ffprobe, reported as clean anyway.
- A transcript flagged `needs_review` with empty `review_reasons`, or vice versa.
- `dup_text_size` values that disagree with a recount from `text_norm`.
- Text-normalization edge cases: Egyptian dialect spellings counted as different words, English telecom terms split inconsistently.
- A split proposal that leaks near-duplicate audio across train/eval (same `text_norm` or same duration+size on both sides).

---

### Task 0: Branch, ignore rules, environment

**Files:**
- Create: `docs/superpowers/plans/2026-11-10-eda-audio-speech.md` (this plan, already written)
- Create: `GATES.md` (already written, unlazy solo ledger)
- Modify: `.gitignore` (copied from `origin/master`)
- Create: `eda/` directory skeleton

**Interfaces:**
- Consumes: repo at `team/audio-speech`, RAR at `~/workspace/ai-customer-support/dataset/dataset.rar`
- Produces: clean branch state, extracted dataset outside repo, Python env decision recorded in the note

- [ ] **Step 1: Copy `.gitignore` from origin/master and verify it blocks data**

Run: `git checkout origin/master -- .gitignore && git status --short`
Expected: only `.gitignore` shown as added; `git check-ignore -v data/x.csv dataset.rar audio/0001.m4a` prints ignore rules for each.

- [ ] **Step 2: Record the Python environment**

Run: `python3 --version && python3 -c "import pandas, matplotlib; print(pandas.__version__, matplotlib.__version__)" || echo NO_PANDAS_MPL`
Expected: version printed, or NO_PANDAS_MPL. If no pandas/matplotlib, use stdlib only and record that in the note; do not pip-install into the system Python. A venv under `~/workspace/ai-customer-support/.venv-eda/` is allowed if a dependency is needed.

- [ ] **Step 3: Extract the dataset outside the repo and verify it**

Run: `mkdir -p ~/workspace/ai-customer-support/dataset/extracted && cd ~/workspace/ai-customer-support/dataset/extracted && LC_ALL=C.UTF-8 unrar x ../dataset.rar && find . -type f | wc -l`
Expected: 6,522 files. Also run `sha256sum ../dataset.rar` and compare to the Global Constraints value.

- [ ] **Step 4: Commit the setup**

Run: `git add .gitignore docs/superpowers/plans/2026-11-10-eda-audio-speech.md GATES.md && git commit -m "eda: plan and gates for audio-speech EDA"`
Expected: commit succeeds; `git status` clean afterwards.

### Task 1: Audio inventory

**Files:**
- Create: `eda/audio_inventory.py`
- Create: `eda/audio_inventory.csv` (aggregate table only, no per-file PII; per-file rows are technical metadata, allowed locally but NOT committed, write it outside the repo)
- Test: `eda/test_eda.py::test_audio_counts`

**Interfaces:**
- Consumes: extracted audio under `~/workspace/ai-customer-support/dataset/extracted/`
- Produces: `total_files`, `formats` dict, `total_duration_s`, `duration_stats`, `sample_rates` dict, `channels` dict, `unreadable` list, `duration_histogram` (for the note/figures)

- [ ] **Step 1: Write the failing test**

```python
def test_audio_counts():
    inv = load_inventory(OUTSIDE_REPO / "audio_inventory.json")
    assert inv["total_files"] == 6522
    assert inv["unreadable"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest eda/test_eda.py::test_audio_counts -v`
Expected: FAIL (no inventory file yet).

- [ ] **Step 3: Implement `eda/audio_inventory.py` probing every file with ffprobe**

Probe format, duration, sample rate, channels per file; record failures with the ffprobe error. Write the per-file table OUTSIDE the repo (`~/workspace/ai-customer-support/dataset/audio_inventory.json`) and the aggregate dict to `eda/eda_summary.json` (merged later, or a partial JSON the note task merges). Keep runtime sane: one ffprobe per file, no re-encoding.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest eda/test_eda.py::test_audio_counts -v`
Expected: PASS. If `unreadable` is non-empty, the test must be updated to assert the exact list, and the note must name the count; never force it to [].

- [ ] **Step 5: Commit**

Run: `git add eda/audio_inventory.py eda/test_eda.py && git commit -m "eda: audio inventory probe (6522 files)"`
Expected: commit succeeds; `git status` shows no audio/csv files staged.

### Task 2: Transcript and STT quality

**Files:**
- Create: `eda/transcript_quality.py`
- Modify: `eda/eda_summary.json` (add transcript section)
- Test: `eda/test_eda.py::test_transcript_counts`, `test_dup_defect`, `test_review_consistency`

**Interfaces:**
- Consumes: `~/workspace/user/files/transcripts_flagged_14_4zfb.csv` (6,024 rows), `~/workspace/user/files/inventory_clean_13_825a.csv`, `~/workspace/user/files/stt_results_12_d6z5.csv`, `~/workspace/user/files/sample_11_laqj.csv` (read-only inputs, never copied into the repo)
- Produces: transcript counts, confidence distributions, `review_reasons` breakdown, duplicate recount, language-mix counts, WER comparison from the 20-row eval

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest eda/test_eda.py -k "transcript or dup or review" -v`
Expected: FAIL (no summary section yet).

- [ ] **Step 3: Implement `eda/transcript_quality.py`**

Compute from the CSVs: row count, `needs_review` count, `review_reasons` value counts, `min_avg_logprob` and `max_no_speech_prob` distributions (mean/median/p10/p90, split by flagged vs clean), `dup_text_size` distribution + independent recount grouped by `text_norm` (report every mismatch, expect the 3 known rows), text length stats on `text` and `text_norm` (words/chars), language mix (count rows containing Latin-script tokens vs pure Arabic, top English telecom terms by frequency as counts only), WER mean per model from the 20-row eval file. Cross-check inventory_clean vs transcripts_flagged file-id sets match exactly (report the overlap counts).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest eda/test_eda.py -v`
Expected: PASS. If a count differs from the anchor, stop, investigate the CSVs, and record the corrected number with evidence; never edit the test to match an unexamined number.

- [ ] **Step 5: Commit**

Run: `git add eda/transcript_quality.py eda/test_eda.py && git commit -m "eda: transcript and STT quality analysis"`
Expected: commit succeeds; no CSVs staged.

### Task 3: Duplicates, near-duplicates, labels gap

**Files:**
- Create: `eda/duplicates_labels.py`
- Modify: `eda/eda_summary.json` (add duplicates + labels sections)
- Test: `eda/test_eda.py::test_duplicate_groups`, `test_labels_empty`

**Interfaces:**
- Consumes: transcripts CSV (text_norm groups), inventory CSV, extracted audio file sizes/durations
- Produces: exact-duplicate `text_norm` groups (counts + sizes only), near-duplicate candidates (same text_norm, different files), label emptiness counts, annotation-protocol proposal (in the note, not code)

- [ ] **Step 1: Write the failing tests**

```python
def test_duplicate_groups():
    s = load_summary()["duplicates"]
    assert s["largest_text_norm_group"] >= 9  # "اشتركوا في القناة" group

def test_labels_empty():
    s = load_summary()["labels"]
    assert s["category_non_empty"] == 0
    assert s["sentiment_non_empty"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest eda/test_eda.py -k "duplicate or labels" -v`
Expected: FAIL.

- [ ] **Step 3: Implement `eda/duplicates_labels.py`**

Group by `text_norm` (count groups, group-size distribution, largest groups with size only, no transcript text in output JSON). Flag near-duplicates as same `text_norm` from different audio files. Check audio-level exact duplicates by (size, duration) collisions and report the count. Count non-empty `category`/`sentiment` in every CSV that has them (expect 0). Draft the annotation-protocol proposal as note text: double annotation + adjudication, Egyptian-dialect glossary, separate category/urgency/state, review queue for the 133 flagged rows; do not assign any label.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest eda/test_eda.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add eda/duplicates_labels.py eda/test_eda.py && git commit -m "eda: duplicates and labels gap"`
Expected: commit succeeds.

### Task 4: Privacy scan, split proposal, figures

**Files:**
- Create: `eda/privacy_split.py`
- Create: `eda/figures/duration_hist.png`, `eda/figures/confidence_hist.png`, `eda/figures/dup_size.png`, `eda/figures/format_bar.png` (matplotlib; if unavailable, record the gap and skip with a note line)
- Modify: `eda/eda_summary.json` (add privacy + split sections)
- Test: `eda/test_eda.py::test_privacy_counts_only`, `test_split_no_leak`

**Interfaces:**
- Consumes: summary so far, transcripts CSV (pattern counts only)
- Produces: PII-pattern counts (phone-like, email-like, name-like is NOT detectable reliably, say so), split proposal (stratified by duration quartile + format, 80/10/10, duplicate groups kept intact on one side), figure PNGs

- [ ] **Step 1: Write the failing tests**

```python
def test_privacy_counts_only():
    s = load_summary()["privacy"]
    assert isinstance(s["phone_like_rows"], int)
    assert "examples" not in s["privacy"]

def test_split_no_leak():
    s = load_summary()["split"]
    assert s["leaked_duplicate_groups"] == 0
    assert s["train"] + s["dev"] + s["test"] == 6024
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest eda/test_eda.py -k "privacy or split" -v`
Expected: FAIL.

- [ ] **Step 3: Implement `eda/privacy_split.py` + figures**

Count regex pattern hits (Egyptian mobile pattern, email pattern) as integers only, no matched strings stored anywhere. Build the split on the 6,024 transcribed rows: group by `text_norm` first so all copies of one text stay on one side, then stratify by duration quartile and format; verify zero duplicate groups span two sides. Generate the four figures from the summary numbers.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest eda/test_eda.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add eda/privacy_split.py eda/figures eda/test_eda.py && git commit -m "eda: privacy scan, split proposal, figures"`
Expected: commit succeeds.

### Task 5: EDA note, final verification, handoff

**Files:**
- Create: `eda/eda_audio_speech.md`
- Create: `eda/eda_summary.json` (final, merged)
- Test: `eda/test_eda.py::test_note_covers_checklist`, `test_note_has_no_pii`, `test_no_data_tracked`

**Interfaces:**
- Consumes: `eda/eda_summary.json`, figures, plan, GATES.md
- Produces: the pair EDA note, ready for the weekly team comparison

- [ ] **Step 1: Write the failing tests**

```python
def test_note_covers_checklist():
    note = (REPO / "eda/eda_audio_speech.md").read_text()
    for item in ["origin", "inventory", "language", "duplicates", "labels", "privacy", "split", "reproducibility"]:
        assert item in note.lower()

def test_note_has_no_pii():
    note = (REPO / "eda/eda_audio_speech.md").read_text()
    assert not re.search(r"01[0-9]{9}", note)
    assert "@" not in note or "hazemelerefy@gmail.com" in note  # only the contact line allowed, no customer emails

def test_no_data_tracked():
    out = subprocess.check_output(["git", "ls-files"], text=True)
    assert not re.search(r"\.(csv|m4a|mp3|ogg|mp4|wav|rar|parquet)$", out, re.M)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest eda/test_eda.py -k "note or tracked" -v`
Expected: FAIL (no note yet).

- [ ] **Step 3: Write `eda/eda_audio_speech.md`**

Cover all 8 checklist items with the recomputed numbers, the STT format v1 + dup defect, the labels gap + annotation protocol proposal, the split proposal, assumptions/limitations (no speaker IDs, no consent/rights determination yet, WER is dialect-inflated, external-provider experiments not approved), and recommended next decisions for the team meeting. Embed the four figures. State the exact commands and dataset checksum so another pair can reproduce it.

- [ ] **Step 4: Run the full suite + unlazy gates**

Run: `python3 -m pytest eda/test_eda.py -v` then `node ~/workspace/custom-skills/local-unlazy/scripts/gate-check.mjs --status GATES.md` (approve only commands you wrote and understand, then run the checker).
Expected: all tests PASS; all gates met with evidence, none abandoned without a handoff note.

- [ ] **Step 5: Commit, do NOT push**

Run: `git add eda/ && git commit -m "eda: Hazem & Ebtihal pair EDA note (Phase 1)" && git status`
Expected: commit succeeds, working tree clean, nothing pushed. Report the branch + commit hash to the parent for verification and push.
