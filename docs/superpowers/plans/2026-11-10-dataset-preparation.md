# Dataset Preparation: Full Expert Pass (Hazem & Ebtihal pair) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the dataset from mechanically cleaned to genuinely ready for model training, as an expert data analyst would. That means: measure every remaining issue, fix everything fixable deterministically, and prepare everything that needs a human (labels, review) so the human work can start immediately with no guessing.

**Correction this plan is built on:** the earlier preprocessing finished the mechanical pipeline (cleaning, 16 kHz mono, split). It did NOT make the dataset training-ready. The router/classifier track has no labels at all, and several data issues are still open. This plan does not claim training readiness until the readiness report proves it per track.

**Architecture:** One notebook, `preparation/dataset_preparation.ipynb`, is the primary artifact (notebook-first rule). It contains the audit, the fixes, the taxonomy discovery, and the annotation package build, with outputs saved. Supporting scripts live in `preparation/` only where a notebook cell would be unreadable (none expected; keep code in the notebook). Tests in `preparation/test_preparation.py` re-verify the notebook's claims from the artifacts. A readiness report, `preparation/dataset_readiness.md`, states per-track status. Derived data stays OUTSIDE the repo under `~/workspace/ai-customer-support/dataset/prepared/`.

**Tech Stack:** Python 3.12 (EDA venv at `~/workspace/ai-customer-support/.venv-eda/`, pandas 2.1.4, matplotlib 3.6.3, pytest 9.2.0, nbconvert 7.17.2, ipykernel; add scikit-learn to the venv ONLY if the clustering task needs it, record the version). ffmpeg/ffprobe 8.1.2 for audio ops. Notebook rules from the user: fewest cells that give the same result, shared helpers loaded once, contents list at top, plain words, no AI slop, no em/en dashes anywhere.

**Spec:** PRD v1.2 (SVR-PRD-01 §3 fields, §8 analysis contract shape, §11 evaluation plan), Architecture v1.2 (SVR-ARCH-02 §2 stages, §4 output semantics, §5 data model, §8 pair interfaces), AI_AGENT_GUIDE v1.2 (§3 EDA before labels, §4 separate fields, §5 claims from evidence), team-allocation v1.2 §3 (8-item EDA checklist) and §5 (Phase 2 freeze). Locked STT output format v1 (10 columns). Split is train/val/test 70/20/10 (user standard).

## Global Constraints

- Dataset snapshot is the Drive RAR `svr-voicemail-corpus.rar`, SHA256 `3518fdd5edad615bf81fc25657f84c0ae476e41f9b31e09c8ea31995f9284e63`, extracted at `~/workspace/ai-customer-support/dataset/extracted/` (6,522 files). Verify before starting.
- **Canonical files are read-only.** The transcripts CSV, inventory CSV, eval/sample CSVs must be byte-identical before and after (record SHA256 in the run log). All fixes go into DERIVED files only.
- **Local only.** No audio, transcripts, or derived data leaves this machine. No external provider, no upload, no Colab.
- **No finalized labels.** Do not assign category, urgency, customer state, or churn values to any row. The taxonomy proposal is a CANDIDATE for the user/team to approve, grounded in clustering evidence. The annotation guide is a DRAFT. The calibration batch is a sample for agreement measurement, not labeled data.
- **No transcript text in the repo.** Notebook outputs, the readiness report, the guide, and the summary carry counts, file IDs, single terms, and reason codes only. Per-file lists with transcripts live OUTSIDE the repo.
- **Two training tracks, judged separately.** Track A (ASR fine-tuning: audio + transcript pairs) and Track B (router/classifier: needs labels). A track is READY only when every blocker for that track is fixed or explicitly waived by the user. Never report the dataset as ready as a whole while any track is blocked.
- **Fixes must be reversible and recorded.** Every audio fix records the exact operation + parameters per file; originals are never overwritten; recovered audio goes to a separate derived dir with a recovery manifest.
- Work on branch `team/audio-speech` only. Commit locally per task; do NOT push (parent verifies, then pushes).
- All numbers must be recomputed by the notebook/tests, never copied from this plan or earlier notes. Anchors to verify against (not copy): 6,522 total files, 6,024 transcripts, 5,881 train-ready, 143 quarantine, 498 excluded, split train 4,117 / val 1,176 / test 588, 133 needs_review, 3 dup rows fixed in derived file, 26 recoverable excluded, 82 .aac duration-drift files, 320 clipping rows.

## The issue inventory (every item must be measured, then fixed or explicitly owned)

1. **No labels.** Category, urgency, customer state, churn: empty everywhere. Blocks Track B entirely.
2. **133 flagged transcripts in quarantine.** Never human-reviewed. Blocks their use in either track.
3. **26 recoverable excluded files.** Recovery ops defined (denoise/declip/chunk/trim) but never applied. Their audio is unusable as-is and they have no transcripts.
4. **82 .aac files with wrong inventory durations.** `duration_s` in the inventory drifts up to 0.487 s from decoded PCM. Every duration-based decision downstream inherits the error.
5. **320 clipping rows in the training pool.** Treatment never applied or decided (declip vs tolerate).
6. **Low-SNR audio.** 22 files under 10 dB, all excluded; denoising never attempted.
7. **One 125.92 s file.** Exceeds the 60 s product maximum (FR-01). Chunking never decided.
8. **Split is not speaker-aware.** No speaker IDs exist; same-speaker leakage cannot be measured. Must be stated as a residual risk, with a mitigation (near-duplicate audio check already done: 0 audio duplicates in train-ready).
9. **Transcript quality is unverified beyond 20 reference rows.** WER is directional only; Whisper output drifts toward MSA spelling while references are Egyptian dialect. Fine-tuning on unchecked transcripts bakes in systematic errors.
10. **dup_text_size fix still proposed, not confirmed.** The user is the reviewer now; the fix needs his explicit confirmation to become canonical.
11. **Rights, consent, retention, processing locations unconfirmed.** Blocks everything beyond local work.
12. **No telecom glossary.** FR-04 requires an agreed Arabic/English telecom glossary + identifier masking before any permitted external text call. The frequent Latin terms are counted but no glossary exists.
13. **Text normalization edge cases.** `text_norm` vs `text` differences unexamined (dialect spelling variants that split one complaint across forms).

## Review Focus

- A label value assigned to any row (must never happen in this phase).
- A fix applied to a canonical file instead of a derived copy.
- A recovered audio file whose duration or content cannot be verified against its source.
- A cluster/theme claim with no term evidence or no size attached.
- A track marked READY while its blocker list is non-empty.
- A number in the readiness report that no test recomputes.

---

### Task 0: Setup and input verification

**Files:**
- Create: `docs/superpowers/plans/2026-11-10-dataset-preparation.md` (this plan, already written)
- Create: `preparation/GATES.md` (already written, unlazy solo ledger)
- Create: `preparation/` directory skeleton

**Interfaces:**
- Consumes: repo at `team/audio-speech`, RAR, extracted audio, canonical CSVs, EDA + preprocessing artifacts (summaries, notebooks, split files, derived CSVs, WAVs)
- Produces: verified inputs, recorded canonical hashes, clean branch state

- [ ] **Step 1: Verify the branch, snapshot, and prior artifacts**

Run: `git rev-parse --abbrev-ref HEAD && sha256sum ~/workspace/ai-customer-support/dataset/dataset.rar && find ~/workspace/ai-customer-support/dataset/extracted -type f | wc -l && ls ~/workspace/ai-customer-support/dataset/preprocessed/`
Expected: `team/audio-speech`, hash `3518fdd5...`, 6522, and the preprocessed dir holds `transcripts_clean.csv`, `audio_16k/` (5,881 WAVs), `split_train.json`, `split_val.json`, `split_test.json`.

- [ ] **Step 2: Record canonical file hashes (before)**

Run: `sha256sum` over the four canonical CSVs into `~/workspace/ai-customer-support/dataset/prepared/run_log_hashes.txt` (outside the repo, `sha256sum -c` format).
Expected: four hashes recorded; `sha256sum -c` passes.

- [ ] **Step 3: Confirm the venv and install scikit-learn only if needed**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import sklearn; print(sklearn.__version__)" || echo NO_SKLEARN`
Expected: version printed, or NO_SKLEARN. If clustering needs it, install into the venv and record the exact version in the notebook and the readiness report. Do not pip-install into system Python.

- [ ] **Step 4: Commit the setup**

Run: `git add docs/superpowers/plans/2026-11-10-dataset-preparation.md preparation/GATES.md && git commit -m "preparation: plan and gates for full dataset preparation"`
Expected: commit succeeds; `git status` clean afterwards.

### Task 1: Issue audit (measure everything, fix nothing yet)

**Files:**
- Create: `preparation/dataset_preparation.ipynb` (sections 1-3: setup, issue audit, glossary + normalization check)
- Create: `preparation/test_preparation.py` (tests for this task first)
- Output (outside repo): `~/workspace/ai-customer-support/dataset/prepared/audit_summary.json`

**Interfaces:**
- Consumes: canonical CSVs, inventory, derived cleaned CSV + manifest, EDA/preprocessing summaries, extracted audio, WAVs, audio_decode.json
- Produces: one measured number per issue (1-13 above), saved in `audit_summary.json`, shown in the notebook

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preparation/test_preparation.py -v`
Expected: FAIL (no audit file yet).

- [ ] **Step 3: Implement the audit in the notebook**

Measure each issue: labels (count non-empty per field, expect 0); quarantine (133 needs_review + 10 silence, reason breakdown); recoverable (26 files with reasons, and for each, whether the defined recovery op is applicable); duration drift (recompute decoded durations for the 82 .aac + 3 .m4a files, record drift distribution); clipping (severity distribution of clip_pct on the 320 kept rows, and whether clipping correlates with low confidence); low SNR (22 files, all excluded, re-measure SNR on the recovered candidates if any); long file (125.92 s, chunk plan into 60 s max segments); speaker awareness (state as unmeasurable, record the 0-audio-duplicate mitigation); transcript quality (confidence distribution of the 133 flagged vs clean, hallucination/repetition/prompt-leak counts, length outliers, MSA-vs-dialect signals you can measure, e.g. rows where text and text_norm differ most); dup confirmation (still proposed); rights (still unconfirmed); glossary (extract the frequent Latin telecom terms with counts + the most frequent Arabic complaint words as single terms, no transcript quotes); normalization (count rows where text and text_norm differ, group the difference types).

- [ ] **Step 4: Run tests to verify they pass**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preparation/test_preparation.py -v`
Expected: PASS. If a count differs from the plan's anchors, stop, investigate, and record the corrected number with evidence.

- [ ] **Step 5: Commit**

Run: `git add preparation/dataset_preparation.ipynb preparation/test_preparation.py && git commit -m "preparation: full issue audit (13 issues measured)"`
Expected: commit succeeds; no data files staged.

### Task 2: Deterministic fixes

**Files:**
- Modify: `preparation/dataset_preparation.ipynb` (sections 4-5: fixes + verification)
- Modify: `preparation/test_preparation.py` (add fix tests)
- Output (outside repo): `dataset/prepared/inventory_corrected.csv`, `dataset/prepared/recovered_audio/*.wav`, `dataset/prepared/recovery_manifest.json`, `dataset/prepared/long_file_chunks.json`

**Interfaces:**
- Consumes: audit results, extracted audio, inventory, audio_decode.json
- Produces: corrected durations, recovered audio + manifest, chunk map, each verified

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preparation/test_preparation.py -k "duration or recovered or chunked" -v`
Expected: FAIL.

- [ ] **Step 3: Implement the fixes in the notebook**

(a) Duration correction: recompute `duration_s` from decoded PCM for every file where inventory duration is unreliable (all .aac + the 3 .m4a), write `inventory_corrected.csv` (derived copy, never overwrite the canonical inventory). Verify drift is 0 within 0.01 s.
(b) Recovery: for each of the 26 recoverable files, apply its defined op (low_snr: ffmpeg `afftdn` denoise; clipped: `adeclip` or tolerate with a recorded decision per file; too_long: chunk; mostly_silence: trim silence with `silenceremove`). Re-measure SNR/clip/duration on each output; keep only outputs that pass (SNR improved, no new clipping, duration within 0.1 s of the expected value). Record every op + parameter + before/after measures in `recovery_manifest.json`. Recovered files have no transcripts: list them under `needs_transcription`, do NOT add them to any training split.
(c) Long file: chunk the 125.92 s file into 60 s max segments with 0 overlap, record the chunk map (segment files stay out of the training pool until transcribed; the map is the deliverable).
(d) Clipping in the training pool: do NOT alter the 320 kept WAVs. Measure and report the treatment recommendation (tolerate vs declip) with evidence: clip severity distribution + confidence comparison of clipped vs clean rows. The decision stays open for the user.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preparation/test_preparation.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add preparation/dataset_preparation.ipynb preparation/test_preparation.py && git commit -m "preparation: deterministic fixes (durations, recovery, long-file chunks)"`
Expected: commit succeeds.

### Task 3: Taxonomy discovery (candidates only, never labels)

**Files:**
- Modify: `preparation/dataset_preparation.ipynb` (section 6: taxonomy discovery)
- Modify: `preparation/test_preparation.py` (add taxonomy tests)
- Output (outside repo): `dataset/prepared/cluster_results.json`; in repo: `preparation/taxonomy_proposal.md`

**Interfaces:**
- Consumes: cleaned CSV `text_norm` (train-ready rows only), cleaned-audio quality flags
- Produces: clusters with sizes + top terms, a candidate taxonomy draft with definitions, and the evidence linking each candidate to its cluster

- [ ] **Step 1: Write the failing tests**

```python
def test_clusters_cover_train_ready():
    c = load_clusters()
    assert sum(c["sizes"].values()) == 5881
    assert all(s > 0 for s in c["sizes"].values())

def test_taxonomy_has_evidence():
    t = load_taxonomy()
    for cand in t["candidates"]:
        assert cand["cluster_id"] in load_clusters()["clusters"]
        assert len(cand["top_terms"]) >= 5
        assert cand["status"] == "proposed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preparation/test_preparation.py -k "cluster or taxonomy" -v`
Expected: FAIL.

- [ ] **Step 3: Implement taxonomy discovery in the notebook**

Vectorize `text_norm` (TF-IDF, Arabic-aware tokenization, keep the English telecom terms as tokens). Cluster (k-means or HDBSCAN if available; choose k by silhouette on a small grid, record the scores, do not tune endlessly). Report per cluster: size, top 10 terms (single terms only), share of flagged rows, mean confidence. From the clusters, draft candidate complaint categories: each candidate gets a name, a one-line definition, the cluster(s) supporting it, size, and top terms. Separately, state what the text CANNOT decide: urgency levels and customer-state classes need human judgment and the annotation guide, not clusters; churn is a candidate dimension only if the clusters show explicit departure language, otherwise mark it unsupported. Record the method + seed + versions so the clustering reproduces.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preparation/test_preparation.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add preparation/dataset_preparation.ipynb preparation/taxonomy_proposal.md preparation/test_preparation.py && git commit -m "preparation: taxonomy discovery (candidates with cluster evidence)"`
Expected: commit succeeds.

### Task 4: Annotation package + readiness report

**Files:**
- Create: `preparation/annotation_guide_draft.md` (in repo)
- Create: `preparation/dataset_readiness.md` (in repo)
- Create: `preparation/preparation_summary.json` (aggregate counts only)
- Modify: `preparation/dataset_preparation.ipynb` (sections 7-8: annotation package + readiness)
- Test: `preparation/test_preparation.py::test_annotation_package`, `test_readiness_tracks`, `test_canonical_unchanged`, `test_no_data_tracked`

**Interfaces:**
- Consumes: audit, fixes, clusters, taxonomy proposal, splits, quarantine list
- Produces: the annotation package (guide draft + calibration batch list + review queue list, file IDs only in repo; transcript-bearing batch files outside the repo), the readiness report, the summary JSON

- [ ] **Step 1: Write the failing tests**

```python
def test_annotation_package():
    g = (REPO / "preparation/annotation_guide_draft.md").read_text()
    for field in ["complaint_category", "complaint_urgency", "customer_state_text"]:
        assert field in g
    assert "DRAFT" in g and "proposed" in g.lower()
    cal = load_calibration_batch()  # outside repo
    assert len(cal) == 100

def test_readiness_tracks():
    r = load_readiness()
    assert r["tracks"]["asr"]["status"] in ("ready", "blocked")
    assert r["tracks"]["router"]["status"] == "blocked"
    assert r["tracks"]["router"]["blockers"]  # non-empty while labels are missing

def test_canonical_unchanged():
    assert hash_canonical_files() == load_recorded_hashes()

def test_no_data_tracked():
    out = subprocess.check_output(["git", "ls-files"], text=True)
    assert not re.search(r"\.(csv|m4a|mp3|ogg|mp4|wav|aac|opus|mpeg|rar|parquet)$", out, re.M)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preparation/test_preparation.py -k "annotation or readiness or canonical or tracked" -v`
Expected: FAIL (no guide/report yet).

- [ ] **Step 3: Write the annotation package + readiness report**

Guide draft: per field (category, urgency, customer_state_text, optional churn) the candidate values (from Task 3 for category; for urgency/state, the dimensions + rules for telling urgency apart from emotion, per PRD risk R3), the Egyptian-dialect glossary (terms + counts), worked examples described WITHOUT quoting full transcripts (field + reason only), double-annotation + adjudication, the 100-row calibration batch (stratified across clusters + a share of flagged rows), and the agreement target before scaling. Calibration batch file (outside repo): 100 file IDs + their cluster + stratum; the transcript-bearing version lives outside the repo only.
Review queue (outside repo): the 133 flagged file IDs + reasons + the recovered-but-untranscribed files, as the human work list.
Readiness report: per track (ASR, router) status + blockers + owner + decision needed; per issue (1-13) status (fixed / proposed / blocked / open) with the evidence pointer; what the user must decide next (dup confirmation, split freeze, rights/consent, taxonomy approval, annotation start + who annotates, clipping treatment, recovered-file transcription); exact reproduction commands.

- [ ] **Step 4: Run the full suite + unlazy gates**

Run: `/home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preparation/test_preparation.py -v` then `node ~/workspace/custom-skills/local-unlazy/scripts/gate-check.mjs --status preparation/GATES.md` (approve only commands you wrote and understand, then run the checker).
Expected: all tests PASS; all gates met with evidence, none abandoned without a handoff note.

- [ ] **Step 5: Commit, do NOT push**

Run: `git add preparation/ && git commit -m "preparation: full dataset preparation (audit, fixes, taxonomy, annotation package)" && git status`
Expected: commit succeeds, working tree clean, nothing pushed. Report the branch + commit hash to the parent for verification and push.
