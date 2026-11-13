"""Import the 100-row calibration batch into Label Studio project SVR calibration.

Usage (from the repo root, with the Label Studio server running):
    LABEL_STUDIO_URL=http://127.0.0.1:8080 LABEL_STUDIO_API_KEY=<admin token> \
        /home/hatch/workspace/ai-customer-support/.venv-labelstudio/bin/python \
        preparation/import_calibration.py

Reads the batch file IDs from dataset/prepared/calibration_batch.json,
joins each ID to its transcript in dataset/preprocessed/transcripts_clean.csv
and its audio. Train-ready rows use the standardized 16 kHz WAV in
dataset/preprocessed/audio_16k/. The 10 flagged rows have no standardized
WAV (they are quarantined, not train-ready), so they use the raw extracted
audio in dataset/extracted/. Audio is served by Label Studio from the
local-files document root, so task audio values are /data/local-files/?d=
paths relative to the dataset directory.

Writes a receipt to dataset/prepared/labeling_import.json (outside the
repo): project id, project title, imported task count, and the config
checksum. Re-running the import creates a second copy of the tasks, so
run it once; the receipt is the guard.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

DATASET = Path("/home/hatch/workspace/ai-customer-support/dataset")
REPO = Path("/home/hatch/workspace/ai-customer-support/smart-voicemail-router")
PROJECT_TITLE = "SVR calibration"


def wav_name(file_id: str) -> str:
    return os.path.basename(file_id.replace("\\", "/")) + ".wav"


def build_tasks():
    batch = json.loads((DATASET / "prepared" / "calibration_batch.json").read_text())
    assert len(batch) == 100, f"calibration batch has {len(batch)} rows, expected 100"
    import pandas as pd

    df = pd.read_csv(DATASET / "preprocessed" / "transcripts_clean.csv",
                     usecols=["file", "text"])
    texts = dict(zip(df["file"], df["text"]))
    tasks = []
    for row in batch:
        file_id = row["file"]
        assert file_id in texts, f"no transcript for {file_id}"
        wav = wav_name(file_id)
        wav_path = DATASET / "preprocessed" / "audio_16k" / wav
        if wav_path.exists():
            audio = f"/data/local-files/?d=preprocessed/audio_16k/{wav}"
        else:
            raw_path = DATASET / "extracted" / file_id.replace("\\", "/")
            assert raw_path.exists(), f"no audio for {file_id}"
            audio = f"/data/local-files/?d=extracted/{file_id.replace(chr(92), '/')}"
        tasks.append({"data": {
            "audio": audio,
            "text": texts[file_id],
            "file_id": file_id,
        }})
    return tasks


def main():
    from label_studio_sdk import Client

    url = os.environ.get("LABEL_STUDIO_URL", "http://127.0.0.1:8080")
    api_key = os.environ["LABEL_STUDIO_API_KEY"]
    config = (REPO / "preparation" / "labeling_config.xml").read_text()
    receipt_path = DATASET / "prepared" / "labeling_import.json"
    if receipt_path.exists():
        print(f"receipt already exists at {receipt_path}; refusing a second import")
        sys.exit(1)
    tasks = build_tasks()
    ls = Client(url=url, api_key=api_key)
    project = ls.start_project(title=PROJECT_TITLE, label_config=config)
    project.import_tasks(tasks)
    receipt = {
        "project_id": project.id,
        "project_title": PROJECT_TITLE,
        "imported_tasks": len(tasks),
        "config_sha256": hashlib.sha256(config.encode()).hexdigest(),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2))
    print(f"project {project.id} '{PROJECT_TITLE}': imported {len(tasks)} tasks")


if __name__ == "__main__":
    main()
