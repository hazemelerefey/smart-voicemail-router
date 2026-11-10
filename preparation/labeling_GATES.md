# Gates: Label Studio labeling setup (audio-speech pair)

Scope: Label Studio 1.23.2 on this VM (port 8080, localhost only), project
SVR calibration with the 100-row calibration batch imported, accounts
admin + hazem + ebtihal, taxonomy approved 2026-11-11, annotators Hazem
and Ebtihal. Docs: preparation/taxonomy_proposal.md (approved),
preparation/annotation_guide_draft.md (approved guide v1), labeling
config preparation/labeling_config.xml, import script
preparation/import_calibration.py, tests preparation/test_labeling.py.

- [ ] L1: Branch is team/audio-speech tracking origin/team/audio-speech
  CHECK: git rev-parse --abbrev-ref HEAD
  EXPECT: team/audio-speech
- [ ] L2: Label Studio installed in the dedicated venv, version 1.23.2
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-labelstudio/bin/python -c "import label_studio; print(label_studio.__version__)"
  EXPECT: 1.23.2
- [ ] L3: Labeling config holds all approved values (10 categories, 3 urgency, 5 state, 2 churn)
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import xml.etree.ElementTree as ET; r=ET.parse('preparation/labeling_config.xml').getroot(); f={c.get('name'): [x.get('value') for x in c.iter('Choice')] for c in r.iter('Choices')}; print('CONFIG_OK' if f=={'complaint_category': ['network_and_connectivity', 'billing_and_charges', 'balance_and_data', 'app_and_account', 'branch_and_staff', 'no_reply_or_long_wait', 'cancellation_request', 'thanks_or_praise', 'greeting_only', 'other'], 'complaint_urgency': ['high', 'medium', 'low'], 'customer_state': ['calm', 'frustrated', 'mad', 'satisfied', 'unclear'], 'churn_risk': ['at_risk', 'not_at_risk']} else 'CONFIG_BAD')"
  EXPECT: CONFIG_OK
- [ ] L4: Calibration project holds exactly 100 imported tasks (live server check)
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json, sqlite3, urllib.request; c=sqlite3.connect('/home/hatch/workspace/ai-customer-support/label-studio/label_studio.sqlite3'); k=c.execute('SELECT key FROM authtoken_token WHERE user_id=1').fetchone()[0]; q=urllib.request.Request('http://127.0.0.1:8080/api/projects/', headers={'Authorization': 'Token '+k}); d=json.loads(urllib.request.urlopen(q, timeout=30).read()); p=[x for x in d['results'] if x['title']=='SVR calibration']; print('IMPORT_OK' if p and p[0]['task_number']==100 else 'IMPORT_BAD')"
  EXPECT: IMPORT_OK
- [ ] L5: Label Studio server responds on port 8080
  CHECK: curl -s -L -o /dev/null -w "%{http_code}" --max-time 10 http://127.0.0.1:8080/
  EXPECT: 200
- [ ] L6: Working tree clean (except gate evidence refresh)
  CHECK: test $(git status --porcelain | wc -l) -eq 0 && echo TREE_CLEAN
  EXPECT: TREE_CLEAN
