# Phase 2 Triage and Routing Preparation

Owner: Ibthal. Branch: team/ibthal-triage-routing.

## Scope and status

I prepare a proposed prediction adapter, synthetic batch runner, verification metrics and automated tests in notebooks/triage-routing/triage_routing_phase2.ipynb. I reuse official implementations without replacing triage, assignment or assembly. No real Validation Predictions, recordings, private datasets or final Test Set are accessed. This preparation is not completed Phase 2 evaluation.

## Official source

Read-only official checkout: configured through SVR_ARAFA_ROOT, or the sibling directory svr-arafa-review next to the project checkout.
Commit: fe695befbb9bd8769273cc7ea2e8dffc84518820.
Schema version: 1. Label version: taxonomy-2026-11-15.

The setup resolves the project root, verifies a clean official checkout and exact SHA, and checks tracked Python sources under src/svr and infra against pinned Git blobs before imports. SHA256 values are printed. Contracts, triage and Agent State come from the same svr package, avoiding private-package class identity mismatches. The project checkout can use a teammate's branch; only the official source checkout must match the fixed commit. The pin is intentionally fixed until another version is reviewed.

Reused paths:

- src/svr/schemas.py: official contracts and enums.
- src/svr/agents.py: process-local state and reservation/release.
- src/svr/stages/triage.py: triage_phase1 and approved priority calculation.
- src/svr/stages/ticket.py: assemble_ticket, exercised in a synthetic handoff test.
- infra/predictions_file.py: read_predictions_file, exercised only on temporary synthetic prediction files.

## Approved policies and agent skills

Automatic routing uses matching official skill, On Shift, available capacity and first eligible Agent in Seed Order. Tier is ignored; Current Load is a capacity condition, not a ranking signal. There is no separate Skill Mapping.

Hazem approved `sim_services` for the Network Agent and `offers_and_packages` for the Billing Agent. The notebook uses the pinned official roster and routing rules.

Priority is urgency (high 3, medium 2, low 1) + churn (at_risk 2, not_at_risk 0) + text state (mad/frustrated 1, calm/satisfied/unclear 0). Buckets: 6 urgent, 5 high, 3-4 normal, 1-2 low. Missing any scoring input leaves both priority fields null and requires Human Review. No defaults are substituted. Voice fusion stays disabled.

## Input format and proposed adapter

The official reader returns flattened prediction rows and probabilities keyed by `audio_file`. I supply the approved export's four `customer_state` values (`calm`, `frustrated`, `mad`, `satisfied`) and the pinned runtime class lists for the other three tasks. The runtime `CustomerState` keeps `unclear`, including for existing synthetic runtime cases. I retain the original labels and probabilities, including the exported argmax `churn_risk`, and map wire `val` to runtime `validation` only after validating the wire header.

`LABEL_MAP` maps `customer_state` to `customer_state_text` and preserves the other labels. The adapter preserves `audio_file`, derives `voicemail_id` from that exact string, and retains the original input index. When legacy fixtures supply a supplemental ID, the batch still rejects duplicate supplied IDs. The supplemental value never becomes the ticket ID.

The Validation handoff uses the official reader output and approved manifest without a per-row producer supplement. It populates `TextAnalysis.schema_version` and `label_version` from the pinned runtime constants after strict wire and runtime metadata checks. The adapter indexes corrected text from the validated `(val, audio_file)` manifest keys in `final/clean_training_val.csv` and preserves prediction order. It uses the corrected `text` for `AudioEvidence.transcript`, preserving whitespace and punctuation. It ignores `text_norm` and `text_whisper`. Missing matches, blank or non-string text, and duplicate transcript keys produce explicit errors.

The provisional `summary` is `text[:200]`, measured in Python characters. The provisional `customer_request` is a short category-based sentence with one representation for each of the 11 approved categories. These rules yield a transcript excerpt and a category description, neither a generated summary nor a verified verbatim request. A null category yields an empty request and requires Human Review. Unsupported categories fail row validation.

For complete rows, the adapter calculates confidence as the minimum predicted-class probability across complaint category, complaint urgency, customer state and churn risk. The adapter and synthetic runner accept a keyword-only `review_threshold` in [0, 1], defaulting to 0.5. The adapter computes the required runtime pre-routing boolean locally as `any_missing_label or confidence < review_threshold`. Final ticket review also applies when routing returns `UNASSIGNED`. The runtime-only null-label path still requires explicit numeric confidence in [0, 1] and a supplied nonblank script for a null category. Missing or null labels in the official export are rejected by the pinned reader and logged in the rejection ledger.

The synthetic runner requires a probability map keyed by `audio_file`. An omitted or null map fails batch configuration. A missing entry for an individual complete row is an indexed row error. The runner preserves input order.

Hazem selected fair-run MARBERTv2 from `runs/exp_fair-marbertv2-lr2e5`, dataset `v2`, with independent Validation reports for seeds 7, 42, 99, 1337 and 2023. Each seed uses `predictions_val_seed<seed>.json` and the complete 1,003-key manifest at revision `32e32436854cd214346ff87e7dc856897645eae0`. The seed report records the source path, SHA-256 of the original bytes, seed, run ID, model, dataset version and manifest revision. The synthetic entry point accepts in-memory fixture bytes and uses its path for provenance only. The authorized entry point acquires the approved bytes itself and returns one independent report per seed.

Fatal preflight errors stop the seed before routing and yield no metrics. They include an unexpected source name or manifest revision, invalid manifest keys or count, undecodable JSON, ambiguous duplicate JSON object fields, malformed envelope or invalid header, wrong split and an empty or non-list rows field.

I scan the full submitted rows array for duplicate composite keys before validating any candidate. Every occurrence of a duplicate is rejected. I pass each unique approved candidate unchanged in a temporary one-row envelope to the public `read_predictions_file()` with `expected_split="val"`. The reader still enforces row shape, label membership, exact probability classes, finite values, probability sums and argmax. I preserve an input slot for every original occurrence and retain order. Recoverable errors include invalid or unexpected keys, reader-rejected rows, and missing or invalid corrected transcript text. The rejection ledger records zero-based source index, composite key when available, stage, reason code and diagnostic.

Run All and the existing synthetic entry points cannot open real data. The separate `run_authorized_validation()` entry point rejects missing or incorrect authorization before touching any artifact.

## Proposed category-to-script mapping

All 11 Egyptian Arabic templates in `PROPOSED_SUGGESTED_SCRIPTS` are drafts pending Hazem's approval for customer-facing use. The adapter uses `suggest_script(category)` for valid predicted categories. The lookup accepts the official enum or its exact wire value. A null category requires a nonblank upstream script and Human Review. Unsupported categories fail validation.

Nine templates preserve the supplied wording. The prior revisions for the two entries below were unavailable in the local backup and the editor snapshot. These proposed replacements avoid assuming a branch visit, direct staff interaction, a contact channel, or an unresolved earlier request.

- `BRANCH_AND_STAFF`

  شكرًا إنك شاركتنا ملاحظتك. ممكن توضح لنا تفاصيل أكتر عن ملاحظتك بخصوص الفرع أو فريق الخدمة؟
- `NO_REPLY_OR_LONG_WAIT`

  ممكن توضح لنا تفاصيل أكتر عن التواصل أو الانتظار، وإيه المساعدة اللي محتاجها دلوقتي؟

## Synthetic capacity lifecycle

Hazem confirmed sequential processing with capacity released after each ticket. The synthetic runner requires the explicit `synthetic_sequential_release` mode. Official triage reserves capacity for an assigned ticket, and the runner releases the returned reservation once in `finally` before the next ticket. Official triage rolls back its own reservation if decision construction fails before returning.

The runner never calls consume after assignment, reset_loads or TicketStore.complete. Snapshots check all Agent fields before and after cleanup. Controlled overlapping-skill fixtures patch process memory only and are restored. Run in a fresh process, never an API worker or concurrent shared runtime.

Reports identify the run scope and use sequential-validation metrics. Concurrent workloads are outside this measurement.

## Approved Validation manifest

The approved source is the ready-branch `clean_training_val.csv`. Reconciliation uses the selected `val` rows and the exact composite key `(split, audio_file)`. The official denominator is 1,003 unique approved keys. The notebook accepts in-memory synthetic manifest rows and uses their actual cardinality. The batch requires a manifest even when predictions are empty. Invalid or duplicate manifest entries stop preflight because they make the denominator unreliable.

Absent approved keys are recorded as missing with a reason. Every occurrence of a duplicated prediction key is rejected. The exact `audio_file` becomes the voicemail ID, so composite-key reconciliation also prevents duplicate derived IDs in the same seed. Unexpected prediction keys are reported and are ineligible for assignment credit. Unknown or missing keys cannot increase the numerator. Rejected submitted rows retain their index, available key and reason. Other rows continue in input order.

## Metrics

- Total input rows: actual supplied batch length, no hardcoded dataset size.
- Valid rows: unique contract-valid rows after adapter preflight.
- Invalid rows: rejected submitted rows, including unexpected and duplicate occurrences. Invalid approved rows count affected manifest keys once. Missing approved rows are reported separately.
- Processed rows: verified returned decisions.
- Input Coverage Rate: processed / all input rows, null for empty input.
- Approved Validation Coverage Rate: successfully processed approved keys / all approved manifest keys.
- Assigned Count: verified assigned approved keys. Unassigned Count: all approved manifest keys minus assigned keys. Routing Unassigned Count separately counts valid decisions that returned Unassigned.
- Assignment Rate: successfully assigned approved keys / 1,003 for each seed. Invalid and missing approved rows count as Unassigned. A valid envelope containing only invalid predictions scores zero. Assigned-over-processed remains a separate diagnostic.
- Reconciliation invariant: assigned + valid routing-Unassigned + invalid approved + missing approved = 1,003. Each invalid approved key contributes once. The separate rejection ledger keeps each rejected submitted occurrence.
- Priority Bucket Distribution includes null; Null Priority Count uses null score.
- Human Review Count uses the pre-routing review flag or a returned `UNASSIGNED` status, matching the official assembler.
- Unassigned Reasons: missing_category, no_matching_skill, off_shift, capacity_exhausted, based on the pre-reservation snapshot. Original nonempty route_reason is retained.
- Contract Validation Errors include indexed contract, shape and duplicate errors.

Rates are fractions from 0 to 1. Empty denominators return null. Runtime verification failures abort instead of emitting a misleading completed report. The 0.9 target is metadata only.

## Actual execution evidence

On 24 November 2026, the full synthetic suite ran in a fresh isolated Python 3.12.10 process against the pinned Arafa source. The latest saved output records 67 passed with zero failures, errors or skips. The suite retains all 58 prior test cases and adds nine loader regressions. Tests exercise the authorization gate, exact paths, redirects before and during open, digest and Git identity failures, malformed manifests and headers, independent five-seed provenance, and parsing from authenticated bytes after files change on disk. Agent State matched the baseline after success, runner verification failure and official triage construction failure. The one-slot fixture assigned two consecutive tickets to the same agent and verified one release per reservation.

The synthetic demonstration assigned 11 of 11 fixtures under the sequential policy. Official Validation Assignment Rate and Coverage Rate remain unmeasured. Tests cover corrected transcript preservation, category requests, confidence and review, priority, routing eligibility and Seed Order, real-data guards and the official assembler handoff.

The reader tests use temporary JSON fixtures for wire validation. The batch tests reconcile synthetic composite keys, including an unexpected key with usable supplemental and transcript data. A separate case covers a missing transcript. The gated loader verifies those bindings at run time. The saved output contains only synthetic evidence.

### Synthetic suite history

The local backup and the VS Code local history snapshot both contain 22 tests. The prior change started from that 22-test version. It kept 21 test names, replaced `test_cleanup_exactly_once` with `test_sequential_capacity_reuse_and_exactly_once_release`, and added seven tests covering official rollback, corrected text joins, summary boundaries, invalid corrected text, category requests, confidence and pre-routing review, and final Unassigned review. That gives 29 tests. The available 22-test snapshot shows no test merges or other removed names.

Of the 21 retained names, 10 method bodies match the 22-test baseline and 11 were updated. Most updates pass the keyed fixture inputs through the new adapter. The substantive changes cover automatic review for explicit null labels (with explicit confidence), release call counts on verification failure, the synthetic official assembler handoff, and the revised supplement requirements.

The reported 38-test revision is absent from the available notebook history, local backup, and Git history for this path. Individual test changes relative to those 38 and full coverage parity remain unverified. This update restores tests for the documented script behaviors (11-template lookup and adapter handoff, unsupported categories, and the null-category upstream requirement) and adds focused checks for missing probability maps, indexed missing-row probabilities, invalid numeric inputs, and batch threshold effects on Human Review, priority, routing and script selection. All 29 tests from the last run remain in the suite.

The previously reported 94 core + 36 API = 130 passed are user-supplied upstream evidence, not rerun results of this preparation task.

Notebook v4 structure, unique cell IDs, types and source fields were checked with stdlib JSON and actual code execution. nbformat is unavailable in this environment, so full nbformat schema validation was not run. No packages or kernels were installed. Optional full library validation remains an environment follow-up.

## Reproduction

### Prerequisites and approved source

Use Python 3.11 or newer, Git on PATH and Pydantic 2.14.3, matching the pinned runtime. Synthetic execution uses only Pydantic and the Python standard library; it does not require the API/demo packages, datasets or models. Full notebook validation additionally needs nbformat; an interactive notebook frontend needs ipykernel and JupyterLab or an equivalent IDE. These optional packages are not installed automatically.

Ask Arafa or the repository owner for a separate clean checkout/worktree at the exact pinned SHA. Prepare that checkout manually under your team's Git workflow before running this notebook. Merely using the same branch name is insufficient. The notebook never fetches, clones, checks out, downloads or changes Git configuration on disk. Its safe.directory override is command-local. Do not install environments inside the official checkout unless they are ignored; the checkout must remain clean.

Choose your intended Python environment and confirm it has Pydantic 2.14.3. If creating a new environment is necessary, manually create it outside the official source checkout and install the needed packages under your normal approval process. The commands below install nothing and change no Git state.

### Configure paths

From the project root, or notebooks/triage-routing, root discovery searches the working directory and its parents. From anywhere else, explicitly set SVR_PROJECT_ROOT to the project checkout. Environment paths expand ~; relative values resolve against the process working directory, so absolute environment values are recommended. No username or OS-specific home directory is assumed.

PowerShell, from the project root with an existing sibling official checkout:

```powershell
$env:SVR_ARAFA_ROOT = (Resolve-Path ../svr-arafa-review).Path
# Optional when launching from outside the project:
$env:SVR_PROJECT_ROOT = (Get-Location).Path
# Activate/select your existing environment so python is the intended interpreter.
python -B -c "import sys, pydantic; print(sys.executable); print(sys.version); print(pydantic.__version__)"
git -C "$env:SVR_ARAFA_ROOT" rev-parse HEAD
git -C "$env:SVR_ARAFA_ROOT" status --short
```

For a differently located checkout, replace ../svr-arafa-review with its actual path. If the conventional sibling exists, SVR_ARAFA_ROOT can be omitted. The same instructions apply to another teammate's checkout regardless of username or drive.

macOS/Linux, from the project root:

```bash
export SVR_ARAFA_ROOT="$(cd ../svr-arafa-review && pwd)"
export SVR_PROJECT_ROOT="$PWD"  # optional outside the supported working directories
python -B -c 'import sys, pydantic; print(sys.executable); print(sys.version); print(pydantic.__version__)'
git -C "$SVR_ARAFA_ROOT" rev-parse HEAD
git -C "$SVR_ARAFA_ROOT" status --short
```

Expected commit: fe695befbb9bd8769273cc7ea2e8dffc84518820. Expected status: empty. Missing directory, wrong commit, changed source, missing module or reused kernel produces an actionable error. Restart the kernel before rerunning all cells. The notebook intentionally rejects preloaded svr/infra modules.

### Run and reproduce

For interactive use, open the notebook in your IDE and select the intended Python environment. If JupyterLab is already available there, use python -m jupyterlab from the project root, open the notebook and Run All in a fresh kernel. Outputs contain source hashes, package versions, metrics and actual test counts. Run All does not invoke the authorized loader.

The following PowerShell command runs every saved code cell in a fresh process from either supported working directory. It performs available nbformat validation, checks Agent State, and does not rewrite outputs or review files. Python -B disables bytecode writes; do not use -O because verification uses assertions.

```powershell
@'
import json, os
from pathlib import Path
start = Path(os.environ.get('SVR_PROJECT_ROOT', Path.cwd())).expanduser().resolve()
root = next(p for p in (start, *start.parents) if (p / 'notebooks/triage-routing/triage_routing_phase2.ipynb').is_file())
p = root / 'notebooks/triage-routing/triage_routing_phase2.ipynb'
n = json.loads(p.read_text(encoding='utf-8-sig'))
assert n['nbformat'] == 4 and n['nbformat_minor'] == 5
assert len({c['id'] for c in n['cells']}) == len(n['cells'])
try:
    import nbformat
except ImportError:
    print('nbformat unavailable; structural checks and actual execution only')
else:
    nbformat.validate(nbformat.from_dict(n))
namespace = {'__name__': '__main__'}
for cell in n['cells']:
    if cell['cell_type'] == 'code':
        exec(compile(''.join(cell['source']), cell['id'], 'exec'), namespace)
assert namespace['snapshot']() == namespace['BASELINE']
print(namespace['TEST_COUNTS'])
'@ | python -B -
```

On macOS/Linux, run the same Python block with python -B - <<'PY' and a closing PY line instead of the PowerShell here-string wrapper. Select an environment providing python, or substitute its python3 command. No virtual environment name is required.

## Separately authorized Real Validation execution

The loader uses six exact allowlisted paths beneath `C:\Users\RC\svr-data`. It rejects symlinks, junctions and other reparse points on every path component. On Windows it holds ancestor directory handles without delete sharing and opens the leaf without following redirects. It reads each artifact once and checks the pinned SHA-256 against the same bytes used for parsing. The manifest SHA-256 authenticates the Windows CRLF bytes. Its Git identity check separately verifies the approved commit and tracked blob `b1adfcc118a766a44bdc1fbe60f372829b2dc720` using the LF-normalized bytes. No Test artifact is on the allowlist.

1. Obtain separate authorization for the official run. Use a fresh isolated Python process or kernel with assertions enabled and the pinned Arafa checkout. Run the notebook setup and synthetic verification.
2. After authorization, call the following explicitly in that process. The argument is a deliberate opt-in and does not replace authorization. Run All contains no call that enables real execution.

   ```python
   reports = run_authorized_validation(authorization="AUTHORIZE_PHASE2_REAL_VALIDATION")
   ```

3. The loader authenticates all six artifacts before routing. It returns independent reports for seeds 7, 42, 99, 1337 and 2023, with source and manifest provenance. Review the aggregate counts and per-seed metrics without displaying records that contain corrected transcripts.

Stop on authorization failure, an unsafe path, a hash or Git identity mismatch, an invalid manifest, a fatal seed header or envelope error, a reconciliation invariant failure, or an Agent State mismatch. The loader returns no partial official report on a fatal failure. A recoverable row rejection stays in the ledger and processing continues. Capacity cleanup runs in the existing per-ticket `finally` path. If state restoration fails, discard partial results, end the isolated process, and investigate before retrying. The loader has no persistent routing writes to roll back.

Customer-facing script approval remains pending. The Final Test Set stays outside this workflow.

## Known integration risks

Arafa owns token-free release risks, double release after completion/reassignment, cleanup when store completion fails, and manual reassignment that checks capacity without automatic skill/shift rules. This runner avoids those store/manual paths. Hazem must decide whether manual override is an exception.

This update touches only the two Phase 2 preparation files. Phase 1 and review source remain unchanged. No commit, push, merge, branch switch or official Validation Evaluation is performed.
