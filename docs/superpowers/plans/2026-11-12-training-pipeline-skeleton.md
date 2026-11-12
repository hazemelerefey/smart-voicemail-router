# Training Pipeline Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the training pipeline skeleton notebook on team/hazem-training-lead that every role uses, so Lama and Sira can start their Phase 1 work on the same setup.

**Architecture:** One executed Jupyter notebook that loads the clean training tables, verifies the audio folders match the splits, and defines the shared config. It is the skeleton, not a full training run. No model training in this task.

**Tech Stack:** Jupyter notebook, pandas, scikit-learn (for the data checks only), Python 3.11, venv .venv-eda.

**Spec:** docs/project/roles-and-workflow.md (Role 1 Hazem Phase 1; Role 3 Lama Phase 1; Role 2 Sira Phase 1), docs/project/team-allocation.md v1.3, research/svr-model-selection-report.md (hyperparameters, seeds).

## Global Constraints

- Notebook-first: all work lives in Jupyter notebooks until the full project is finalized, only then convert to .py.
- Notebooks must be executed with outputs saved.
- Notebook style: professional, organized, simple, effective; fewest cells; shared helpers in one early setup cell; short contents list at top; plain words; no AI slop.
- Notebooks are written as a data analyst doing the work, present tense, first person; they must NOT read as AZZAR explaining to the team, NOT say they were made because anyone asked, and must NOT mention AZZAR anywhere.
- Labels are presented as coming from "the model" (deep/machine learning), never from AZZAR or an agent.
- NO em dashes and NO en dashes ever, in chat, notes, code, or notebooks.
- Split: train / validation / test, never "dev". Ratio 70/20/10. Counts: train 4,031 / val 1,136 / test 584, total 5,751, seed 42.
- Dataset is the SVR Voicemail Corpus. Audio is 16 kHz mono WAV.
- Branch: team/hazem-training-lead. Hazem reviews and merges to develop. Push each finished piece as soon as it is done and verified, never batch.
- The data lives on the local-env branch (worktree ../svr-data). The notebook reads from the worktree path, never from a hardcoded absolute path that only works on one machine.
- Venv: ~/workspace/ai-customer-support/.venv-eda/bin/python (pandas 2.1.4, scikit-learn 1.9.1). No torch, no transformers, no GPU. Notebooks use object-oriented matplotlib API only (no pyplot) and display saved PNGs via IPython.display.Image.

## Review Focus

- A notebook that hardcodes an absolute path to the data folder will break on every other member's machine. The notebook must resolve the data path relative to the repo or accept it as a variable at the top.
- A notebook that claims the splits match without counting the audio files is not verified. The count check must run and assert.
- A notebook that defines the config in prose but never as a dict the code can import is not a shared config. The config must be a dict in the notebook.
- A notebook that mentions AZZAR, or says it was made because someone asked, violates the notebook rule and must be rewritten.
- A notebook with em or en dashes anywhere violates the writing ban and must be fixed before it ships.

---

### Task 1: Training pipeline skeleton notebook

**Files:**
- Create: `notebooks/training/training_pipeline_skeleton.ipynb`
- Test: execute the notebook with nbconvert and confirm 0 errors.

**Interfaces:**
- Consumes: the clean training tables in `../svr-data/final/` (clean_training_train.csv, clean_training_val.csv, clean_training_test.csv) and the audio folders in `../svr-data/dataset/` (train, val, test).
- Produces: the shared config dict (seed 42, max_seq_len 128, split 70/20/10, dataset_version v2) and the verified counts (train 4,031, val 1,136, test 584), which Lama and Sira build on.

- [ ] **Step 1: Create the notebook with a contents list and a setup cell**

Create `notebooks/training/training_pipeline_skeleton.ipynb` with a short contents list at the top and one early setup cell that imports pandas and defines the data paths (tables in `../svr-data/final/`, audio in `../svr-data/dataset/`) and the shared config dict (seed 42, max_seq_len 128, split 70/20/10, dataset_version v2).

- [ ] **Step 2: Load the three clean training tables and assert the counts**

Add a cell that loads clean_training_train.csv, clean_training_val.csv, and clean_training_test.csv, prints the row count of each, and asserts train is 4,031, val is 1,136, test is 584, total is 5,751.

- [ ] **Step 3: Count the audio files and assert they match the tables**

Add a cell that counts the WAV files in `../svr-data/dataset/train`, `../svr-data/dataset/val`, and `../svr-data/dataset/test`, prints the counts, and asserts train is 4,031, val is 1,136, test is 584.

- [ ] **Step 4: Show a sample of the training table**

Add a cell that shows the first 3 rows of the train table with the text_norm column and the four label fields (complaint_category, complaint_urgency, customer_state, churn_risk).

- [ ] **Step 5: Close with what the skeleton gives every role**

Add a final cell that states what this skeleton gives every role: data loading, shared config, seed handling, output format for results.

- [ ] **Step 6: Execute the notebook and confirm 0 errors**

Run: `~/workspace/ai-customer-support/.venv-eda/bin/python -m nbconvert --to notebook --execute --inplace notebooks/training/training_pipeline_skeleton.ipynb`
Expected: exit 0, 0 errors, outputs saved in the notebook.

- [ ] **Step 7: Verify cleanliness**

Run: `grep -c` for em/en dashes (expect 0), `grep -ci azzar` (expect 0), and confirm the notebook has no .py file alongside it.
Expected: 0 dashes, 0 AZZAR.

- [ ] **Step 8: Commit and push**

Run: `git add notebooks/training/training_pipeline_skeleton.ipynb docs/superpowers/plans/2026-11-12-training-pipeline-skeleton.md`
Run: `git commit -m "Add training pipeline skeleton notebook (Phase 1)"`
Run: `git push origin team/hazem-training-lead`
Expected: push succeeds, commit visible on origin.

---

### Task 2: Messages for Lama and Sira

**Files:**
- Create: `~/workspace/ai-customer-support/phase-1-implementation/lama-sira-messages.md` (working file, not committed).

**Interfaces:**
- Consumes: the pushed skeleton notebook commit (Task 1 Step 8) and the Phase 1 steps for Lama and Sira from the roles guide.
- Produces: two ready-to-send messages, one for Lama and one for Sira, each naming the skeleton, the exact commands, and the Phase 1 deliverable.

- [ ] **Step 1: Draft Lama's message**

Write Lama's message: the skeleton is pushed (commit hash, branch team/hazem-training-lead), her exact checkout command, the setup steps, her Phase 1 work (single-task setup, tokenizers, seq len 128, training script, smoke test), and the note that she adopts Aya's infrastructure when it lands.

- [ ] **Step 2: Draft Sira's message**

Write Sira's message: the skeleton is pushed (commit hash, branch team/hazem-training-lead), her exact checkout command, the setup steps, her Phase 1 work (audio verification 5,751 files 16 kHz mono WAV, intake check, Whisper sample, XLS-R baseline), and the note that the audio is verified against the tables.

- [ ] **Step 3: Verify both messages name the real commit and the real commands**

Check each message against the pushed commit hash and the exact branch commands. Fix any placeholder.
Expected: both messages are ready to send with no placeholders.
