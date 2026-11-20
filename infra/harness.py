"""The evaluation harness: score a set of predictions against the true labels.

It works on rows in memory, so it runs on mock predictions before any model exists.
A row is a dict with an `audio_file` and one label per field.

Rules it enforces:
- Rows are matched by `audio_file` INSIDE one split. The same name can appear in
  different splits (they are different recordings), so a split is always scored on
  its own and names are never compared across splits.
- Every true row needs exactly one predicted row, and the other way round: nothing
  missing, nothing extra, nothing repeated. Every field must be predicted.
- Predicted labels must be in the class list of their field (the approved enums).
- The macro average is taken over the class list of each field (see metrics.py).
- An exclusion removes the rows with a given TRUE label from ONE field's score only
  (for example `unclear` from customer_state, by Hazem's decision). Those rows still
  count in every other field. Each exclusion is written in the report under
  `exceptions`, with the reason and the number of rows removed.
- The report always says that the labels come from a model and are still being
  audited, until the audit approves them.

It does not decide which split may be scored, or how many times: the rule that the
test split is evaluated exactly once is a separate guard.
"""
from infra.metrics import MetricsError, combine_macro_f1, evaluate_field
from infra.once_guard import EvaluationClaim, GuardError
from infra.run_record import EVALUATED_SPLITS

SCHEMA_VERSION = 2

DEFAULT_LABEL_STATUS = (
    "The labels come from a model and are still being audited by the team. "
    "They are not human-verified until the audit approves them."
)


class HarnessError(ValueError):
    """The predictions and the true labels cannot be compared."""


def _index_by_audio_file(name, rows, fields):
    if not isinstance(rows, list) or not rows:
        raise HarnessError(f"{name} must be a non-empty list of rows")
    indexed = {}
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("audio_file"), str) or not row["audio_file"]:
            raise HarnessError(f"{name}[{i}] needs a non-empty string 'audio_file'")
        missing = [f for f in fields if f not in row]
        if missing:
            raise HarnessError(f"{name}[{i}] ({row['audio_file']}) is missing fields {missing}")
        if row["audio_file"] in indexed:
            raise HarnessError(f"{name} has the audio_file {row['audio_file']!r} more than once")
        indexed[row["audio_file"]] = row
    return indexed


def _check_exclusions(exclusions_by_field, classes_by_field):
    """exclusions_by_field: {field: {"labels": [...], "reason": "..."}}"""
    if exclusions_by_field is None:
        return {}
    if not isinstance(exclusions_by_field, dict):
        raise HarnessError("exclusions_by_field must be a dict of field -> {labels, reason}")
    for field, rule in exclusions_by_field.items():
        if field not in classes_by_field:
            raise HarnessError(f"exclusion for {field!r}, which is not one of the fields")
        if not isinstance(rule, dict) or set(rule) != {"labels", "reason"}:
            raise HarnessError(f"exclusion for {field} needs exactly the keys 'labels' and 'reason'")
        labels, reason = rule["labels"], rule["reason"]
        if not isinstance(labels, list) or not labels or not all(isinstance(x, str) and x for x in labels):
            raise HarnessError(f"exclusion for {field}: labels must be a non-empty list of strings")
        if not isinstance(reason, str) or not reason.strip():
            raise HarnessError(f"exclusion for {field} needs a reason")
        overlap = sorted(set(labels) & set(classes_by_field[field]))
        if overlap:
            raise HarnessError(
                f"exclusion for {field}: {overlap} are also in the class list, "
                "a label cannot be both scored and excluded"
            )
    return exclusions_by_field


def evaluate_predictions(
    split,
    truth_rows,
    pred_rows,
    classes_by_field,
    exclusions_by_field=None,
    label_status=DEFAULT_LABEL_STATUS,
    test_claim=None,
):
    if split not in EVALUATED_SPLITS:
        raise HarnessError(f"split must be one of {EVALUATED_SPLITS}, got {split!r}")
    if split == "test":
        if not isinstance(test_claim, EvaluationClaim):
            raise HarnessError(
                "the test split can only be scored with a claim from the test-once guard"
            )
        try:
            test_claim.consume()
        except GuardError as exc:
            raise HarnessError(str(exc)) from exc
    elif test_claim is not None:
        raise HarnessError("test_claim must be None when scoring the 'val' split")
    if not isinstance(classes_by_field, dict) or not classes_by_field:
        raise HarnessError("classes_by_field must be a non-empty dict of field -> class list")
    exclusions = _check_exclusions(exclusions_by_field, classes_by_field)
    fields = list(classes_by_field)

    truth = _index_by_audio_file("truth_rows", truth_rows, fields)
    preds = _index_by_audio_file("pred_rows", pred_rows, fields)

    missing = sorted(set(truth) - set(preds))
    extra = sorted(set(preds) - set(truth))
    if missing:
        raise HarnessError(f"{len(missing)} true rows have no prediction, for example {missing[:5]}")
    if extra:
        raise HarnessError(f"{len(extra)} predictions have no true row, for example {extra[:5]}")

    keys = list(truth)  # a fixed order, so every field uses the same rows
    reports, exceptions = {}, []
    for field, classes in classes_by_field.items():
        excluded_labels = set(exclusions[field]["labels"]) if field in exclusions else set()
        # A prediction must be a real class even on a row that is left out of the score.
        for k in keys:
            if preds[k][field] not in classes:
                raise HarnessError(
                    f"field {field}: the prediction for {k!r} is {preds[k][field]!r}, "
                    f"which is not in the class list {classes}"
                )
        scored = [k for k in keys if truth[k][field] not in excluded_labels]
        try:
            report = evaluate_field(
                [truth[k][field] for k in scored],
                [preds[k][field] for k in scored],
                classes,
            )
        except MetricsError as exc:
            raise HarnessError(f"field {field}: {exc}") from exc
        report["n_excluded"] = len(keys) - len(scored)
        reports[field] = report
        if field in exclusions:
            exceptions.append({
                "field": field,
                "excluded_labels": list(exclusions[field]["labels"]),
                "rows_excluded": len(keys) - len(scored),
                "n_scored": len(scored),
                "n_total_rows": len(keys),
                "reason": exclusions[field]["reason"],
            })

    return {
        "schema_version": SCHEMA_VERSION,
        "split": split,
        "n": len(keys),
        "label_status": label_status,
        "fields": reports,
        "exceptions": exceptions,
        "combined_macro_f1": combine_macro_f1(reports),
    }


def load_truth_table(path, split, fields):
    """Read the true labels of one split from a clean_training_<split>.csv.

    Only audio_file, split and the label columns are read. The transcript text
    columns are never loaded.
    """
    import pandas as pd

    columns = ["audio_file", "split", *fields]
    try:
        table = pd.read_csv(path, usecols=columns, dtype=str, keep_default_na=False)
    except ValueError as exc:  # a missing column
        raise HarnessError(f"{path}: {exc}") from exc
    wrong = sorted(set(table["split"]) - {split})
    if wrong:
        raise HarnessError(f"{path}: the split column has {wrong}, expected only {split!r}")
    return table[["audio_file", *fields]].to_dict("records")