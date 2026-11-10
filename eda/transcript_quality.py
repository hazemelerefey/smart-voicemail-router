"""Transcript and STT quality analysis for the Smart Voicemail Router EDA.

Reads the four analysis CSVs (read-only, never copied into the repo) and
merges a "transcripts" section into eda/eda_summary.json (existing sections
preserved). All numbers are recomputed here; nothing is copied from memory.

The STT output format v1 (10 columns) is locked; this script verifies the
transcripts file carries those columns plus the dropped `prompt` column, and
recomputes `dup_text_size` from `text_norm` to verify the known defect
(3 rows where the stored value is wrong).

Usage:
    python3 eda/transcript_quality.py
"""

import csv
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CSV_DIR = Path("/home/hatch/workspace/user/files")
SUMMARY_JSON = REPO / "eda" / "eda_summary.json"

TRANSCRIPTS_CSV = CSV_DIR / "transcripts_flagged_14_4zfb.csv"
INVENTORY_CSV = CSV_DIR / "inventory_clean_13_825a.csv"
EVAL_CSV = CSV_DIR / "stt_results_12_d6z5.csv"
SAMPLE_CSV = CSV_DIR / "sample_11_laqj.csv"

LOCKED_FORMAT_COLUMNS = [
    "file", "model", "text", "text_norm", "min_avg_logprob",
    "max_no_speech_prob", "needs_review", "review_reasons",
    "dup_text_size", "error",
]

LATIN_TOKEN_RE = re.compile(r"[A-Za-z]+")


def read_csv(path: Path) -> list:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def dist(values: list) -> dict:
    vals = sorted(float(v) for v in values if v not in (None, ""))
    if not vals:
        return {"count": 0}
    qs = statistics.quantiles(vals, n=10) if len(vals) >= 10 else [vals[0], vals[-1]]
    return {
        "count": len(vals),
        "mean": round(statistics.mean(vals), 4),
        "median": round(statistics.median(vals), 4),
        "min": round(vals[0], 4),
        "max": round(vals[-1], 4),
        "p10": round(qs[0], 4),
        "p90": round(qs[8] if len(qs) > 8 else qs[-1], 4),
    }


def length_stats(texts: list) -> dict:
    words = [len(t.split()) for t in texts]
    chars = [len(t) for t in texts]
    return {
        "words": dist(words),
        "chars": dist(chars),
    }


def merge_summary(section: str, data: dict) -> None:
    summary = {}
    if SUMMARY_JSON.exists():
        summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    summary[section] = data
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    rows = read_csv(TRANSCRIPTS_CSV)
    inv_rows = read_csv(INVENTORY_CSV)
    eval_rows = read_csv(EVAL_CSV)
    sample_rows = read_csv(SAMPLE_CSV)

    flagged = [r for r in rows if r["needs_review"].strip().lower() == "true"]
    clean = [r for r in rows if r["needs_review"].strip().lower() != "true"]

    reason_combos = Counter(r["review_reasons"].strip() for r in flagged)
    reason_tokens = Counter()
    for r in flagged:
        for tok in r["review_reasons"].split(","):
            tok = tok.strip()
            if tok:
                reason_tokens[tok] += 1

    needs_review_without_reason = sum(
        1 for r in flagged if not r["review_reasons"].strip())
    review_reason_without_flag = sum(
        1 for r in clean if r["review_reasons"].strip())

    # Independent dup recount grouped by text_norm.
    group_sizes = Counter(r["text_norm"] for r in rows)
    mismatches = []
    for r in rows:
        actual = group_sizes[r["text_norm"]]
        try:
            stored = int(r["dup_text_size"])
        except (TypeError, ValueError):
            stored = None
        if stored != actual:
            mismatches.append({
                "file": r["file"],
                "stored_dup_text_size": stored,
                "actual_dup_text_size": actual,
            })
    dup_sizes = Counter(group_sizes.values())

    # Language mix: Latin-script tokens vs pure Arabic rows.
    latin_tokens = Counter()
    rows_with_latin = 0
    for r in rows:
        toks = [t.lower() for t in LATIN_TOKEN_RE.findall(r["text"] or "")]
        if toks:
            rows_with_latin += 1
            latin_tokens.update(toks)

    # Inventory cross-check on file ids.
    t_files = {r["file"] for r in rows}
    i_files = {r["file"] for r in inv_rows}
    exclude_reasons = Counter(
        (r["exclude_reason"] or "").strip() or "(kept)" for r in inv_rows)

    eval_wer = {
        "whisper-large-v3": dist([r["whisper-large-v3__wer"] for r in eval_rows]),
        "whisper-large-v3-turbo": dist([r["whisper-large-v3-turbo__wer"] for r in eval_rows]),
    }
    eval_sec = {
        "whisper-large-v3": dist([r["whisper-large-v3__sec"] for r in eval_rows]),
        "whisper-large-v3-turbo": dist([r["whisper-large-v3-turbo__sec"] for r in eval_rows]),
    }

    # Audio quality aggregates from inventory_clean.csv per-file measures
    # (rms/peak/clip/silence/snr were measured when the inventory was built;
    # this recomputes the aggregates from those per-file values).
    def fvals(rows, col):
        return [float(r[col]) for r in rows if (r.get(col) or "") != ""]

    kept_rows = [r for r in inv_rows if not (r["exclude_reason"] or "").strip()]
    audio_quality = {
        "source_file": INVENTORY_CSV.name,
        "rows": len(inv_rows),
        "kept_rows": len(kept_rows),
        "rms_db": dist(fvals(inv_rows, "rms_db")),
        "peak": dist(fvals(inv_rows, "peak")),
        "clip_pct": dist(fvals(inv_rows, "clip_pct")),
        "clip_pct_gt0": sum(1 for v in fvals(inv_rows, "clip_pct") if v > 0),
        "clip_pct_gt0_kept": sum(1 for v in fvals(kept_rows, "clip_pct") if v > 0),
        "silence_pct": dist(fvals(inv_rows, "silence_pct")),
        "silence_pct_gt50": sum(1 for v in fvals(inv_rows, "silence_pct") if v > 50),
        "snr_db": dist(fvals(inv_rows, "snr_db")),
        "snr_db_lt10": sum(1 for v in fvals(inv_rows, "snr_db") if v < 10),
        "duration_total_h": round(sum(fvals(inv_rows, "duration_s")) / 3600, 3),
        "duration_kept_h": round(sum(fvals(kept_rows, "duration_s")) / 3600, 3),
    }
    merge_summary("audio_quality", audio_quality)

    section = {
        "source_file": TRANSCRIPTS_CSV.name,
        "rows": len(rows),
        "columns_present": [c for c in LOCKED_FORMAT_COLUMNS],
        "columns_present_ok": all(
            c in (rows[0].keys() if rows else []) for c in LOCKED_FORMAT_COLUMNS),
        "extra_columns": sorted(set(rows[0].keys()) - set(LOCKED_FORMAT_COLUMNS)) if rows else [],
        "models": dict(sorted(Counter(r["model"] for r in rows).items())),
        "needs_review": len(flagged),
        "clean": len(clean),
        "needs_review_without_reason": needs_review_without_reason,
        "review_reason_without_flag": review_reason_without_flag,
        "review_reasons_combination": dict(sorted(reason_combos.items())),
        "review_reasons_token": dict(sorted(reason_tokens.items())),
        "error_non_empty": sum(1 for r in rows if (r["error"] or "").strip()),
        "empty_text": sum(1 for r in rows if not (r["text"] or "").strip()),
        "empty_text_norm": sum(1 for r in rows if not (r["text_norm"] or "").strip()),
        "prompt_values": dict(sorted(Counter((r["prompt"] or "").strip() for r in rows).items())),
        "min_avg_logprob": {
            "all": dist([r["min_avg_logprob"] for r in rows]),
            "flagged": dist([r["min_avg_logprob"] for r in flagged]),
            "clean": dist([r["min_avg_logprob"] for r in clean]),
        },
        "max_no_speech_prob": {
            "all": dist([r["max_no_speech_prob"] for r in rows]),
            "flagged": dist([r["max_no_speech_prob"] for r in flagged]),
            "clean": dist([r["max_no_speech_prob"] for r in clean]),
        },
        "text_length": length_stats([r["text"] or "" for r in rows]),
        "text_norm_length": length_stats([r["text_norm"] or "" for r in rows]),
        "dup_text_size_distribution": {str(k): v for k, v in sorted(dup_sizes.items())},
        "dup_text_size_wrong_rows": len(mismatches),
        "dup_mismatches": mismatches,
        "dup_groups": len(group_sizes),
        "largest_dup_group": max(group_sizes.values()) if group_sizes else 0,
        "language_mix": {
            "rows_with_latin_tokens": rows_with_latin,
            "rows_pure_arabic": len(rows) - rows_with_latin,
            "top_latin_tokens": dict(latin_tokens.most_common(15)),
        },
        "wer_eval_rows": len(eval_rows),
        "wer_mean": {k: v["mean"] for k, v in eval_wer.items()},
        "wer_eval": eval_wer,
        "eval_seconds": eval_sec,
        "inventory_cross_check": {
            "inventory_rows": len(inv_rows),
            "overlap_file_ids": len(t_files & i_files),
            "transcripts_only": len(t_files - i_files),
            "inventory_only": len(i_files - t_files),
            "excluded": len(i_files - t_files),
            "exclude_reasons": dict(sorted(exclude_reasons.items())),
            "is_duplicate_true": sum(
                1 for r in inv_rows if (r["is_duplicate"] or "").strip().lower() == "true"),
        },
        "sample_rows": len(sample_rows),
    }
    merge_summary("transcripts", section)
    print(f"rows={section['rows']} needs_review={section['needs_review']} "
          f"dup_wrong={section['dup_text_size_wrong_rows']} "
          f"wer_large_v3={section['wer_mean']['whisper-large-v3']} "
          f"wer_turbo={section['wer_mean']['whisper-large-v3-turbo']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
