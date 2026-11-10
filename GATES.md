# Gates: EDA audio-speech (Hazem & Ebtihal pair, Phase 1)

OWNS: docs/superpowers/plans/2026-11-10-eda-audio-speech.md, GATES.md, .gitignore, eda/**

Scope: Reproducible pair EDA note for the Smart Voicemail Router dataset snapshot, on branch team/audio-speech, aggregate statistics only, no audio/transcripts/PII committed.

- [x] G1: Branch is team/audio-speech tracking origin/team/audio-speech
  CHECK: git rev-parse --abbrev-ref HEAD && git status --porcelain --branch | head -1
  EXPECT: team/audio-speech
  EVIDENCE: automatic-evidence=v1; definition-sha256=78d77f280a87698f088c4b79d5d6e0f758e7701aec4888dc4c91d8e19d8cb8dc; exit=0; EXPECT=matched; output-sha256=42466b2b046e9059b748a6d803314b769153723bef3e632ea9b6a49a5393bb23; output-bytes=76; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [x] G2: Dataset extracted outside the repo, 6,522 audio files, RAR SHA256 matches the plan value
  CHECK: find /home/hatch/workspace/ai-customer-support/dataset/extracted -type f | wc -l && sha256sum /home/hatch/workspace/ai-customer-support/dataset/dataset.rar | grep -c 3518fdd5edad615bf81fc25657f84c0ae476e41f9b31e09c8ea31995f9284e63
  EXPECT: 6522
  EVIDENCE: automatic-evidence=v1; definition-sha256=134d8fc941fa004871ee56fe0260e268ba40beee79e88e0da3f79499c11a269f; exit=0; EXPECT=matched; output-sha256=35514693661808da14bf1c451d0f5b03671da413c94de373d88d67f7ee2742a0; output-bytes=7; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [x] G3: Full EDA pytest suite passes
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest eda/test_eda.py -q && echo EDA_TESTS_OK
  EXPECT: EDA_TESTS_OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=3dea4dcd167f6014f56cbe894032bb8698ef4115a0f9fc6f7ad397afc5b38d23; exit=0; EXPECT=matched; output-sha256=7ce66f72cec9d5f6500854956ca2481dcc3deca5c34e8d783ec85f54dd425dec; output-bytes=112; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [x] G4: Summary counts reproduce the anchors from source (6522 total, 6024 transcripts, 133 needs_review, 3 dup_text_size mismatches)
  CHECK: python3 -c "import json; s=json.load(open('eda/eda_summary.json')); print(s['audio']['total_files'], s['transcripts']['rows'], s['transcripts']['needs_review'], s['transcripts']['dup_text_size_wrong_rows'])"
  EXPECT: 6522 6024 133 3
  EVIDENCE: automatic-evidence=v1; definition-sha256=091ca3a339edf43e0428d82e88d5004e9cee3abe1f5f63fe21a8a642ae7f5b44; exit=0; EXPECT=matched; output-sha256=4ddab331c55df9bb08d6b3bde13ccb4147d1c3211f21052e512af62489e3cb9b; output-bytes=16; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [x] G5: EDA note exists and covers all 8 checklist items
  CHECK: python3 -c "n=open('eda/eda_audio_speech.md').read().lower(); print('CHECKLIST_OK' if all(w in n for w in ['origin','inventory','language','duplicates','labels','privacy','split','reproducibility']) else 'CHECKLIST_MISSING')"
  EXPECT: CHECKLIST_OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=2fba11a2927d9c1d5b30e8c7350463933fe93ce1799c8f1285efe720fed72c76; exit=0; EXPECT=matched; output-sha256=4c5635400b6b76f78b83b42e86fc78dc69df8c556147de832b1bf4ebcb887ee1; output-bytes=13; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [x] G6: No PII or raw transcripts in the note (no Egyptian mobile pattern, no customer email)
  CHECK: test $(grep -E "01[0-9]{9}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}" eda/eda_audio_speech.md | grep -v hazemelerefy@gmail.com | wc -l) -eq 0 && echo NO_PII_FOUND
  EXPECT: NO_PII_FOUND
  EVIDENCE: automatic-evidence=v1; definition-sha256=b719e72589796bdf54017a39bfe64d473222973be1f21bbe431374f525aee767; exit=0; EXPECT=matched; output-sha256=8c238daa0a03cad914e7a1ff6f325ee538d9acdb8363f365b48e1f2a6e10a633; output-bytes=13; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [x] G7: No data, audio, or transcript files are tracked by git
  CHECK: test $(git ls-files | grep -E "\.(csv|m4a|mp3|ogg|mp4|wav|aac|opus|mpeg|rar|parquet)$" | wc -l) -eq 0 && echo NO_DATA_TRACKED
  EXPECT: NO_DATA_TRACKED
  EVIDENCE: automatic-evidence=v1; definition-sha256=c9eabb9d0f3f3455a897726afa84008180ce1400be8ebab9d7c2afe3af8c6f23; exit=0; EXPECT=matched; output-sha256=aff021e6084aee36d69e6a841988d7debca80563c8b80935431092ebc14676d2; output-bytes=16; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [x] G8: Four figures exist and are referenced by the note
  CHECK: ls eda/figures/*.png | wc -l && grep -c "figures/" eda/eda_audio_speech.md
  EXPECT: 4
  EVIDENCE: automatic-evidence=v1; definition-sha256=dc4cc1111cd68f419125b29190996fba8c55a1b96076ead9d69801ed86d8d6b9; exit=0; EXPECT=matched; output-sha256=ab2fafd33682c9e5457b36098c493a9f06572e6bd9b562f2513943b7869560a1; output-bytes=4; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [ ] G9: Working tree clean after the EDA commit, nothing pushed yet
  CHECK: test $(git status --porcelain | wc -l) -eq 0 && echo TREE_CLEAN
  EXPECT: TREE_CLEAN
  EVIDENCE: pending
