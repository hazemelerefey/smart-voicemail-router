"""Audio inventory probe for the Smart Voicemail Router EDA (Phase 1).

Probes every extracted audio file with ffprobe (format, codec, duration,
sample rate, channels). Writes the per-file table OUTSIDE the repo to
~/workspace/ai-customer-support/dataset/audio_inventory.json and merges the
aggregate section into eda/eda_summary.json (existing sections preserved).

Usage:
    python3 eda/audio_inventory.py [--workers N]
"""

import argparse
import json
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATASET_DIR = Path("/home/hatch/workspace/ai-customer-support/dataset")
EXTRACTED_DIR = DATASET_DIR / "extracted"
INVENTORY_JSON = DATASET_DIR / "audio_inventory.json"
SUMMARY_JSON = REPO / "eda" / "eda_summary.json"

DURATION_BINS = [
    (0, 2, "0-2s"),
    (2, 4, "2-4s"),
    (4, 6, "4-6s"),
    (6, 8, "6-8s"),
    (8, 10, "8-10s"),
    (10, 15, "10-15s"),
    (15, 30, "15-30s"),
    (30, 60, "30-60s"),
    (60, float("inf"), "60s+"),
]


def probe_file(path: Path) -> dict:
    """Probe one audio file with ffprobe; never raises, records failures."""
    rel = str(path.relative_to(EXTRACTED_DIR))
    row = {
        "file": rel,
        "ext": path.suffix.lower(),
        "format": None,
        "codec": None,
        "duration_s": None,
        "sample_rate": None,
        "channels": None,
        "error": None,
    }
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels",
        "-show_entries", "format=format_name,duration",
        "-of", "json", str(path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        row["error"] = "ffprobe timeout after 30s"
        return row
    if proc.returncode != 0:
        row["error"] = (proc.stderr or "ffprobe failed").strip()[:300]
        return row
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        row["error"] = f"unparsable ffprobe output: {exc}"
        return row
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    stream = streams[0] if streams else {}
    if not streams:
        row["error"] = "no audio stream found"
        return row
    try:
        row["duration_s"] = float(fmt["duration"])
    except (KeyError, TypeError, ValueError):
        row["error"] = "missing duration"
        return row
    row["format"] = fmt.get("format_name")
    row["codec"] = stream.get("codec_name")
    try:
        row["sample_rate"] = int(stream["sample_rate"])
    except (KeyError, TypeError, ValueError):
        row["sample_rate"] = None
    try:
        row["channels"] = int(stream["channels"])
    except (KeyError, TypeError, ValueError):
        row["channels"] = None
    return row


def summarize(rows: list) -> dict:
    from collections import Counter

    durations = [r["duration_s"] for r in rows if r["duration_s"] is not None]
    unreadable = sorted(r["file"] for r in rows if r["error"] is not None)
    hist = {label: 0 for _, _, label in DURATION_BINS}
    for d in durations:
        for lo, hi, label in DURATION_BINS:
            if lo <= d < hi:
                hist[label] += 1
                break
    return {
        "total_files": len(rows),
        "formats": dict(sorted(Counter(r["ext"] for r in rows).items())),
        "total_duration_s": round(sum(durations), 3),
        "total_duration_h": round(sum(durations) / 3600, 3),
        "duration_stats": {
            "min_s": round(min(durations), 3),
            "max_s": round(max(durations), 3),
            "mean_s": round(statistics.mean(durations), 3),
            "median_s": round(statistics.median(durations), 3),
            "p10_s": round(statistics.quantiles(durations, n=10)[0], 3),
            "p90_s": round(statistics.quantiles(durations, n=10)[8], 3),
        },
        "sample_rates": {str(k): v for k, v in sorted(
            Counter(r["sample_rate"] for r in rows if r["sample_rate"] is not None).items())},
        "channels": {str(k): v for k, v in sorted(
            Counter(r["channels"] for r in rows if r["channels"] is not None).items())},
        "codecs": dict(sorted(Counter(r["codec"] for r in rows if r["codec"]).items())),
        "unreadable": unreadable,
        "unreadable_count": len(unreadable),
        "duration_histogram": hist,
    }


def merge_summary(section: str, data: dict) -> None:
    summary = {}
    if SUMMARY_JSON.exists():
        summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    summary[section] = data
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    files = sorted(p for p in EXTRACTED_DIR.rglob("*") if p.is_file())
    print(f"probing {len(files)} files with {args.workers} workers ...", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(probe_file, files))
    rows.sort(key=lambda r: r["file"])
    aggregate = summarize(rows)
    INVENTORY_JSON.write_text(
        json.dumps({"aggregate": aggregate, "files": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    merge_summary("audio", aggregate)
    print(f"total_files={aggregate['total_files']} "
          f"total_duration_h={aggregate['total_duration_h']} "
          f"unreadable={aggregate['unreadable_count']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
