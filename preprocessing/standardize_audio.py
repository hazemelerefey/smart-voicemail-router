"""Task 2: audio standardization + content-hash dedup.

For each train-ready file: decode with ffmpeg to 16 kHz mono s16le PCM,
SHA256 the decoded PCM (content hash, catches cross-format duplicates),
keep the first occurrence, quarantine later copies with reason
duplicate_audio. Kept files are written as 16 kHz mono WAVs via the
wave module from exactly the hashed PCM bytes.

Outputs (outside the repo):
  - dataset/preprocessed/audio_16k/<basename>.wav
  - updated dataset/preprocessed/disposition_manifest.csv
  - updated dataset/preprocessed/transcripts_clean.csv (same disposition)

Dedup decisions are made in manifest order after parallel hash
computation, so results are deterministic regardless of worker timing.
Loudness is NOT changed. A file that fails to decode stops the run
(fail loudly), EDA found 0 unreadable files.

Verification of each WAV: re-read with the wave module (sample rate,
channels, frame count == decoded PCM samples) and check file size ==
44-byte header + PCM bytes. Duration is verified against the DECODED
PCM, not the inventory duration_s: ffprobe's estimate is unreliable
for raw ADTS .aac (e.g. 0185.aac: ffprobe 7.681 s vs decoded 8.149 s),
so gating on it would reject good audio. Inventory drift is measured
and recorded in audio_decode.json instead of gated.

Also writes dataset/preprocessed/audio_decode.json: per kept file the
decoded-PCM SHA256, sample count, and duration, plus the drift-vs-
inventory summary. The pytest suite checks every WAV against it.

Run: /home/hatch/workspace/ai-customer-support/.venv-eda/bin/python preprocessing/standardize_audio.py
"""
import hashlib
import json
import subprocess
import sys
import unicodedata
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
PREP_DIR = Path("/home/hatch/workspace/ai-customer-support/dataset/preprocessed")
EXTRACTED = Path("/home/hatch/workspace/ai-customer-support/dataset/extracted")
INVENTORY_CSV = Path("/home/hatch/workspace/user/files/inventory_clean_13_825a.csv")
CLEAN_CSV = PREP_DIR / "transcripts_clean.csv"
MANIFEST_CSV = PREP_DIR / "disposition_manifest.csv"
AUDIO_16K = PREP_DIR / "audio_16k"
DECODE_JSON = PREP_DIR / "audio_decode.json"

WORKERS = 8
SAMPLE_RATE = 16000


def source_path(dataset_file):
    """Dataset file values use backslashes: 'svr-voicemail-corpus\\0001.m4a'.

    Normalize to NFD: unrar extracted accented Latin names decomposed
    (e + combining acute, e.g. 'Café Suprême' files), while the CSVs
    store them composed (NFC). NFD is identity for ASCII and Arabic, so
    normalizing every path is safe.
    """
    return EXTRACTED / unicodedata.normalize(
        "NFD", dataset_file.replace("\\", "/")
    )


def wav_path(dataset_file):
    basename = Path(dataset_file.replace("\\", "/")).name
    return AUDIO_16K / (basename + ".wav")


def decode_pcm(dataset_file):
    """Decode to 16 kHz mono s16le PCM bytes. Raises on decode failure."""
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(source_path(dataset_file)),
        "-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-",
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(
            f"ffmpeg decode failed for {dataset_file}: "
            f"{proc.stderr.decode(errors='replace')[:500]}"
        )
    return proc.stdout


def content_hash(pcm_bytes):
    return hashlib.sha256(pcm_bytes).hexdigest()


def write_wav(path, pcm_bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm_bytes)


def verify_wav(path, pcm_bytes):
    """Verify the written WAV holds exactly the decoded PCM: header
    rate/channels/frame count plus file size (44-byte header + PCM)."""
    expected_frames = len(pcm_bytes) // 2
    if path.stat().st_size != 44 + len(pcm_bytes):
        raise RuntimeError(f"{path}: file size mismatch after write")
    with wave.open(str(path), "rb") as w:
        if w.getframerate() != SAMPLE_RATE or w.getnchannels() != 1:
            raise RuntimeError(f"{path}: not 16 kHz mono")
        if w.getnframes() != expected_frames:
            raise RuntimeError(
                f"{path}: frame count {w.getnframes()} != {expected_frames}"
            )


def main():
    manifest = pd.read_csv(MANIFEST_CSV, dtype=str, encoding="utf-8")
    clean_df = pd.read_csv(CLEAN_CSV, dtype=str, encoding="utf-8")
    inventory = pd.read_csv(INVENTORY_CSV, dtype=str, encoding="utf-8-sig")
    durations = dict(zip(inventory["file"], inventory["duration_s"].astype(float)))

    train_ready = manifest[manifest["prep_status"] == "train_ready"]["file"].tolist()
    print(f"train-ready files to standardize: {len(train_ready)}")

    # Parallel hash computation; decisions made in manifest order afterwards.
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        pcms = list(pool.map(decode_pcm, train_ready))
    hashes = [content_hash(p) for p in pcms]

    seen = {}
    kept = []
    duplicates = []
    for dataset_file, pcm, h in zip(train_ready, pcms, hashes):
        if h in seen:
            duplicates.append((dataset_file, seen[h]))
        else:
            seen[h] = dataset_file
            kept.append((dataset_file, pcm))

    print(f"kept: {len(kept)}, duplicate_audio quarantined: {len(duplicates)}")
    for dup_file, first_file in duplicates:
        print(f"  duplicate: {dup_file} == {first_file}")

    AUDIO_16K.mkdir(parents=True, exist_ok=True)
    # Clear stale WAVs from any earlier partial run.
    for stale in AUDIO_16K.glob("*.wav"):
        stale.unlink()

    def write_and_verify(item):
        dataset_file, pcm = item
        out = wav_path(dataset_file)
        write_wav(out, pcm)
        verify_wav(out, pcm)
        return dataset_file

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(write_and_verify, kept))
    print(f"WAVs written and verified: {len(kept)}")

    # Decode record + inventory-drift measurement (reported, not gated).
    inv_ext = dict(zip(inventory["file"], inventory["ext"]))
    decode_record = {}
    drift_by_format = {}
    drift_gt = 0
    max_drift = 0.0
    for dataset_file, pcm in kept:
        samples = len(pcm) // 2
        dur = samples / SAMPLE_RATE
        decode_record[dataset_file] = {
            "pcm_sha256": content_hash(pcm),
            "samples": samples,
            "duration_s": round(dur, 6),
        }
        drift = abs(dur - durations[dataset_file])
        max_drift = max(max_drift, drift)
        if drift > 0.1:
            drift_gt += 1
            fmt = inv_ext[dataset_file]
            drift_by_format[fmt] = drift_by_format.get(fmt, 0) + 1
    DECODE_JSON.write_text(json.dumps({
        "files": decode_record,
        "drift_vs_inventory": {
            "gt_0.1s": drift_gt,
            "by_format": drift_by_format,
            "max_drift_s": round(max_drift, 3),
        },
    }, indent=1, sort_keys=True))
    print(f"decoded-vs-inventory drift > 0.1s: {drift_gt} files "
          f"{drift_by_format}, max {max_drift:.3f}s")
    print(f"wrote {DECODE_JSON}")

    # Update both disposition records identically (only if dedup found any).
    if duplicates:
        dup_files = {d for d, _ in duplicates}

        def mark_quarantine(df):
            df = df.copy()
            df["prep_reason"] = df["prep_reason"].fillna("")
            mask = df["file"].isin(dup_files)
            df.loc[mask, "prep_status"] = "quarantine"
            df.loc[mask, "prep_reason"] = df.loc[mask, "prep_reason"].apply(
                lambda r: (r + ";duplicate_audio") if r else "duplicate_audio"
            )
            return df

        manifest = mark_quarantine(manifest)
        clean_df = mark_quarantine(clean_df)
        manifest.to_csv(MANIFEST_CSV, index=False, encoding="utf-8",
                        lineterminator="\n")
        clean_df.to_csv(CLEAN_CSV, index=False, encoding="utf-8",
                        lineterminator="\n")
        print("manifest prep_status counts:")
        print(manifest["prep_status"].value_counts().to_string())
    else:
        print("no duplicates: manifest and cleaned CSV unchanged")
    print(f"wrote {len(kept)} WAVs to {AUDIO_16K}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
