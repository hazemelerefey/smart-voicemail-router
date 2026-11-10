# Gates: Preprocessing audio-speech (Hazem & Ebtihal pair, Phase 2)

OWNS: docs/superpowers/plans/2026-11-10-preprocessing-audio-speech.md, preprocessing/**

Scope: Deterministic, local-only preprocessing of the EDA-verified dataset into a cleaned training-ready set (derived CSV + 16 kHz mono WAVs + recomputed split), on branch team/audio-speech, canonical files untouched, no data committed.

- [ ] P1: Branch is team/audio-speech tracking origin/team/audio-speech
  CHECK: git rev-parse --abbrev-ref HEAD && git status --porcelain --branch | head -1
  EXPECT: team/audio-speech
  EVIDENCE: pending

- [ ] P2: Dataset snapshot verified (RAR SHA256 matches, 6,522 extracted files)
  CHECK: find /home/hatch/workspace/ai-customer-support/dataset/extracted -type f | wc -l && sha256sum /home/hatch/workspace/ai-customer-support/dataset/dataset.rar | grep -c 3518fdd5edad615bf81fc25657f84c0ae476e41f9b31e09c8ea31995f9284e63
  EXPECT: 6522
  EVIDENCE: pending

- [ ] P3: Full preprocessing pytest suite passes
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preprocessing/test_preprocessing.py -q && echo PREP_TESTS_OK
  EXPECT: PREP_TESTS_OK
  EVIDENCE: pending

- [ ] P4: Dispositions reconcile (train_ready + quarantine = 6024 transcripts; exclusions = 498; dup_text_size recomputed in derived file)
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; s=json.load(open('preprocessing/preprocessing_summary.json')); print(s['transcripts']['train_ready'] + s['transcripts']['quarantine'], s['files']['excluded'], s['transcripts']['dup_fixed_rows'])"
  EXPECT: 6024 498 3
  EVIDENCE: pending

- [ ] P5: Standardized audio matches the train-ready set, all 16 kHz mono, no duplicate audio content
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; s=json.load(open('preprocessing/preprocessing_summary.json')); print('AUDIO_OK' if s['audio']['standardized_files'] == s['transcripts']['train_ready'] else 'AUDIO_MISMATCH')"
  EXPECT: AUDIO_OK
  EVIDENCE: pending

- [ ] P6: Split reconciles with the train-ready set, 0 leaked text_norm groups
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; s=json.load(open('preprocessing/preprocessing_summary.json')); print('SPLIT_OK' if s['split']['train'] + s['split']['dev'] + s['split']['test'] == s['transcripts']['train_ready'] and s['split']['leaked_groups'] == 0 else 'SPLIT_BAD')"
  EXPECT: SPLIT_OK
  EVIDENCE: pending

- [ ] P7: Canonical files byte-identical before and after
  CHECK: sha256sum -c /home/hatch/workspace/ai-customer-support/dataset/preprocessed/run_log_hashes.txt && echo CANONICAL_UNCHANGED
  EXPECT: CANONICAL_UNCHANGED
  EVIDENCE: pending

- [ ] P8: No data, audio, or transcript files are tracked by git
  CHECK: test $(git ls-files | grep -E "\.(csv|m4a|mp3|ogg|mp4|wav|aac|opus|mpeg|rar|parquet)$" | wc -l) -eq 0 && echo NO_DATA_TRACKED
  EXPECT: NO_DATA_TRACKED
  EVIDENCE: pending

- [ ] P9: Preprocessing note exists and covers scope, dispositions, and open team items
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "n=open('preprocessing/preprocessing_audio_speech.md').read().lower(); print('PREP_NOTE_OK' if all(w in n for w in ['disposition','dedup','split','quarantine','ebtihal','rights','reproducibility']) else 'PREP_NOTE_MISSING')"
  EXPECT: PREP_NOTE_OK
  EVIDENCE: pending

- [ ] P10: Working tree clean after the preprocessing commit, nothing pushed yet
  CHECK: test $(git status --porcelain | wc -l) -eq 0 && echo TREE_CLEAN
  EXPECT: TREE_CLEAN
  EVIDENCE: pending
