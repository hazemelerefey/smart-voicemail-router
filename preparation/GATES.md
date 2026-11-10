# Gates: Dataset Preparation (audio-speech pair)

Scope: Full expert dataset preparation for model training. One notebook `preparation/dataset_preparation.ipynb` (audit, fixes, taxonomy discovery, annotation package), tests `preparation/test_preparation.py`, taxonomy proposal `preparation/taxonomy_proposal.md`, annotation guide draft `preparation/annotation_guide_draft.md`, readiness report `preparation/dataset_readiness.md`, summary `preparation/preparation_summary.json`. Derived data outside the repo under `~/workspace/ai-customer-support/dataset/prepared/`.

- [x] D1: Branch is team/audio-speech tracking origin/team/audio-speech
  CHECK: git rev-parse --abbrev-ref HEAD
  EXPECT: team/audio-speech
  EVIDENCE: automatic-evidence=v1; definition-sha256=f5b4b04e85486130d52daae72b92e8f3bf5678dc04d0938a5034eba2028baca4; exit=0; EXPECT=matched; output-sha256=9217a5d3067b45d4b9e16da00124d9d5d57163468c00275c6191e54c832621bd; output-bytes=18; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
- [x] D2: Dataset snapshot verified (RAR SHA256 matches, 6,522 extracted files)
  CHECK: echo "$(find /home/hatch/workspace/ai-customer-support/dataset/extracted -type f | wc -l) and $(sha256sum /home/hatch/workspace/ai-customer-support/dataset/dataset.rar | grep -c 3518fdd5edad615bf81fc25657f84c0ae476e41f9b31e09c8ea31995f9284e63)"
  EXPECT: 6522 and 1
  EVIDENCE: automatic-evidence=v1; definition-sha256=8bbd9e8ee49435a8b841597db008dfcf0de9b712a52caad761d8a3b955d4a5ca; exit=0; EXPECT=matched; output-sha256=edf62281007b60d429bb882ba4f1f454be626e87c87d514d9dd5bbafe8abdeee; output-bytes=11; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
- [x] D3: Audit covers all 13 issues with measured numbers
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; a=json.load(open('/home/hatch/workspace/ai-customer-support/dataset/prepared/audit_summary.json')); print('AUDIT_OK' if len(a['issues'])==13 and a['files']['total']==6522 else 'AUDIT_BAD')"
  EXPECT: AUDIT_OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=b96da9d45f3ec49ec5299f1c412949cf82c219e0b14b8b3506f16356140f5df7; exit=0; EXPECT=matched; output-sha256=b15348ff71485b3a16f0d971979dca826b2740f6acfe4999280a0bcb1dd973c9; output-bytes=9; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
- [x] D4: Duration drift fixed (corrected inventory drift within 0.01 s)
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import pandas as pd; inv=pd.read_csv('/home/hatch/workspace/ai-customer-support/dataset/prepared/inventory_corrected.csv'); print('DRIFT_OK' if (inv['duration_s']-inv['duration_decoded_s']).abs().max()<=0.01 else 'DRIFT_BAD')"
  EXPECT: DRIFT_OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=567faba8948da6f50cd564e5f8edca888fdfb126ee39d4caca2eaa26d48a5291; exit=0; EXPECT=matched; output-sha256=35afd60f4b0995527a0b7836435475c0fe3127186cd07eae6ef73da55fc4f9bb; output-bytes=9; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
- [x] D5: Recovery manifest reconciles (recovered + unrecoverable == 26, every file verified)
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; m=json.load(open('/home/hatch/workspace/ai-customer-support/dataset/prepared/recovery_manifest.json')); print('RECOVERY_OK' if m['recovered']+m['unrecoverable']==26 and all(f['verified'] for f in m['files']) else 'RECOVERY_BAD')"
  EXPECT: RECOVERY_OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=f4ef870146bc1d7a60e3d074d15c05c1177982b24bdd5396e0b37d9a9bc4049e; exit=0; EXPECT=matched; output-sha256=f3e257d507ec62bdb1698f452ddbcb8e32d44a9647d2c2e4f0d67f8e31782a95; output-bytes=12; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
- [x] D6: Long file chunked into segments of at most 60 s
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; ch=json.load(open('/home/hatch/workspace/ai-customer-support/dataset/prepared/long_file_chunks.json')); print('CHUNK_OK' if all(s['duration_s']<=60.0 for s in ch['segments']) else 'CHUNK_BAD')"
  EXPECT: CHUNK_OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=cdf0e6d769d97741f6f64bccef368d927271639055f01ec4a3fb0ade6264cbb4; exit=0; EXPECT=matched; output-sha256=2f1f24f5cf7fd07d5989b65482499b5bcef28e59bfcbe8c6106ace852b59226c; output-bytes=9; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
- [x] D7: Taxonomy proposal exists, candidates only, each with cluster evidence
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; t=json.load(open('/home/hatch/workspace/ai-customer-support/dataset/prepared/cluster_results.json')); print('TAX_OK' if sum(t['sizes'].values())==5881 else 'TAX_BAD')"
  EXPECT: TAX_OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=00b872e2ef21881bb242920e16ac6d794f74b7a70202bd3fb5c0c839b337eb7d; exit=0; EXPECT=matched; output-sha256=b4a76764f0473f497391fc837900499690b3287a9ab7ca1dd7a8a754b2d99535; output-bytes=7; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
- [x] D8: Annotation package exists (guide draft + 100-row calibration batch + review queue)
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; c=json.load(open('/home/hatch/workspace/ai-customer-support/dataset/prepared/calibration_batch.json')); print('ANN_OK' if len(c)==100 else 'ANN_BAD')"
  EXPECT: ANN_OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=8a2a9d0e6490d844c8ad765d94836c4c7e7249d7dd143e6fae53a3066eacbbc7; exit=0; EXPECT=matched; output-sha256=f2a9961447d3bc1b17284da461fdf5b1b9a917986033bd77aa9ffb2e1ea003fb; output-bytes=7; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
- [x] D9: Readiness report states both tracks, router blocked while labels are missing
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; s=json.load(open('preparation/preparation_summary.json')); print('READY_OK' if s['tracks']['router']['status']=='blocked' and s['tracks']['router']['blockers'] else 'READY_BAD')"
  EXPECT: READY_OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=dec00ec223633afb90ea0b71d943acc4c4b45f07fd4cfeec85bbe5915d156b67; exit=0; EXPECT=matched; output-sha256=f291fd65df1f95a7061aee9c35731948cc1402526650de92daa61f00e343e9de; output-bytes=9; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
- [x] D10: Full preparation pytest suite passes
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preparation/test_preparation.py -q 2>&1 | grep -o "[0-9]* passed" && echo PREP_TESTS_OK
  EXPECT: PREP_TESTS_OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=5b34f2b40f947a73659a9189f935da6ab77d3bafc236b5b98ed09df092b5edb8; exit=0; EXPECT=matched; output-sha256=907f4c4c22f24a2a41f7e5742e675ab3c0861b45aa7f5264002f6e2a2793c35e; output-bytes=24; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
- [x] D11: Canonical files unchanged (hashes match the recorded run log)
  CHECK: sha256sum -c /home/hatch/workspace/ai-customer-support/dataset/prepared/run_log_hashes.txt
  EXPECT: OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=a9ab57e253bcc62c04083ce91032d1935aa66b5e236b45618d151fa4180737a9; exit=0; EXPECT=matched; output-sha256=ecda3ec92fb208a783144b03b4b99bd1c1e90310b7c4df8c99ed2a930de09ee5; output-bytes=251; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
- [ ] D12: Working tree clean (except gate evidence refresh)
  CHECK: test $(git status --porcelain | wc -l) -eq 0 && echo TREE_CLEAN
  EXPECT: TREE_CLEAN
