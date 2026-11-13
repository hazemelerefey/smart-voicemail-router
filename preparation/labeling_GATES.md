# Gates: Label Studio labeling setup (audio-speech pair)

Scope: Label Studio 1.23.2 on this VM (port 8080, localhost only), project
SVR calibration with the 100-row calibration batch imported, accounts
admin + hazem + ebtihal, taxonomy approved 2026-11-11, annotators Hazem
and Ebtihal. Docs: preparation/taxonomy_proposal.md (approved),
preparation/annotation_guide_draft.md (approved guide v1), labeling
config preparation/labeling_config.xml, import script
preparation/import_calibration.py, tests preparation/test_labeling.py.

- [x] L1: Branch is team/audio-speech tracking origin/team/audio-speech
  CHECK: git rev-parse --abbrev-ref HEAD
  EXPECT: team/audio-speech
  EVIDENCE: automatic-evidence=v1; definition-sha256=f5b4b04e85486130d52daae72b92e8f3bf5678dc04d0938a5034eba2028baca4; exit=0; EXPECT=matched; output-sha256=9217a5d3067b45d4b9e16da00124d9d5d57163468c00275c6191e54c832621bd; output-bytes=18; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
- [x] L2: Label Studio installed in the dedicated venv, version 1.23.2
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-labelstudio/bin/python -c "import label_studio; print(label_studio.__version__)"
  EXPECT: 1.23.2
  EVIDENCE: automatic-evidence=v1; definition-sha256=b1e97bf78a182bc9786a4149d2582cd53031beade8049fb25db00567574c3581; exit=0; EXPECT=matched; output-sha256=48d625eaf5c6c9ce0c6890c697201fd6087c6147773feb8ca9a85e4f8004e79f; output-bytes=7; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
- [x] L3: Labeling config holds all approved values (10 categories, 3 urgency, 5 state, 2 churn)
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import xml.etree.ElementTree as ET; r=ET.parse('preparation/labeling_config.xml').getroot(); f={c.get('name'): [x.get('value') for x in c.iter('Choice')] for c in r.iter('Choices')}; print('CONFIG_OK' if f=={'complaint_category': ['network_and_connectivity', 'billing_and_charges', 'balance_and_data', 'app_and_account', 'branch_and_staff', 'no_reply_or_long_wait', 'cancellation_request', 'thanks_or_praise', 'greeting_only', 'other'], 'complaint_urgency': ['high', 'medium', 'low'], 'customer_state': ['calm', 'frustrated', 'mad', 'satisfied', 'unclear'], 'churn_risk': ['at_risk', 'not_at_risk']} else 'CONFIG_BAD')"
  EXPECT: CONFIG_OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=9dd26039be162e045a308c3b474cbf6e987d8b075c1e15a0cf3f55761078dfb3; exit=0; EXPECT=matched; output-sha256=4d939306a112cc72aeb5596651d4e6a3e0af29b6c457f4ac9658fe803a472645; output-bytes=10; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
- [x] L4: Calibration project holds exactly 100 imported tasks (live server check)
  CHECK: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python -c "import json, sqlite3, urllib.request; c=sqlite3.connect('/home/hatch/workspace/ai-customer-support/label-studio/label_studio.sqlite3'); k=c.execute('SELECT key FROM authtoken_token WHERE user_id=1').fetchone()[0]; q=urllib.request.Request('http://127.0.0.1:8080/api/projects/', headers={'Authorization': 'Token '+k}); d=json.loads(urllib.request.urlopen(q, timeout=30).read()); p=[x for x in d['results'] if x['title']=='SVR calibration']; print('IMPORT_OK' if p and p[0]['task_number']==100 else 'IMPORT_BAD')"
  EXPECT: IMPORT_OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=392594743be8728cc6e4593384248a871be10d5931ef750354a8e73aa8f0bd8b; exit=0; EXPECT=matched; output-sha256=182210181d1cc69014904c7de328d3ef941c366c24c9e594b5a4a9d4f25a6c5d; output-bytes=10; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
- [x] L5: Label Studio server responds on port 8080
  CHECK: curl -s -L -o /dev/null -w "%{http_code}" --max-time 10 http://127.0.0.1:8080/
  EXPECT: 200
  EVIDENCE: automatic-evidence=v1; definition-sha256=38e84fe2f1645904daa103dafa91c12ff205d70d0a71a1eca228334dafb42cf3; exit=0; EXPECT=matched; output-sha256=27badc983df1780b60c2b3fa9d3a19a00e46aac798451f0febdca52920faaddf; output-bytes=3; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
- [x] L6: Working tree clean (except gate evidence refresh)
  CHECK: test $(git status --porcelain | wc -l) -eq 0 && echo TREE_CLEAN
  EXPECT: TREE_CLEAN
  EVIDENCE: automatic-evidence=v1; definition-sha256=1308d9fdb20dad22a4ea6fad49cab7bcb390041ba2ed381e9409b18e880110ce; exit=0; EXPECT=matched; output-sha256=aae759e7feba7044a7768be621e4903bc475dc06185d754ee91c532cd54ad749; output-bytes=11; shell=/bin/sh; cwd=/home/hatch/workspace/ai-customer-support/smart-voicemail-router; path=47e26463d816/21 entries
