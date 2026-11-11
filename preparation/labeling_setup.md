# Label Studio setup (SVR calibration)

## Service

- Label Studio 1.23.2, dedicated venv `~/workspace/ai-customer-support/.venv-labelstudio`
- Data dir `~/workspace/ai-customer-support/label-studio`
- Start script `~/workspace/ai-customer-support/label-studio/start.sh`
- Port 8080. The build binds 0.0.0.0:8080 despite `--host 127.0.0.1`; it is reachable on the VM tailnet IP, not on the public internet.
- VM tailnet IP: 100.66.238.35. Reach it from a tailnet member at `http://100.66.238.35:8080`.
- Restart: run the start script with nohup after a VM replacement. There is no user systemd bus in this environment, so no service unit.
- Telemetry off: `COLLECT_ANALYTICS=false` in start.sh. No Sentry DSN is configured. Two telemetry approvals stayed pending and were never granted, so no data left the machine.

## Project

- Project "SVR calibration", 100 tasks, all from the calibration batch.
- Config `preparation/labeling_config.xml`: audio + transcript + file_id + notes, and four required single-choice fields (category 10, urgency 3, state 5, churn 2).
- Import script `preparation/import_calibration.py`.

## Accounts

- admin@svr.local (admin, password in the database only, reset with `label-studio reset_password --username admin@svr.local`)
- hazem@svr.local (username hazem), ebtihal@svr.local (username ebtihal)
- The two annotator accounts were created without passwords. They cannot log in until a password is set, by invite link or CLI reset, once the tailnet link is verified.
- No password value is written anywhere in this repo or in any report.

## Gaps

- Tailnet reachability from Hazem's phone is not yet verified; the check needs his approval of the pending tunnel request.
- Ebtihal's route to the server is unknown; she needs tailnet access or another path Hazem provides.
- The server does not survive a VM replacement; restart it with start.sh.
