"""Capture an authorized Phase 2 reproduction without persisting transcript text."""
import argparse
from collections import Counter
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
from unittest.mock import patch

OUT = Path(__file__).resolve().parent
SEEDS = (7, 42, 99, 1337, 2023)
NOTEBOOK = Path("notebooks/triage-routing/triage_routing_phase2.ipynb")
HISTORY = Path("reports/triage-routing")
ARCHIVE = [HISTORY / f"phase2-real-validation.{ext}" for ext in ("md", "csv", "json")]

def utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def digest(data):
    return hashlib.sha256(data).hexdigest()

def save(name, data):
    if not isinstance(data, bytes):
        data = (json.dumps(data, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()
    with (OUT / name).open("xb") as stream:
        stream.write(data)
    return {"file": name, "sha256": digest(data), "size_bytes": len(data)}

def log(name, action, **fields):
    with (OUT / name).open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({"timestamp_utc": utc(), "event": action, **fields}) + "\n")
        stream.flush()

def git(*args):
    return subprocess.check_output(["git", "--no-optional-locks", *args], text=True).strip()

def projection(report):
    return dict(report, records=[{key: value for key, value in row.items() if key != "transcript"}
                                 for row in report["records"]])

def recompute(seed, approved, baseline):
    saved = json.loads((OUT / f"seed-{seed}-result.json").read_bytes())
    report = saved["result"]
    rows = report["records"]
    ledger = report["rejected_submitted_occurrences"]
    assert all("transcript" not in row for row in rows)
    keys = {("val", row["audio_file"]) for row in rows}
    rejected = {tuple(item["key"]) for item in ledger if item["key"] is not None}
    indexes = [row["row_index"] for row in rows] + [item["source_index"] for item in ledger]
    assert sorted(indexes) == list(range(len(indexes)))
    assert len(keys) == len(rows) and keys <= approved and not keys & rejected
    missing = approved - keys - rejected
    assert {tuple(key) for key in report["manifest_reconciliation"]["missing_keys"]} == missing
    statuses = Counter(row["decision"]["assignment_status"] for row in rows)
    assert set(statuses) <= {"assigned", "unassigned"}
    assigned, unassigned, invalid = statuses["assigned"], statuses["unassigned"], len(rejected & approved)
    assert assigned + unassigned + invalid + len(missing) == len(approved) == 1003
    assert saved["agent_state"]["before"] == saved["agent_state"]["after"] == baseline
    assert saved["agent_state"]["release_calls"] == assigned
    for ticket, row in zip(saved["ticket_audit"], rows, strict=True):
        assert ticket["voicemail_id"] == row["voicemail_id"]
        assert ticket["agent_id"] == row["decision"]["assigned_agent_id"]
        assert ticket["releases"] == int(row["decision"]["assignment_status"] == "assigned")
        assert ticket["pre_routing_review"] == (ticket["confidence"] < report["review_threshold"])
        assert row["human_review"] == (ticket["pre_routing_review"] or ticket["agent_id"] is None)
    values = {
        "approved_rows": len(approved), "assigned": assigned, "valid_routing_unassigned": unassigned,
        "invalid_approved": invalid, "missing_approved": len(missing), "rejected_occurrences": len(ledger),
        "input_coverage": len(rows) / len(indexes), "manifest_coverage": len(rows) / len(approved),
        "assignment_rate": assigned / len(approved), "human_review": sum(row["human_review"] for row in rows),
    }
    fields = ("assignment_rate_denominator", "assigned_count", "routing_unassigned_count",
              "invalid_approved_rows", "missing_approved_rows", "invalid_rows", "input_coverage_rate",
              "approved_validation_coverage_rate", "assignment_rate", "human_review_count")
    assert list(values.values()) == [report[field] for field in fields]
    return values

def main(authorization):
    if not __debug__:
        raise RuntimeError("Assertions must be enabled")
    with (OUT / "run.jsonl").open("x", encoding="utf-8"):
        pass
    log("run.jsonl", "run_started", reproduction_id=OUT.name)
    stage = "source_capture"
    try:
        relative = OUT.relative_to(Path.cwd()).as_posix()
        head = git("rev-parse", "HEAD")
        branch = git("branch", "--show-current")
        status = git("status", "--porcelain=v1", "--untracked-files=all", "--",
                     ".", f":(exclude){relative}/**").splitlines()
        historical = {p.as_posix(): digest(p.read_bytes()) for p in ARCHIVE}
        notebook = NOTEBOOK.read_bytes()
        cells = {cell["id"]: "".join(cell["source"]) for cell in json.loads(notebook)["cells"]}
        for info in (save("runner-source.ipynb", notebook),
                     save("adapter-code.py", cells["cell-5"].encode("utf-8"))):
            log("run.jsonl", "artifact_written", **info)
        scope = {"__name__": "__main__"}
        stage = "synthetic_preflight"
        with redirect_stdout(io.StringIO()):
            for cell in ("cell-2", "cell-5", "cell-9"):
                exec(compile(cells[cell], cell, "exec"), scope)
        counts = scope["TEST_COUNTS"]
        assert counts == {"passed": 67, "failed": 0, "error": 0, "skipped": 0}
        snapshot = scope["snapshot"]
        baseline = snapshot()
        assert baseline == scope["BASELINE"]
        log("run.jsonl", "synthetic_preflight_completed", counts=counts, agent_state_restored=True)
        stage = "authorized_validation"
        authenticated, manifest_info, approved = {}, {}, set()
        agents = scope["agents"]
        original_artifact, original_manifest, original_seed, original_reader, original_triage = (
            scope[name] for name in ("authenticated_artifact", "authenticated_manifest", "_run_validation_seed",
                                     "read_predictions_file", "triage_phase1"))
        original_release = agents.release

        def observe_artifact(relative):
            log("run.jsonl", "artifact_authentication_started", relative_path=relative)
            path, payload = original_artifact(relative)
            info = {"path": path.as_posix(), "sha256": digest(payload), "size_bytes": len(payload)}
            assert info["sha256"] == scope["APPROVED_ARTIFACT_SHA256"][relative]
            authenticated[relative] = info
            log("run.jsonl", "artifact_authenticated", **info)
            return path, payload

        def observe_manifest(payload):
            log("run.jsonl", "manifest_identity_check_started")
            rows = original_manifest(payload)
            approved.update(scope["validation_manifest_keys"](rows))
            manifest_info.update(manifest_file_path=authenticated[scope["TRANSCRIPT_SOURCE"]]["path"],
                                 manifest_sha256=digest(payload), manifest_git_blob=scope["APPROVED_MANIFEST_BLOB"])
            log("run.jsonl", "manifest_verified", **manifest_info,
                revision=scope["APPROVED_MANIFEST_REVISION"], approved_rows=len(approved))
            return rows

        def observe_seed(payload, **options):
            seed = options["seed"]
            name = f"seed-{seed}.jsonl"
            before, started = snapshot(), utc()
            assert before == baseline
            file_key = f"{scope['APPROVED_PREDICTIONS_DIR']}/predictions_val_seed{seed}.json"
            log(name, "seed_started", seed=seed, started_at_utc=started,
                authenticated_input=authenticated[file_key], manifest=manifest_info,
                manifest_revision=scope["APPROVED_MANIFEST_REVISION"])
            log("run.jsonl", "seed_started", seed=seed, log_file=name)
            reader_counts, tickets = Counter(), []
            pending, releases = None, 0

            def reader(*args, **kwargs):
                assert kwargs["expected_split"] == "val"
                assert args[1] == scope["EXPORT_CLASSES"]
                reader_counts["calls"] += 1
                try:
                    result = original_reader(*args, **kwargs)
                except scope["PredictionsFileError"]:
                    reader_counts["rejected"] += 1
                    raise
                reader_counts["accepted"] += 1
                return result

            def triage(text):
                nonlocal pending
                assert pending is None
                decision = original_triage(text)
                item = {"voicemail_id": text.voicemail_id, "agent_id": decision.assigned_agent_id,
                        "confidence": text.confidence, "pre_routing_review": text.needs_human_review,
                        "predicted_labels": {name: getattr(text, name).value for name in scope["LABEL_MAP"].values()},
                        "releases": 0}
                tickets.append(item)
                if decision.assigned_agent_id is not None:
                    pending = item
                return decision

            def release(agent_id):
                nonlocal pending, releases
                result = original_release(agent_id)
                releases += 1
                if pending is not None:
                    assert pending["agent_id"] == agent_id and pending["releases"] == 0
                    pending["releases"] += 1
                    pending = None
                return result

            try:
                with (patch.dict(scope, {"read_predictions_file": reader, "triage_phase1": triage}),
                      patch.object(agents, "release", release)):
                    report = original_seed(payload, **options)
                after = snapshot()
                assert after == before and pending is None
                assert releases == report["assigned_count"] == sum(row["releases"] for row in tickets)
                assert reader_counts["calls"] == reader_counts["accepted"] + reader_counts["rejected"]
                assert reader_counts["rejected"] == sum(
                    row["stage"] == "official_reader" for row in report["rejected_submitted_occurrences"])
                result = projection(report)
                # The authorized entry point appends these same verified fields immediately after return.
                result["provenance"] = dict(result["provenance"], **manifest_info)
                completed = utc()
                info = save(f"seed-{seed}-result.json", {
                    "audit_schema_version": 1, "reproduction_id": OUT.name, "started_at_utc": started,
                    "completed_at_utc": completed, "redacted_runner_fields": ["records[].transcript"],
                    "runner_revision": head, "runner_worktree_status_excluding_this_run": status,
                    "runner_notebook_sha256": digest(notebook), "pinned_arafa_commit": scope["SHA"],
                    "effective_configuration": {"confidence_threshold": report["review_threshold"],
                        "wire_schema_version": scope["PREDICTIONS_SCHEMA_VERSION"], "wire_split": "val",
                        "wire_classes": scope["EXPORT_CLASSES"], "runtime_schema_version": scope["SCHEMA_VERSION"],
                        "runtime_label_version": scope["LABEL_VERSION"],
                        "agent_seed_order": [agent["id"] for agent in before], "agent_roster": before,
                        "capacity_policy": report["capacity_mode"]},
                    "agent_state": {"before": before, "after": after, "restored": True,
                                    "release_calls": releases, "exactly_once_verified": True},
                    "reader": {field: reader_counts[field] for field in ("calls", "accepted", "rejected")},
                    "ticket_audit": tickets, "result": result,
                })
                log(name, "reader_completed", **{field: reader_counts[field] for field in ("calls", "accepted", "rejected")})
                log(name, "seed_completed", seed=seed, completed_at_utc=completed, result_artifact=info,
                    reconciliation_total=sum(report[key] for key in ("assigned_count", "routing_unassigned_count",
                                                                       "invalid_approved_rows", "missing_approved_rows")),
                    assigned=report["assigned_count"], routing_unassigned=report["routing_unassigned_count"],
                    invalid_approved=report["invalid_approved_rows"], missing_approved=report["missing_approved_rows"],
                    rejected_occurrences=report["invalid_rows"], release_calls=releases, state_restored=True)
                log("run.jsonl", "seed_completed", seed=seed, result_artifact=info,
                    seed_log={"file": name, "sha256": digest((OUT / name).read_bytes())})
                return report
            except BaseException as exc:
                log(name, "fatal_stop", error_type=type(exc).__name__, agent_state_restored=snapshot() == before,
                    reader=dict(reader_counts), release_calls=releases)
                raise

        with patch.dict(scope, {"authenticated_artifact": observe_artifact,
                                "authenticated_manifest": observe_manifest, "_run_validation_seed": observe_seed}):
            reports = scope["run_authorized_validation"](authorization=authorization)

        stage = "verify_and_report"
        assert tuple(reports) == SEEDS and snapshot() == baseline
        for seed, report in reports.items():
            saved = json.loads((OUT / f"seed-{seed}-result.json").read_bytes())
            assert saved["result"] == json.loads(json.dumps(projection(report)))
        assert all(digest(path.read_bytes()) == historical[path.as_posix()] for path in ARCHIVE)
        current = {seed: recompute(seed, approved, baseline) for seed in SEEDS}
        previous = {row["seed"]: row for row in json.loads(ARCHIVE[2].read_bytes())["seed_results"]}
        differences = {seed: {key: {"historical": previous[seed][key], "reproduction": val}
                              for key, val in metrics.items() if previous[seed][key] != val}
                       for seed, metrics in current.items()}
        metadata = save("run-metadata.json", {
            "audit_schema_version": 1, "reproduction_id": OUT.name, "runner": {
                "git_commit": head, "branch": branch, "worktree_status_excluding_this_run": status,
                "notebook_sha256": digest(notebook), "adapter_code_sha256": digest(cells["cell-5"].encode()),
                "official_arafa_commit": scope["SHA"], "official_source_sha256": scope["SOURCE_HASHES"],
                "python": platform.python_version(), "pydantic": scope["pydantic"].__version__},
            "historical_archive_sha256": historical, "synthetic_preflight": counts,
            "artifacts_authenticated": authenticated,
            "manifest": dict(manifest_info, revision=scope["APPROVED_MANIFEST_REVISION"]),
            "approved_manifest_keys": sorted(approved), "seeds": list(SEEDS), "agent_state_restored": True,
            "recomputed_metrics": current, "historical_metric_differences": differences,
        })
        lines = ["# Phase 2 Real Validation reproduction", "", f"Reproduction ID {OUT.name}.", "",
                 "This separately authorized rerun used the gated loader and five approved Validation exports. "
                 "The metrics below were recomputed from the persisted result objects.",
                 "", "| Seed | Assigned | Routing Unassigned | Invalid approved | Missing approved | Rejected | Input coverage | Manifest coverage | Assignment rate | Human Review | Releases |",
                 "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for seed, m in current.items():
            lines.append(f"| {seed} | {m['assigned']} | {m['valid_routing_unassigned']} | {m['invalid_approved']} | "
                         f"{m['missing_approved']} | {m['rejected_occurrences']} | {m['input_coverage']:.0%} | "
                         f"{m['manifest_coverage']:.0%} | {m['assignment_rate']:.0%} | {m['human_review']} | {m['assigned']} |")
        comparison = "See run-metadata.json for differences." if any(differences.values()) else "Every compared metric matches the historical summary."
        lines += ["", "Each seed reconciled to 1,003 approved rows and returned Agent State to baseline.", comparison,
                  "", "## Provenance and scope", "",
                  f"- Runner Git commit {head}, branch {branch}, exact notebook SHA-256 {digest(notebook)}.",
                  f"- Pinned Arafa commit {scope['SHA']}. All input digests and manifest identity are in [run metadata](run-metadata.json).",
                  "- MARBERTv2, fair-marbertv2-lr2e5, dataset v2, Validation split val. The separate synthetic preflight passed 67 tests.",
                  "- Result objects include source row identifiers and runner fields with corrected transcript text omitted. Reader and release observations were recorded during this run. No historical per-ticket evidence was reconstructed.",
                  "- The assignments measure routing at sequential capacity. They do not measure classification accuracy or concurrent capacity. Human Review uses threshold 0.5. Scripts remain pending Hazem's customer-facing approval. Final Test was outside scope.",
                  "", "## Evidence", "", "- [Full execution log](run.jsonl) and [SHA-256 inventory](SHA256SUMS.txt).",
                  "- [Executed notebook snapshot](runner-source.ipynb), [adapter code](adapter-code.py), and [capture script](capture.py).",
                  "", "The capture script reads the checked-out notebook. Use the recorded revision and verify its notebook SHA-256 before any independently authorized reproduction. Run it in a new evidence directory from the project root with an explicit authorization argument.", ""]
        lines += [f"- Seed {seed} [result](seed-{seed}-result.json) and [log](seed-{seed}.jsonl)." for seed in SEEDS]
        report_info = save("audit-report.md", ("\n".join(lines) + "\n").encode())
        log("run.jsonl", "artifacts_written", artifacts=[metadata, report_info])
        log("run.jsonl", "run_completed", seeds=list(SEEDS), agent_state_restored=True,
            metrics_recomputed_from_disk=True, historical_differences=differences)
        sums = "".join(f"{digest(p.read_bytes())}  {p.name}\n" for p in sorted(OUT.iterdir()) if p.is_file())
        inventory = save("SHA256SUMS.txt", sums.encode("ascii"))
        print(json.dumps({"status": "completed", "path": OUT.as_posix(), "metrics": current,
                          "differences": differences, "inventory": inventory}))
    except BaseException as exc:
        # Log failure class and stage without potentially sensitive input values.
        log("run.jsonl", "fatal_stop", stage=stage, error_type=type(exc).__name__)
        print(json.dumps({"status": "stopped", "stage": stage, "error_type": type(exc).__name__,
                          "path": OUT.as_posix()}))
        raise SystemExit(1) from None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", required=True)
    main(parser.parse_args().authorization)
