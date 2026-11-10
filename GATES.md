# Gates: EDA audio-speech (Hazem & Ebtihal pair, Phase 1)

OWNS: docs/superpowers/plans/2026-11-10-eda-audio-speech.md, GATES.md, .gitignore, eda/**

Scope: Reproducible pair EDA note for the Smart Voicemail Router dataset snapshot, on branch team/audio-speech, aggregate statistics only, no audio/transcripts/PII committed.

- [ ] G1: Branch is team/audio-speech tracking origin/team/audio-speech
  CHECK: git rev-parse --abbrev-ref HEAD && git status --porcelain --branch | head -1
  EXPECT: team/audio-speech
  EVIDENCE: pending

- [ ] G2: Dataset extracted outside the repo, 6,522 audio files, RAR SHA256 matches the plan value
  CHECK: find /home/hatch/workspace/ai-customer-support/dataset/extracted -type f | wc -l && sha256sum /home/hatch/workspace/ai-customer-support/dataset/dataset.rar | grep -c 3518fdd5edad615bf81fc25657f84c0ae476e41f9b31e09c8ea31995f9284e63
  EXPECT: 6522
  EVIDENCE: pending

- [ ] G3: Full EDA pytest suite passes
  CHECK: python3 -m pytest eda/test_eda.py -q && echo EDA_TESTS_OK
  EXPECT: EDA_TESTS_OK
  EVIDENCE: pending

- [ ] G4: Summary counts reproduce the anchors from source (6522 total, 6024 transcripts, 133 needs_review, 3 dup_text_size mismatches)
  CHECK: python3 -c "import json; s=json.load(open('eda/eda_summary.json')); print(s['audio']['total_files'], s['transcripts']['rows'], s['transcripts']['needs_review'], s['transcripts']['dup_text_size_wrong_rows'])"
  EXPECT: 6522 6024 133 3
  EVIDENCE: pending

- [ ] G5: EDA note exists and covers all 8 checklist items
  CHECK: python3 -c "n=open('eda/eda_audio_speech.md').read().lower(); print('CHECKLIST_OK' if all(w in n for w in ['origin','inventory','language','duplicates','labels','privacy','split','reproducibility']) else 'CHECKLIST_MISSING')"
  EXPECT: CHECKLIST_OK
  EVIDENCE: pending

- [ ] G6: No PII or raw transcripts in the note (no Egyptian mobile pattern, no customer email)
  CHECK: test $(grep -E "01[0-9]{9}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}" eda/eda_audio_speech.md | grep -v hazemelerefy@gmail.com | wc -l) -eq 0 && echo NO_PII_FOUND
  EXPECT: NO_PII_FOUND
  EVIDENCE: pending

- [ ] G7: No data, audio, or transcript files are tracked by git
  CHECK: test $(git ls-files | grep -E "\.(csv|m4a|mp3|ogg|mp4|wav|aac|opus|mpeg|rar|parquet)$" | wc -l) -eq 0 && echo NO_DATA_TRACKED
  EXPECT: NO_DATA_TRACKED
  EVIDENCE: pending

- [ ] G8: Four figures exist and are referenced by the note
  CHECK: ls eda/figures/*.png | wc -l && grep -c "figures/" eda/eda_audio_speech.md
  EXPECT: 4
  EVIDENCE: pending

- [ ] G9: Working tree clean after the EDA commit, nothing pushed yet
  CHECK: test $(git status --porcelain | wc -l) -eq 0 && echo TREE_CLEAN
  EXPECT: TREE_CLEAN
  EVIDENCE: pending
