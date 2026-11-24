"""Mock predictions for fixtures: no model, fully predictable.

make_mock_predictions copies the true labels. With wrong_every=k, every k-th row
(counting from 1) gets the NEXT class in the field's class list instead, in every
field, so the expected scores can be worked out by hand. It uses no randomness.

A true label that is excluded for a field (see harness.py) is not a class, so a
model could never predict it. For those rows the mock predicts the first class.
"""
from infra.harness import HarnessError


def make_mock_predictions(truth_rows, classes_by_field, wrong_every=None, exclusions_by_field=None):
    if wrong_every is not None and (
        isinstance(wrong_every, bool) or not isinstance(wrong_every, int) or wrong_every < 1
    ):
        raise HarnessError(f"wrong_every must be a positive integer or None, got {wrong_every!r}")
    exclusions = exclusions_by_field or {}
    preds = []
    for i, row in enumerate(truth_rows, start=1):
        pred = {"audio_file": row["audio_file"]}
        for field, classes in classes_by_field.items():
            label = row[field]
            if label in exclusions.get(field, {}).get("labels", []):
                label = classes[0]
            elif label not in classes:
                raise HarnessError(f"row {row['audio_file']}: {field}={label!r} is not in {classes}")
            elif wrong_every is not None and i % wrong_every == 0:
                label = classes[(classes.index(label) + 1) % len(classes)]
            pred[field] = label
        preds.append(pred)
    return preds