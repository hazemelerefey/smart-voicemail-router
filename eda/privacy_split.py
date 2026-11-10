"""Privacy scan, split proposal, and figures for the SVR EDA (Phase 1).

Privacy: counts of identifier-like patterns in transcript text only
(Egyptian mobile pattern, international +20 pattern, email pattern, long
digit runs). Counts are integers only; no matched strings, no examples, no
raw text is stored anywhere. Name-like detection is not reliable from
transcripts alone and is recorded as such, not attempted.

Split: 80/10/10 train/dev/test over the 6,024 transcribed rows. Whole
text_norm groups stay on one side (no duplicate leakage), assignment is
greedy within duration-quartile x format strata, deterministic. The
per-file assignment table is written OUTSIDE the repo for Phase 2 reuse.

Figures: four aggregate PNGs in eda/figures/ (matplotlib, Agg backend).

Usage:
    python3 eda/privacy_split.py
"""

import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CSV_DIR = Path("/home/hatch/workspace/user/files")
DATASET_DIR = Path("/home/hatch/workspace/ai-customer-support/dataset")
SUMMARY_JSON = REPO / "eda" / "eda_summary.json"
INVENTORY_JSON = DATASET_DIR / "audio_inventory.json"
SPLIT_ASSIGNMENT_JSON = DATASET_DIR / "split_assignment.json"
FIGURES_DIR = REPO / "eda" / "figures"

TRANSCRIPTS_CSV = CSV_DIR / "transcripts_flagged_14_4zfb.csv"

PHONE_RE = re.compile(r"01[0-9]{9}")
INTL_PHONE_RE = re.compile(r"(?:\+20|0020)\s?1[0-9]{9}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
LONG_DIGITS_RE = re.compile(r"\d{10,}")

TARGET_SHARES = {"train": 0.8, "dev": 0.1, "test": 0.1}


def read_csv(path: Path) -> list:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def merge_summary(section: str, data: dict) -> None:
    summary = {}
    if SUMMARY_JSON.exists():
        summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    summary[section] = data
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def privacy_scan(rows: list) -> dict:
    phone = email = long_digits = intl = 0
    for r in rows:
        text = (r["text"] or "") + " " + (r["text_norm"] or "")
        if PHONE_RE.search(text):
            phone += 1
        if INTL_PHONE_RE.search(text):
            intl += 1
        if EMAIL_RE.search(text):
            email += 1
        if LONG_DIGITS_RE.search(text):
            long_digits += 1
    return {
        "rows_scanned": len(rows),
        "fields_scanned": ["text", "text_norm"],
        "phone_like_rows": phone,
        "intl_phone_like_rows": intl,
        "email_like_rows": email,
        "long_digit_run_rows": long_digits,
        "name_like_detectable": False,
        "name_like_note": (
            "Person names cannot be detected reliably from transcripts alone "
            "(no name list, dialect spellings vary); not attempted."
        ),
    }


def build_split(rows: list, durations: dict) -> tuple:
    """Greedy group-aware 80/10/10 split. Returns (summary, assignment)."""
    groups = defaultdict(list)
    for r in rows:
        groups[r["text_norm"]].append(r)

    # CSV file ids use backslashes ("...\\0001.m4a"); probed paths use
    # forward slashes. Normalize to forward slashes before joining.
    norm = lambda f: f.replace("\\", "/")
    row_durations = sorted(durations[norm(r["file"])] for r in rows if norm(r["file"]) in durations)
    q1, q2, q3 = statistics.quantiles(row_durations, n=4)

    def quartile(d: float) -> str:
        if d <= q1:
            return "Q1"
        if d <= q2:
            return "Q2"
        if d <= q3:
            return "Q3"
        return "Q4"

    group_info = []
    for text_norm, members in groups.items():
        durs = [durations[norm(m["file"])] for m in members if norm(m["file"]) in durations]
        mean_dur = statistics.mean(durs) if durs else 0.0
        ext = Counter(Path(m["file"]).suffix.lower() for m in members).most_common(1)[0][0]
        group_info.append({
            "text_norm": text_norm,
            "size": len(members),
            "mean_duration": mean_dur,
            "stratum": (quartile(mean_dur), ext),
        })
    group_info.sort(key=lambda g: (g["stratum"], -g["size"], g["text_norm"]))

    total = len(rows)
    targets = {k: round(v * total) for k, v in TARGET_SHARES.items()}
    targets["train"] += total - sum(targets.values())  # keep the sum exact
    counts = Counter()
    assignment = {}
    for g in group_info:
        # Split with the largest relative shortfall gets the group.
        split = max(
            TARGET_SHARES,
            key=lambda s: (targets[s] - counts[s]) / targets[s],
        )
        counts[split] += g["size"]
        for m in groups[g["text_norm"]]:
            assignment[m["file"]] = split

    # Verification: no text_norm group spans two sides.
    group_sides = defaultdict(set)
    for r in rows:
        group_sides[r["text_norm"]].add(assignment[r["file"]])
    leaked = sum(1 for sides in group_sides.values() if len(sides) > 1)

    per_split = {}
    for split in ("train", "dev", "test"):
        members = [r for r in rows if assignment[r["file"]] == split]
        durs = [durations[norm(r["file"])] for r in members if norm(r["file"]) in durations]
        per_split[split] = {
            "rows": len(members),
            "needs_review": sum(1 for r in members if r["needs_review"].strip().lower() == "true"),
            "duration_mean_s": round(statistics.mean(durs), 3) if durs else None,
            "duration_median_s": round(statistics.median(durs), 3) if durs else None,
            "formats": dict(sorted(Counter(Path(r["file"]).suffix.lower() for r in members).items())),
        }

    summary = {
        "method": "group-aware greedy 80/10/10: whole text_norm groups kept on one side, "
                  "ordered by (duration quartile, format) stratum, assigned to the split "
                  "with the largest relative shortfall",
        "target_shares": TARGET_SHARES,
        "target_rows": targets,
        "train": counts["train"],
        "dev": counts["dev"],
        "test": counts["test"],
        "total_rows": total,
        "leaked_duplicate_groups": leaked,
        "duration_quartiles_s": {"q1": round(q1, 3), "q2": round(q2, 3), "q3": round(q3, 3)},
        "per_split": per_split,
        "assignment_file_outside_repo": str(SPLIT_ASSIGNMENT_JSON),
    }
    return summary, assignment


def make_figures(summary: dict, rows: list) -> list:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    made = []

    audio = summary["audio"]
    hist = audio["duration_histogram"]
    fig, ax = plt.subplots()
    ax.bar(list(hist.keys()), list(hist.values()))
    ax.set_title("Audio duration distribution (6,522 files)")
    ax.set_xlabel("Duration bin")
    ax.set_ylabel("Files")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    p = FIGURES_DIR / "duration_hist.png"
    fig.savefig(p, dpi=120)
    plt.close(fig)
    made.append(p)

    flagged = [float(r["min_avg_logprob"]) for r in rows
               if r["needs_review"].strip().lower() == "true"]
    clean = [float(r["min_avg_logprob"]) for r in rows
             if r["needs_review"].strip().lower() != "true"]
    fig, ax = plt.subplots()
    ax.hist([clean, flagged], bins=30, label=["clean (5,891)", "needs review (133)"],
            stacked=True)
    ax.set_title("Transcript confidence (min_avg_logprob)")
    ax.set_xlabel("min_avg_logprob (closer to 0 = more confident)")
    ax.set_ylabel("Rows")
    ax.legend()
    fig.tight_layout()
    p = FIGURES_DIR / "confidence_hist.png"
    fig.savefig(p, dpi=120)
    plt.close(fig)
    made.append(p)

    dup = summary["duplicates"]["group_size_distribution"]
    xs = sorted((int(k) for k in dup), key=int)
    fig, ax = plt.subplots()
    ax.bar([str(x) for x in xs], [dup[str(x)] for x in xs])
    ax.set_title("Duplicate group sizes (text_norm groups, 5,872 groups)")
    ax.set_xlabel("Files sharing one normalized transcript")
    ax.set_ylabel("Groups")
    fig.tight_layout()
    p = FIGURES_DIR / "dup_size.png"
    fig.savefig(p, dpi=120)
    plt.close(fig)
    made.append(p)

    formats = audio["formats"]
    fig, ax = plt.subplots()
    ax.barh(list(formats.keys()), list(formats.values()))
    ax.set_title("Audio files by container format")
    ax.set_xlabel("Files")
    fig.tight_layout()
    p = FIGURES_DIR / "format_bar.png"
    fig.savefig(p, dpi=120)
    plt.close(fig)
    made.append(p)
    return made


def main() -> int:
    rows = read_csv(TRANSCRIPTS_CSV)
    summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))

    privacy = privacy_scan(rows)
    merge_summary("privacy", privacy)

    inv_data = json.loads(INVENTORY_JSON.read_text(encoding="utf-8"))
    durations = {r["file"]: r["duration_s"] for r in inv_data["files"]
                 if r["duration_s"] is not None}
    split_summary, assignment = build_split(rows, durations)
    merge_summary("split", split_summary)
    SPLIT_ASSIGNMENT_JSON.write_text(
        json.dumps({"assignment": assignment}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    made = make_figures(summary, rows)
    print(f"phone_like={privacy['phone_like_rows']} email_like={privacy['email_like_rows']} "
          f"split train/dev/test={split_summary['train']}/{split_summary['dev']}/{split_summary['test']} "
          f"leaked={split_summary['leaked_duplicate_groups']} "
          f"figures={len(made)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
