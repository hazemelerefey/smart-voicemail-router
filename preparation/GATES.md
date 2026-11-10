# Gates: Dataset Preparation (audio-speech pair)

Scope: Full expert dataset preparation for model training. One notebook `preparation/dataset_preparation.ipynb` (audit, fixes, taxonomy discovery, annotation package), tests `preparation/test_preparation.py`, taxonomy proposal `preparation/taxonomy_proposal.md`, annotation guide draft `preparation/annotation_guide_draft.md`, readiness report `preparation/dataset_readiness.md`, summary `preparation/preparation_summary.json`. Derived data outside the repo under `~/workspace/ai-customer-support/dataset/prepared/`.

- [ ] D1: Branch is team/audio-speech tracking origin/team/audio-speech
  CHECK: git rev-parse --abbrev-ref HEAD && git status --porcelain --branch | head -1
  EXPECT: team/audio-speech
- [ ] D2: Dataset snapshot verified (RAR SHA256 matches, 6,522 extracted files)
  CHECK: find /home/hatch/workspace/ai-customer-support/dataset/extracted -type f | wc -l && sha256sum /home/hatch/workspace/ai-customer-support/dataset/dataset.rar | grep -c 3518fdd5edad615bf81fc25657f84c0ae476e41f9b31e09c8ea31995f9284e63
  EXPECT: 6522 and 1
- [ ] D3: Audit covers all 13 issues with measured numbers
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; a=json.load(open('/home/hatch/workspace/ai-customer-support/dataset/prepared/audit_summary.json')); print('AUDIT_OK' if len(a['issues'])==13 and a['files']['total']==6522 else 'AUDIT_BAD')"
  EXPECT: AUDIT_OK
- [ ] D4: Duration drift fixed (corrected inventory drift within 0.01 s)
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import pandas as pd; inv=pd.read_csv('/home/hatch/workspace/ai-customer-support/dataset/prepared/inventory_corrected.csv'); print('DRIFT_OK' if (inv['duration_s']-inv['duration_decoded_s']).abs().max()<=0.01 else 'DRIFT_BAD')"
  EXPECT: DRIFT_OK
- [ ] D5: Recovery manifest reconciles (recovered + unrecoverable == 26, every file verified)
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; m=json.load(open('/home/hatch/workspace/ai-customer-support/dataset/prepared/recovery_manifest.json')); print('RECOVERY_OK' if m['recovered']+m['unrecoverable']==26 and all(f['verified'] for f in m['files']) else 'RECOVERY_BAD')"
  EXPECT: RECOVERY_OK
- [ ] D6: Long file chunked into segments of at most 60 s
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; ch=json.load(open('/home/hatch/workspace/ai-customer-support/dataset/prepared/long_file_chunks.json')); print('CHUNK_OK' if all(s['duration_s']<=60.0 for s in ch['segments']) else 'CHUNK_BAD')"
  EXPECT: CHUNK_OK
- [ ] D7: Taxonomy proposal exists, candidates only, each with cluster evidence
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; t=json.load(open('/home/hatch/workspace/ai-customer-support/dataset/prepared/cluster_results.json')); print('TAX_OK' if sum(t['sizes'].values())==5881 else 'TAX_BAD')"
  EXPECT: TAX_OK
- [ ] D8: Annotation package exists (guide draft + 100-row calibration batch + review queue)
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; c=json.load(open('/home/hatch/workspace/ai-customer-support/dataset/prepared/calibration_batch.json')); print('ANN_OK' if len(c)==100 else 'ANN_BAD')"
  EXPECT: ANN_OK
- [ ] D9: Readiness report states both tracks, router blocked while labels are missing
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json; s=json.load(open('preparation/preparation_summary.json')); print('READY_OK' if s['tracks']['router']['status']=='blocked' and s['tracks']['router']['blockers'] else 'READY_BAD')"
  EXPECT: READY_OK
- [ ] D10: Full preparation pytest suite passes
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -m pytest preparation/test_preparation.py -q && echo PREP_TESTS_OK
  EXPECT: PREP_TESTS_OK
- [ ] D11: Canonical files unchanged (hashes match the recorded run log)
  CHECK: sha256sum -c /home/hatch/workspace/ai-customer-support/dataset/prepared/run_log_hashes.txt
  EXPECT: OK
- [ ] D12: Working tree clean (except gate evidence refresh)
  CHECK: git status --porcelain
  EXPECT: (empty)
