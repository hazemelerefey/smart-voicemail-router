import copy
import json

import pytest

from infra.harness import evaluate_predictions
from infra.predictions_file import (
    PredictionsFileError,
    predictions_path,
    read_predictions_file,
    write_predictions_file,
)

# The class lists of the approved enums (the keys of class_weights.json).
# customer_state has the 4 classes only: unclear is not a class.
CLASSES = {
    "complaint_category": [
        "app_and_account", "balance_and_data", "billing_and_charges", "branch_and_staff",
        "cancellation_request", "network_and_connectivity", "no_reply_or_long_wait",
        "offers_and_packages", "other", "sim_services", "thanks_or_praise",
    ],
    "complaint_urgency": ["high", "low", "medium"],
    "customer_state": ["calm", "frustrated", "mad", "satisfied"],
    "churn_risk": ["at_risk", "not_at_risk"],
}
HEADER = dict(run_id="001", model="EgyBERT", split="val", seed=42, dataset_version="v2")


def probs_for(label_by_field, confidence=0.7):
    """A valid probability dict whose most probable class is the given one."""
    out = {}
    for field, classes in CLASSES.items():
        rest = (1.0 - confidence) / (len(classes) - 1)
        out[field] = {c: (confidence if c == label_by_field[field] else rest) for c in classes}
    return out


def labels(**overrides):
    base = {
        "complaint_category": "other", "complaint_urgency": "low",
        "customer_state": "calm", "churn_risk": "not_at_risk",
    }
    base.update(overrides)
    return base


def rows():
    return [
        {"audio_file": "a1.wav", "probabilities": probs_for(labels())},
        {"audio_file": "a2.wav", "probabilities": probs_for(labels(customer_state="mad", churn_risk="at_risk"))},
        {"audio_file": "a3.wav", "probabilities": probs_for(labels(complaint_urgency="high"))},
    ]


def write(tmp_path, **overrides):
    args = dict(HEADER, path=tmp_path / "p.json", rows=rows(), classes_by_field=CLASSES)
    args.update(overrides)
    return write_predictions_file(**args)


def read(path, **overrides):
    args = dict(path=path, classes_by_field=CLASSES, expected_split="val")
    args.update(overrides)
    return read_predictions_file(**args)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------- writing and reading ----------

def test_the_file_has_the_agreed_shape(tmp_path):
    data = load(write(tmp_path))
    assert list(data) == ["schema_version", "run_id", "model", "split", "seed", "dataset_version", "rows"]
    assert data["run_id"] == "001" and data["split"] == "val" and data["seed"] == 42
    assert list(data["rows"][0]) == ["audio_file", "labels", "probabilities"]
    assert set(data["rows"][0]["labels"]) == set(CLASSES)
    assert set(data["rows"][0]["probabilities"]["customer_state"]) == {"calm", "frustrated", "mad", "satisfied"}


def test_the_writer_computes_the_labels_from_the_probabilities(tmp_path):
    data = load(write(tmp_path))
    assert data["rows"][1]["labels"]["customer_state"] == "mad"
    assert data["rows"][1]["labels"]["churn_risk"] == "at_risk"
    assert data["rows"][2]["labels"]["complaint_urgency"] == "high"


def test_a_tie_goes_to_the_first_class_in_the_list(tmp_path):
    flat = {field: {c: 1 / len(classes) for c in classes} for field, classes in CLASSES.items()}
    data = load(write(tmp_path, rows=[{"audio_file": "a1.wav", "probabilities": flat}]))
    assert data["rows"][0]["labels"] == {field: classes[0] for field, classes in CLASSES.items()}
    read(tmp_path / "p.json")  # and the reader accepts it


def test_round_trip(tmp_path):
    path = write(tmp_path)
    result = read(path)
    assert result["meta"] == {**HEADER, "schema_version": 1, "n_rows": 3}
    assert result["harness_rows"][1] == {"audio_file": "a2.wav", **labels(customer_state="mad", churn_risk="at_risk")}
    assert result["probabilities"]["a1.wav"]["customer_state"]["calm"] == pytest.approx(0.7)
    assert list(result["probabilities"]) == ["a1.wav", "a2.wav", "a3.wav"]


def test_numpy_floats_are_accepted_and_written_as_plain_numbers(tmp_path):
    np = pytest.importorskip("numpy")
    rs = rows()
    rs[0]["probabilities"]["churn_risk"] = {"at_risk": np.float32(0.25), "not_at_risk": np.float32(0.75)}
    data = load(write(tmp_path, rows=rs))
    assert data["rows"][0]["labels"]["churn_risk"] == "not_at_risk"
    read(tmp_path / "p.json")


def test_the_file_never_overwrites(tmp_path):
    write(tmp_path)
    with pytest.raises(FileExistsError):
        write(tmp_path)


def test_the_path_helper(tmp_path):
    p = predictions_path(tmp_path, "001", "val", 42)
    assert p == tmp_path / "exp_001" / "predictions_val_seed42.json"
    with pytest.raises(PredictionsFileError, match="split"):
        predictions_path(tmp_path, "001", "train", 42)
    assert "transcript" not in str(p)


def test_the_writer_creates_the_run_folder(tmp_path):
    path = write(tmp_path, path=predictions_path(tmp_path, "001", "val", 42))
    assert path.is_file() and path.parent.name == "exp_001"


# ---------- it feeds the harness, including the unclear row ----------

def test_the_rows_go_straight_into_the_harness_with_the_unclear_exception(tmp_path):
    truth = [
        {"audio_file": "a1.wav", **labels()},
        {"audio_file": "a2.wav", **labels(customer_state="mad", churn_risk="at_risk")},
        {"audio_file": "a3.wav", **labels(customer_state="unclear", complaint_urgency="high")},
    ]
    exclusions = {"customer_state": {"labels": ["unclear"], "reason": "left out of customer_state only"}}
    # a3's true state is unclear: the model still has to predict one of the 4 classes.
    result = read(write(tmp_path))
    report = evaluate_predictions("val", truth, result["harness_rows"], CLASSES, exclusions)
    assert report["fields"]["customer_state"]["n"] == 2
    assert report["fields"]["complaint_urgency"]["n"] == 3
    assert report["exceptions"][0]["rows_excluded"] == 1
    assert report["fields"]["customer_state"]["accuracy"] == pytest.approx(1.0)


# ---------- the writer refuses bad input ----------

def test_the_writer_needs_the_probabilities_of_every_field(tmp_path):
    rs = rows()
    del rs[1]["probabilities"]["churn_risk"]
    with pytest.raises(PredictionsFileError, match="forced"):
        write(tmp_path, rows=rs)


def test_the_writer_refuses_probabilities_that_do_not_add_up(tmp_path):
    rs = rows()
    rs[0]["probabilities"]["customer_state"]["calm"] = 0.2
    with pytest.raises(PredictionsFileError, match="add up"):
        write(tmp_path, rows=rs)
    assert not (tmp_path / "p.json").exists()


def test_the_writer_refuses_unclear_as_a_state_class(tmp_path):
    rs = rows()
    rs[0]["probabilities"]["customer_state"] = {
        "calm": 0.5, "frustrated": 0.1, "mad": 0.1, "satisfied": 0.1, "unclear": 0.2,
    }
    with pytest.raises(PredictionsFileError, match="exactly the classes"):
        write(tmp_path, rows=rs)


def test_the_writer_refuses_extra_row_keys_such_as_text(tmp_path):
    rs = rows()
    rs[0]["text"] = "SECRET"
    with pytest.raises(PredictionsFileError, match="exactly"):
        write(tmp_path, rows=rs)


def test_the_writer_refuses_bad_headers(tmp_path):
    for bad in [
        dict(run_id="../x"), dict(run_id=""), dict(model=" "), dict(split="train"),
        dict(seed=-1), dict(seed=True), dict(seed="42"), dict(dataset_version=""),
    ]:
        with pytest.raises(PredictionsFileError):
            write(tmp_path, **bad)


@pytest.mark.parametrize("bad", [[], None, "x"])
def test_the_writer_refuses_missing_rows(tmp_path, bad):
    with pytest.raises(PredictionsFileError):
        write(tmp_path, rows=bad)


def test_the_writer_refuses_repeated_audio_files(tmp_path):
    rs = rows()
    rs.append(copy.deepcopy(rs[0]))
    with pytest.raises(PredictionsFileError, match="more than once"):
        write(tmp_path, rows=rs)


@pytest.mark.parametrize("bad", [-0.1, 1.2, float("nan"), float("inf"), None, True, "0.5"])
def test_the_writer_refuses_bad_probability_values(tmp_path, bad):
    rs = rows()
    rs[0]["probabilities"]["churn_risk"]["at_risk"] = bad
    with pytest.raises(PredictionsFileError):
        write(tmp_path, rows=rs)


def test_bad_class_lists_are_refused(tmp_path):
    for bad in [{}, {"f": []}, {"f": ["a", "a"]}, {"f": ["a", ""]}, {"": ["a"]}, [1]]:
        with pytest.raises(PredictionsFileError):
            write(tmp_path, classes_by_field=bad)


# ---------- the reader refuses bad files ----------

def test_the_reader_needs_to_be_told_the_split(tmp_path):
    path = write(tmp_path)
    with pytest.raises(TypeError):
        read_predictions_file(path, CLASSES)
    with pytest.raises(PredictionsFileError, match="expected_split"):
        read(path, expected_split="train")


def test_a_file_of_another_split_is_refused(tmp_path):
    path = write(tmp_path, split="test")
    with pytest.raises(PredictionsFileError, match="expected"):
        read(path, expected_split="val")
    assert read(path, expected_split="test")["meta"]["split"] == "test"


def test_missing_and_broken_files(tmp_path):
    with pytest.raises(PredictionsFileError, match="not found"):
        read(tmp_path / "nope.json")
    broken = tmp_path / "bad.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(PredictionsFileError, match="not valid JSON"):
        read(broken)
    notdict = tmp_path / "list.json"
    notdict.write_text("[1]", encoding="utf-8")
    with pytest.raises(PredictionsFileError, match="object"):
        read(notdict)


def test_the_reader_refuses_extra_or_missing_top_level_keys(tmp_path):
    path = write(tmp_path)
    data = load(path)
    save(path, {**data, "transcript": "SECRET"})
    with pytest.raises(PredictionsFileError, match="not allowed"):
        read(path)
    del data["seed"]
    save(path, data)
    with pytest.raises(PredictionsFileError, match="missing"):
        read(path)


def test_the_reader_refuses_another_schema_version(tmp_path):
    path = write(tmp_path)
    data = load(path)
    data["schema_version"] = 2
    save(path, data)
    with pytest.raises(PredictionsFileError, match="schema_version"):
        read(path)


def _edited(tmp_path, edit):
    path = write(tmp_path)
    data = load(path)
    edit(data)
    save(path, data)
    return path


def test_the_reader_refuses_a_label_outside_the_class_list(tmp_path):
    path = _edited(tmp_path, lambda d: d["rows"][0]["labels"].update(customer_state="unclear"))
    with pytest.raises(PredictionsFileError, match="not in the class list"):
        read(path)


def test_the_reader_refuses_a_label_that_is_not_the_most_probable(tmp_path):
    path = _edited(tmp_path, lambda d: d["rows"][0]["labels"].update(customer_state="mad"))
    with pytest.raises(PredictionsFileError, match="most probable"):
        read(path)


def test_the_reader_refuses_a_missing_field_in_labels_or_probabilities(tmp_path):
    path = _edited(tmp_path, lambda d: d["rows"][0]["labels"].pop("churn_risk"))
    with pytest.raises(PredictionsFileError, match="labels must have exactly"):
        read(path)
    path2 = tmp_path / "second"
    path2.mkdir()
    path = _edited(path2, lambda d: d["rows"][0]["probabilities"].pop("churn_risk"))
    with pytest.raises(PredictionsFileError, match="forced"):
        read(path)


def test_the_reader_refuses_wrong_classes_in_the_probabilities(tmp_path):
    path = _edited(tmp_path, lambda d: d["rows"][0]["probabilities"]["customer_state"].pop("mad"))
    with pytest.raises(PredictionsFileError, match="exactly the classes"):
        read(path)


def test_the_reader_refuses_probabilities_that_do_not_add_up(tmp_path):
    path = _edited(tmp_path, lambda d: d["rows"][0]["probabilities"]["churn_risk"].update(at_risk=0.5))
    with pytest.raises(PredictionsFileError, match="add up"):
        read(path)


def test_the_reader_refuses_a_probability_that_is_not_a_proper_number(tmp_path):
    path = _edited(tmp_path, lambda d: d["rows"][0]["probabilities"]["churn_risk"].update(at_risk=-0.2, not_at_risk=1.2))
    with pytest.raises(PredictionsFileError, match="between 0 and 1"):
        read(path)
    path2 = tmp_path / "second"
    path2.mkdir()
    path = _edited(path2, lambda d: d["rows"][0]["probabilities"]["churn_risk"].update(at_risk=float("nan")))
    with pytest.raises(PredictionsFileError, match="between 0 and 1"):
        read(path)


def test_the_reader_refuses_extra_row_keys_and_repeated_audio_files(tmp_path):
    path = _edited(tmp_path, lambda d: d["rows"][0].update(text="SECRET"))
    with pytest.raises(PredictionsFileError, match="exactly the keys"):
        read(path)
    path2 = tmp_path / "second"
    path2.mkdir()
    path = _edited(path2, lambda d: d["rows"].append(copy.deepcopy(d["rows"][0])))
    with pytest.raises(PredictionsFileError, match="more than once"):
        read(path)


def test_the_reader_refuses_empty_rows(tmp_path):
    path = _edited(tmp_path, lambda d: d.update(rows=[]))
    with pytest.raises(PredictionsFileError, match="rows"):
        read(path)


def test_the_reader_refuses_a_bad_header(tmp_path):
    path = _edited(tmp_path, lambda d: d.update(seed="42"))
    with pytest.raises(PredictionsFileError, match="seed"):
        read(path)


def test_the_reader_names_the_row_and_the_audio_file(tmp_path):
    path = _edited(tmp_path, lambda d: d["rows"][2]["labels"].update(churn_risk="maybe"))
    with pytest.raises(PredictionsFileError, match=r"rows\[2\] \(a3.wav\)"):
        read(path)