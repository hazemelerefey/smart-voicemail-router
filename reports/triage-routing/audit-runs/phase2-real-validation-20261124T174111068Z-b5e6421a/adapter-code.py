LABEL_MAP = {"complaint_category": "complaint_category", "complaint_urgency": "complaint_urgency",
             "customer_state": "customer_state_text", "churn_risk": "churn_risk"}
SUPPLEMENT_FIELDS = {"schema_version", "label_version"}
REQUIRED_META = {"run_id", "model", "dataset_version", "seed", "split"}
def validate_meta(meta):
    if not isinstance(meta, dict) or REQUIRED_META - meta.keys():
        raise ValueError("Producer metadata missing: run_id, model, dataset_version, seed, split")
    if meta["split"] != "validation":
        raise ValueError("Only validation accepted; final test access forbidden")
    for name in ("run_id", "model", "dataset_version"):
        if not isinstance(meta[name], str) or not meta[name].strip():
            raise ValueError(f"Missing metadata: {name}")
    if type(meta["seed"]) is not int or meta["seed"] < 0:
        raise ValueError("seed must be nonnegative integer")
    if meta.get("schema_version") != SCHEMA_VERSION or meta.get("label_version") != LABEL_VERSION:
        raise ValueError("Explicit runtime schema_version and label_version required")
    return copy.deepcopy(meta)

def load_validation_predictions(path=None, *, approvals=None, classes_by_field=None):
    # Fail before opening ANY file, even if approval-like flags are supplied.
    raise PermissionError("Real loading disabled: verified artifacts and authorization required")

TRANSCRIPT_SOURCE = "final/clean_training_val.csv"
APPROVED_VALIDATION_SPLIT = "val"
APPROVED_VALIDATION_ROW_COUNT = 1003
APPROVED_PREDICTIONS_RUN = "fair-marbertv2-lr2e5"
APPROVED_PREDICTIONS_DIR = f"runs/exp_{APPROVED_PREDICTIONS_RUN}"

def validation_manifest_keys(manifest_rows):
    """Validate the selected val rows from the ready-branch manifest."""
    keys = set()
    for index, row in enumerate(manifest_rows):
        if not isinstance(row, dict) or row.get("split") != APPROVED_VALIDATION_SPLIT:
            raise ValueError(f"Manifest row {index} must have split val")
        audio_file = row.get("audio_file")
        if not isinstance(audio_file, str) or not audio_file.strip():
            raise ValueError(f"Manifest row {index} must have a nonempty audio_file")
        key = (row["split"], audio_file)
        if key in keys:
            raise ValueError(f"Duplicate approved manifest key: {key}")
        keys.add(key)
    return keys
DEFAULT_REVIEW_THRESHOLD = 0.5
CATEGORY_REQUESTS = {
    "network_and_connectivity": "The customer is contacting support about network connectivity.",
    "billing_and_charges": "The customer is contacting support about billing or charges.",
    "balance_and_data": "The customer is contacting support about balance or data.",
    "app_and_account": "The customer is contacting support about the app or their account.",
    "branch_and_staff": "The customer is contacting support about a branch or staff.",
    "no_reply_or_long_wait": "The customer reports a long wait or no reply.",
    "cancellation_request": "The customer is asking about cancellation.",
    "thanks_or_praise": "The customer is expressing thanks or praise.",
    "other": "The customer is contacting support about another topic.",
    "offers_and_packages": "The customer is contacting support about offers or packages.",
    "sim_services": "The customer is contacting support about SIM services.",
}

def index_transcripts(csv_rows):
    """Index parsed clean_training_val.csv rows without rewriting their text."""
    indexed = {}
    for row in csv_rows:
        key = row.get("audio_file")
        if not isinstance(key, str) or not key.strip() or key in indexed:
            raise ValueError("Transcript rows require unique, nonempty audio_file keys")
        indexed[key] = row.get("text")
    return indexed

def summarize_transcript(transcript):
    """Return the provisional first 200 Python characters of corrected text."""
    if not isinstance(transcript, str) or not transcript.strip():
        raise ValueError("Corrected text must be a nonempty string")
    return transcript[:200]

def category_customer_request(category):
    """Return a provisional category sentence, or an empty string for a null category."""
    if category is None:
        return ""
    return CATEGORY_REQUESTS[ComplaintCategory(category).value]

PROPOSED_SUGGESTED_SCRIPTS = {
    ComplaintCategory.NETWORK_AND_CONNECTIVITY:
        "ممكن توضح المشكلة بتحصل في المكالمات ولا في الإنترنت، وبتظهر في مكان معين؟",
    ComplaintCategory.BILLING_AND_CHARGES:
        "ممكن توضح أنهي بند في الفاتورة أو أنهي رسوم محتاج تستفسر عنها؟",
    ComplaintCategory.BALANCE_AND_DATA:
        "استفسارك عن الرصيد ولا عن استهلاك الإنترنت؟ ممكن توضح إيه اللي لاحظته؟",
    ComplaintCategory.APP_AND_ACCOUNT:
        "المشكلة في تسجيل الدخول ولا في استخدام خدمة جوه التطبيق؟ ممكن توضح عند أنهي خطوة ظهرت؟",
    ComplaintCategory.BRANCH_AND_STAFF:
        "شكرًا إنك شاركتنا ملاحظتك. ممكن توضح لنا تفاصيل أكتر عن ملاحظتك بخصوص الفرع أو فريق الخدمة؟",
    ComplaintCategory.NO_REPLY_OR_LONG_WAIT:
        "ممكن توضح لنا تفاصيل أكتر عن التواصل أو الانتظار، وإيه المساعدة اللي محتاجها دلوقتي؟",
    ComplaintCategory.CANCELLATION_REQUEST:
        "ممكن توضح أنهي خدمة بتسأل عن إلغائها؟ نقدر نوضح لك الخطوات والشروط الخاصة بيها.",
    ComplaintCategory.THANKS_OR_PRAISE:
        "شكرًا إنك شاركتنا تجربتك. يسعدنا نعرف إيه اللي عجبك في الخدمة.",
    ComplaintCategory.OTHER:
        "ممكن توضح موضوع استفسارك وإيه المساعدة اللي محتاجها؟",
    ComplaintCategory.OFFERS_AND_PACKAGES:
        "ممكن توضح أنهي عرض أو باقة بتسأل عنها، أو إيه أهم حاجة بتدور عليها في الباقة؟",
    ComplaintCategory.SIM_SERVICES:
        "استفسارك عن تفعيل الشريحة، استبدالها، ولا عن استخدامها؟ ممكن توضح إيه اللي محتاجه؟",
}

def suggest_script(category):
    """Look up a proposed draft for Hazem's review by enum or exact wire value."""
    return PROPOSED_SUGGESTED_SCRIPTS[ComplaintCategory(category)]

def unit_interval(value, name):
    if type(value) not in (int, float) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be numeric in [0, 1]")
    return value

def adapt_row(row, supplements, meta, *, transcripts, probabilities,
              review_threshold=DEFAULT_REVIEW_THRESHOLD):
    validate_meta(meta)
    expected = {"audio_file", *LABEL_MAP}
    if not isinstance(row, dict) or set(row) != expected:
        raise ValueError(f"Unsupported row; exact keys required: {sorted(expected)}")
    key = row["audio_file"]
    if not isinstance(key, str) or not key.strip():
        raise ValueError("audio_file must be nonempty")
    extra = {}
    if supplements is not None:
        # Runtime-only fixtures can carry explicit null-label evidence and versions.
        if not isinstance(supplements, dict) or key not in supplements:
            raise ValueError("Missing runtime fixture supplemental fields for audio_file")
        extra = supplements[key]
        if (not isinstance(extra, dict) or not SUPPLEMENT_FIELDS <= extra.keys()
                or extra.keys() - (SUPPLEMENT_FIELDS | {"confidence", "suggested_script", "voicemail_id"})):
            missing = SUPPLEMENT_FIELDS - set(extra) if isinstance(extra, dict) else SUPPLEMENT_FIELDS
            raise ValueError(f"Runtime fixture supplemental fields missing/unsupported: {sorted(missing)}")
        if extra["schema_version"] != meta["schema_version"] or extra["label_version"] != meta["label_version"]:
            raise ValueError("Row and metadata versions differ")
    if key not in transcripts:
        raise ValueError("Missing corrected text for audio_file")
    transcript = transcripts[key]
    summary = summarize_transcript(transcript)
    customer_request = category_customer_request(row["complaint_category"])
    unit_interval(review_threshold, "review_threshold")
    missing_label = any(row[field] is None for field in LABEL_MAP)
    if missing_label:
        confidence = unit_interval(extra.get("confidence"), "explicit null-label confidence")
    else:
        try:
            scores = [probabilities[key][field][row[field]] for field in LABEL_MAP]
        except (KeyError, TypeError) as exc:
            raise ValueError("Missing predicted-class probability for audio_file") from exc
        confidence = min(unit_interval(score, "predicted-class probability") for score in scores)
    category = row["complaint_category"]
    if category is None:
        script = extra.get("suggested_script")
        if not isinstance(script, str) or not script.strip():
            raise ValueError("Null category requires an explicit upstream script")
    else:
        script = suggest_script(category)
    payload = dict(extra, voicemail_id=key, summary=summary, customer_request=customer_request, confidence=confidence,
                   suggested_script=script, schema_version=SCHEMA_VERSION, label_version=LABEL_VERSION,
                   needs_human_review=missing_label or confidence < review_threshold)
    payload.update({target: row[source] for source, target in LABEL_MAP.items()})
    return TextAnalysis.model_validate(payload)

def priority_expected(text):
    # Independent verification oracle, never used to produce decisions.
    if any(getattr(text, f) is None for f in ("complaint_urgency", "churn_risk", "customer_state_text")):
        return None, None
    score = {"high": 3, "medium": 2, "low": 1}[text.complaint_urgency.value]
    score += 2 if text.churn_risk.value == "at_risk" else 0
    score += int(text.customer_state_text.value in ("mad", "frustrated"))
    return score, {1: "low", 2: "low", 3: "normal", 4: "normal", 5: "high", 6: "urgent"}[score]

def reason_type(text, before):
    if text.complaint_category is None:
        return "missing_category"
    matched = [a for a in before if text.complaint_category.value in a["skills"]]
    if not matched:
        return "no_matching_skill"
    shifted = [a for a in matched if a["on_shift"]]
    return "off_shift" if not shifted else "capacity_exhausted"

def run_batch(rows, supplements, meta, *, capacity_mode, transcripts=None, probabilities=None,
              synthetic=False, manifest_rows=None, review_threshold=DEFAULT_REVIEW_THRESHOLD,
              wire_rejections=None):
    if synthetic is not True:
        raise PermissionError("Official validation execution disabled in preparation")
    if capacity_mode != "synthetic_sequential_release":
        raise ValueError("Select explicit synthetic_sequential_release test lifecycle")
    return _run_batch(rows, supplements, meta, transcripts=transcripts, probabilities=probabilities,
                      manifest_rows=manifest_rows, review_threshold=review_threshold,
                      wire_rejections=wire_rejections)

def _run_batch(rows, supplements, meta, *, transcripts, probabilities, manifest_rows,
               review_threshold, wire_rejections, real=False):
    meta = validate_meta(meta)
    unit_interval(review_threshold, "review_threshold")
    if not isinstance(transcripts, dict) or not isinstance(probabilities, dict):
        raise ValueError("Batch requires transcript and probability maps keyed by audio_file")
    if not isinstance(rows, list):
        raise ValueError("rows must be a list")
    if not isinstance(manifest_rows, list):
        raise ValueError("Batch requires approved manifest rows")
    approved_keys = validation_manifest_keys(manifest_rows)
    approved_row_count = len(approved_keys)
    # The official reader flattens rows after validating one file-level split.
    input_keys = [prediction_key(row) for row in rows]
    wire_rejections = wire_rejections or {}
    counts = Counter(key for key in input_keys if key is not None)
    missing_keys = sorted(approved_keys - counts.keys())
    unexpected_keys = sorted(counts.keys() - approved_keys)
    duplicate_keys = sorted(key for key, count in counts.items() if count > 1)
    joined_ids = {}
    if isinstance(supplements, dict):
        for key in approved_keys & counts.keys():
            extra = supplements.get(key[1])
            voicemail_id = extra.get("voicemail_id") if isinstance(extra, dict) else None
            if isinstance(voicemail_id, str) and voicemail_id.strip():
                joined_ids[key] = voicemail_id
    id_counts = Counter(joined_ids.values())
    initial, records, errors, rejections, prepared = snapshot(), [], [], [], []
    for index, (row, composite_key) in enumerate(zip(rows, input_keys, strict=True)):
        stage = "manifest_reconciliation"
        if composite_key is None:
            code, diagnostic = "invalid_prediction_key", "Missing or invalid prediction audio_file"
        elif counts[composite_key] > 1:
            code, diagnostic = "duplicate_prediction_key", "Duplicate prediction composite key"
        elif composite_key not in approved_keys:
            code, diagnostic = "unexpected_prediction_key", "Unexpected prediction composite key"
        elif index in wire_rejections:
            stage = "official_reader"
            code, diagnostic = "invalid_wire_row", wire_rejections[index]
        elif id_counts[joined_ids.get(composite_key)] > 1:
            code, diagnostic = "duplicate_legacy_id", "Duplicate voicemail_id"
        else:
            try:
                text = adapt_row(row, supplements, meta, transcripts=transcripts,
                                 probabilities=probabilities, review_threshold=review_threshold)
                prepared.append((index, composite_key[1], text))
                continue
            except (ValueError, TypeError) as exc:
                stage = "runtime_adapter"
                code, diagnostic = "invalid_runtime_row", str(exc)
        errors.append({"row_index": index, "key": composite_key, "error": diagnostic})
        rejections.append({"source_index": index, "key": composite_key, "stage": stage,
                           "reason_code": code, "diagnostic": diagnostic})
    for index, key, text in prepared:
        before = snapshot()
        eligible = [a for a in before if text.complaint_category is not None
                    and text.complaint_category.value in a["skills"] and a["on_shift"]
                    and a["current_load"] < a["capacity"]]
        decision = None
        try:
            decision = triage_phase1(text)
            expected_id = eligible[0]["id"] if eligible else None
            assert decision.assigned_agent_id == expected_id
            assert decision.assignment_status.value == ("assigned" if expected_id else "unassigned")
            assert decision.route_reason.strip()
            score, bucket = priority_expected(text)
            assert decision.priority_score == score
            assert (decision.queue_priority.value if decision.queue_priority else None) == bucket
            assert score is not None or text.needs_human_review
            expected_loads = copy.deepcopy(before)
            for a in expected_loads:
                a["current_load"] += int(a["id"] == expected_id)
            assert snapshot() == expected_loads, "Unexpected Agent mutation"
            records.append({"row_index": index, "audio_file": key, "voicemail_id": text.voicemail_id,
                "transcript": transcripts[key], "decision": decision.model_dump(mode="json"), "human_review": text.needs_human_review or expected_id is None,
                "unassigned_type": reason_type(text, before) if expected_id is None else None,
                "eligibility_verified": True, "priority_verified": True})
        finally:
            # Runner owns returned reservations; official triage owns its own failed construction.
            # No TicketStore.complete call, no second release, no reset_loads.
            if decision is not None and decision.assigned_agent_id is not None:
                agents.release(decision.assigned_agent_id)
            assert snapshot() == before, "Reservation cleanup failed"
    assert snapshot() == initial
    processed = len(records)
    assigned = sum(r["decision"]["assignment_status"] == "assigned" for r in records)
    invalid_approved = len({item["key"] for item in rejections if item["key"] in approved_keys})
    routing_unassigned = processed - assigned
    if assigned + routing_unassigned + invalid_approved + len(missing_keys) != approved_row_count:
        raise RuntimeError("Approved manifest reconciliation invariant failed")
    return {"scope": "REAL VALIDATION" if real else "SYNTHETIC ONLY", "metrics_scope": "sequential_validation",
        "metadata": meta, "capacity_mode": "sequential_release" if real else "synthetic_sequential_release",
        "review_threshold": review_threshold,
        "skill_additions_approval": "APPROVED_HAZEM", "total_input_rows": len(rows),
        "approved_manifest_rows": approved_row_count,
        "manifest_reconciliation": {"missing_keys": missing_keys, "duplicate_keys": duplicate_keys,
                                    "unexpected_keys": unexpected_keys},
        "missing_predictions": [{"key": key, "error": "Missing prediction for approved manifest key"}
                                for key in missing_keys],
        "valid_rows": len(prepared), "invalid_rows": len(errors), "processed_rows": processed,
        "input_coverage_rate": processed / len(rows) if rows else None,
        "approved_validation_coverage_rate": processed / approved_row_count if approved_row_count else None,
        "assigned_count": assigned, "unassigned_count": approved_row_count - assigned,
        "routing_unassigned_count": routing_unassigned,
        "invalid_approved_rows": invalid_approved,
        "missing_approved_rows": len(missing_keys),
        "assignment_rate": assigned / approved_row_count if approved_row_count else None,
        "assignment_rate_denominator": approved_row_count,
        "assigned_over_processed_diagnostic": assigned / processed if processed else None,
        "priority_bucket_distribution": dict(Counter(r["decision"]["queue_priority"] or "null" for r in records)),
        "null_priority_count": sum(r["decision"]["priority_score"] is None for r in records),
        "human_review_count": sum(r["human_review"] for r in records),
        "unassigned_reasons": dict(Counter(r["unassigned_type"] for r in records if r["unassigned_type"])),
        "contract_validation_errors": errors, "rejected_submitted_occurrences": rejections, "records": records,
        "official_validation_result": real or None, "target_assignment_rate": 0.9}

APPROVED_VALIDATION_SEEDS = (7, 42, 99, 1337, 2023)
APPROVED_MANIFEST_REVISION = "32e32436854cd214346ff87e7dc856897645eae0"
EXPORT_CLASSES = {
    "complaint_category": [category.value for category in ComplaintCategory],
    "complaint_urgency": [urgency.value for urgency in ComplaintUrgency],
    "customer_state": ["calm", "frustrated", "mad", "satisfied"],
    "churn_risk": [risk.value for risk in ChurnRisk],
}

class ValidationFileError(ValueError):
    """Fatal preflight failure. No seed metrics are produced."""

def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationFileError(f"Duplicate JSON object field: {key}")
        result[key] = value
    return result

def prediction_key(row):
    audio_file = row.get("audio_file") if isinstance(row, dict) else None
    if isinstance(audio_file, str) and audio_file.strip():
        return APPROVED_VALIDATION_SPLIT, audio_file
    return None

def run_validation_seed(payload, *, source_path, seed, manifest_rows, manifest_revision,
                        synthetic=False, review_threshold=DEFAULT_REVIEW_THRESHOLD):
    """Exercise one seed using supplied synthetic bytes. This never opens source_path."""
    if synthetic is not True:
        raise PermissionError("Use the separately authorized Real Validation entry point")
    return _run_validation_seed(payload, source_path=source_path, seed=seed, manifest_rows=manifest_rows,
                                manifest_revision=manifest_revision, review_threshold=review_threshold)

def _run_validation_seed(payload, *, source_path, seed, manifest_rows, manifest_revision,
                         review_threshold, real=False):
    if type(seed) is not int or seed not in APPROVED_VALIDATION_SEEDS:
        raise ValidationFileError("Seed is not approved for Validation")
    expected_path = Path(APPROVED_PREDICTIONS_DIR) / f"predictions_val_seed{seed}.json"
    source_path = Path(source_path)
    if source_path.parts[-len(expected_path.parts):] != expected_path.parts:
        raise ValidationFileError(f"Expected Validation source path ending in {expected_path.as_posix()}")
    if manifest_revision != APPROVED_MANIFEST_REVISION:
        raise ValidationFileError("Unexpected approved manifest revision")
    try:
        if not isinstance(manifest_rows, list):
            raise ValueError("Expected a list of Validation manifest rows")
        approved_keys = validation_manifest_keys(manifest_rows)
    except ValueError as exc:
        raise ValidationFileError(str(exc)) from exc
    if len(approved_keys) != APPROVED_VALIDATION_ROW_COUNT:
        raise ValidationFileError("Approved manifest must contain exactly 1,003 unique val keys")
    if not isinstance(payload, bytes):
        raise ValidationFileError("Expected in-memory prediction bytes")
    try:
        envelope = json.loads(payload.decode("utf-8"), object_pairs_hook=unique_json_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationFileError(f"Invalid prediction JSON: {exc}") from exc
    header = {"schema_version": PREDICTIONS_SCHEMA_VERSION, "split": APPROVED_VALIDATION_SPLIT,
              "seed": seed, "run_id": APPROVED_PREDICTIONS_RUN, "model": "MARBERTv2",
              "dataset_version": "v2"}
    if not isinstance(envelope, dict) or envelope.keys() != header.keys() | {"rows"}:
        raise ValidationFileError("Unexpected prediction envelope fields")
    for name, expected in header.items():
        actual = envelope[name]
        if type(actual) is not type(expected) or actual != expected:
            raise ValidationFileError(f"Unexpected prediction header {name}: expected {expected!r}")
    original_rows = envelope["rows"]
    if not isinstance(original_rows, list) or not original_rows:
        raise ValidationFileError("Prediction envelope requires a non-empty rows list")
    keys = [prediction_key(row) for row in original_rows]
    occurrences = Counter(key for key in keys if key is not None)
    rows, probabilities, wire_rejections = [], {}, {}
    with TemporaryDirectory(prefix="svr-row-validation-") as temporary:
        candidate_path = Path(temporary) / "validation_row.json"
        for index, (row, key) in enumerate(zip(original_rows, keys, strict=True)):
            # Keep one slot per submitted occurrence so reconciliation retains source indexes.
            rows.append({"audio_file": key[1]} if key else {})
            if key is None or occurrences[key] > 1 or key not in approved_keys:
                continue
            candidate_path.write_text(json.dumps(dict(header, rows=[row])), encoding="utf-8")
            try:
                validated = read_predictions_file(candidate_path, EXPORT_CLASSES,
                                                  expected_split=APPROVED_VALIDATION_SPLIT)
            except PredictionsFileError as exc:
                wire_rejections[index] = str(exc)
                continue
            rows[index] = validated["harness_rows"][0]
            probabilities.update(validated["probabilities"])
    meta = dict(header, split="validation", schema_version=SCHEMA_VERSION, label_version=LABEL_VERSION)
    report = _run_batch(rows, None, meta, transcripts=index_transcripts(manifest_rows), probabilities=probabilities,
                        manifest_rows=manifest_rows, wire_rejections=wire_rejections,
                        review_threshold=review_threshold, real=real)
    report["provenance"] = {
        "file_path": source_path.as_posix(), "sha256": hashlib.sha256(payload).hexdigest(),
        "seed": seed, "run_id": header["run_id"], "model": header["model"],
        "dataset_version": header["dataset_version"], "manifest_revision": manifest_revision,
    }
    return report

# Real execution is opt-in and is never invoked by Run All.
APPROVED_DATA_ROOT = Path("C:/Users/RC/svr-data")
APPROVED_MANIFEST_BLOB = "b1adfcc118a766a44bdc1fbe60f372829b2dc720"
REAL_VALIDATION_AUTHORIZATION = "AUTHORIZE_PHASE2_REAL_VALIDATION"
APPROVED_ARTIFACT_SHA256 = {
    TRANSCRIPT_SOURCE: "50df253ad6506b70a262b512eff1f79562f2cd65d58143127899025ad707cb18",
    f"{APPROVED_PREDICTIONS_DIR}/predictions_val_seed7.json":
        "8c560479b2b71441eca9ed8011dc1adfe68e1c3e8029293917841d75d0853036",
    f"{APPROVED_PREDICTIONS_DIR}/predictions_val_seed42.json":
        "8caa187812034242a56ef9f3fa33a6417bcbc797a9b9b94065b2f3c3f9a038c7",
    f"{APPROVED_PREDICTIONS_DIR}/predictions_val_seed99.json":
        "8c4fcfbca9eab8ed0dc6418ca035a98ba996378957c0a15add30cef170877225",
    f"{APPROVED_PREDICTIONS_DIR}/predictions_val_seed1337.json":
        "05525ece42b95db58ca1f4d1f71fe580e6d349ecdbfc1b3e8c973ff69771befc",
    f"{APPROVED_PREDICTIONS_DIR}/predictions_val_seed2023.json":
        "e6948b2150dd7af0682d21ac897ca0cb5eb968960b08abcca5ed9de398bc3f51",
}

def approved_artifact_path(relative):
    if relative not in APPROVED_ARTIFACT_SHA256:
        raise ValidationFileError("Path is outside the approved Validation allowlist")
    path = APPROVED_DATA_ROOT / relative
    try:
        for component in (*reversed(path.parents), path):
            info = component.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValidationFileError(f"Validation artifact path contains a redirect: {component}")
        if path.resolve(strict=True) != path or not stat.S_ISREG(info.st_mode):
            raise ValidationFileError(f"Expected a regular file at the exact approved path: {path}")
    except (OSError, RuntimeError) as exc:
        raise ValidationFileError(f"Cannot verify Validation artifact path: {path}") from exc
    return path

def read_windows_artifact(path):
    """Hold each directory open without delete sharing and open the leaf without following redirects."""
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    open_handle = kernel.CreateFileW
    open_handle.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    open_handle.restype = wintypes.HANDLE
    close_handle = kernel.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    get_attributes = kernel.GetFileInformationByHandleEx
    get_attributes.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
    open_existing = 3
    open_reparse_point = 0x00200000
    backup_semantics = 0x02000000
    attribute_tag_info = 9
    read_attributes = 0x80
    generic_read = 0x80000000
    share_read, share_write = 1, 2
    invalid_handle = ctypes.c_void_p(-1).value

    def checked_handle(component, *, directory):
        handle = open_handle(str(component), read_attributes if directory else generic_read,
                             share_read | share_write if directory else share_read,
                             None, open_existing, open_reparse_point | backup_semantics, None)
        if handle == invalid_handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            # FILE_ATTRIBUTE_TAG_INFO consists of two DWORDs.
            attributes = (wintypes.DWORD * 2)()
            if not get_attributes(handle, attribute_tag_info, ctypes.byref(attributes), ctypes.sizeof(attributes)):
                raise ctypes.WinError(ctypes.get_last_error())
            if (attributes[0] & stat.FILE_ATTRIBUTE_REPARSE_POINT
                    or bool(attributes[0] & stat.FILE_ATTRIBUTE_DIRECTORY) != directory):
                raise ValidationFileError(f"Unexpected file type or redirect at {component}")
        except BaseException:
            close_handle(handle)
            raise
        return handle

    with ExitStack() as parents:
        for parent in reversed(path.parents):
            parents.callback(close_handle, checked_handle(parent, directory=True))
        handle = checked_handle(path, directory=False)
        try:
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except BaseException:
            close_handle(handle)
            raise
        with os.fdopen(fd, "rb") as stream:
            return stream.read()

def read_posix_artifact(path):
    """Walk from the root using directory descriptors without following symlinks."""
    with ExitStack() as descriptors:
        flags = os.O_RDONLY | os.O_NOFOLLOW
        directory = os.open(path.anchor, flags | os.O_DIRECTORY)
        descriptors.callback(os.close, directory)
        for part in path.parts[1:-1]:
            directory = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
            descriptors.callback(os.close, directory)
        fd = os.open(path.name, flags | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValidationFileError("Expected a regular Validation artifact")
            return stream.read()

def authenticated_artifact(relative):
    path = approved_artifact_path(relative)
    try:
        payload = read_windows_artifact(path) if os.name == "nt" else read_posix_artifact(path)
    except OSError as exc:
        raise ValidationFileError(f"Cannot safely open Validation artifact: {path}") from exc
    if hashlib.sha256(payload).hexdigest() != APPROVED_ARTIFACT_SHA256[relative]:
        raise ValidationFileError(f"SHA-256 mismatch for {relative}")
    return path, payload

def authenticated_manifest(payload):
    if (git(APPROVED_DATA_ROOT, "rev-parse", "HEAD") != APPROVED_MANIFEST_REVISION
            or git(APPROVED_DATA_ROOT, "rev-parse", f"{APPROVED_MANIFEST_REVISION}:{TRANSCRIPT_SOURCE}")
            != APPROVED_MANIFEST_BLOB):
        raise ValidationFileError("Approved manifest Git revision or tracked blob mismatch")
    # The SHA-256 authenticates exact CRLF working bytes. Git stores the LF-normalized blob.
    normalized = payload.replace(b"\r\n", b"\n")
    git_object_header = f"blob {len(normalized)}\0".encode("ascii")
    if hashlib.sha1(git_object_header + normalized).hexdigest() != APPROVED_MANIFEST_BLOB:
        raise ValidationFileError("Manifest bytes do not match the approved Git blob")
    try:
        with io.StringIO(payload.decode("utf-8-sig"), newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            headers = reader.fieldnames or []
            if len(headers) != len(set(headers)) or not {"split", "audio_file", "text"} <= set(headers):
                raise ValidationFileError("Manifest header has missing or duplicate fields")
            rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValidationFileError("Invalid approved manifest CSV") from exc
    if (len(validation_manifest_keys(rows)) != APPROVED_VALIDATION_ROW_COUNT
            or any(None in row or None in row.values() or not row["text"].strip() for row in rows)):
        raise ValidationFileError("Manifest requires 1,003 complete and unique val keys with corrected text")
    return rows

def run_authorized_validation(*, authorization=None, review_threshold=DEFAULT_REVIEW_THRESHOLD):
    """Run the five approved seeds only after explicit authorization and artifact authentication."""
    if type(authorization) is not str or authorization != REAL_VALIDATION_AUTHORIZATION:
        raise PermissionError("Separate explicit authorization is required for Real Validation")
    if not __debug__ or snapshot() != BASELINE:
        raise RuntimeError("Real Validation requires assertions and baseline Agent State")
    unit_interval(review_threshold, "review_threshold")
    manifest_path, manifest_bytes = authenticated_artifact(TRANSCRIPT_SOURCE)
    manifest_rows = authenticated_manifest(manifest_bytes)
    sources = {
        seed: authenticated_artifact(f"{APPROVED_PREDICTIONS_DIR}/predictions_val_seed{seed}.json")
        for seed in APPROVED_VALIDATION_SEEDS
    }
    reports = {}
    try:
        for seed, (path, payload) in sources.items():
            report = _run_validation_seed(
                payload, source_path=path, seed=seed, manifest_rows=manifest_rows,
                manifest_revision=APPROVED_MANIFEST_REVISION, review_threshold=review_threshold, real=True,
            )
            report["provenance"].update(manifest_file_path=manifest_path.as_posix(),
                                        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
                                        manifest_git_blob=APPROVED_MANIFEST_BLOB)
            reports[seed] = report
    finally:
        if snapshot() != BASELINE:
            raise RuntimeError("Real Validation failed to restore Agent State")
    return reports

META = {"run_id": "synthetic-preparation", "model": "synthetic-fixture-v1",
        "dataset_version": "synthetic-only", "seed": 42, "split": "validation",
        "schema_version": 1, "label_version": LABEL_VERSION}
def fixture(key="synthetic-001", **labels):
    row = {"audio_file": key, "complaint_category": "network_and_connectivity",
           "complaint_urgency": "medium", "customer_state": "frustrated", "churn_risk": "not_at_risk"}
    row.update(labels)
    supplement = {"voicemail_id": "vm-" + key, "suggested_script": "Synthetic draft script",
        "confidence": 0.9,
        "schema_version": 1, "label_version": LABEL_VERSION}
    return row, {key: supplement}
def run_one(**labels):
    row, supplemental = fixture(**labels)
    return synthetic_batch([row], supplemental, META, capacity_mode="synthetic_sequential_release", synthetic=True)

SYNTHETIC_TRANSCRIPT = "  Corrected transcript with punctuation! "
def fixture_inputs(rows):
    return {
        "transcripts": index_transcripts({"audio_file": row["audio_file"], "text": SYNTHETIC_TRANSCRIPT}
                                         for row in rows if isinstance(row, dict)
                                         and isinstance(row.get("audio_file"), str)),
        "probabilities": {row["audio_file"]: {field: {row.get(field): 0.9} for field in LABEL_MAP}
                          for row in rows if isinstance(row, dict) and isinstance(row.get("audio_file"), str)},
    }

def adapt_fixture(row, supplements, meta):
    return adapt_row(row, supplements, meta, **fixture_inputs([row]))

def synthetic_batch(rows, supplements, meta, **kwargs):
    unique = {row["audio_file"]: row for row in rows
              if isinstance(row, dict) and isinstance(row.get("audio_file"), str)}
    kwargs.setdefault("manifest_rows", fixture_manifest(supplements))
    return run_batch(rows, supplements, meta, **fixture_inputs(unique.values()), **kwargs)

def fixture_manifest(audio_files):
    return [{"split": APPROVED_VALIDATION_SPLIT, "audio_file": key} for key in audio_files]