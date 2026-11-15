# Phase 1 Triage and Routing

Owner: Ibthal, Triage and Routing Engineer

Branch: `team/ibthal-triage-routing`

Contract: SVR Contracts v1.0

Schema version: `1`

Label version: `taxonomy-2026-11-15`

## Purpose and scope

The notebook `notebooks/triage-routing/triage_routing_phase1.ipynb` implements an explainable decision prototype on synthetic inputs and fictional seeded agents. It produces official `TriageDecision` objects, preserves human-review requirements, and verifies the handoff to Arafa's existing ticket assembler.

Hazem approves the priority formula implemented here. I add urgency points, churn points, and customer_state_text points, then populate priority_score and queue_priority. Fusion stays disabled. Missing-input handling requires Hazem confirmation.

This work does not load models, access datasets, read recordings, evaluate the real test split, or measure routing agreement. It creates no competing ticket assembler. The 80 percent agreement target remains a later evaluation requirement, not a result of these mock tests.

## Source of truth and reproducibility

The official modules are read with `git show` from commit `6f21d9bd20af4a175fd9ac011ac89384f32e4c97`, fetched from `team/arafa-systems-demo` on 15 November 2026. The explicit fetch resolves through `FETCH_HEAD`; the local remote-tracking ref still points to the previous commit. The notebook prints that older ref separately and loads the verified full commit below.

| Official path at that commit | Use |
|---|---|
| `src/svr/schemas.py` | Unchanged Pydantic models, enums, validation, and versions |
| `src/svr/agents.py` | Fictional demo seeds and atomic capacity reservation/release |
| `src/svr/stages/triage.py` | Current mock behavior and compatibility comparison |
| `src/svr/stages/ticket.py` | Unchanged `assemble_ticket` and review-ticket interface |
| `src/svr/fixtures.py` | Explicitly synthetic contract fixture |
| `src/svr/pipeline.py`, `src/svr/store.py` | Official result container and completion lifecycle |

The notebook loads supporting official latency/intake/STT/classification/voice modules to satisfy the result/store imports. It does not run their pipeline, open audio, start an API, or make inference calls.

The loader creates a private `_ibthal_phase1_official` package in memory and executes the unchanged source blobs there. It bypasses the package initializer's eager pipeline import, then loads dependencies explicitly in order. No official source is copied into the worktree and no replacement schema is defined. Git source SHA256 values are printed in the saved setup output. The full commit is pinned so moving the remote-tracking ref does not silently change the experiment. Setup prints both the current ref and the pinned commit.

The notebook follows the role/workflow guide and Phase 1 guidance under `docs/project/`. Root `GATES.md` belongs to older audio EDA and is unchanged. The current worktree initially has empty `src/svr/` and `tests/` directories. The implementation remains notebook-first.


### Verified contract revision

The latest fetched integration commit is `6f21d9bd20af4a175fd9ac011ac89384f32e4c97`, titled `Align complaint schema with approved PRD taxonomy`. I inspect the diff from the previous pin `84205e98cc8d78fe9e949098c18e6a3ad27e96db` before updating the notebook. Eight files change, with 48 insertions and 41 deletions.

- The actual `ComplaintCategory` enum contains exactly 11 values. It removes `greeting_only` and adds `offers_and_packages` and `sim_services`.
- SVR Contracts stays v1.0 and Schema Version stays `1`. Label Version changes from `taxonomy-2026-11-11` to `taxonomy-2026-11-15` across official evidence, decisions, and tickets.
- The general seed loses `greeting_only`. No seed gains either new category.
- `stages/ticket.py`, `stages/triage.py`, `pipeline.py`, `store.py`, and `fixtures.py` have identical blobs across the two commits. The existing assembler interface and reservation lifecycle remain available.
- Upstream README and schema comments still call priority open. This notebook implements the newly supplied approval with config `ibthal-phase1-demo-0.2`; Arafa needs to align upstream descriptions during integration.

## Architecture and ownership

```text
Official TextAnalysis + optional VoiceEvidence
                    |
          Ibthal: triage_phase1
          validate -> reserve -> explain
                    |
              TriageDecision
                    |
AudioEvidence + text + optional voice + stage metadata
                    |
       Arafa: existing assemble_ticket
                    |
             Ticket / TicketDetail
                    |
       Arafa: existing TicketStore.complete
          persists in memory and releases capacity
```

Ibthal owns the decision, explanation, contributing signals, and triage configuration version. Arafa owns system orchestration, ticket assembly, status derivation, timing, API/demo, and lifecycle integration. Lama supplies text analysis including the summary, request, and suggested script; Ibthal does not regenerate these fields. Sira supplies audio and optional voice evidence.

## Input contract

`triage_phase1(text: TextAnalysis, voice_evidence: VoiceEvidence | None = None) -> TriageDecision`

`TextAnalysis` requires `voicemail_id`, `summary`, `customer_request`, `suggested_script`, `confidence`, and `needs_human_review`. It carries nullable `complaint_category`, `complaint_urgency`, `customer_state_text`, and `churn_risk`; `keywords` defaults to an empty list. `language_mix` must remain null. Confidence is bounded to `[0, 1]`. A null classification label requires `needs_human_review=True`.

`VoiceEvidence` requires `voicemail_id` and `model_version`; it carries nullable `voice_state_candidate` and `voice_confidence`, plus `quality_features` and `acoustic_features` dictionaries. Voice confidence is bounded to `[0, 1]` when present. All evidence uses the fixed schema and label versions. Unexpected fields and invalid enums are rejected by the official models.

The prototype requires official model objects and revalidates their dumped payloads because mutable objects and `model_copy` can bypass earlier validation. Text and voice IDs must match before any reservation. Voice is accepted as evidence but does not change urgency, text state, priority, or eligibility.

## Output contract

The official `TriageDecision` forbids extra fields:

| Field | Official type/default | Prototype behavior |
|---|---|---|
| `voicemail_id` | Required `str` | Same as validated text |
| `priority_score` | `float \| None = None` | Approved score, or null when a scoring signal is missing |
| `queue_priority` | `QueuePriority \| None = None` | Approved bucket, or null when a scoring signal is missing |
| `assigned_agent_id` | `str \| None = None` | Existing fictional seed ID or null |
| `assignment_status` | Required `AssignmentStatus` | `assigned` or `unassigned`, consistent with ID |
| `route_reason` | Required `str` | Specific, nonempty explanation including policy limits |
| `contributing_signals` | `list[str]`, default empty | Four text labels, review flag, point components, score and bucket, or missing-input reason; voice ignored marker when supplied |
| `config_version` | Required `str` | `ibthal-phase1-demo-0.2` |
| `evaluation` | `dict \| None = None` | Null; no invented evaluation result |
| `schema_version` | Literal `1` | `1` |
| `label_version` | Literal `taxonomy-2026-11-15` | Exact literal |

The existing `QueuePriority` enum contains `low`, `normal`, `high`, and `urgent`. Hazem's approved bucket policy is implemented in the notebook. The schema permits non-null priority values and does not enforce assigned-ID/status consistency; the prototype and tests enforce the Phase 1 requirements without modifying the schema.

## Decision workflow

1. Check official input types, revalidate payloads, and reject mismatched voice IDs.
2. Record the existing text labels and review flag without guessing missing values.
3. If category is null, return unassigned with a missing-category reason and reserve nothing.
4. Otherwise call official `agents.assign_agent(category)` exactly once. It checks listed skills, shift, and remaining capacity under its lock.
5. If no seed is eligible, return unassigned with a null ID and an explanation for human routing.
6. If reservation succeeds, return assigned with the returned fictional ID and explain the demo skill match and reservation.
7. Calculate priority from validated urgency, churn risk, and customer_state_text. Leave both priority fields null when any scoring signal is missing. Keep evaluation null, record versions, and preserve the text review flag.
8. If constructing the decision fails after reservation, release that reservation before propagating the error.

No new confidence threshold or label-to-agent mapping is introduced. Customer state contributes only its approved text-state points. Complaint urgency is never inferred from emotional tone.

## Approved priority formula and decision table

```python
priority_score = urgency_points + churn_points + customer_state_points
```

Urgency points are high = 3, medium = 2, and low = 1. Churn points are at_risk = 2 and not_at_risk = 0. Customer-state points use `customer_state_text` only. Mad and frustrated each contribute 1. Calm, satisfied, and unclear each contribute 0. Valid scores are 1 to 6.

Queue buckets are 6 = urgent, 5 = high, 3-4 = normal, and 1-2 = low.

| complaint_urgency | churn_risk | customer_state_text group | State points | priority_score | queue_priority |
|---|---|---|---|---|---|
| `high` | `at_risk` | mad/frustrated | 1 | 6 | `urgent` |
| `high` | `at_risk` | calm/satisfied/unclear | 0 | 5 | `high` |
| `high` | `not_at_risk` | mad/frustrated | 1 | 4 | `normal` |
| `high` | `not_at_risk` | calm/satisfied/unclear | 0 | 3 | `normal` |
| `medium` | `at_risk` | mad/frustrated | 1 | 5 | `high` |
| `medium` | `at_risk` | calm/satisfied/unclear | 0 | 4 | `normal` |
| `medium` | `not_at_risk` | mad/frustrated | 1 | 3 | `normal` |
| `medium` | `not_at_risk` | calm/satisfied/unclear | 0 | 2 | `low` |
| `low` | `at_risk` | mad/frustrated | 1 | 4 | `normal` |
| `low` | `at_risk` | calm/satisfied/unclear | 0 | 3 | `normal` |
| `low` | `not_at_risk` | mad/frustrated | 1 | 2 | `low` |
| `low` | `not_at_risk` | calm/satisfied/unclear | 0 | 1 | `low` |

### Missing-input policy requiring Hazem confirmation

A missing urgency, churn risk, or customer_state_text leaves both priority fields null and preserves human review. I choose this conservative continuation of existing review behavior pending Hazem confirmation. Missing category leaves routing unassigned, while complete scoring inputs still allow priority calculation. A valid category may receive a demo reservation while another missing label still requires review.

Invalid required labels, versions, or unexpected fields raise official validation errors before reservation. The caller uses Arafa's existing failed-run review path. No replacement labels, default points, or voice-based values are guessed. Explicit `unclear` is an approved state worth 0 and differs from a missing state.

## Fictional demo routing assumptions

These are existing seeds from the pinned integration implementation, not approved production mappings:

| Seed ID | Existing listed skills | Capacity | Initial load | Shift |
|---|---|---|---|---|
| `agent-demo-network` | `network_and_connectivity`, `no_reply_or_long_wait` | 5 | 1 | On |
| `agent-demo-billing` | `billing_and_charges`, `balance_and_data` | 5 | 2 | On |
| `agent-demo-general` | `app_and_account`, `branch_and_staff`, `cancellation_request`, `thanks_or_praise`, `other` | 3 | 0 | On |

Official reservation uses the first eligible seed in its existing list order. The prototype reuses that demo behavior without approving a production tie-break. Existing tiers and languages are not used to introduce new routing policy. Tests change only private in-memory fictional availability/load fixtures and restore them after every method.

The verified taxonomy contains exactly these 11 values.

`network_and_connectivity`, `billing_and_charges`, `balance_and_data`, `app_and_account`, `branch_and_staff`, `no_reply_or_long_wait`, `cancellation_request`, `thanks_or_praise`, `other`, `offers_and_packages`, `sim_services`.

`offers_and_packages` and `sim_services` have no seeded skill match. They return unassigned with a human-routing explanation and reserve no capacity. `greeting_only` is rejected. Unknown values remain validation failures. Data owners still need to align older annotation and dataset artifacts with this taxonomy before model evaluation.

## Review and failure handling

Null labels are valid only with the text review flag true. The prototype leaves labels and the flag unchanged, includes review in the explanation, and relies on Arafa's assembler to derive `needs_review`. Unknown enum strings, invalid versions, and unexpected fields raise validation errors before routing.

Assignment and review are separate: a complete category can permit demo assignment while a different missing label still requires review. An unassigned ticket with complete labels is not automatically `needs_review` in the current assembler, although its routing explanation calls for human routing. No new policy changes that behavior here.

The triage object has no review-flag field. Callers must pass the original validated text to the assembler. The official failed-run path uses `build_review_ticket`; the prototype does not invent a substitute error schema or ticket.

## Capacity ownership

`assign_agent` selects and reserves one unit atomically. The prototype never follows it with `consume`. Reservation counts concurrent processing, not a persistent callback backlog. The official store releases the unit when it completes the run. Ticket assembly itself neither reserves nor releases.

A standalone notebook caller uses `agents.release(assigned_agent_id)` once when its synthetic run ends. A caller using `TicketStore.complete` must not release again. When assembly fails before completion, the caller that owns the reservation must clean it up. The tests exercise that explicit cleanup.

Loads are process-local and seeded resets are for isolated tests only. Release accepts an agent ID, not a reservation token; repeated release can reduce preexisting load. Retrying triage is not idempotent and reserves again. Future integration must define failure/retry ownership and use the same shared agent module as Arafa's pipeline, not this notebook's private test package. Reassignment is Arafa's lifecycle responsibility and is not reimplemented or fully tested here.

## Automated cases and actual execution results

The notebook executes successfully in a fresh kernel on 15 November 2026, with all four code cells executed and outputs saved. Actual final results: **31 passed, 0 failed, 0 errors, 0 skipped**. The 31 test methods include additional subcases; subcases are not counted as separate test methods.

| Execution component | Actual version |
|---|---|
| Python | `3.12.10` |
| Pydantic | `2.14.3`, matching the integration requirements |
| nbformat | `5.11.1` |
| nbclient | `0.11.0` |
| ipykernel | `7.4.0` |

The approved packages are installed in workspace-local `.venv-triage`, ignored by the existing `.gitignore`. The saved setup output confirms the pinned commit `6f21d9bd20af4a175fd9ac011ac89384f32e4c97`, schema `1`, label version `taxonomy-2026-11-15`, and 11 categories. The printed remote-tracking ref remains at `84205e98cc8d78fe9e949098c18e6a3ad27e96db`; the explicit fetch supplies the newer commit through FETCH_HEAD.

Test coverage:

| Methods | Coverage |
|---|---|
| 01-07 | Eligible assignment, null/unknown category, empty eligibility, off shift, full capacity, reserve/release |
| 08 | All 30 urgency/churn/text-state combinations, all 12 scoring groups, scores 1-6 and all four buckets, same demo category routing |
| 09-10 | Each missing classification label and explicit human-review flags with complete labels |
| 11-13 | Invalid enums, extra fields, incorrect schema and label versions |
| 14 | Five text states crossed with absent voice and five voice states, 30 subcases |
| 15-17 | Reset repeatability, exact decision serialization, official assembler handoff |
| 18-21 | Each mismatched stage ID, failed stages, pre-reservation ID checks, mutated input validation |
| 22-23 | Official store completion releases once; failed decision construction rolls back |
| 24-25 | All 11 categories, including two without seeded skills; 16 concurrent attempts for four available network slots |
| 26-29 | Existing mock routing compatibility, disabled fusion/language mix, no tier policy, input types and voice-confidence bounds |
| 30 | Exact taxonomy, removed category rejection, previous Label Version rejection |
| 31 | All seven nonempty combinations of missing scoring inputs, null priorities, human review, voice ignored |

The test runner prints each method result, totals, Python/Pydantic versions, source hashes, and a synthetic handoff example. Expected validation exceptions are assertions of correct rejection. They are not failed or skipped tests. The deliberately corrupted-input serializer warning is captured as an explicit expectation. Mock timings in the example are zero-valued shape fixtures, not latency measurements.

The saved example shows `agent-demo-network` load changing from `1` to `2` during the reservation and back to `1` after official store completion. The example computes `2 + 0 + 1 = 3`, returns `normal`, and preserves null `customer_state_final`. Decision JSON successfully round-trips through the unchanged official Pydantic model. The assembler and store accept the decision without replacing their implementations.

## Integration handoff to Arafa

The future integration candidate is `triage_phase1`, which follows the current mock's positional text/voice interface and returns the official decision model. It improves explanations, records all text signals and review state, checks voice IDs early, and revalidates mutable input objects. Its configuration version differs from `mock-triage-0.1` to identify behavior.

The notebook passes decisions to the existing keyword-only `assemble_ticket` with `ticket_id`, `voicemail_id`, `audio`, `text`, `voice_evidence`, `decision`, `stage_status`, `stage_timing_ms`, `processing_ms`, and optional `created_at`. The assembler rejects mismatched IDs and any stage marked `failed`; it derives status from classification completeness and the text review flag.

Base `Ticket` copies assignment status, priority score, and route reason. It takes summary/request/script from text and transcript from audio; it keeps `customer_state_final` null and `cached` false. Base `Ticket` does not carry `assigned_agent_id`, `queue_priority`, contributing signals, or triage configuration version. `TicketDetail.triage_decision` preserves them. A display/API requirement for those fields must use that detail or be coordinated with Arafa.

No integration files are modified and the live pipeline still uses its existing mock. This deliverable demonstrates compatibility at the pinned revision. It does not claim the notebook function has been deployed or that a later integration revision is compatible without rerunning the checks.

## Reproduction

Prerequisites: the correct role branch, the pinned commit available locally, Python 3.11 or newer, Git, Pydantic 2, and notebook execution packages. No dataset is required and no network is used by the notebook itself.

From PowerShell in `C:\Users\RC\svr-ibthal`, the approved setup commands are:

```powershell
& 'C:\Users\RC\AppData\Local\Programs\Python\Python312\python.exe' -m venv .venv-triage
.\.venv-triage\Scripts\python.exe -m pip install pydantic==2.14.3 nbformat nbclient ipykernel
```

With that environment already available, verify the source and execute the notebook in place without installing a global kernelspec:

```powershell
git branch --show-current
git status --short
git fetch origin team/arafa-systems-demo
git rev-parse FETCH_HEAD
git diff 84205e98cc8d78fe9e949098c18e6a3ad27e96db 6f21d9bd20af4a175fd9ac011ac89384f32e4c97 -- src/svr/schemas.py src/svr/agents.py
git show 6f21d9bd20af4a175fd9ac011ac89384f32e4c97:src/svr/schemas.py
$env:PYTHONDONTWRITEBYTECODE = '1'
@'
import importlib.metadata as metadata
import pathlib
import sys
import nbformat
from nbclient import NotebookClient
from jupyter_client.kernelspec import KernelSpec, KernelSpecManager

class VenvKernelSpecManager(KernelSpecManager):
    def get_kernel_spec(self, kernel_name):
        if kernel_name != "python3":
            raise ValueError(kernel_name)
        return KernelSpec(
            argv=[sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
            display_name="Python 3 (SVR triage)", language="python",
        )

p = pathlib.Path("notebooks/triage-routing/triage_routing_phase1.ipynb")
n = nbformat.read(p, as_version=4)
client = NotebookClient(n, timeout=180, kernel_name="python3",
    resources={"metadata": {"path": str(pathlib.Path.cwd())}})
client.km = client.create_kernel_manager()
client.km.kernel_spec_manager = VenvKernelSpecManager()
try:
    client.execute()
    n.metadata.svr_phase1.execution_status = "executed"
except Exception:
    n.metadata.svr_phase1.execution_status = "failed"
    raise
finally:
    n.metadata.svr_phase1.environment = {
        name: metadata.version(name)
        for name in ("pydantic", "nbformat", "nbclient", "ipykernel")
    }
    nbformat.validate(n)
    nbformat.write(n, p)
for cell in n.cells:
    for output in cell.get("outputs", []):
        if output.output_type == "stream":
            print(output.text)
'@ | .\.venv-triage\Scripts\python.exe -
git diff --check
git diff --stat
git status --short
git diff --no-index --check -- /dev/null docs/project/triage-routing-phase1.md
git diff --no-index --check -- /dev/null notebooks/triage-routing/triage_routing_phase1.ipynb
git diff --no-index --stat -- /dev/null docs/project/triage-routing-phase1.md
git diff --no-index --stat -- /dev/null notebooks/triage-routing/triage_routing_phase1.ipynb
```

The client overrides the kernel executable in memory to use this virtual environment, so it does not register a user-wide kernel. On Windows, temporary Jupyter runtime files may require execution outside the filesystem sandbox. Only the notebook is intentionally rewritten by the execution command. The workspace-local environment is ignored by the existing `.gitignore`. The two deliverables remain untracked for review, so ordinary `git diff` does not display their content. The `--no-index` commands compare each new file against an empty file; a difference exit code is expected. Neither staging nor committing is needed.

## Pending approvals and readiness

Hazem still needs to confirm the missing-input policy, production skill mapping, tier policy, agent tie-breaking, fusion, and language_mix values. The supplied formula, score range, bucket thresholds, and verified 11-category contract are implemented.

Arafa and Ibthal must confirm extraction from the notebook, shared runtime agent state, and retry/error cleanup ownership. The two new categories currently lack seeded skills. Unassigned tickets with complete labels can still receive completed status from the official assembler. Upstream priority comments need alignment with Hazem's new approval. Older dataset and annotation labels require their owners' alignment before evaluation.

Actual fresh-kernel execution on 15 November 2026 in `.venv-triage` reports **Passed 31, Failed 0, Error 0, Skipped 0**, with all four code cells and their outputs saved. Subcases are additional checks within the 31 methods. Execution prints Windows/Jupyter runtime warnings about the event loop fallback and local TCP transport and completes successfully.

The two requested deliverables remain untracked for review. Production integration, full API/reassignment coverage, and real routing agreement evaluation remain future work.
