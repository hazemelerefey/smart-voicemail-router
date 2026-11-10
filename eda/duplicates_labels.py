"""Duplicates, near-duplicates, and labels gap for the SVR EDA (Phase 1).

Groups transcripts by text_norm (counts and group sizes only, never the
transcript text), checks audio-level exact duplicates by (file size,
probed duration) collisions from the extracted audio, and counts non-empty
category/sentiment values in every CSV that carries label columns.
Merges "duplicates" and "labels" sections into eda/eda_summary.json
(existing sections preserved). No labels are assigned here.

Usage:
    python3 eda/duplicates_labels.py
"""

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CSV_DIR = Path("/home/hatch/workspace/user/files")
DATASET_DIR = Path("/home/hatch/workspace/ai-customer-support/dataset")
EXTRACTED_DIR = DATASET_DIR / "extracted"
SUMMARY_JSON = REPO / "eda" / "eda_summary.json"
INVENTORY_JSON = DATASET_DIR / "audio_inventory.json"

TRANSCRIPTS_CSV = CSV_DIR / "transcripts_flagged_14_4zfb.csv"
INVENTORY_CSV = CSV_DIR / "inventory_clean_13_825a.csv"
EVAL_CSV = CSV_DIR / "stt_results_12_d6z5.csv"
SAMPLE_CSV = CSV_DIR / "sample_11_laqj.csv"

LABEL_COLUMNS = ["category_label", "sentiment_label"]


def read_csv(path: Path) -> list:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def non_empty_count(rows: list, column: str) -> int:
    return sum(1 for r in rows if (r.get(column) or "").strip())


def merge_summary(section: str, data: dict) -> None:
    summary = {}
    if SUMMARY_JSON.exists():
        summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    summary[section] = data
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    t_rows = read_csv(TRANSCRIPTS_CSV)
    inv_rows = read_csv(INVENTORY_CSV)
    eval_rows = read_csv(EVAL_CSV)
    sample_rows = read_csv(SAMPLE_CSV)

    # Exact text duplicates: groups keyed by normalized transcript text.
    groups = defaultdict(list)
    for r in t_rows:
        groups[r["text_norm"]].append(r["file"])
    sizes = sorted((len(v) for v in groups.values()), reverse=True)
    multi = [s for s in sizes if s > 1]
    ext_per_group = defaultdict(set)
    for r in t_rows:
        ext_per_group[r["text_norm"]].add(Path(r["file"]).suffix.lower())
    multi_ext_groups = sum(1 for v in ext_per_group.values() if len(v) > 1)

    # Audio-level exact duplicates: (file size in bytes, probed duration).
    inv_data = json.loads(INVENTORY_JSON.read_text(encoding="utf-8"))
    durations = {r["file"]: r["duration_s"] for r in inv_data["files"]}
    size_duration = Counter()
    for rel, dur in durations.items():
        path = EXTRACTED_DIR / rel
        try:
            size = path.stat().st_size
        except OSError:
            continue
        size_duration[(size, round(dur, 3))] += 1
    collision_groups = sum(1 for c in size_duration.values() if c > 1)
    files_in_collisions = sum(c for c in size_duration.values() if c > 1)

    # Inventory md5-based duplicate flag, for comparison.
    inv_dup_flag = sum(
        1 for r in inv_rows if (r["is_duplicate"] or "").strip().lower() == "true")

    duplicates = {
        "total_text_norm_groups": len(groups),
        "groups_size_gt1": len(multi),
        "rows_in_duplicate_groups": sum(multi),
        "largest_text_norm_group": sizes[0] if sizes else 0,
        "largest_group_sizes": sizes[:10],
        "group_size_distribution": {str(k): v for k, v in sorted(Counter(sizes).items())},
        "duplicate_groups_spanning_multiple_formats": multi_ext_groups,
        "audio_size_duration_collisions": {
            "collision_groups": collision_groups,
            "files_in_collisions": files_in_collisions,
            "method": "(file size bytes, probed duration rounded to 3 decimals)",
        },
        "inventory_is_duplicate_flag_true": inv_dup_flag,
    }

    labels = {
        "columns_checked": {},
        "category_non_empty": 0,
        "sentiment_non_empty": 0,
    }
    for name, rows in [
        ("transcripts_flagged_14_4zfb.csv", t_rows),
        ("inventory_clean_13_825a.csv", inv_rows),
        ("stt_results_12_d6z5.csv", eval_rows),
        ("sample_11_laqj.csv", sample_rows),
    ]:
        present = [c for c in LABEL_COLUMNS if rows and c in rows[0]]
        counts = {c: non_empty_count(rows, c) for c in present}
        labels["columns_checked"][name] = {
            "label_columns_present": present,
            "non_empty": counts,
        }
        labels["category_non_empty"] += counts.get("category_label", 0)
        labels["sentiment_non_empty"] += counts.get("sentiment_label", 0)

    merge_summary("duplicates", duplicates)
    merge_summary("labels", labels)
    print(f"dup_groups={duplicates['total_text_norm_groups']} "
          f"largest={duplicates['largest_text_norm_group']} "
          f"size_duration_collisions={collision_groups} "
          f"category_non_empty={labels['category_non_empty']} "
          f"sentiment_non_empty={labels['sentiment_non_empty']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
