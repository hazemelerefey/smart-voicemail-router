"""Tests for the Label Studio labeling setup (project SVR calibration).

Requires the Label Studio server running on 127.0.0.1:8080 with the
calibration project imported. The admin API key is read from
LABEL_STUDIO_API_KEY, or from the Label Studio sqlite database
(authtoken_token table, admin user) when the variable is unset.
"""

import json
import os
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATASET = Path("/home/hatch/workspace/ai-customer-support/dataset")
LS_DIR = Path("/home/hatch/workspace/ai-customer-support/label-studio")
URL = os.environ.get("LABEL_STUDIO_URL", "http://127.0.0.1:8080")

EXPECTED = {
    "complaint_category": [
        "network_and_connectivity", "billing_and_charges", "balance_and_data",
        "app_and_account", "branch_and_staff", "no_reply_or_long_wait",
        "cancellation_request", "thanks_or_praise", "greeting_only", "other",
    ],
    "complaint_urgency": ["high", "medium", "low"],
    "customer_state": ["calm", "frustrated", "mad", "satisfied", "unclear"],
    "churn_risk": ["at_risk", "not_at_risk"],
}


def api_key():
    key = os.environ.get("LABEL_STUDIO_API_KEY")
    if key:
        return key
    db = LS_DIR / "label_studio.sqlite3"
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT t.key FROM authtoken_token t JOIN htx_user u ON u.id = t.user_id "
        "WHERE u.email = 'admin@svr.local'"
    ).fetchone()
    con.close()
    assert row, "no admin API token in the Label Studio database"
    return row[0]


def api_get(path):
    req = urllib.request.Request(
        URL + path, headers={"Authorization": f"Token {api_key()}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def calibration_project():
    projects = api_get("/api/projects/")
    matches = [p for p in projects["results"]
               if p["title"] == "SVR calibration"]
    assert matches, "no Label Studio project titled 'SVR calibration'"
    return matches[0]


def test_config_values():
    root = ET.parse(REPO / "preparation" / "labeling_config.xml").getroot()
    found = {}
    for choices in root.iter("Choices"):
        name = choices.get("name")
        found[name] = [c.get("value") for c in choices.iter("Choice")]
        assert choices.get("choice") == "single", f"{name} is not single choice"
        assert choices.get("required") == "true", f"{name} is not required"
    assert found == EXPECTED, f"config values differ: {found}"


def test_server_responds():
    with urllib.request.urlopen(URL + "/", timeout=30) as resp:
        assert resp.status == 200


def test_calibration_import_count():
    project = calibration_project()
    assert project["task_number"] == 100, (
        f"project has {project['task_number']} tasks, expected 100")


def test_task_data_complete():
    project = calibration_project()
    payload = api_get(f"/api/projects/{project['id']}/tasks/?page_size=5")
    tasks = payload if isinstance(payload, list) else payload["results"]
    assert len(tasks) == 5
    for task in tasks:
        data = task["data"]
        assert data["audio"].startswith("/data/local-files/?d="), data["audio"]
        assert data["text"].strip(), f"empty transcript for {data['file_id']}"
        assert data["file_id"]
        rel = data["audio"].split("?d=", 1)[1]
        assert (DATASET / rel).exists(), f"audio file missing: {rel}"
