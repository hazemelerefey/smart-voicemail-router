# Gates: Preprocessing audio-speech (Hazem & Ebtihal pair, Phase 2)

OWNS: docs/superpowers/plans/2026-11-10-preprocessing-audio-speech.md, preprocessing/**

Scope: Deterministic, local-only preprocessing of the EDA-verified dataset into a cleaned training-ready set (derived CSV + 16 kHz mono WAVs + recomputed split), on branch team/audio-speech, canonical files untouched, no data committed.

- [x] P1: Branch is team/audio-speech tracking origin/team/audio-speech
  CHECK: git rev-parse --abbrev-ref HEAD && git status --porcelain --branch | head -1
  EXPECT: team/audio-speech
  EVIDENCE: automatic-evidence=v1; definition-sha256=78d77f280a87698f088c4b79d5d6e0f758e7701aec4888dc4c91d8e19d8cb8dc; exit=0; EXPECT=matched; output-sha256=35c57ae0a61f66d0de776694d1d1385bd2f6a1a1a04f9fb9d5febcb4dab66d76; output-bytes=66; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [x] P2: Dataset snapshot verified (RAR SHA256 matches, 6,522 extracted files)
  CHECK: find /home/hatch/workspace/ai-customer-support/dataset/extracted -type f | wc -l && sha256sum /home/hatch/workspace/ai-customer-support/dataset/dataset.rar | grep -c 3518fdd5edad615bf81fc25657f84c0ae476e41f9b31e09c8ea31995f9284e63
  EXPECT: 6522
  EVIDENCE: automatic-evidence=v1; definition-sha256=134d8fc941fa004871ee56fe0260e268ba40beee79e88e0da3f79499c11a269f; exit=0; EXPECT=matched; output-sha256=35514693661808da14bf1c451d0f5b03671da413c94de373d88d67f7ee2742a0; output-bytes=7; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [x] P3: Full preprocessing pytest suite passes
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preprocessing/test_preprocessing.py -q && echo PREP_TESTS_OK
  EXPECT: PREP_TESTS_OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=513be85b09bd39faf4b285b28c1254aa69709a21efc8cc948dd5878c81cf1b24; exit=0; EXPECT=matched; output-sha256=7c154bd54f970867d8e1c77a1bce5df561ae76d580b25841e771974972b3b26a; output-bytes=124; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [x] P4: Dispositions reconcile (train_ready + quarantine = 6024 transcripts; exclusions = 498; dup_text_size recomputed in derived file)
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; s=json.load(open('preprocessing/preprocessing_summary.json')); print(s['transcripts']['train_ready'] + s['transcripts']['quarantine'], s['files']['excluded'], s['transcripts']['dup_fixed_rows'])"
  EXPECT: 6024 498 3
  EVIDENCE: automatic-evidence=v1; definition-sha256=59bdff0a954a4dac77c3cd3d91dd8f0bbc5a61e22198189870f686dfa585768f; exit=0; EXPECT=matched; output-sha256=ee9c990cd380f6a3d1263d8ceae693db1e7d8332f5e0cbbc35d5565591ba8c5a; output-bytes=11; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [x] P5: Standardized audio matches the train-ready set, all 16 kHz mono, no duplicate audio content
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; s=json.load(open('preprocessing/preprocessing_summary.json')); print('AUDIO_OK' if s['audio']['standardized_files'] == s['transcripts']['train_ready'] else 'AUDIO_MISMATCH')"
  EXPECT: AUDIO_OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=ecb0138dfd53a17bba6a807389a2ad8bdfd5ca0458d78d08f270871263ec0a62; exit=0; EXPECT=matched; output-sha256=07b16c53b2adaba5393724202fda63a1ac0dfbfc5d8da2bb59360b4dc73c34ee; output-bytes=9; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [x] P6: Split reconciles with the train-ready set, 0 leaked text_norm groups
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; s=json.load(open('preprocessing/preprocessing_summary.json')); print('SPLIT_OK' if s['split']['train'] + s['split']['val'] + s['split']['test'] == s['transcripts']['train_ready'] and s['split']['leaked_groups'] == 0 else 'SPLIT_BAD')"
  EXPECT: SPLIT_OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=795e9c624df39feb662225fd0bf836309617fb91c8e1ec1e304c57f0d43a10b6; exit=0; EXPECT=matched; output-sha256=eff048e768fd38f21a8223cd59a997f34dba8341c091defbf702306d307f3c1e; output-bytes=9; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [x] P7: Canonical files byte-identical before and after
  CHECK: sha256sum -c /home/hatch/workspace/ai-customer-support/dataset/preprocessed/run_log_hashes.txt && echo CANONICAL_UNCHANGED
  EXPECT: CANONICAL_UNCHANGED
  EVIDENCE: automatic-evidence=v1; definition-sha256=4afa9430ec26ba708c7ee3fd72dca3344003480961d310baff3d2b7d2d38e1e9; exit=0; EXPECT=matched; output-sha256=709437218bed2af6482239643c87862b41f0ac2e11b18687a540e4ca33b8bbca; output-bytes=271; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [x] P8: No data, audio, or transcript files are tracked by git
  CHECK: test $(git ls-files | grep -E "\.(csv|m4a|mp3|ogg|mp4|wav|aac|opus|mpeg|rar|parquet)$" | wc -l) -eq 0 && echo NO_DATA_TRACKED
  EXPECT: NO_DATA_TRACKED
  EVIDENCE: automatic-evidence=v1; definition-sha256=c9eabb9d0f3f3455a897726afa84008180ce1400be8ebab9d7c2afe3af8c6f23; exit=0; EXPECT=matched; output-sha256=aff021e6084aee36d69e6a841988d7debca80563c8b80935431092ebc14676d2; output-bytes=16; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [x] P9: Preprocessing note exists and covers scope, dispositions, and open team items
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "n=open('preprocessing/preprocessing_audio_speech.md').read().lower(); print('PREP_NOTE_OK' if all(w in n for w in ['disposition','dedup','split','quarantine','ebtihal','rights','reproducibility']) else 'PREP_NOTE_MISSING')"
  EXPECT: PREP_NOTE_OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=27528cace1638475afb8478b74851a31a8b65f3fc9204bd9896789927ec1bddf; exit=0; EXPECT=matched; output-sha256=4fbe1b9bb913e78aeaa1337ace53d5feb803dd6c907d54a8c67eb87be34f51f2; output-bytes=13; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries

- [x] P10: Working tree clean after the preprocessing commit, nothing pushed yet
  CHECK: test $(git status --porcelain | wc -l) -eq 0 && echo TREE_CLEAN
  EXPECT: TREE_CLEAN
  EVIDENCE: automatic-evidence=v1; definition-sha256=1308d9fdb20dad22a4ea6fad49cab7bcb390041ba2ed381e9409b18e880110ce; exit=0; EXPECT=matched; output-sha256=aae759e7feba7044a7768be621e4903bc475dc06185d754ee91c532cd54ad749; output-bytes=11; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
